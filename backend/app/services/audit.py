"""Append-only run events. Store payloads, never SDK headers or exception bodies."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class AuditLog:
    def __init__(self, review_id: str, directory: Path | None = None, secret: str | None = None):
        self.review_id = review_id
        self.directory = directory
        self.secret = secret
        self.events = []
        if directory:
            directory.mkdir(parents=True, exist_ok=False)

    def sanitize(self, value):
        if isinstance(value, dict):
            return {key: ("[REDACTED]" if key.lower() in {"authorization", "api_key", "openai_api_key", "x-openai-api-key", "portkey_api_key", "x-portkey-api-key", "headers"} else self.sanitize(item)) for key, item in value.items()}
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        if isinstance(value, str):
            if self.secret:
                value = value.replace(self.secret, "[REDACTED]")
            return re.sub(r"\b(?:sk|pk)-[A-Za-z0-9_-]{16,}\b", "[REDACTED]", value)
        return value

    def add(self, actor, action, status="ok", duration_ms=None, **data):
        event = self.sanitize(dict(sequence=len(self.events)+1, timestamp=utc_now(), review_id=self.review_id,
                                   actor=actor, action=action, status=status, duration_ms=duration_ms, data=data))
        self.events.append(event)
        if self.directory:
            with (self.directory / "audit.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=True) + "\n")
        return event

    def save_result(self, result: dict):
        if self.directory:
            target = self.directory / "result.json"
            temporary = self.directory / "result.tmp"
            temporary.write_text(json.dumps(self.sanitize(result), indent=2), encoding="utf-8")
            temporary.replace(target)
