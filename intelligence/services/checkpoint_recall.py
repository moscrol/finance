"""[V] 回检块：答题前「翻旧账」——检索系统对该题材/个股登记过的可证伪判断 + 当前裁决。

背景（为什么要这个块，和 M 块的分工）：
    M 块（``user_memory``）给的是**用户自己的核心判断/纠偏原则 + 类别级聚合胜率**
    （「这类判断该信多少」）；本块补的是另一半——系统在 ``checkpoints.jsonl`` 里
    登记过的**逐条可证伪点当前裁决到哪了**（hit/miss/partial/unverifiable、到期日、
    观测证据）。让回答带上「过去对这个题材说过什么、后来验证对不对」，形成闭环。

    一句话区分：M = 观点正文 + 命中率（该信多少）；V = 逐条旧账的裁决快照（说对了没）。

设计（沿用 D7/D8/M 的三件套纪律：相关性召回 + 确定性渲染 + 缺数写缺口）：
    - **相关性召回**：复用 M 块的轻量打分（标签命中权重高于正文重合），只召回与
      query（题材/实体/关键词）相关的可证伪点；无相关记录返回空串（不追加块，
      无台账用户行为逐字节不变）。
    - **裁决只报事实**：每条判断取其最新裁决（append-only 台账后写覆盖先写）；
      ``unverifiable`` 是非终态，显式标「暂无法判定」，不冒充命中，不计入结论。
    - **数据新鲜度自检**：标注台账截至日（最新登记 / 最近回检），并在给到盘面库
      ``data_asof`` 时核对其落后今日多少天，过期显式声明——避免拿旧盘面裁决冒充
      「最新已兑现」。盘面库不可用（本机无 DuckDB）时也显式声明未做增量核对。

本模块只用标准库 + 复用 ``checkpoints`` / ``user_memory``（均离线、stdlib），可独立单测。
盘面数据截至日由上层（``ask.py``）惰性接 ``MarketAdapter.latest_date`` 注入，缺则降级。
"""

from __future__ import annotations

from datetime import date as date_cls
from pathlib import Path
from typing import Any

from intelligence import userspace
from intelligence.services import checkpoints
from intelligence.services.user_memory import select_relevant

DEFAULT_LOAD_WINDOW = 300
DEFAULT_LIMIT = 5
# 盘面数据截至日落后今日超过这个自然日数即判为「过期」，显式声明缺口。
STALE_DAYS = 3

_VERDICT_LABEL = {
    "hit": "命中 ✓",
    "miss": "落空 ✗",
    "partial": "半对 ◐",
    "unverifiable": "暂无法判定",
}


def _today() -> str:
    return date_cls.today().isoformat()


def _days_behind(asof: str, today: str) -> int | None:
    try:
        return (date_cls.fromisoformat(today[:10]) - date_cls.fromisoformat(asof[:10])).days
    except ValueError:
        return None


