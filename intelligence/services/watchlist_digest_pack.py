"""自选简报包：画像清单 × 当日盘面四袋的确定性接合（WatchlistDigestPack）。

Spec: docs/superpowers/specs/2026-08-26-watchlist-digest-pack-design.md
台账: R-20260826-05（路由）/ -06（快照合同）/ -07（只委托四袋）。

三条硬约束：

- 盘面事实只经**一次** ``run_market_watch_pack`` 委托取得；本模块零袋内口径、
  零库连接（test_module_contains_no_private_market_sql 机械核查源码）。
- 公开稿数字只来自包内冻结行；每条 fact 带方法行（哪一袋、served_date）；
  事后对账只对 ``to_snapshot()`` 那份，不现场再查邻日。
- 简报是观察件不是投顾：不产任何买卖动作句（词面在测试里锁死）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from intelligence.services.market_watch_pack import (
    BAG_DUAL_RED,
    BAG_LIMIT_HEAT,
    BAG_MAINLINE,
    BAG_MARKET,
    MarketWatchPack,
    _names_match,
    run_market_watch_pack,
)
from intelligence.services.theme_fermentation import trace_sectors_fermentation
from intelligence.userspace import effective_profile, resolve_user_id, user_space

# 快照落盘根目录的重定位环境变量（测试与多机部署用）。
ENV_SNAPSHOT_DIR = "WATCHLIST_DIGEST_DIR"

DigestTier = Literal["fact", "inference", "gap"]
DigestKind = Literal["watchlist", "theme"]
# locked = 正常冻结；empty = 清单空或四袋应停（休市/无该日）；locked_db = 库打不开。
DigestStatus = Literal["locked", "empty", "locked_db"]

# 接合只对有名字空间的三袋；全市场袋是总量行，进「全市场上下文」不进接合。
_JOIN_BAGS = (BAG_MAINLINE, BAG_DUAL_RED, BAG_LIMIT_HEAT)

_BAG_LABELS = {
    BAG_MAINLINE: "主线袋",
    BAG_DUAL_RED: "严格双红袋",
    BAG_LIMIT_HEAT: "涨停热度袋",
    BAG_MARKET: "全市场袋",
}

_TIER_PREFIX = {"fact": "（事实）", "inference": "（推断）", "gap": "（缺口）"}

_TIER_LEGEND = (
    "主张档图例：（事实）=袋内锁定数字；（推断）=接合陈述，不引入袋外数字；"
    "（缺口）=清单项当日未见于袋。"
)


@dataclass(frozen=True)
class DigestRow:
    subject: str
    kind: DigestKind
    tier: DigestTier
    bag: str | None
    served_date: str | None
    text: str
    source_row: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "kind": self.kind,
            "tier": self.tier,
            "bag": self.bag,
            "served_date": self.served_date,
            "text": self.text,
            "source_row": self.source_row,
        }


@dataclass(frozen=True)
class WatchlistDigestPack:
    standing_date: str | None
    user_id: str
    status: DigestStatus
    watchlist: tuple[str, ...]
    focus_themes: tuple[str, ...]
    tape: MarketWatchPack
    rows: tuple[DigestRow, ...]
    method_card: str
    stop_text: str | None = None
    # P1a：题材项命中主线/双红后的窗口轨迹（theme_fermentation 委托产物）。
    fermentations: tuple[dict[str, Any], ...] = ()

    def to_snapshot(self) -> dict[str, Any]:
        """证据快照：生成时刻看到的一切。事后对账只对这份。"""

        return {
            "schema": "watchlist-digest-snapshot/v1",
            "standing_date": self.standing_date,
            "explicit": self.tape.explicit,
            "user_id": self.user_id,
            "status": self.status,
            "stop_text": self.stop_text,
            "watchlist": list(self.watchlist),
            "focus_themes": list(self.focus_themes),
            "method_card": self.method_card,
            "bags": [
                {
                    "name": bag.name,
                    "requested_date": bag.requested_date,
                    "served_date": bag.served_date,
                    "status": bag.status,
                    "rows": [_json_safe_row(dict(row)) for row in bag.rows],
                }
                for bag in self.tape.bags
            ],
            "rows": [_json_safe_row(row.to_dict()) for row in self.rows],
            "fermentations": [
                _json_safe_row(item) for item in self.fermentations
            ],
        }

    def to_receipt(self) -> dict[str, Any]:
        """瘦收据：只有状态/计数/缺口，进 episode 报告；整袋行留在快照里。"""

        return {
            "status": self.status,
            "standing_date": self.standing_date,
            "user_id": self.user_id,
            "watchlist_count": len(self.watchlist),
            "focus_theme_count": len(self.focus_themes),
            "fact_rows": sum(1 for row in self.rows if row.tier == "fact"),
            "inference_rows": sum(
                1 for row in self.rows if row.tier == "inference"
            ),
            "gap_rows": sum(1 for row in self.rows if row.tier == "gap"),
            "fermentation_rows": len(self.fermentations),
            "bag_status": {bag.name: bag.status for bag in self.tape.bags},
            "stop_text": self.stop_text,
        }

    def to_prompt_block(self) -> str:
        return f"## 自选简报组件包\n{self.render_public_answer()}"

    def render_public_answer(self) -> str:
        """公开稿填格。段序锁死（spec §6），缺段用缺口句占位。"""

        date_label = self.standing_date or "站立日不可用"
        kind = "显式指定" if self.tape.explicit else "库内最新交易日"
        lines = [f"# 自选简报（{date_label}）"]
        if self.status == "locked_db":
            lines.append(f"- 站立日：{date_label}。")
            lines.append(f"- （缺口）{self.stop_text}")
            return "\n".join(lines)
        if self.status == "empty":
            lines.append(f"- 站立日：{date_label}（{kind}）。")
            lines.append(f"- （缺口）{self.stop_text}")
            return "\n".join(lines)
        lines.append(
            f"- 站立日：{date_label}（{kind}，trade_date = ? 精确命中，未回落邻日）。"
        )
        lines.append(f"- 方法卡：{self.method_card}")
        lines.append("## 清单命中")
        ferm_by_subject = {
            str(item.get("subject")): item for item in self.fermentations
        }
        hit_lines = []
        pending_subject: str | None = None

        def _flush_fermentation(next_subject: str | None) -> None:
            nonlocal pending_subject
            if pending_subject == next_subject:
                return
            item = (
                ferm_by_subject.pop(pending_subject, None)
                if pending_subject is not None
                else None
            )
            if item is not None:
                hit_lines.append(
                    f"- （发酵摘要）{item.get('text')}"
                    f"〔方法：逐日复用严格双红/涨停热度袋口径，"
                    f"窗口={_cell(item.get('window_days'))}交易日；"
                    "袋有截断，计数为在袋/在榜口径〕"
                )
            pending_subject = next_subject

        for row in self.rows:
            if row.tier == "fact":
                _flush_fermentation(row.subject)
                label = _BAG_LABELS.get(row.bag or "", row.bag)
                hit_lines.append(
                    f"- {_TIER_PREFIX['fact']}{row.text}"
                    f"〔方法：{label}，served_date={row.served_date}〕"
                )
            elif row.tier == "inference":
                _flush_fermentation(row.subject)
                hit_lines.append(f"- {_TIER_PREFIX['inference']}{row.text}")
        _flush_fermentation(None)
        lines.extend(
            hit_lines
            or ["- （缺口）清单项当日在主线/严格双红/涨停热度三袋均无命中行。"]
        )
        lines.append("## 清单未命中")
        gap_lines = [
            f"- {_TIER_PREFIX['gap']}{row.text}"
            for row in self.rows
            if row.tier == "gap"
        ]
        lines.extend(gap_lines or ["- 无：清单项全部有袋内命中。"])
        lines.append("## 全市场上下文（全市场袋，不是你的清单）")
        market = self.tape.bag(BAG_MARKET)
        if market is not None and market.status == "hit" and market.rows:
            row = market.rows[0]
            lines.append(
                "- （事实）全市场成交额 {} 亿、涨停 {} 家、跌停 {} 家、"
                "量能 {}、阶段 {}。〔方法：全市场袋，served_date={}〕".format(
                    _cell(row.get("total_amount")),
                    _cell(row.get("limit_up")),
                    _cell(row.get("limit_down")),
                    _cell(row.get("volume_state")),
                    _cell(row.get("market_stage")),
                    market.served_date,
                )
            )
        else:
            lines.append("- （缺口）全市场袋当日无行。")
        lines.append(f"- {_TIER_LEGEND}")
        return "\n".join(lines)


def merge_digest_into_public_answer(
    text: str,
    pack: WatchlistDigestPack | None,
) -> str:
    """公开稿以包体为先；残差（P1 才开）只能追加在包体之后，不得改数字。"""

    if pack is None:
        return text
    body = pack.render_public_answer()
    residual = (text or "").strip()
    if not residual or residual in body:
        return body
    return f"{body}\n\n{residual}"


def run_watchlist_digest_pack(
    query: str,
    *,
    user_id: str | None = None,
    market_db_path: str | Path | None,
    calendar_disclosure: str | None = None,
    cutoff: str | None = None,
) -> WatchlistDigestPack:
    """纯函数入口：清单来自 effective_profile，盘面只委托一次四袋包。

    站立日语义与四袋包同源：显式日（问句日期或 ``cutoff``）精确命中；
    隐式「今天」= 库内最新交易日；禁止邻日回落。
    """

    uid = resolve_user_id(user_id)
    profile, _warnings = effective_profile(user_space(uid))
    watchlist = tuple(str(item) for item in profile.get("watchlist") or ())
    themes = tuple(str(item) for item in profile.get("focus_themes") or ())
    tape = run_market_watch_pack(
        query,
        market_db_path=market_db_path,
        calendar_disclosure=calendar_disclosure,
        cutoff=cutoff,
        substitute_probes=False,
    )
    method_card = _method_card(tape)

    def _stopped(status: DigestStatus, stop_text: str) -> WatchlistDigestPack:
        return WatchlistDigestPack(
            standing_date=tape.standing_date,
            user_id=uid,
            status=status,
            watchlist=watchlist,
            focus_themes=themes,
            tape=tape,
            rows=(),
            method_card=method_card,
            stop_text=stop_text,
        )

    if not watchlist and not themes:
        return _stopped(
            "empty",
            "画像清单为空：profile 里既没有钉住的 watchlist / focus_themes，"
            "也没有未过期的派生项。先在画像里钉清单，再要简报；"
            "本题不回落成全市场日报。",
        )
    db_reachable = bool(market_db_path) and (
        Path(str(market_db_path)).expanduser().exists()
    )
    market_bag = tape.bag(BAG_MARKET)
    if not db_reachable or (market_bag is not None and market_bag.locked):
        return _stopped(
            "locked_db",
            "盘面库不可用（路径缺失或写锁中）：读不到任何袋行，稍后再试；"
            "这不是该日缺数据。",
        )
    if tape.should_stop:
        return _stopped("empty", tape.stop_text())
    if tape.standing_date is None:
        return _stopped(
            "locked_db",
            "盘面库里没有可解析的交易日行，无法确定站立日；库可能尚未初始化。",
        )
    rows = _join_rows(watchlist, themes, tape)
    fermentations = _delegate_fermentations(rows, market_db_path, tape)
    return WatchlistDigestPack(
        standing_date=tape.standing_date,
        user_id=uid,
        status="locked",
        watchlist=watchlist,
        focus_themes=themes,
        tape=tape,
        rows=rows,
        method_card=method_card,
        fermentations=fermentations,
    )


def watchlist_digest_degrade_codes(
    pack: WatchlistDigestPack,
) -> tuple[str, ...]:
    if pack.status == "empty":
        return ("watchlist_digest_pack_empty",)
    if pack.status == "locked_db":
        return ("watchlist_digest_pack_locked_db",)
    return ()


def write_snapshot(
    pack: WatchlistDigestPack,
    *,
    base_dir: str | Path | None = None,
) -> Path:
    """证据快照落盘（运行时目录，gitignore，不入库）。

    目录形状：``<base>/<user>/<standing_date>/snapshot-<utc>.json``。
    base 解析顺序：显式参数 > ``WATCHLIST_DIGEST_DIR`` 环境变量 >
    ``~/.finance-runtime/watchlist-digest``。
    """

    directory = (
        _snapshot_base_dir(base_dir)
        / pack.user_id
        / (pack.standing_date or "no-standing-date")
    )
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"snapshot-{stamp}.json"
    payload = dict(pack.to_snapshot())
    payload["written_at_utc"] = stamp
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _snapshot_base_dir(base_dir: str | Path | None = None) -> Path:
    if base_dir is not None:
        return Path(base_dir).expanduser()
    env = os.environ.get(ENV_SNAPSHOT_DIR)
    if env and env.strip():
        return Path(env.strip()).expanduser()
    return Path.home() / ".finance-runtime" / "watchlist-digest"


def _method_card(tape: MarketWatchPack) -> str:
    kind = "显式指定站立日" if tape.explicit else "隐式取库内最新交易日"
    return (
        "清单来自 effective_profile（钉住项优先，并入未过期派生项）；"
        "盘面袋一次性委托 run_market_watch_pack"
        "（market_daily / mainline / dual_red / limit_heat 四袋）；"
        f"袋内查询按 trade_date = ? 精确命中站立日（{kind}），禁止邻日回落；"
        "清单×袋行按名字文本包含对齐（与主线∩双红缺口句同源规则）；"
        "数字只来自包内冻结行。"
    )


def _join_rows(
    watchlist: tuple[str, ...],
    themes: tuple[str, ...],
    tape: MarketWatchPack,
) -> tuple[DigestRow, ...]:
    rows: list[DigestRow] = []
    subjects: list[tuple[str, DigestKind]] = [
        *((item, "watchlist") for item in watchlist),
        *((item, "theme") for item in themes),
    ]
    for subject, kind in subjects:
        hits: list[tuple[str, str | None, dict[str, Any]]] = []
        for bag_name in _JOIN_BAGS:
            bag = tape.bag(bag_name)
            if bag is None or bag.status != "hit":
                continue
            for row in bag.rows:
                name = _bag_row_name(bag_name, row)
                if name and _names_match(subject, name):
                    # 袋行已按显著度排序，每袋只取最优一行。
                    hits.append((bag_name, bag.served_date, dict(row)))
                    break
        if not hits:
            rows.append(
                DigestRow(
                    subject=subject,
                    kind=kind,
                    tier="gap",
                    bag=None,
                    served_date=None,
                    text=(
                        f"清单项「{subject}」当日未见于主线、严格双红、"
                        "涨停热度三袋，无可锁定行情行。"
                    ),
                )
            )
            continue
        for bag_name, served, row in hits:
            rows.append(
                DigestRow(
                    subject=subject,
                    kind=kind,
                    tier="fact",
                    bag=bag_name,
                    served_date=served,
                    text=_fact_text(subject, bag_name, row),
                    source_row=row,
                )
            )
        if len(hits) >= 2:
            labels = " 与 ".join(
                _BAG_LABELS[bag_name] for bag_name, _served, _row in hits
            )
            rows.append(
                DigestRow(
                    subject=subject,
                    kind=kind,
                    tier="inference",
                    bag=None,
                    served_date=None,
                    text=(
                        f"清单项「{subject}」同日出现在 {labels}"
                        "（接合陈述，不引入袋外数字）。"
                    ),
                )
            )
    return tuple(rows)


def _delegate_fermentations(
    rows: tuple[DigestRow, ...],
    market_db_path: str | Path | None,
    tape: MarketWatchPack,
) -> tuple[dict[str, Any], ...]:
    """P1a 触发面（spec §3.3）：仅 theme 项命中主线或严格双红时回看。

    watchlist（个股）项与仅命中涨停热度的题材不触发；轨迹判定整体委托
    theme_fermentation（其内部逐日复用袋口径），本模块不携带任何口径。
    追溯主键优先用严格双红命中行的板块名（真实板块名字空间），
    仅主线命中时退回主线题材名。
    """

    subjects: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if row.kind != "theme" or row.tier != "fact":
            continue
        if row.bag not in (BAG_MAINLINE, BAG_DUAL_RED):
            continue
        if row.subject in seen:
            continue
        dual_hit = next(
            (
                item
                for item in rows
                if item.subject == row.subject
                and item.tier == "fact"
                and item.bag == BAG_DUAL_RED
            ),
            None,
        )
        source = dual_hit or row
        sector_name = _bag_row_name(source.bag or "", source.source_row or {})
        if not sector_name:
            continue
        subjects.append((row.subject, sector_name))
        seen.add(row.subject)
    if not subjects:
        return ()
    summaries = trace_sectors_fermentation(
        subjects,
        market_db_path=market_db_path,
        standing_date=tape.standing_date,
    )
    return tuple(summary.to_dict() for summary in summaries)


def _bag_row_name(bag_name: str, row: dict[str, Any]) -> str:
    if bag_name == BAG_MAINLINE:
        return str(row.get("theme_name") or row.get("sector_name") or "")
    return str(row.get("sector_name") or "")


def _fact_text(subject: str, bag_name: str, row: dict[str, Any]) -> str:
    name = _bag_row_name(bag_name, row)
    if bag_name == BAG_DUAL_RED:
        return (
            f"清单项「{subject}」命中严格双红袋：{name}，"
            f"涨幅 {_cell(row.get('pct_chg'))}%、"
            f"边际量 {_cell(row.get('diff_ratio'))}%、"
            f"成交额 {_cell(row.get('amount'))} 亿。"
        )
    if bag_name == BAG_LIMIT_HEAT:
        return (
            f"清单项「{subject}」命中涨停热度袋：{name}，"
            f"涨停 {_cell(row.get('limit_up_count'))} 家、"
            f"涨停占比 {_cell(row.get('market_share'))}。"
        )
    # 主线袋：在榜只说在榜，不写成加量（沿用盘面包 mainline_dual_red_gap 纪律）。
    count = row.get("sector_count")
    tail = f"（sector_count={_cell(count)}）" if count is not None else ""
    return f"清单项「{subject}」当日在主线名单：{name}{tail}；在榜不构成加量证据。"


def _cell(value: Any) -> str:
    return "—" if value is None else str(value)


def _json_safe(value: Any) -> Any:
    # 袋行里的 trade_date 是 date 对象；快照必须可 JSON 序列化（对账合同）。
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_safe(value) for key, value in row.items()}
