"""Browser API: bounded uploads, background reviews, scoped retrieval and exports."""

import asyncio
import hashlib
import hmac
import json
import re
import secrets
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import Field, ValidationError, model_validator

from backend.app.config import PROJECT_ROOT, load_settings
from backend.app.review import run_review
from backend.app.schemas import Contract, Filing
from backend.app.services.audit import AuditLog
from backend.app.services.reports import render_memo, segment_csv
from backend.app.services.presentation import enrich
from backend.app.services.comparison import compare
from backend.app.services.web_store import ReviewStore, web_settings
from backend.app.tools.calculations import analyze_filing
from backend.app.tools.inputs import InputValidationError, load_filing

router = APIRouter(prefix="/api")
tasks = set()
COOKIE = "lumen_session"
SCENARIOS = ("clean", "flawed", "adversarial")
_store = None


def store():
    global _store
    config = web_settings()
    if _store is None or _store.config != config:
        _store = ReviewStore(config)
    return _store


def owner(request):
    token = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[a-f0-9]{64}", token):
        raise HTTPException(401, "Open the application to establish a browser session, then try again.")
    return hashlib.sha256(token.encode()).hexdigest()


def check_origin(request):
    config = web_settings()
    origin = request.headers.get("origin")
    expected = config.origin or str(request.base_url).rstrip("/")
    if (config.public and origin != expected) or (origin and origin != expected):
        raise HTTPException(403, "This request must originate from the application.")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site requests are not accepted.")


def allow_live(request):
    check_origin(request)
    config = web_settings()
    if not config.live_enabled:
        raise HTTPException(403, "Live AI reviews are disabled on this deployment. Explore a saved review instead.")
    if config.access_code and not hmac.compare_digest(request.headers.get("x-review-code", ""), config.access_code):
        raise HTTPException(403, "A valid review access code is required.")
    if not load_settings().api_key_configured:
        raise HTTPException(503, "The server's model key is not configured. Saved reviews are available.")


def sanitize(value):
    return AuditLog("browser", secret=load_settings().openai_api_key).sanitize(value)


def saved(scenario):
    if scenario not in SCENARIOS:
        raise HTTPException(404, "Example not found")
    filing = load_filing(PROJECT_ROOT / "data/examples" / scenario)
    result = json.loads((PROJECT_ROOT / f"docs/evidence/phase2-{scenario}.json").read_text(encoding="utf-8"))
    if result["deterministic"]["source_file_sha256"] != filing.file_sha256:
        raise HTTPException(409, "Example inputs changed; the saved review must be regenerated.")
    return sanitize(enrich(dict(job_id=f"example-{scenario}", stage=result["status"], source="saved", filing=filing.model_dump(mode="json"), result=result)))


@router.get("/session")
def session(request: Request, response: Response):
    config = web_settings()
    if not re.fullmatch(r"[a-f0-9]{64}", request.cookies.get(COOKIE, "")):
        response.set_cookie(COOKIE, secrets.token_hex(32), httponly=True, secure=config.public, samesite="strict", max_age=86400)
    return dict(live_enabled=config.live_enabled and load_settings().api_key_configured,
                access_code_required=bool(config.access_code), public=config.public,
                daily_reviews=config.daily_reviews, session_reviews=config.session_reviews,
                retention_hours=config.retention_hours, upload_limit_bytes=2_000_000, row_limit=500)


@router.get("/examples/{scenario}")
def example(scenario: str):
    return saved(scenario)


@router.get("/examples/{scenario}/files/{filename}")
def example_file(scenario: str, filename: str):
    if scenario not in (*SCENARIOS, "revised") or filename not in ("rates.csv", "rates.xlsx", "filing.json", "narrative.md"):
        raise HTTPException(404, "Example file not found")
    directory = PROJECT_ROOT / ("data/workflow/revised" if scenario == "revised" else f"data/examples/{scenario}")
    return FileResponse(directory / filename, filename=filename)


async def read_upload(request):
    check_origin(request)
    owner(request)
    directory = PROJECT_ROOT / "runtime/uploads"
    directory.mkdir(parents=True, exist_ok=True)
    async with request.form(max_files=3, max_fields=0, max_part_size=2_000_000) as form:
        if set(form) != {"rates", "metadata", "narrative"} or len(form.multi_items()) != 3:
            raise HTTPException(422, "Supply rates.csv or rates.xlsx, filing.json and narrative.md.")
        rate_file = form["rates"]
        suffix = Path(getattr(rate_file, "filename", "") or "").suffix.lower()
        if suffix not in (".csv", ".xlsx"):
            raise HTTPException(422, "Rate data must be CSV or values-only XLSX with a rates sheet.")
        # Client filenames never determine filesystem paths.
        with tempfile.TemporaryDirectory(dir=directory) as temporary:
            paths = {"rates": "rates" + suffix, "metadata": "filing.json", "narrative": "narrative.md"}
            for field, filename in paths.items():
                upload = form[field]
                if not hasattr(upload, "read"):
                    raise HTTPException(422, "Each input must be a file.")
                content = await upload.read(2_000_001)
                if len(content) > 2_000_000:
                    raise HTTPException(413, "File size limit exceeded")
                (Path(temporary) / filename).write_bytes(content)
            try:
                filing = load_filing(Path(temporary), paths["rates"])
                if len(filing.rows) > 500:
                    raise HTTPException(422, "The web application supports up to 500 segments per review.")
                return filing
            except InputValidationError as error:
                raise HTTPException(422, sanitize(error.issues)) from None
            except (ValidationError, ValueError):
                raise HTTPException(422, "Invalid filing package. Use the supplied template and check required fields.") from None


