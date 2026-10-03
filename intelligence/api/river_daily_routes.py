"""Additive, read-only daily river and public attention endpoints."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from intelligence.services.opinion_attention import attention_snapshot, cutoff_for_date, default_ledger_path, read_ledger
from intelligence.services.river_daily_overview import daily_overview
from intelligence.services.river_daily_review import daily_review_snapshot


def register_daily_river_routes(app: FastAPI, *, market_db_path: Path | None = None, attention_ledger_path: Path | None = None, review_exports_path: Path | None = None) -> None:
    @app.get("/api/river/daily-overview")
    def overview(days: int = Query(default=20, ge=5, le=120), end: date | None = None) -> dict:
        from intelligence.paths import default_market_db_path

        try:
            return daily_overview(Path(market_db_path) if market_db_path else default_market_db_path(), days=days, end=end)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/river/daily-review")
    def review(as_of: date) -> dict:
        from intelligence.paths import default_paths

        exports = Path(review_exports_path) if review_exports_path else default_paths().market_exports
        try:
            return daily_review_snapshot(exports, as_of=as_of)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=503, detail="日报归档不可读或结构无效；未使用其他日期替代。") from exc

    @app.get("/api/river/opinion-attention")
    def attention(as_of: date, entity_id: str | None = Query(default=None, max_length=160)) -> dict:
        path = Path(attention_ledger_path) if attention_ledger_path else default_ledger_path()
        try:
            return attention_snapshot(read_ledger(path), cutoff_for_date(as_of), entity_id=entity_id)
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
