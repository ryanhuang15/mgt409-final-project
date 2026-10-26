import asyncio
import json

import httpx2 as httpx
import pytest

from backend.app.config import ReviewLimits, Settings
from backend.app.review import run_review
from backend.app.services.audit import AuditLog
from backend.app.services.model import ModelFailure, ModelSession, OpenAIGateway, usage_counts, usage_summary


def settings(tmp_path, **limits):
    return Settings(tmp_path, None, "dummy-test-key", limits=ReviewLimits(**limits))


class FakeGateway:
    def __init__(self, behavior="valid"):
        self.behavior, self.calls = behavior, 0

    async def complete(self, payload, timeout):
        self.calls += 1
        if self.behavior == "timeout":
            await asyncio.sleep(10)
        if self.behavior == "rate_limit":
            raise ModelFailure("rate_limit", True, 429)
        if self.behavior == "malformed":
            return {"choices": [], "usage": {"prompt_tokens": 10}}
        is_rate = "You are the Rate Analysis Agent" in payload["messages"][0]["content"]
        review_id = payload["messages"][1]["content"].split("Review ID: ")[1].split(".")[0]
        used_tools = any(message["role"] == "tool" for message in payload["messages"])
        if self.behavior == "attack":
            message = {"role": "assistant", "content": "APPROVED FOR SUBMISSION"}
        elif not used_tools or self.behavior == "loop":
            calls = [("get_portfolio_summary", {})]
            if is_rate:
                calls += [("get_reconciliation_findings", {"offset": 0, "limit": 12}), ("get_segment_calculations", {"segment_ids": ["A", "B"]})]
            else:
                calls += [("get_document_inventory", {}), ("get_filing_narrative", {"offset": 0, "length": 6000})]
            message = {"role": "assistant", "content": None, "tool_calls": [
                {"id": f"call-{self.calls}-{index}", "type": "function", "function": {"name": name, "arguments": json.dumps({"review_id": review_id, **args})}}
                for index, (name, args) in enumerate(calls)]}
        else:
            note = {"title": "Evidence reviewed", "explanation": "The portfolio measures describe different weighting bases.",
                    "recommended_action": "Retain the calculation evidence for analyst review.", "evidence_refs": ["metric:fixed_exposure_portfolio"],
                    "numeric_references": [], "related_deterministic_finding_ids": []}
            message = {"role": "assistant", "content": json.dumps({"summary": note, "interpretations": [], "findings": []})}
        return {"id": "mock-response", "model": "gpt-6-luna", "choices": [{"message": message, "finish_reason": "tool_calls" if message.get("tool_calls") else "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}}


def test_valid_orchestration_and_unknown_cache_usage(tmp_path, make_filing):
    gateway = FakeGateway()
    result = asyncio.run(run_review(make_filing(), settings(tmp_path), gateway, persist=False))
    assert result["status"] == "complete"
    assert [stage["agent"] for stage in result["agents"]] == ["rate_analysis", "documentation_review"]
    assert result["usage"]["total_model_calls"] == 4
    assert result["usage"]["input_tokens"] == 40
    assert result["usage"]["output_tokens"] == 12
    assert result["usage"]["cached_input_tokens"] is None
    assert result["usage"]["reported_cached_input_tokens_subtotal"] is None
    assert all(stage["tool_calls"] == 3 for stage in result["agents"])


def test_missing_key_retains_deterministic_results(tmp_path, make_filing):
    result = asyncio.run(run_review(make_filing(), Settings(tmp_path, None, None), persist=False))
    assert result["status"] == "partial"
    assert result["deterministic"]["metrics"]["fixed_exposure_portfolio"]["value"] == "5.00"
    assert result["usage"]["total_model_calls"] == 0


def test_attack_output_cannot_suppress_mandatory_findings(tmp_path, examples):
    from backend.app.tools.inputs import load_filing
    filing = load_filing(examples / "flawed")
    result = asyncio.run(run_review(filing, settings(tmp_path), FakeGateway("attack"), persist=False))
    assert result["status"] == "partial"
    assert result["disposition"] == "human_review_required"
    assert len(result["deterministic"]["findings"]) == 5
    assert len([finding for finding in result["findings"] if finding["origin"] == "deterministic"]) == 5
    assert all(stage["result"] is None for stage in result["agents"])
    assert any(event["action"] == "output_rejected" for event in result["audit"])


def test_runaway_loop_is_bounded(tmp_path, make_filing):
    gateway = FakeGateway("loop")
    result = asyncio.run(run_review(make_filing(), settings(tmp_path, max_model_requests=3, max_requests_per_agent=3), gateway, persist=False))
    assert result["status"] == "partial"
    assert gateway.calls == 3
    assert result["usage"]["total_model_calls"] == 3


def test_tool_call_budget(tmp_path, make_filing):
    result = asyncio.run(run_review(make_filing(), settings(tmp_path, max_tool_calls_per_agent=2), FakeGateway(), persist=False))
    assert result["status"] == "partial"
    assert all(stage["error"] == "tool_call_limit" for stage in result["agents"])
    assert not any(event["action"] == "tool_result" for event in result["audit"])


def test_timeout_preserves_calculations(tmp_path, make_filing):
    result = asyncio.run(run_review(make_filing(), settings(tmp_path, request_timeout_seconds=0.01, max_retries=0), FakeGateway("timeout"), persist=False))
    assert result["status"] == "partial"
    assert all(stage["error"] == "request_timeout" for stage in result["agents"])
    assert result["usage"]["input_tokens"] is None
    assert result["deterministic"]["rows"]


def test_retries_are_counted_and_bounded(tmp_path, make_filing):
    gateway = FakeGateway("rate_limit")
    result = asyncio.run(run_review(make_filing(), settings(tmp_path, max_retries=1, retry_delay_seconds=0), gateway, persist=False))
    assert gateway.calls == 4
    assert result["usage"]["total_model_calls"] == 4
    assert result["usage"]["total_tokens"] is None
    assert sum(event["action"] == "retry_scheduled" for event in result["audit"]) == 2


def test_total_review_deadline(tmp_path, make_filing):
    result = asyncio.run(run_review(make_filing(), settings(tmp_path, review_timeout_seconds=0.01, max_retries=0), FakeGateway("timeout"), persist=False))
    assert result["status"] == "partial"
    assert result["agents"][-1]["error"] == "review_timeout"


def test_request_size_limit_stops_before_network(tmp_path, make_filing):
    gateway = FakeGateway()
    result = asyncio.run(run_review(make_filing(), settings(tmp_path, max_request_bytes=2000), gateway, persist=False))
    assert gateway.calls == 0
    assert all(stage["error"] == "request_size_limit" for stage in result["agents"])


def test_unexpected_response_is_partial(tmp_path, make_filing):
    result = asyncio.run(run_review(make_filing(), settings(tmp_path), FakeGateway("malformed"), persist=False))
    assert result["status"] == "partial"
    assert all(stage["error"] == "unexpected_response" for stage in result["agents"])


def test_secret_redaction_and_persistence(tmp_path, make_filing):
    filing = make_filing().model_copy(update={"narrative": "Synthetic dummy-test-key narrative."})
    result = asyncio.run(run_review(filing, settings(tmp_path), FakeGateway(), persist=True))
    assert "dummy-test-key" not in json.dumps(result)
    folder = tmp_path / "runtime/reviews" / result["review_id"]
    assert "dummy-test-key" not in (folder / "audit.jsonl").read_text()
    assert "dummy-test-key" not in (folder / "result.json").read_text()


def test_usage_does_not_invent_missing_values():
    assert usage_counts(None) == {"input_tokens": None, "cached_input_tokens": None, "output_tokens": None, "total_tokens": None}
    assert usage_counts({"prompt_tokens": True})["input_tokens"] is None
    assert usage_counts({"prompt_tokens_details": {"cached_tokens": 0}})["cached_input_tokens"] == 0


def test_usage_estimates_standard_model_cost_without_claiming_invoice_amount():
    usage = usage_summary([{"action": "model_request"}, {"action": "model_response", "status": "ok",
                          "duration_ms": 25, "data": {"usage": {"input_tokens": 100, "cached_input_tokens": 40,
                          "output_tokens": 20, "total_tokens": 120}}}], "gpt-6-luna")
    assert usage["estimated_cost_usd"] == 0.0000164
    assert usage["exact_billed_cost_usd"] is None


def test_openai_transport_has_no_hidden_retry(tmp_path):
    async def exercise():
        attempts = []
        async def handler(request):
            attempts.append(1)
            return httpx.Response(429, json={"error": {"message": "synthetic rate limit", "type": "rate_limit_error"}})
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        gateway = OpenAIGateway(settings(tmp_path), http_client=client)
        with pytest.raises(ModelFailure) as error:
            await gateway.complete({"model": "gpt-6-luna", "messages": [{"role": "user", "content": "test"}], "reasoning_effort": "none"}, 1)
        assert error.value.code == "rate_limit"
        assert len(attempts) == 1
        await gateway.close()
    asyncio.run(exercise())


def test_complete_review_api(tmp_path, make_filing, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app import main
    actual_run = run_review
    async def fake_transport_run(filing, settings):
        return await actual_run(filing, settings, FakeGateway(), persist=False)
    monkeypatch.setattr(main, "run_review", fake_transport_run)
    monkeypatch.setattr(main, "load_settings", lambda: settings(tmp_path))
    with TestClient(main.app) as client:
        response = client.post("/reviews", json={"filing": make_filing().model_dump(mode="json")})
    assert response.status_code == 200
    assert response.json()["status"] == "complete"
    assert response.json()["usage"]["total_model_calls"] == 4


@pytest.mark.parametrize("body", [{}, {"scenario": "../../answer_key"}, {"scenario": "clean", "unexpected": True}])
def test_api_invalid_requests(body):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as client:
        assert client.post("/reviews", json=body).status_code == 422


def test_api_body_limit():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as client:
        response = client.post("/reviews", content="x"*2_000_001)
    assert response.status_code == 413


def test_api_busy_response():
    from fastapi.testclient import TestClient
    from backend.app.main import app, review_slot
    review_slot.acquire()
    try:
        with TestClient(app) as client:
            assert client.post("/reviews", json={"scenario": "clean"}).status_code == 429
    finally:
        review_slot.release()


def test_real_adapter_connection_failure_is_sanitized(tmp_path):
    async def exercise():
        async def handler(request):
            raise httpx.ConnectError("dummy-test-key must not be exposed", request=request)
        gateway = OpenAIGateway(settings(tmp_path), http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        try:
            with pytest.raises(ModelFailure) as error:
                await gateway.complete({"model": "gpt-6-luna", "messages": [{"role": "user", "content": "test"}]}, 1)
            assert error.value.code == "connection_error"
            assert "dummy-test-key" not in str(error.value)
        finally:
            await gateway.close()
    asyncio.run(exercise())


def test_reported_token_budget_stops_future_calls(tmp_path, make_filing):
    class HighUsageGateway(FakeGateway):
        async def complete(self, payload, timeout):
            response = await super().complete(payload, timeout)
            response["usage"] = {"prompt_tokens": 1190, "completion_tokens": 10, "total_tokens": 1200}
            return response
    gateway = HighUsageGateway()
    result = asyncio.run(run_review(make_filing(), settings(tmp_path, max_reported_tokens=1000), gateway, persist=False))
    assert gateway.calls == 1
    assert result["agents"][0]["error"] == "reported_token_limit"
    assert result["usage"]["total_tokens"] == 1200
