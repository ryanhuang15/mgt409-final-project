"""Native tool loop: every executed tool originates in a real model tool_call."""

import json
import time

from pydantic import ValidationError

from backend.app.agents.contracts import AgentOutput, output_format
from backend.app.agents.prompts import PROMPT_VERSION, system_prompt
from backend.app.agents.validation import FindingRejected, validate_output
from backend.app.services.model import ModelFailure


async def run_agent(agent, session, registry, handoff=None):
    started = time.monotonic()
    audit = session.audit
    audit.add(agent, "agent_started", prompt_version=PROMPT_VERSION)
    messages = [{"role": "system", "content": system_prompt(agent)},
                {"role": "user", "content": f"Review ID: {registry.review_id}. Review the current Personal Auto filing. Retrieve evidence through your tools."}]
    if handoff:
        messages.append({"role": "user", "content": "Validated rate-agent handoff (interpretation only): " + json.dumps(handoff)[:6000]})
    tool_count, repair_count, rejected = 0, 0, []
    result = None
    error_code = None
    try:
        while True:
            response = await session.request(agent, messages, tools=registry.definitions(agent), response_format=output_format())
            choice = response["choices"][0]
            message = choice.get("message")
            if not isinstance(message, dict) or message.get("refusal"):
                raise ModelFailure("model_refusal_or_invalid_message")
            calls = message.get("tool_calls") or []
            if choice.get("finish_reason") == "length":
                raise ModelFailure("model_output_truncated")
            if calls:
                if not isinstance(calls, list) or tool_count+len(calls) > session.limits.max_tool_calls_per_agent:
                    raise ModelFailure("tool_call_limit")
                if any(call.get("type") != "function" or not isinstance(call.get("function"), dict)
                       or not isinstance(call.get("id"), str) or not isinstance(call["function"].get("arguments"), str)
                       or not isinstance(call["function"].get("name"), str) for call in calls):
                    raise ModelFailure("malformed_native_tool_call")
                if len({call["id"] for call in calls}) != len(calls):
                    raise ModelFailure("duplicate_tool_call_id")
                messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
                for call in calls:
                    if session.remaining() <= 0:
                        raise ModelFailure("review_timeout")
                    tool_count += 1
                    body = registry.call(agent, call["function"]["name"], call["function"]["arguments"], call["id"])
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(body)})
                continue
            content = message.get("content")
            try:
                if not isinstance(content, str):
                    raise FindingRejected("missing_structured_content")
                output = AgentOutput.model_validate_json(content)
                missing = registry.missing_coverage(agent)
                if missing:
                    raise FindingRejected("required_evidence_not_retrieved:" + ",".join(missing))
                result = validate_output(output, registry, agent)
                break
            except (ValidationError, FindingRejected) as error:
                code = str(error) if isinstance(error, FindingRejected) else "invalid_output_schema"
                rejected.append(code)
                audit.add(agent, "output_rejected", status="rejected", error=code)
                if repair_count >= 1:
                    raise ModelFailure("output_validation_failed") from None
                repair_count += 1
                messages.append({"role": "assistant", "content": content if isinstance(content, str) else ""})
                messages.append({"role": "user", "content": "The application rejected this output: " + code + ". Correct the output using evidence already retrieved. Only call more tools if evidence is genuinely missing. Remaining tool calls: " + str(session.limits.max_tool_calls_per_agent-tool_count) + ". Do not weaken the rules."})
    except ModelFailure as error:
        error_code = error.code
    except Exception as error:
        error_code = "agent_internal_error"
        audit.add(agent, "internal_error", status="error", error_type=type(error).__name__)
    elapsed = round((time.monotonic()-started)*1000, 3)
    status = "complete" if result else "incomplete"
    audit.add(agent, "agent_finished", status=status, duration_ms=elapsed, error=error_code,
              executed_tool_calls=tool_count, rejected_outputs=rejected)
    return dict(agent=agent, status=status, duration_ms=elapsed, tool_calls=tool_count,
                error=error_code, rejected_outputs=rejected, result=result)