@router.post("/uploads/preview")
async def preview(request: Request):
    filing = await read_upload(request)
    return sanitize(dict(filing=filing.model_dump(mode="json"), analysis=analyze_filing(filing).model_dump(mode="json")))


async def execute(job_id, filing, repository):
    try:
        result = await run_review(filing, settings=load_settings(), persist=False,
                                  progress=lambda stage: repository.update(job_id, stage))
        repository.update(job_id, result["status"], result)
    except asyncio.CancelledError:
        repository.update(job_id, "interrupted")
        raise
    except Exception:
        # Never serialize provider exceptions or submitted values into public errors.
        repository.update(job_id, "failed")


def submit(request, filing, parent_id=None):
    repository = store()
    job_id = repository.admit(owner(request), sanitize(filing.model_dump(mode="json")), parent_id)
    task = asyncio.create_task(execute(job_id, filing, repository))
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return dict(job_id=job_id, stage="validating")


class ExampleRequest(Contract):
    scenario: Literal["clean", "flawed", "adversarial"]


@router.post("/reviews", status_code=202)
async def new_example(body: ExampleRequest, request: Request):
    allow_live(request)
    return submit(request, load_filing(PROJECT_ROOT / "data/examples" / body.scenario))


@router.post("/reviews/upload", status_code=202)
async def new_upload(request: Request):
    allow_live(request)
    filing = await read_upload(request)
    return submit(request, filing)


@router.get("/reviews")
def history(request: Request):
    return store().history(owner(request))


@router.get("/reviews/{job_id}")
def get_review(job_id: str, request: Request):
    return enrich(store().get(job_id, owner(request)))


def review_source(job_id, request):
    if job_id.startswith("example-"):
        return saved(job_id.removeprefix("example-"))
    return enrich(store().get(job_id, owner(request)))


class FindingAction(Contract):
    status: Literal["open", "under_review", "resolved", "accepted_risk", "not_applicable"]
    note: str = Field(default="", max_length=2000)
    resolution: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def closed_has_reason(self):
        if self.status in {"resolved", "accepted_risk", "not_applicable"} and not self.resolution.strip():
            raise ValueError("A resolution explanation is required for this status")
        return self


@router.get("/reviews/{job_id}/workflow")
def workflow(job_id: str, request: Request):
    user = owner(request)
    envelope = review_source(job_id, request)
    if not envelope["result"]:
        raise HTTPException(409, "The review has no findings yet.")
    return store().actions(user, job_id)


@router.put("/reviews/{job_id}/findings/{finding_id}")
def update_finding(job_id: str, finding_id: str, action: FindingAction, request: Request):
    check_origin(request)
    user = owner(request)
    envelope = review_source(job_id, request)
    if not envelope["result"] or finding_id not in {item["finding_id"] for item in envelope["result"]["findings"]}:
        raise HTTPException(404, "Finding not found in this review.")
    if not action.note.strip() and not action.resolution.strip() and action.status == "open":
        raise HTTPException(422, "Add a note or choose a new status.")
    return store().save_action(user, job_id, finding_id, action.status, action.note.strip(), action.resolution.strip())


@router.post("/reviews/{job_id}/revisions", status_code=202)
async def new_revision(job_id: str, request: Request):
    allow_live(request)
    original = review_source(job_id, request)
    if not original["result"]:
        raise HTTPException(409, "Finish the original review before submitting a revision.")
    filing = await read_upload(request)
    if filing.metadata.insurer != original["filing"]["metadata"]["insurer"]:
        raise HTTPException(422, "A revision must identify the same fictional insurer as the original filing.")
    return submit(request, filing, parent_id=job_id)


@router.get("/reviews/{job_id}/comparison")
def revision_comparison(job_id: str, request: Request):
    revised = enrich(store().get(job_id, owner(request)))
    if not revised["parent_id"] or not revised["result"]:
        raise HTTPException(409, "A completed revised review is required for comparison.")
    original = review_source(revised["parent_id"], request)
    if not original["result"]:
        raise HTTPException(409, "The original review is unavailable.")
    return compare(original, revised)


@router.get("/exports/{kind}/{identifier}/{format}")
def export(kind: Literal["example", "review"], identifier: str, format: Literal["html", "json", "csv"], request: Request):
    envelope = saved(identifier) if kind == "example" else enrich(store().get(identifier, owner(request)))
    if not envelope["result"]:
        raise HTTPException(409, "This review has no exportable result yet.")
    try:
        user = owner(request)
    except HTTPException:
        user = None
    if user:
        review_key = f"example-{identifier}" if kind == "example" else identifier
        envelope["workflow"] = store().actions(user, review_key)
    if kind == "review" and envelope.get("parent_id"):
        envelope["comparison"] = compare(review_source(envelope["parent_id"], request), envelope)
    content = render_memo(envelope) if format == "html" else segment_csv(envelope) if format == "csv" else json.dumps(envelope, indent=2)
    media = {"html": "text/html", "csv": "text/csv", "json": "application/json"}[format]
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="lumen-review.{format}"'})
