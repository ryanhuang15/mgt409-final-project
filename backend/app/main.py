"""Local API for deterministic foundations and bounded AI reviews."""

import threading
import asyncio
from contextlib import asynccontextmanager
import time
from collections import deque
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import model_validator

from backend.app.config import PROJECT_ROOT, load_settings
from backend.app.review import run_review
from backend.app.schemas import Contract, Filing
from backend.app.tools.inputs import load_filing
from backend.app.services.web_store import web_settings
from backend.app.web import router
from backend.app import web

@asynccontextmanager
async def lifespan(app):
    web_settings()  # Fail closed on an unsafe public configuration.

    async def retention_cleanup():
        while True:
            if web._store is not None:
                await asyncio.to_thread(web._store.prune)
            await asyncio.sleep(60)

    cleanup = asyncio.create_task(retention_cleanup())
    try:
        yield
    finally:
        cleanup.cancel()
        active = list(web.tasks)
        for task in active:
            task.cancel()
        await asyncio.gather(cleanup, *active, return_exceptions=True)


app = FastAPI(title="Lumen | Insurance Rate Filing Assistant", version="0.3.0", lifespan=lifespan,
              docs_url=None, redoc_url=None)
review_slot = threading.BoundedSemaphore(1)


class ReviewRequest(Contract):
    scenario: Literal["clean", "flawed", "adversarial"] | None = None
    filing: Filing | None = None

    @model_validator(mode="after")
    def exactly_one_input(self):
        if (self.scenario is None) == (self.filing is None):
            raise ValueError("Provide exactly one of scenario or filing")
        return self


class RequestSizeLimit:
    def __init__(self, app, maximum=2_000_000):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        messages, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.maximum:
                await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"detail":"request_body_limit"}'})
                return
            messages.append(message)
            if not message.get("more_body", False):
                break

        async def replay():
            return messages.pop(0) if messages else await receive()
        await self.app(scope, replay, send)


app.add_middleware(RequestSizeLimit)
app.include_router(router)
mutation_times = deque()


@app.middleware("http")
async def browser_safety(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH"} and request.url.path.startswith("/api/"):
        now = time.monotonic()
        while mutation_times and mutation_times[0] < now - 60:
            mutation_times.popleft()
        if len(mutation_times) >= 30:
            return JSONResponse({"detail": "Request limit reached. Please wait one minute."}, status_code=429)
        mutation_times.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": [{"location": ".".join(map(str,e["loc"])), "message": e["msg"]} for e in exc.errors()]})


@app.get("/health")
def health() -> dict:
    settings = load_settings()
    return {
        "status": "ok",
        "phase": "analytics-workspace",
        "state_context": "CT",
        "line_of_business": "Personal Auto",
        "regulatory_checks": "not_implemented",
        "ai_enabled": settings.api_key_configured,
        "model": settings.model,
        "api_key_configured": settings.api_key_configured,
    }


@app.post("/reviews")
async def create_review(request: ReviewRequest):
    if web_settings().public:
        raise HTTPException(403, "Use the protected browser review workflow on public deployments.")
    if not review_slot.acquire(blocking=False):
        raise HTTPException(429, "A review is already running; retry after it finishes.")
    try:
        filing = request.filing or load_filing(PROJECT_ROOT / "data/examples" / request.scenario)
        return await run_review(filing, settings=load_settings())
    except ValueError:
        raise HTTPException(422, "Invalid filing or review configuration") from None
    finally:
        review_slot.release()


build = PROJECT_ROOT / "frontend/dist"
if (build / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=build / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def dashboard():
    if not (build / "index.html").is_file():
        return JSONResponse({"detail": "Build the frontend with npm run build in frontend, then restart the server."}, status_code=503)
    return FileResponse(build / "index.html")
