from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .demo import demo_matches
from .models import AssignmentRequest, Category, CATEGORY_LABELS, JoinRequest, QuestionRequest, ReportRequest, VoteRequest
from .store import ArenaError, ArenaStore, digest


def data_path() -> Path:
    return Path(os.environ.get("ARENA_DATA_DIR", str(Path.home() / ".local/share/finance-arena"))) / "arena.sqlite3"


def create_app(store: ArenaStore | None = None, *, seed_demo: bool = True) -> FastAPI:
    store = store or ArenaStore(data_path())
    if seed_demo:
        for match in demo_matches():
            store.add_match(match, published=True)
    app = FastAPI(title="FinArena", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    hosts = os.environ.get("ARENA_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)
    public_origin = os.environ.get("ARENA_PUBLIC_ORIGIN", "").rstrip("/")
    secure = public_origin.startswith("https://")

    @app.exception_handler(ArenaError)
    async def arena_error(_request: Request, exc: ArenaError):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.middleware("http")
    async def session_and_security(request: Request, call_next):
        new_cookie = None
        if request.url.path.startswith("/api/arena/"):
            client = request.client.host if request.client else "unknown"
            try:
                if request.method != "GET":
                    length = request.headers.get("content-length", "")
                    if not length.isdigit() or int(length) > 24000:
                        return JSONResponse({"detail": "请求大小无效。"}, status_code=413)
                session, new_cookie = store.session(request.cookies.get("arena_session"))
                request.state.session = session
                if request.method not in ("GET", "HEAD", "OPTIONS"):
                    origin = request.headers.get("origin")
                    expected = public_origin or f"{request.url.scheme}://{request.url.netloc}"
                    if origin and origin.rstrip("/") != expected:
                        raise ArenaError("不接受跨站请求。", 403)
                    if request.headers.get("sec-fetch-site") == "cross-site":
                        raise ArenaError("不接受跨站请求。", 403)
                    if not secrets.compare_digest(request.headers.get("x-arena-csrf", ""), session["csrf"]):
                        raise ArenaError("会话已过期，请刷新后重试。", 403)
                    store.limit(f"write:{session['id']}", 100, 60)
                    store.limit(f"ip:{digest(client)}", 300, 60)
                request.state.client_key = digest(client)
            except ArenaError as exc:
                return JSONResponse({"detail": exc.message}, status_code=exc.status)
        response = await call_next(request)
        if new_cookie:
            response.set_cookie("arena_session", new_cookie, httponly=True, secure=secure, samesite="lax", max_age=30 * 86400, path="/")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/arena/bootstrap")
    def bootstrap(request: Request):
        session = request.state.session
        return {"csrf": session["csrf"], "reviewer": session["reviewer"], "categories": CATEGORY_LABELS, "summary": store.summary(), "phase": "invite-pilot"}

    @app.post("/api/arena/join")
    def join(body: JoinRequest, request: Request):
        store.limit(f"join:{request.state.client_key}", 10, 900)
        return {"reviewer": store.join(request.state.session["id"], body.code)}

    @app.post("/api/arena/assignments")
    def assign(body: AssignmentRequest, request: Request):
        return {"assignment": store.assign(request.state.session["id"], body.mode, body.category, question_id=body.question_id)}

    @app.get("/api/arena/assignments/{assignment_id}")
    def assignment(assignment_id: str, request: Request):
        return store.assignment(request.state.session["id"], assignment_id)

    @app.post("/api/arena/assignments/{assignment_id}/vote")
    def vote(assignment_id: str, body: VoteRequest, request: Request):
        return store.vote(request.state.session["id"], assignment_id, body.choice, body.reasons)

    @app.post("/api/arena/assignments/{assignment_id}/skip")
    def skip(assignment_id: str, request: Request):
        store.skip(request.state.session["id"], assignment_id)
        return {"ok": True}

    @app.post("/api/arena/assignments/{assignment_id}/report")
    def report(assignment_id: str, body: ReportRequest, request: Request):
        store.report(request.state.session["id"], assignment_id, body.reason, body.detail)
        return {"ok": True}

    @app.post("/api/arena/questions", status_code=201)
    def question(body: QuestionRequest, request: Request):
        store.limit(f"questions:{request.state.session['id']}", 5, 86400)
        return {"id": store.question(request.state.session["id"], body.question, body.category), "status": "pending"}

    @app.get("/api/arena/history")
    def history(request: Request):
        return store.history(request.state.session["id"])

    @app.get("/api/arena/leaderboard")
    def leaderboard(category: Category | None = None):
        return store.leaderboard(category)

    @app.get("/api/arena/strategies")
    def strategies():
        return {"strategies": store.strategies(), "settlement": "not_connected"}

    static = Path(os.environ.get("ARENA_STATIC_DIR", str(Path(__file__).resolve().parents[1] / "webapp/dist-arena")))
    if (static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="arena-assets")

    @app.get("/arena-evidence.png")
    def evidence_image():
        if not (static / "arena-evidence.png").is_file():
            return JSONResponse({"detail": "图片尚未构建。"}, status_code=404)
        return FileResponse(static / "arena-evidence.png")

    @app.get("/")
    @app.get("/arena.html")
    def index():
        if not (static / "arena.html").is_file():
            return JSONResponse({"detail": "请先构建 Arena 前端。"}, status_code=503)
        return FileResponse(static / "arena.html")

    # Configuration errors must fail at startup, before accepting public votes.
    if public_origin and (urlsplit(public_origin).scheme not in ("http", "https") or not urlsplit(public_origin).netloc):
        raise ValueError("ARENA_PUBLIC_ORIGIN must be an absolute http(s) origin")
    return app
