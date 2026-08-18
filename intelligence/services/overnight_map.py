"""D17 隔夜美股→A 股映射块。

KC-15 规格写的是 [D11]，但 D11 已是个股走势类比；本块用 D17，不抢 D11/D12。
读 fph2026 ``query overnight`` 的隔夜对照产物，输出三列：

    美股主题涨跌 → 对照 A 股板块 → 当日 A 股实际表现

全部带日期与数据源。只列映射事实，不表示必然跟涨，不是买卖信号。
对照表没写的主题显式说「这张表没写」，不编映射。
"""
from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.paths import default_market_db_path

EVIDENCE_ID = "D17"
FETCH_ENV_FLAG = "FINANCE_OVERNIGHT_FETCH"
DEFAULT_FPH_ROOT = Path(
    os.environ.get(
        "FPH2026_ROOT",
        str(Path.home() / "Documents/Codex/2026-08-15/fupanhui-hard-2026"),
    )
)
DEFAULT_LIMIT = 10

OvernightFetcher = Callable[[], dict[str, Any]]

_US_TERMS = (
    "隔夜",
    "美股",
    "纳指",
    "纳斯达克",
    "外盘",
    "qqq",
    "soxx",
)
_MAP_TERMS = (
    "映射",
    "对标",
    "对照",
    "对应",
    "跟涨",
    "联动",
    "板块",
)
_COMPOUND = (
    "隔夜美股",
    "隔夜纳指",
    "隔夜外盘",
    "隔夜映射",
)


def parse_overnight_intent(query: str) -> bool:
    """命中隔夜美股对照意图才路由。单独「对标/板块」不抢 D8/D11。"""
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return False
    folded = text.lower()
    if any(term in text for term in _COMPOUND):
        return True
    has_us = any(term in text if not term.isascii() else term in folded for term in _US_TERMS)
    has_map = any(term in text for term in _MAP_TERMS)
    return has_us and has_map


@dataclass(frozen=True)
class OvernightTarget:
    sector_code: str
    sector_name: str
    relation: str
    amount_chain_ratio: float | None
    limit_up_count: int | None
    is_double_red: bool | None
    pct_chg: float | None
    note: str


@dataclass(frozen=True)
class OvernightThemeRow:
    theme_code: str
    theme_name: str
    heat: float | None
    rank: int | None
    avg_pct_chg: float | None
    targets: tuple[OvernightTarget, ...]


@dataclass(frozen=True)
class OvernightArtifact:
    evidence_id: str
    available: bool
    as_of: str | None
    barometer_as_of: str | None
    map_source: str
    map_note: str
    is_trade_signal: bool
    themes: tuple[OvernightThemeRow, ...]
    degrade_reason: str
    source_label: str


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    return bool(value)


def _fmt_num(value: float | None) -> str:
    if value is None:
        return "缺数"
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "缺数"
    return f"{value:+.2f}%"


def _fmt_bool_label(value: bool | None, yes: str, no: str) -> str:
    if value is None:
        return "缺数"
    return yes if value else no


def _import_fph_query() -> tuple[Any, Any]:
    try:
        from fph2026.query import query_overnight, query_us_theme
    except ImportError:
        root = str(DEFAULT_FPH_ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)
        from fph2026.query import query_overnight, query_us_theme
    return query_overnight, query_us_theme


def _enrich_us_pct(
    payload: dict[str, Any],
    query_us_theme: Any,
    fph_db_path: Path | None,
) -> None:
    day = payload.get("as_of")
    themes = payload.get("themes") or []
    if not day or not themes:
        return
    kwargs: dict[str, Any] = {"start": day, "end": day}
    if fph_db_path is not None:
        kwargs["db_path"] = fph_db_path
    rows = query_us_theme(**kwargs)
    by_code = {str(row.get("theme_code") or ""): row for row in rows}
    for theme in themes:
        extra = by_code.get(str(theme.get("theme_code") or ""), {})
        if theme.get("avg_pct_chg") in (None, "") and extra.get("avg_pct_chg") not in (None, ""):
            theme["avg_pct_chg"] = extra.get("avg_pct_chg")
        if not theme.get("theme_name"):
            theme["theme_name"] = extra.get("category") or extra.get("theme_name") or ""


