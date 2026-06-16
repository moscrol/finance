"""第 2 层 · refresh-profile：自动派生并校验用户画像（不碰飞书）。

数据来源（飞书已退役，历史数据已入库 DuckDB）：

- **DuckDB 强势股**（盘面真实）：``MarketAdapter`` 的新高方向 / 双红题材给候选
  ``focus_themes``，各方向里的强势个股（``sqrt(amount)*pct_chg`` 加权）给候选
  ``watchlist``。
- **知识库 theme_signals**（认知/发酵）：``KnowledgeAdapter.load_relation
  ("theme_signals")``，按「认知阶段 ★ 数 + 最近事件日期 + 市场热度 Tier」给候选
  ``focus_themes``。

派生结果**不覆盖**用户钉住的画像（``profile.json``），而是写入独立的
``profile.derived.json``，带 ``source`` / ``as_of`` / ``stale`` 标记；
:func:`intelligence.userspace.effective_profile` 在合并时「钉住项优先、派生项补充、
过期项跳过」。**默认只出 diff、``--apply`` 才落盘**。

优雅降级：DuckDB 驱动或库文件缺失时只用知识库，反之亦然；两者都不可用时给出
警告并返回空 proposal（状态 WARN），绝不抛栈。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.userspace import UserSpace

# 派生项「连续未被命中」的衰减阈值：先标 stale（停止影响 foresight），再彻底删除。
STALE_AFTER_MISSES = 2
DROP_AFTER_MISSES = 4

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TIER_RE = re.compile(r"[Tt]ier\s*([0-9]+)")


@dataclass(frozen=True)
class RefreshOptions:
    user: str | None = None
    lookback: int = 20  # 预留：当前按最新快照派生，后续可扩展为多日持续性
    date: str | None = None
    top: int = 12
    kb_wiki: str | Path | None = None
    db_path: str | Path | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _norm(name: str) -> str:
    return re.sub(r"\s+", "", str(name or "")).lower()


# --------------------------------------------------------------------------- #
# 知识库 theme_signals 打分（字段噪声大，全部防御式解析）
# --------------------------------------------------------------------------- #
def _count_stars(text: Any) -> int:
    return str(text or "").count("★")


def _max_date(strings: list[str]) -> str | None:
    found = [m.group(0) for s in strings for m in [_DATE_RE.search(str(s))] if m]
    return max(found) if found else None


def _min_tier(market_heat: Any) -> int | None:
    if not isinstance(market_heat, list):
        market_heat = [market_heat]
    tiers = [int(m.group(1)) for s in market_heat for m in [_TIER_RE.search(str(s))] if m]
    return min(tiers) if tiers else None


def _score_kb_theme(theme_obj: dict[str, Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """返回 (排序键, 可解释 signals)。排序键越大越靠前：近期 > ★ 多 > 进度 > 热度高。"""
    timeline = theme_obj.get("recognition_timeline")
    timeline = timeline if isinstance(timeline, list) else []
    ruler = theme_obj.get("progress_ruler")
    ruler = ruler if isinstance(ruler, list) else []

    last_event = _max_date([str(item.get("time_window", "")) for item in timeline if isinstance(item, dict)])
    stars = 0
    for item in timeline:
        if isinstance(item, dict):
            stars = max(stars, _count_stars(item.get("recognition_stage")))
    stage_position = 0
    for item in ruler:
        if isinstance(item, dict):
            stars = max(stars, _count_stars(item.get("current_stage")))
            try:
                stage_position = max(stage_position, int(item.get("stage_position") or 0))
            except (TypeError, ValueError):
                pass
    tier = _min_tier(theme_obj.get("market_heat"))
    tier_bonus = max(0, 4 - tier) if tier is not None else 0

    signals = {
        "last_event": last_event,
        "stars": stars,
        "stage_position": stage_position,
        "tier": tier,
    }
    sort_key = (last_event or "", stars, tier_bonus, stage_position)
    return sort_key, signals


def derive_from_kb(options: RefreshOptions) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "as_of": None, "themes": [], "warnings": []}
    try:
        adapter = KnowledgeAdapter(wiki_root=options.kb_wiki)
        relation = adapter.load_relation("theme_signals")
    except Exception as exc:  # pragma: no cover - defensive
        out["warnings"].append(f"知识库 theme_signals 读取异常：{exc}")
        return out
    if not relation.get("found"):
        warns = relation.get("warnings") or ["theme_signals 不可用"]
        out["warnings"].append(f"知识库 theme_signals 不可用：{'; '.join(warns)}（path={relation.get('path')}）")
        return out

    data = relation.get("data") or {}
    themes = data.get("themes")
    if not isinstance(themes, dict) or not themes:
        out["warnings"].append("知识库 theme_signals.themes 为空")
        return out

    ranked: list[tuple[tuple[Any, ...], str, dict[str, Any]]] = []
    for name, theme_obj in themes.items():
        if not isinstance(theme_obj, dict):
            continue
        sort_key, signals = _score_kb_theme(theme_obj)
        ranked.append((sort_key, str(name), signals))
    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)

    out["ok"] = True
    out["as_of"] = data.get("updated")
    out["themes"] = [{"theme": name, "signals": signals} for _, name, signals in ranked]
    return out


# --------------------------------------------------------------------------- #
# DuckDB 强势股（盘面真实）；适配器在 import 时即依赖 duckdb，故懒加载 + 守卫
# --------------------------------------------------------------------------- #
def derive_from_duckdb(options: RefreshOptions) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "as_of": None, "directions": [], "watchlist": [], "warnings": []}
    try:
        from intelligence.adapters.market import MarketAdapter
    except Exception as exc:
        out["warnings"].append(f"DuckDB 适配器不可用（缺 duckdb 驱动？）：{exc}")
        return out

    adapter = MarketAdapter(db_path=options.db_path)
    health = adapter.health()
    if not health.get("ok"):
        out["warnings"].append(f"DuckDB 不可用：{'; '.join(health.get('errors') or ['unknown'])}（{health.get('db_path')}）")
        return out

    try:
        new_high = adapter.get_new_high_directions(options.date)
        double_red = adapter.get_double_red_themes(options.date)
    except Exception as exc:
        out["warnings"].append(f"DuckDB 方向查询异常：{exc}")
        return out

    trade_date = new_high.get("trade_date") or double_red.get("trade_date")
    out["as_of"] = trade_date
    out["warnings"].extend(new_high.get("errors") or [])
    out["warnings"].extend(double_red.get("errors") or [])

    # 合并新高方向 + 双红题材，按各自 score 取每个方向的最大分。
    scored: dict[str, dict[str, Any]] = {}
    for item in new_high.get("themes") or []:
        name = str(item.get("sector_name") or "").strip()
        if not name:
            continue
        scored.setdefault(name, {"theme": name, "score": 0.0, "tags": []})
        scored[name]["score"] = max(scored[name]["score"], float(item.get("score") or 0))
        scored[name]["tags"].append("new_high")
    for item in double_red.get("themes") or []:
        name = str(item.get("sector_name") or "").strip()
        if not name:
            continue
        entry = scored.setdefault(name, {"theme": name, "score": 0.0, "tags": []})
        entry["score"] = max(entry["score"], float(item.get("diff_ratio") or 0))
        entry["tags"].append("double_red")

    directions = sorted(scored.values(), key=lambda d: (d["score"], d["theme"]), reverse=True)
    out["directions"] = directions

    # watchlist：取前若干方向的强势个股（加权排序后跨方向再排）。
    top_dir_names = [d["theme"] for d in directions[: max(options.top, 8)]]
    if top_dir_names and trade_date:
        try:
            sig = adapter.get_theme_stock_signals(trade_date, top_dir_names, limit=8)
        except Exception as exc:
            out["warnings"].append(f"DuckDB 强势股查询异常：{exc}")
            sig = {"signals": {}}
        watch: dict[str, dict[str, Any]] = {}
        for theme, payload in (sig.get("signals") or {}).items():
            for stock in payload.get("strong_stocks") or []:
                name = str(stock.get("stock_name") or "").strip()
                if not name:
                    continue
                weighted = float(stock.get("weighted") or 0)
                if name not in watch or weighted > watch[name]["weighted"]:
                    watch[name] = {
                        "name": name,
                        "code": stock.get("stock_ts_code"),
                        "weighted": weighted,
                        "pct_chg": stock.get("pct_chg"),
                        "theme": theme,
                    }
        out["watchlist"] = sorted(watch.values(), key=lambda s: s["weighted"], reverse=True)

    out["ok"] = True
    return out


# --------------------------------------------------------------------------- #
# 组合：把 DuckDB 与 KB 的候选合成一份 proposal（来源融合 + both 优先）
# --------------------------------------------------------------------------- #
def derive(options: RefreshOptions) -> dict[str, Any]:
    kb = derive_from_kb(options)
    duck = derive_from_duckdb(options)
    warnings = list(kb["warnings"]) + list(duck["warnings"])

    kb_themes = kb["themes"]
    duck_dirs = duck["directions"]
    kb_index = {_norm(t["theme"]): t for t in kb_themes}
    duck_index = {_norm(d["theme"]): d for d in duck_dirs}

    focus: list[dict[str, Any]] = []
    used: set[str] = set()

    def _add(name: str, source: str, signals: dict[str, Any]) -> None:
        key = _norm(name)
        if not key or key in used:
            return
        used.add(key)
        focus.append({"theme": name, "source": source, "signals": signals})

    # 1) 知识库与盘面都命中的题材最强信号，优先。
    for theme in kb_themes:
        key = _norm(theme["theme"])
        if key in duck_index:
            merged = {**theme["signals"], "duck_score": duck_index[key]["score"], "duck_tags": duck_index[key]["tags"]}
            _add(theme["theme"], "both", merged)
    # 2) 知识库认知热度高的题材。
    for theme in kb_themes:
        _add(theme["theme"], "kb", theme["signals"])
    # 3) 盘面强但知识库还没收录的方向。
    for direction in duck_dirs:
        _add(direction["theme"], "duckdb", {"duck_score": direction["score"], "duck_tags": direction["tags"]})

    focus = focus[: options.top]
    watchlist = [{**w, "source": "duckdb"} for w in duck["watchlist"][: options.top]]

    status = "PASS" if (kb["ok"] or duck["ok"]) else "WARN"
    return {
        "generated_at": _now_iso(),
        "user": options.user or "default",
        "lookback": options.lookback,
        "as_of": {"duckdb": duck["as_of"], "kb": kb["as_of"]},
        "sources": {
            "duckdb": {"ok": duck["ok"], "warnings": duck["warnings"]},
            "kb": {"ok": kb["ok"], "warnings": kb["warnings"]},
        },
        "focus_themes": focus,
        "watchlist": watchlist,
        "warnings": warnings,
        "status": status,
    }


# --------------------------------------------------------------------------- #
# diff（默认只出 diff）/ apply（--apply 才落盘，带衰减）
# --------------------------------------------------------------------------- #
def diff_against_profile(current_profile: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    cur_themes = {_norm(t) for t in current_profile.get("focus_themes") or []}
    cur_watch = {_norm(w) for w in current_profile.get("watchlist") or []}
    new_themes = [t for t in proposal.get("focus_themes") or [] if _norm(t["theme"]) not in cur_themes]
    kept_themes = [t for t in proposal.get("focus_themes") or [] if _norm(t["theme"]) in cur_themes]
    new_watch = [w for w in proposal.get("watchlist") or [] if _norm(w["name"]) not in cur_watch]
    kept_watch = [w for w in proposal.get("watchlist") or [] if _norm(w["name"]) in cur_watch]
    return {
        "new_themes": new_themes,
        "kept_themes": kept_themes,
        "new_watchlist": new_watch,
        "kept_watchlist": kept_watch,
    }


def _decay_merge(
    existing: list[dict[str, Any]],
    proposed: list[dict[str, Any]],
    key: str,
    as_of: Any,
) -> list[dict[str, Any]]:
    """命中的项 misses 归零；未命中的累加 misses，超阈值标 stale，再超则删除。"""
    proposed_keys = {_norm(item[key]) for item in proposed}
    result: list[dict[str, Any]] = []
    for item in proposed:
        result.append({**item, "misses": 0, "stale": False, "last_seen": as_of})
    seen = {_norm(item[key]) for item in result}
    for item in existing:
        nk = _norm(item.get(key, ""))
        if not nk or nk in seen or nk in proposed_keys:
            continue
        misses = int(item.get("misses") or 0) + 1
        if misses >= DROP_AFTER_MISSES:
            continue
        seen.add(nk)
        result.append({**item, "misses": misses, "stale": misses >= STALE_AFTER_MISSES})
    return result


def apply_derived(us: UserSpace, proposal: dict[str, Any]) -> tuple[Path, dict[str, int]]:
    us.ensure_dir()
    existing: dict[str, Any] = {}
    if us.derived_path.exists():
        try:
            existing = json.loads(us.derived_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
        if not isinstance(existing, dict):
            existing = {}

    duck_as_of = proposal.get("as_of", {}).get("duckdb")
    kb_as_of = proposal.get("as_of", {}).get("kb")
    focus = _decay_merge(
        existing.get("focus_themes") or [],
        proposal.get("focus_themes") or [],
        "theme",
        kb_as_of or duck_as_of,
    )
    watchlist = _decay_merge(
        existing.get("watchlist") or [],
        proposal.get("watchlist") or [],
        "name",
        duck_as_of,
    )

    payload = {
        "updated": proposal.get("generated_at"),
        "user": proposal.get("user"),
        "as_of": proposal.get("as_of"),
        "sources": proposal.get("sources"),
        "focus_themes": focus,
        "watchlist": watchlist,
    }
    us.derived_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stats = {
        "focus_active": sum(1 for f in focus if not f.get("stale")),
        "focus_stale": sum(1 for f in focus if f.get("stale")),
        "watchlist_active": sum(1 for w in watchlist if not w.get("stale")),
        "watchlist_stale": sum(1 for w in watchlist if w.get("stale")),
    }
    return us.derived_path, stats


# --------------------------------------------------------------------------- #
# 渲染
# --------------------------------------------------------------------------- #
def _theme_line(item: dict[str, Any]) -> str:
    sig = item.get("signals") or {}
    bits: list[str] = [f"来源={item.get('source')}"]
    if sig.get("last_event"):
        bits.append(f"最近事件={sig['last_event']}")
    if sig.get("stars"):
        bits.append("★" * int(sig["stars"]))
    if sig.get("tier") is not None:
        bits.append(f"Tier{sig['tier']}")
    if sig.get("duck_score"):
        bits.append(f"盘面分={round(float(sig['duck_score']), 1)}")
    return f"  - {item['theme']}（{'，'.join(bits)}）"


def _watch_line(item: dict[str, Any]) -> str:
    bits = [f"加权={round(float(item.get('weighted') or 0), 1)}"]
    if item.get("theme"):
        bits.append(f"方向={item['theme']}")
    if item.get("code"):
        bits.append(str(item["code"]))
    return f"  - {item['name']}（{'，'.join(bits)}）"


def render(proposal: dict[str, Any], diff: dict[str, Any], applied_path: str | Path | None = None) -> str:
    lines: list[str] = []
    lines.append(f"# refresh-profile · 用户 {proposal.get('user')}")
    as_of = proposal.get("as_of") or {}
    lines.append(f"- 数据快照：DuckDB={as_of.get('duckdb') or '-'}，知识库={as_of.get('kb') or '-'}")
    srcs = proposal.get("sources") or {}
    lines.append(
        f"- 数据源：DuckDB={'OK' if srcs.get('duckdb', {}).get('ok') else 'OFF'}，"
        f"知识库={'OK' if srcs.get('kb', {}).get('ok') else 'OFF'}"
    )
    for warn in proposal.get("warnings") or []:
        lines.append(f"- ⚠️ {warn}")

    lines.append("")
    lines.append(f"## 候选 focus_themes（{len(proposal.get('focus_themes') or [])}）— 新增 {len(diff.get('new_themes') or [])}")
    if diff.get("new_themes"):
        lines.append("- 建议新增：")
        lines.extend(_theme_line(item) for item in diff["new_themes"])
    if diff.get("kept_themes"):
        lines.append(f"- 已在画像中（{len(diff['kept_themes'])}）：" + "、".join(t["theme"] for t in diff["kept_themes"]))

    lines.append("")
    lines.append(f"## 候选 watchlist（{len(proposal.get('watchlist') or [])}）— 新增 {len(diff.get('new_watchlist') or [])}")
    if diff.get("new_watchlist"):
        lines.append("- 建议新增：")
        lines.extend(_watch_line(item) for item in diff["new_watchlist"])
    if diff.get("kept_watchlist"):
        lines.append(f"- 已在自选中（{len(diff['kept_watchlist'])}）：" + "、".join(w["name"] for w in diff["kept_watchlist"]))

    lines.append("")
    if applied_path:
        lines.append(f"已写入派生画像：{applied_path}（不覆盖 profile.json；effective 合并时钉住项优先）。")
    else:
        lines.append("（预览模式，未落盘。加 `--apply` 写入 profile.derived.json。）")
    return "\n".join(lines) + "\n"
