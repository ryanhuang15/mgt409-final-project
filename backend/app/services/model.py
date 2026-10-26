"""Official OpenAI client adapter; all application calls pass through here."""

import asyncio
import json
import time

from openai import AsyncOpenAI

from backend.app.config import Settings
from backend.app.services.audit import AuditLog


class ModelFailure(Exception):
    def __init__(self, code, retryable=False, status_code=None):
        self.code, self.retryable, self.status_code = code, retryable, status_code
        super().__init__(code)


def usage_counts(raw):
    raw = raw if isinstance(raw, dict) else {}
    details = raw.get("prompt_tokens_details") or {}

    def count(value):
        return value if type(value) is int and value >= 0 else None

    return {
        "input_tokens": count(raw.get("prompt_tokens")),
        "cached_input_tokens": count(details.get("cached_tokens")) if isinstance(details, dict) else None,
        "output_tokens": count(raw.get("completion_tokens")),
        "total_tokens": count(raw.get("total_tokens")),
    }


def usage_summary(events, model=None):
    outcomes = [event for event in events if event["action"] == "model_response"]
    requests = [event for event in events if event["action"] == "model_request"]
    measured = [event["data"].get("usage", {}) for event in outcomes]
    result = {"total_model_calls": len(requests), "successful_responses": sum(e["status"] == "ok" for e in outcomes),
              "model_latency_ms": round(sum(event["duration_ms"] or 0 for event in outcomes), 3)}
    for field in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"):
        values = [item.get(field) for item in measured]
        known = [value for value in values if value is not None]
        result[field] = sum(known) if len(known) == len(requests) else None
        result["reported_" + field + "_subtotal"] = sum(known) if known else (0 if not requests else None)
    result["usage_complete"] = all(result[field] is not None for field in ("input_tokens", "output_tokens", "total_tokens"))
    result["exact_billed_cost_usd"] = None
    estimated = None
    if model == "gpt-6-luna" and all(result[field] is not None for field in ("input_tokens", "cached_input_tokens", "output_tokens")):
        uncached_input = max(0, result["input_tokens"] - result["cached_input_tokens"])
        estimated = round((uncached_input * 0.10 + result["cached_input_tokens"] * 0.01 + result["output_tokens"] * 0.50) / 1_000_000, 9)
    result["estimated_cost_usd"] = estimated
    result["cost_note"] = (
        "Estimated at published standard gpt-6-luna rates ($0.10/M uncached input, $0.01/M cached input, $0.50/M output); "
        "not an invoice amount. Exact billed cost and any cache-write or account-specific charges are unavailable."
        if estimated is not None else
        "Token measurements only; exact billed cost and a complete rate-based estimate are unavailable."
    )
    return result


class OpenAIGateway:
    def __init__(self, settings: Settings, http_client=None):
        if not settings.api_key_configured:
            raise ModelFailure("missing_api_key")
        if settings.model != "gpt-6-luna" or settings.reasoning_effort != "none":
            raise ModelFailure("unsupported_model_configuration")
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, http_client=http_client, max_retries=0)

    async def complete(self, payload, timeout):
        try:
            response = await self.client.chat.completions.create(**payload, timeout=timeout)
            data = response.model_dump(mode="json")
            # _headers and other transport details are deliberately not copied.
            return {name: data.get(name) for name in ("id", "model", "choices", "usage")}
        except asyncio.CancelledError:
            raise
        except Exception as error:
            status = getattr(error, "status_code", None)
            name = type(error).__name__
            if "Timeout" in name:
                raise ModelFailure("request_timeout", True) from None
            if "Connection" in name or name in {"ConnectError", "NetworkError"}:
                raise ModelFailure("connection_error", True) from None
            if status == 429:
                raise ModelFailure("rate_limit", True, status) from None
            if status in {408, 409} or (isinstance(status, int) and status >= 500):
                raise ModelFailure("provider_unavailable", True, status) from None
            raise ModelFailure("provider_response_error", False, status) from None

    async def close(self):
        await self.client.close()


class ModelSession:
    """Enforce request, token, size, retry, and wall-clock budgets across agents."""
    def __init__(self, gateway, settings, audit: AuditLog):
        self.gateway, self.settings, self.audit = gateway, settings, audit
        self.limits = settings.limits
        self.deadline = time.monotonic() + self.limits.review_timeout_seconds
        self.calls = 0
        self.agent_calls = {}
        self.reported_tokens = 0

    def remaining(self):
        return self.deadline - time.monotonic()

    async def request(self, agent, messages, tools=None, response_format=None, output_tokens=None):
        payload = dict(model=self.settings.model, reasoning_effort=self.settings.reasoning_effort,
                       messages=messages, max_completion_tokens=output_tokens or self.limits.max_output_tokens)
        if tools:
            payload.update(tools=tools, tool_choice="auto", parallel_tool_calls=True)
        if response_format:
            payload["response_format"] = response_format
        if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > self.limits.max_request_bytes:
            raise ModelFailure("request_size_limit")
        for attempt in range(self.limits.max_retries+1):
            if self.remaining() <= 0:
                raise ModelFailure("review_timeout")
            if self.calls >= self.limits.max_model_requests or self.agent_calls.get(agent, 0) >= self.limits.max_requests_per_agent:
                raise ModelFailure("model_request_limit")
            if self.reported_tokens >= self.limits.max_reported_tokens:
                raise ModelFailure("reported_token_limit")
            self.calls += 1
            self.agent_calls[agent] = self.agent_calls.get(agent, 0)+1
            self.audit.add(agent, "model_request", request_number=self.calls, attempt=attempt+1, payload=payload)
            start = time.monotonic()
            try:
                response = await asyncio.wait_for(self.gateway.complete(payload, min(self.limits.request_timeout_seconds, self.remaining())),
                                                  timeout=min(self.limits.request_timeout_seconds, self.remaining()))
                counts = usage_counts(response.get("usage")) if isinstance(response, dict) else usage_counts(None)
                self.reported_tokens += counts["total_tokens"] or 0
                valid = isinstance(response, dict) and isinstance(response.get("choices"), list) and len(response["choices"]) == 1
                self.audit.add(agent, "model_response", status="ok" if valid else "invalid", duration_ms=round((time.monotonic()-start)*1000, 3),
                               request_number=self.calls, response=response, usage=counts)
                if not valid:
                    raise ModelFailure("unexpected_response")
                return response
            except (ModelFailure, TimeoutError) as error:
                failure = error if isinstance(error, ModelFailure) else ModelFailure("request_timeout", True)
                # Unexpected bodies already have a response event with any reported usage.
                if failure.code != "unexpected_response":
                    self.audit.add(agent, "model_response", status="error", duration_ms=round((time.monotonic()-start)*1000, 3),
                                   request_number=self.calls, error=failure.code, http_status=failure.status_code, usage=usage_counts(None))
                if not failure.retryable or attempt >= self.limits.max_retries:
                    raise failure
                delay = min(self.limits.retry_delay_seconds * (2**attempt), max(0, self.remaining()))
                self.audit.add(agent, "retry_scheduled", reason=failure.code, delay_seconds=delay)
                await asyncio.sleep(delay)