def latest_verdicts(verdicts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """每个 checkpoint id 取最后一条裁决（台账 append-only，后写即最新）。"""
    out: dict[str, dict[str, Any]] = {}
    for v in verdicts:
        cid = str(v.get("id") or "").strip()
        if cid:
            out[cid] = v
    return out


def _ledger_asof(
    cks: list[dict[str, Any]], vds: list[dict[str, Any]]
) -> tuple[str | None, str | None]:
    """台账截至日：可证伪点最新登记日、最近一次回检日（无则 None）。"""
    ck_dates = [str(c.get("ts") or c.get("due") or "")[:10] for c in cks]
    v_dates = [str(v.get("checked_at") or "")[:10] for v in vds]
    ck_max = max((d for d in ck_dates if d), default=None)
    v_max = max((d for d in v_dates if d), default=None)
    return ck_max, v_max


def select_relevant_checkpoints(
    checkpoints_records: list[dict[str, Any]],
    query: str,
    theme: str | None = None,
    entity: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """相关性召回：按 claim/category 正文 + themes/stocks 标签与 query 轻量重合打分。"""
    return select_relevant(
        checkpoints_records,
        query,
        theme,
        entity,
        text_keys=("claim", "category"),
        tag_keys=("themes", "stocks"),
        limit=limit,
    )


def _status_label(ck: dict[str, Any], verdict: dict[str, Any] | None, today: str) -> str:
    v = str((verdict or {}).get("verdict") or "").strip()
    if v in checkpoints.TERMINAL_VERDICTS:
        return _VERDICT_LABEL[v]
    if v == "unverifiable":
        return _VERDICT_LABEL["unverifiable"]
    due = str(ck.get("due") or "")
    if due and due <= today:
        return "到期待判"
    return "跟踪中"


def _truncate(text: Any, width: int) -> str:
    s = str(text or "").strip().replace("\n", " ").replace("|", "／")
    return s if len(s) <= width else s[: width - 1] + "…"


def _row(ck: dict[str, Any], verdict: dict[str, Any] | None, today: str) -> str:
    claim = _truncate(ck.get("claim"), 40)
    due = str(ck.get("due") or "—")
    status = _status_label(ck, verdict, today)
    category = _truncate(ck.get("category") or "未分类", 10)
    if verdict:
        detail = verdict.get("reason") or ""
        if not detail and verdict.get("observed"):
            detail = str(verdict["observed"])
        detail = _truncate(detail, 46)
    else:
        detail = "—"
    return f"| {claim} | {due} | {status} | {category} | {detail} |"


def _freshness_lines(
    today: str,
    data_asof: str | None,
    ledger: tuple[str | None, str | None],
) -> list[str]:
    ck_asof, v_asof = ledger
    lines = [
        f"- 台账截至：可证伪点最新登记 {ck_asof or '—'} · 最近回检 {v_asof or '—'}。"
    ]
    if data_asof:
        n = _days_behind(data_asof, today)
        if n is not None and n > STALE_DAYS:
            lines.append(
                f"- ⚠数据新鲜度：盘面库 fact_market_daily 截至 {data_asof}，落后今日 {n} 天，"
                "机检类裁决可能未覆盖最新走势；过期部分按缺口声明，禁止据此宣称「已是最新兑现」。"
            )
        else:
            behind = f"（落后 {n} 天）" if n is not None else ""
            lines.append(f"- 数据新鲜度：盘面库 fact_market_daily 截至 {data_asof}{behind}，视为新鲜。")
    else:
        lines.append(
            "- 数据新鲜度：本机未接盘面库（DuckDB 不可用/未提供），机检类裁决维持台账登记时状态，"
            "本轮未做增量核对，不得据此宣称最新已兑现。"
        )
    return lines


def build_recall_block(
    matched: list[dict[str, Any]],
    verdicts_by_id: dict[str, dict[str, Any]],
    *,
    today: str | None = None,
    data_asof: str | None = None,
    ledger: tuple[str | None, str | None] = (None, None),
) -> str:
    """渲染 [V] 回检块；无召回记录时返回空串（不追加块）。"""
    if not matched:
        return ""
    today = today or _today()
    lines = [
        "## 回检块 [V]（系统对该题材/个股登记过的可证伪判断 × 当前裁决；翻旧账用，非市场预测）"
    ]
    lines += _freshness_lines(today, data_asof, ledger)
    lines.append("")
    lines.append("| 可证伪判断 | 到期 | 裁决 | 类别 | 观测/依据 |")
    lines.append("|---|---|---|---|---|")
    tally: dict[str, int] = {}
    for ck in matched:
        verdict = verdicts_by_id.get(str(ck.get("id") or ""))
        lines.append(_row(ck, verdict, today))
        tally[_status_label(ck, verdict, today)] = tally.get(_status_label(ck, verdict, today), 0) + 1
    summary = " · ".join(f"{k} {v}" for k, v in tally.items())
    lines.append("")
    lines.append(f"- 本块召回 {len(matched)} 条：{summary}。")
    lines.append(
        "- 使用要求：本块是**已登记可证伪点的裁决快照**，不是新预测。命中/落空/半对是历史事实，"
        "可用来校准「系统过去在这题材上准不准」；「暂无法判定/到期待判」不得当成已兑现或已证伪，"
        "「跟踪中」的判断到期前不下结论；与最新硬数据块冲突时以硬数据为准并显式指出，缺数按缺口处理。"
        "回答应优先呈现相对旧判断的增量变化，而不是重述完整背景。"
    )
    return "\n".join(lines)


def recall_block_for_query(
    query: str,
    theme: str | None = None,
    entity: str | None = None,
    user: str | None = None,
    limit: int = DEFAULT_LIMIT,
    users_root: str | Path | None = None,
    data_asof: str | None = None,
    today: str | None = None,
) -> str:
    """加载可证伪点 + 裁决台账 → 相关性召回 → 渲染 [V]；台账缺失/无相关记录时返回空串。"""
    if users_root is not None:
        root = Path(users_root).expanduser()
        ck_path = root / "checkpoints.jsonl"
        v_path = root / "verdicts.jsonl"
    else:
        us = userspace.user_space(user)
        ck_path, v_path = us.checkpoints_path, us.verdicts_path
    cks, _ = checkpoints.load_checkpoints(ck_path)
    if not cks:
        return ""
    matched = select_relevant_checkpoints(cks, query, theme, entity, limit=limit)
    if not matched:
        return ""
    vds, _ = checkpoints.load_verdicts(v_path)
    return build_recall_block(
        matched,
        latest_verdicts(vds),
        today=today,
        data_asof=data_asof,
        ledger=_ledger_asof(cks, vds),
    )
