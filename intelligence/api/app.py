"""Workbench API（第 1 步）：把一条 ``ask`` 流包成 HTTP + SSE。

用法::

    pip install -r intelligence/api/requirements.txt
    uvicorn intelligence.api.app:app --port 8788
    # 浏览器打开 http://127.0.0.1:8788/

接口：

    POST /api/runs                     {question, user?, task_type?, session_id?, parent_run_id?, compose?}
    GET  /api/runs?user=               run 列表（新→旧）
    GET  /api/runs/{run_id}?user=      run.json
    GET  /api/runs/{run_id}/trace      trace 步骤数组
    GET  /api/runs/{run_id}/events     SSE：先重放已落盘步骤，再跟进直到终态
    GET  /api/runs/{run_id}/artifacts/{name}   产物文件

设计取舍（教学）：

- **FastAPI + 线程池，不上 Celery**：本地单用户工作台，任务量级是「同时跑一两个」，
  in-process ``ThreadPoolExecutor`` 足够；引入消息队列/独立 worker 是多用户/多机
  才需要的复杂度。这个「先进程内、后队列」的演进路径在任何任务系统设计里通用。
- **SSE 直接轮询 trace.jsonl 文件，不做内存 pub/sub**：run_store 本来就边跑边
  append，SSE 只是文件的「tail -f」投影。好处：浏览器刷新、甚至 API 进程重启后，
  凭 run_id 重连照样能重放全部历史——状态在盘上，不在内存里（crash-safe 的关键）。
  替代方案是 asyncio.Queue 推送，延迟略低，但状态在内存、重启即丢，还要处理多订阅。
- **执行层直接 import ``intelligence.services.ask``，不 subprocess 包 CLI**：
  CLI 与 API 共享同一 service 层，错误类型/遥测不丢失（见 P0 实施计划）。
- **无 LLM key 优雅降级**：``answer_query`` 本身无 key 也能出六段模板答案，
  API 不加任何 key 检查，降级信息进 run.degrades / warnings。
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from intelligence.services import run_store as rs
from intelligence.services.run_store import RunStore

STATIC_DIR = Path(__file__).resolve().parent / "static"

# 单进程任务池：本地工作台并发需求极小；max_workers=2 防止重任务把机器吃满。
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="workbench-run")

_SSE_POLL_SECONDS = 0.5
_SSE_MAX_SECONDS = 15 * 60


class CreateRunRequest(BaseModel):
    question: str = Field(min_length=1)
    user: str | None = None
    task_type: str = "ask"
    session_id: str | None = None
    parent_run_id: str | None = None
    compose: bool = True


def _run_ask(store: RunStore, run_id: str, req: CreateRunRequest) -> None:
    """在工作线程里执行一条 ask 流，把过程与产物落进 run 目录。

    trace 粒度说明：``answer_query`` 目前是单入口（内部含路由/多源检索/合成），
    所以第 1 步先按「检索合成 / 渲染产物」两个 step 打点；后续在 service 层内
    打细粒度点（每个源一个 step）属于第 3 步接 theme 时的工作。
    """
    from intelligence.services.ask import AskOptions, answer_query, render_answer

    t0 = rs._now_iso()
    store.append_step(run_id, step_id="s01", name="ask_retrieve_compose", status="running",
                      input_summary=req.question, started_at=t0)
    try:
        result = answer_query(AskOptions(query=req.question, user=req.user, compose=req.compose))
    except Exception as exc:  # noqa: BLE001 —— 任何执行失败都要落成 failed run，而不是让线程静默死掉
        store.append_step(run_id, step_id="s01", name="ask_retrieve_compose", status="failed",
                          input_summary=req.question, started_at=t0, finished_at=rs._now_iso(),
                          warnings=[f"{type(exc).__name__}: {exc}"])
        store.finish_run(run_id, rs.STATUS_FAILED, error=f"{type(exc).__name__}: {exc}")
        return

    hits = [s for s, ok in (("market", result.found_market), ("graph", result.found_graph),
                            ("wiki", result.found_wiki)) if ok]
    store.append_step(run_id, step_id="s01", name="ask_retrieve_compose", status="completed",
                      input_summary=req.question, started_at=t0, finished_at=rs._now_iso(),
                      output_summary=f"命中源：{'+'.join(hits) or '无'}；引用 {len(result.citations)} 条"
                                     f"；模块 {','.join(result.routed_modules) or '—'}",
                      warnings=list(result.warnings))
    for w in result.warnings:
        if "不可用" in w or "降级" in w or "unavailable" in w.lower():
            store.add_degrade(run_id, w)
    if req.compose and not (result.llm_refined or result.synthesis):
        store.add_degrade(run_id, "llm_unavailable_template_answer")

    t1 = rs._now_iso()
    answer_md = render_answer(result)
    store.add_artifact(run_id, "answer.md", answer_md, renderer="markdown",
                       title=f"研究回答：{req.question[:24]}")
    summary = {
        "trade_date": result.trade_date,
        "matched_theme": result.matched_theme,
        "question_type": result.question_plan.question_type if result.question_plan else None,
        "citations": len(result.citations),
        "llm_refined": result.llm_refined,
        "llm_composed": bool(result.synthesis),
        "warnings": list(result.warnings),
    }
    store.add_artifact(run_id, "summary.json", json.dumps(summary, ensure_ascii=False, indent=2),
                       renderer="json", title="结构化摘要")
    store.append_step(run_id, step_id="s02", name="render_artifacts", status="completed",
                      started_at=t1, finished_at=rs._now_iso(),
                      output_summary="answer.md + summary.json")
    store.finish_run(run_id, rs.STATUS_COMPLETED)


def create_app() -> FastAPI:
    app = FastAPI(title="Market Intelligence Workbench API")

    @app.post("/api/runs")
    def create_run(req: CreateRunRequest) -> dict[str, Any]:
        store = RunStore(user_id=req.user)
        run = store.create_run(
            req.question,
            req.task_type,
            session_id=req.session_id,
            parent_run_id=req.parent_run_id,
        )
        _EXECUTOR.submit(_run_ask, store, run.run_id, req)
        return {"run_id": run.run_id, "status": run.status}

    @app.get("/api/runs")
    def list_runs(user: str | None = None) -> list[dict[str, Any]]:
        from dataclasses import asdict

        return [asdict(r) for r in reversed(RunStore(user_id=user).list_runs())]

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, user: str | None = None) -> dict[str, Any]:
        from dataclasses import asdict

        store = RunStore(user_id=user)
        try:
            return asdict(store.load_run(run_id))
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc

    @app.get("/api/runs/{run_id}/trace")
    def get_trace(run_id: str, user: str | None = None) -> list[dict[str, Any]]:
        store = RunStore(user_id=user)
        if not store.run_path(run_id).exists():
            raise HTTPException(404, f"run 不存在：{run_id}")
        return store.load_trace(run_id)

    @app.get("/api/runs/{run_id}/events")
    def run_events(run_id: str, user: str | None = None) -> StreamingResponse:
        store = RunStore(user_id=user)
        if not store.run_path(run_id).exists():
            raise HTTPException(404, f"run 不存在：{run_id}")

        def stream():
            sent = 0
            deadline = time.monotonic() + _SSE_MAX_SECONDS
            while True:
                steps = store.load_trace(run_id)
                for step in steps[sent:]:
                    yield f"event: step\ndata: {json.dumps(step, ensure_ascii=False)}\n\n"
                sent = len(steps)
                run = store.load_run(run_id)
                if run.status in (rs.STATUS_COMPLETED, rs.STATUS_FAILED, rs.STATUS_CANCELLED):
                    from dataclasses import asdict

                    yield f"event: run\ndata: {json.dumps(asdict(run), ensure_ascii=False)}\n\n"
                    return
                if time.monotonic() > deadline:
                    yield "event: timeout\ndata: {}\n\n"
                    return
                time.sleep(_SSE_POLL_SECONDS)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/runs/{run_id}/artifacts/{name}")
    def get_artifact(run_id: str, name: str, user: str | None = None) -> FileResponse:
        store = RunStore(user_id=user)
        run_dir = store.run_dir(run_id)
        path = (run_dir / name).resolve()
        if run_dir.resolve() not in path.parents or not path.is_file():
            raise HTTPException(404, f"产物不存在：{name}")
        return FileResponse(path)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