def _enrich_a_share_pct(
    payload: dict[str, Any],
    finance_db_path: Path | None,
) -> None:
    day = payload.get("barometer_as_of") or payload.get("as_of")
    themes = payload.get("themes") or []
    if not day or not themes:
        return
    market = Path(finance_db_path) if finance_db_path else default_market_db_path()
    if not market.exists():
        return
    codes: list[str] = []
    for theme in themes:
        for target in theme.get("targets") or []:
            code = str(target.get("sector_code") or "").strip()
            if code:
                codes.append(code)
    if not codes:
        return
    unique = sorted(set(codes))
    placeholders = ", ".join("?" * len(unique))
    try:
        import duckdb
    except ImportError:
        return
    try:
        con = duckdb.connect(str(market), read_only=True)
        try:
            rows = con.execute(
                f"""
                SELECT replace(sector_ts_code, '.TI', '.FP') AS sector_code, pct_chg
                FROM fact_sector_daily
                WHERE trade_date = ? AND replace(sector_ts_code, '.TI', '.FP') IN ({placeholders})
                """,
                [day, *unique],
            ).fetchall()
        finally:
            con.close()
    except Exception:
        return
    by_code = {str(row[0]): row[1] for row in rows}
    for theme in themes:
        for target in theme.get("targets") or []:
            if target.get("pct_chg") not in (None, ""):
                continue
            code = str(target.get("sector_code") or "")
            if code in by_code:
                target["pct_chg"] = by_code[code]


def fetch_overnight_payload(
    *,
    finance_db_path: str | Path | None = None,
    fph_db_path: str | Path | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    if os.environ.get(FETCH_ENV_FLAG, "1") == "0":
        raise RuntimeError(f"{FETCH_ENV_FLAG}=0")
    query_overnight, query_us_theme = _import_fph_query()
    kwargs: dict[str, Any] = {"limit": limit}
    resolved_fph = Path(fph_db_path) if fph_db_path else None
    resolved_fin = Path(finance_db_path) if finance_db_path else None
    if resolved_fph is not None:
        kwargs["db_path"] = resolved_fph
    if resolved_fin is not None:
        kwargs["finance_db"] = resolved_fin
    payload = query_overnight(**kwargs)
    _enrich_us_pct(payload, query_us_theme, resolved_fph)
    _enrich_a_share_pct(payload, resolved_fin)
    return payload


def _parse_target(raw: dict[str, Any]) -> OvernightTarget:
    return OvernightTarget(
        sector_code=str(raw.get("sector_code") or "").strip(),
        sector_name=str(raw.get("sector_name") or "").strip() or "缺数",
        relation=str(raw.get("relation") or "").strip() or "缺数",
        amount_chain_ratio=_as_float(raw.get("amount_chain_ratio")),
        limit_up_count=_as_int(raw.get("limit_up_count")),
        is_double_red=_as_bool(raw.get("is_double_red")),
        pct_chg=_as_float(raw.get("pct_chg")),
        note=str(raw.get("note") or "").strip(),
    )


def _parse_theme(raw: dict[str, Any]) -> OvernightThemeRow:
    targets = tuple(_parse_target(item) for item in (raw.get("targets") or []) if isinstance(item, dict))
    return OvernightThemeRow(
        theme_code=str(raw.get("theme_code") or "").strip(),
        theme_name=str(raw.get("theme_name") or raw.get("category") or "").strip() or "缺数",
        heat=_as_float(raw.get("heat")),
        rank=_as_int(raw.get("rank")),
        avg_pct_chg=_as_float(raw.get("avg_pct_chg")),
        targets=targets,
    )


def load_overnight_artifact(
    *,
    finance_db_path: str | Path | None = None,
    fph_db_path: str | Path | None = None,
    fetcher: OvernightFetcher | None = None,
) -> OvernightArtifact:
    source_label = (
        "fph2026 旁路库 query overnight"
        "（fact_us_theme_heat_fph × dim_us_theme_a_share_map × fact_sector_barometer_fph；"
        "双红/涨跌另读主库 fact_sector_daily，只读）"
    )
    try:
        payload = fetcher() if fetcher is not None else fetch_overnight_payload(
            finance_db_path=finance_db_path,
            fph_db_path=fph_db_path,
        )
    except Exception as exc:
        return OvernightArtifact(
            evidence_id=EVIDENCE_ID,
            available=False,
            as_of=None,
            barometer_as_of=None,
            map_source="",
            map_note="",
            is_trade_signal=False,
            themes=(),
            degrade_reason=f"D17 隔夜对照不可用：{exc}",
            source_label=source_label,
        )
    themes = tuple(
        _parse_theme(item) for item in (payload.get("themes") or []) if isinstance(item, dict)
    )
    as_of = str(payload.get("as_of") or "").strip() or None
    baro = payload.get("barometer_as_of")
    barometer_as_of = str(baro).strip() if baro not in (None, "") else None
    if not themes:
        return OvernightArtifact(
            evidence_id=EVIDENCE_ID,
            available=False,
            as_of=as_of,
            barometer_as_of=barometer_as_of,
            map_source=str(payload.get("map_source") or ""),
            map_note=str(payload.get("map_note") or ""),
            is_trade_signal=bool(payload.get("is_trade_signal")),
            themes=(),
            degrade_reason="D17 近窗无美股主题热度行",
            source_label=source_label,
        )
    return OvernightArtifact(
        evidence_id=EVIDENCE_ID,
        available=True,
        as_of=as_of,
        barometer_as_of=barometer_as_of,
        map_source=str(payload.get("map_source") or ""),
        map_note=str(payload.get("map_note") or ""),
        is_trade_signal=bool(payload.get("is_trade_signal")),
        themes=themes,
        degrade_reason="",
        source_label=source_label,
    )


def render_overnight_block(artifact: OvernightArtifact) -> str:
    lines = [f"## 隔夜美股映射块 [{artifact.evidence_id}]"]
    us_day = artifact.as_of or "缺数"
    a_day = artifact.barometer_as_of or "缺数"
    lines.append(
        f"- 口径：{artifact.source_label}。美股主题热度日期 {us_day}；"
        f"A 股温度计/涨跌日期 {a_day}；对照表来源 {artifact.map_source or '缺数'}。"
        "不是公司映射，不是买卖信号，不表示必然跟涨。"
        f"is_trade_signal={artifact.is_trade_signal}。"
    )
    if artifact.map_note:
        lines.append(f"- 对照表说明：{artifact.map_note}")
    if not artifact.available:
        lines.append(
            f"- 数据缺口：{artifact.degrade_reason or 'D17 无隔夜对照'}，禁止外推。"
        )
        return "\n".join(lines)
    lines.append("")
    lines.append(
        "| 美股主题（日期/热度/排名/均涨） | 对照 A 股板块（关系） | 当日 A 股实际（日期/涨跌/额环比/涨停/双红） |"
    )
    lines.append("| --- | --- | --- |")
    for theme in artifact.themes:
        us_cell = (
            f"{theme.theme_name}（{theme.theme_code or '缺数'}，{us_day}；"
            f"热度 {_fmt_num(theme.heat)} / 排名 {theme.rank if theme.rank is not None else '缺数'} / "
            f"均涨 {_fmt_pct(theme.avg_pct_chg)}）"
        )
        if not theme.targets:
            lines.append(f"| {us_cell} | 这张表没写 | 缺数 |")
            continue
        for target in theme.targets:
            limit = (
                f"涨停{target.limit_up_count}"
                if target.limit_up_count is not None
                else "涨停缺数"
            )
            a_cell = (
                f"{a_day}；涨跌 {_fmt_pct(target.pct_chg)}；"
                f"额环比 {_fmt_num(target.amount_chain_ratio)}；{limit}；"
                f"{_fmt_bool_label(target.is_double_red, '双红是', '双红否')}"
            )
            note = f"；{target.note}" if target.note else ""
            map_cell = f"{target.sector_name}（{target.sector_code or '缺数'}，{target.relation}{note}）"
            lines.append(f"| {us_cell} | {map_cell} | {a_cell} |")
    lines.append("")
    lines.append(
        "- 使用要求：只列对照表与当日实际，禁止写成「美股涨则 A 股必然跟涨」；"
        "双红是主库观察标签，不是买卖信号。"
    )
    return "\n".join(lines)


def overnight_block_for_llm(
    *,
    finance_db_path: str | Path | None = None,
    fph_db_path: str | Path | None = None,
    fetcher: OvernightFetcher | None = None,
) -> str:
    artifact = load_overnight_artifact(
        finance_db_path=finance_db_path,
        fph_db_path=fph_db_path,
        fetcher=fetcher,
    )
    return render_overnight_block(artifact)
