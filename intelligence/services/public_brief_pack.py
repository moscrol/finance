"""公开晚报包 —— 可对外分享的一页晚报，公开安全白名单渲染。

spec: docs/superpowers/specs/2026-08-27-public-evening-brief-design.md

与内部复盘/自选简报的本质区别：公开分享 = 公开出版。本模块的骨架是
**数据许可白名单**，不是信息量——供应商派生口径（边际量/双红/主线/阶段标签/
题材热度榜）在渲染层物理够不到；能出场的只有公开可复核事实（指数/涨跌停/
成交额/连板分布）与自家知识库加工（题材候选的名字和 KB 统计）。

双保险：``_public_market_row`` 白名单（名单外的键不进模板）+ deny-token
测试（渲染产物匹配到供应商口径词或买卖词即红）。产物是文件不是题型：
不进问答路由、不碰 8792。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Literal

import duckdb

from intelligence.services.market_watch_pack import (
    BAG_MARKET,
    run_market_watch_pack,
)

# 公开安全白名单：market_daily 袋只有这些键可进渲染（spec §1）。
# market_stage / stage_day / volume_state 是供应商标签，刻意不在名单上。
_MARKET_BAG_WHITELIST = (
    "trade_date",
    "total_amount",
    "amount_vs_yesterday_pct",
    "limit_up",
    "limit_down",
    "sh_index_pct_chg",
)

# 渲染产物全文不得出现的口径词与动作词（spec §1 / §6.2）。
DENY_TOKEN_RE = re.compile(
    r"边际量|diff_ratio|双红|double_red|主线|市场阶段|量能状态|买入|卖出|加仓|减仓|做多|做空"
)

_DISCLAIMER = "AI 生成，人工复核后分享；不构成投资建议。"


@dataclass(frozen=True)
class BriefFact:
    label: str
    value: str
    source: str


@dataclass(frozen=True)
class BriefLadder:
    max_boards: int
    leaders: tuple[str, ...]
    distribution: tuple[tuple[int, int], ...]  # (连板数, 家数)，按连板数降序


@dataclass(frozen=True)
class BriefTheme:
    name: str
    concept_pages: int
    exposure_count: int
    evidence_count: int


@dataclass(frozen=True)
class PublicEveningBrief:
    standing_date: str | None
    status: Literal["locked_db", "empty", "locked"]
    stop_text: str | None
    facts: tuple[BriefFact, ...]
    ladder: BriefLadder | None
    themes: tuple[BriefTheme, ...]
    method_card: str
    generated_at: str

    @property
    def snapshot_id(self) -> str:
        payload = json.dumps(self.to_snapshot_body(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    def to_snapshot_body(self) -> dict[str, Any]:
        """快照正文：冻结全部渲染输入（不含 generated_at，保证同输入同 ID）。"""
        return {
            "standing_date": self.standing_date,
            "status": self.status,
            "stop_text": self.stop_text,
            "facts": [
                {"label": f.label, "value": f.value, "source": f.source}
                for f in self.facts
            ],
            "ladder": (
                {
                    "max_boards": self.ladder.max_boards,
                    "leaders": list(self.ladder.leaders),
                    "distribution": [list(item) for item in self.ladder.distribution],
                }
                if self.ladder
                else None
            ),
            "themes": [
                {
                    "name": t.name,
                    "concept_pages": t.concept_pages,
                    "exposure_count": t.exposure_count,
                    "evidence_count": t.evidence_count,
                }
                for t in self.themes
            ],
            "method_card": self.method_card,
        }

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "snapshot_id": self.snapshot_id,
            "generated_at": self.generated_at,
            **self.to_snapshot_body(),
        }

    def render_html(self) -> str:
        e = html.escape
        head = (
            "<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>晚报 · {e(self.standing_date or '无站立日')}</title>"
            "<style>"
            "body{margin:0;background:#0f1420;color:#e8ecf4;font:15px/1.7 -apple-system,"
            "'PingFang SC','Microsoft YaHei',sans-serif}"
            ".page{max-width:750px;margin:0 auto;padding:28px 22px 20px}"
            "h1{font-size:22px;margin:0 0 2px}"
            ".sub{color:#8b95ab;font-size:12px;margin-bottom:18px}"
            ".card{background:#171e2e;border:1px solid #232c42;border-radius:12px;"
            "padding:14px 16px;margin-bottom:14px}"
            ".card h2{font-size:14px;color:#9fb0d0;margin:0 0 10px;font-weight:600}"
            ".facts{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}"
            ".fact .v{font-size:19px;font-weight:700}"
            ".fact .l{font-size:12px;color:#8b95ab}"
            ".row{margin:4px 0}"
            ".theme{display:flex;justify-content:space-between;gap:8px;margin:6px 0}"
            ".theme .kb{color:#8b95ab;font-size:12px;white-space:nowrap}"
            ".method,.footer{font-size:11px;color:#6d7890}"
            ".footer{margin-top:14px;border-top:1px solid #232c42;padding-top:10px}"
            ".stop{font-size:16px;padding:24px 0}"
            "</style></head><body><div class=\"page\">"
        )
        parts: list[str] = [head]
        parts.append(f"<h1>A 股晚报 · {e(self.standing_date or '—')}</h1>")
        parts.append("<div class=\"sub\">公开行情统计 × 本地知识库 · 每个数字可审计</div>")
        if self.status != "locked":
            parts.append(f"<div class=\"card stop\">{e(self.stop_text or '当日数据不可用。')}</div>")
        else:
            parts.append("<div class=\"card\"><h2>盘面事实</h2><div class=\"facts\">")
            for fact in self.facts:
                parts.append(
                    "<div class=\"fact\">"
                    f"<div class=\"v\">{e(fact.value)}</div>"
                    f"<div class=\"l\">{e(fact.label)}</div></div>"
                )
            parts.append("</div></div>")
            parts.append("<div class=\"card\"><h2>连板观察（公开行情可复核）</h2>")
            if self.ladder is None:
                parts.append("<div class=\"row\">当日连板梯队数据未同步，本段缺口。</div>")
            else:
                leaders = "、".join(self.ladder.leaders)
                dist = "、".join(
                    f"{boards}板 {count} 只" for boards, count in self.ladder.distribution
                )
                parts.append(
                    f"<div class=\"row\">最高 {self.ladder.max_boards} 板：{e(leaders)}</div>"
                )
                parts.append(f"<div class=\"row\">{e(dist)}</div>")
            parts.append("</div>")
            parts.append("<div class=\"card\"><h2>题材候选（本地知识库图谱）</h2>")
            if not self.themes:
                parts.append("<div class=\"row\">当日题材候选产物未生成，本段缺口。</div>")
            else:
                for theme in self.themes:
                    parts.append(
                        "<div class=\"theme\">"
                        f"<div>{e(theme.name)}</div>"
                        f"<div class=\"kb\">概念 {theme.concept_pages} · 暴露公司 "
                        f"{theme.exposure_count} · 证据 {theme.evidence_count}</div></div>"
                    )
            parts.append("</div>")
        parts.append(f"<div class=\"method card\">{e(self.method_card)}</div>")
        parts.append(
            "<div class=\"footer\">"
            f"{e(_DISCLAIMER)} 快照 {e(self.snapshot_id)} · 生成于 {e(self.generated_at)}"
            "</div>"
        )
        parts.append("</div></body></html>")
        return "".join(parts)


def _format_amount(value: Any) -> str:
    try:
        return f"{float(value):,.0f} 亿"
    except (TypeError, ValueError):
        return "未知"


def _format_pct(value: Any) -> str:
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "未知"


def _format_int(value: Any) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "未知"


def _public_market_row(rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """白名单准入：名单外的键在这里物理丢弃，渲染层永远看不见。"""
    if not rows:
        return {}
    row = rows[0]
    return {key: row.get(key) for key in _MARKET_BAG_WHITELIST}


def _query_public_extras(con: Any, standing: str) -> dict[str, Any]:
    row = con.execute(
        "select sh_index_close, advancers from fact_market_daily "
        "where trade_date = cast(? as date) limit 1",
        [standing],
    ).fetchone()
    if not row:
        return {}
    return {"sh_index_close": row[0], "advancers": row[1]}


def _query_ladder(con: Any, standing: str) -> BriefLadder | None:
    rows = con.execute(
        "select stock_name, boards from fact_limit_advance_daily "
        "where trade_date = cast(? as date) order by boards desc, stock_name",
        [standing],
    ).fetchall()
    if not rows:
        return None
    counts: dict[int, int] = {}
    for _, boards in rows:
        counts[int(boards)] = counts.get(int(boards), 0) + 1
    max_boards = max(counts)
    leaders = tuple(
        str(name) for name, boards in rows if int(boards) == max_boards
    )[:3]
    distribution = tuple(
        (boards, counts[boards]) for boards in sorted(counts, reverse=True)
    )
    return BriefLadder(max_boards=max_boards, leaders=leaders, distribution=distribution)


_THEME_ROW_RE = re.compile(r"^\|\s*\d+\s*\|")


def _parse_theme_candidates(path: Path, limit: int = 3) -> tuple[BriefTheme, ...]:
    """从当日题材候选 md 里取前 N 行的题材名与自家 KB 统计。

    列序（spec §3.3）：排名|题材|标准概念|申万一级|评分|触发|概念|公司暴露|证据|缺口。
    「触发」列含供应商信号词，刻意不读。文件缺失 → 空元组（题材段整段缺口）。
    """
    if not path.exists():
        return ()
    themes: list[BriefTheme] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not _THEME_ROW_RE.match(line.strip()):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 9:
            continue

        def _count(cell: str) -> int:
            try:
                return int(cell)
            except ValueError:
                return 0

        themes.append(
            BriefTheme(
                name=cells[1],
                concept_pages=_count(cells[6]),
                exposure_count=_count(cells[7]),
                evidence_count=_count(cells[8]),
            )
        )
        if len(themes) >= limit:
            break
    return tuple(themes)


def _method_card(standing: str | None, ladder_present: bool, theme_count: int) -> str:
    pieces = [
        f"方法卡：站立日 {standing or '未定'}，全部数字按 trade_date = 站立日精确命中，无邻日回落。",
        "盘面事实为公开行情统计（指数/涨跌停/成交额，本地库自算口径）；",
        "连板分布可由公开行情逐日复核；" if ladder_present else "连板段当日缺口；",
        f"题材候选来自本地知识库图谱（当日 Top {theme_count}，不含盘面信号词）。"
        if theme_count
        else "题材段当日缺口。",
    ]
    return "".join(pieces)


def run_public_evening_brief(
    *,
    market_db_path: str | Path | None,
    exports_dir: str | Path,
    cutoff: str | None = None,
) -> PublicEveningBrief:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    tape = run_market_watch_pack(
        "今天市场怎么样", market_db_path=market_db_path, cutoff=cutoff
    )
    market_bag = tape.bag(BAG_MARKET)
    if market_bag is not None and market_bag.locked:
        return PublicEveningBrief(
            standing_date=tape.standing_date,
            status="locked_db",
            stop_text="盘面库暂不可读（写锁/不可用），不是该日无行情；稍后重试。",
            facts=(),
            ladder=None,
            themes=(),
            method_card=_method_card(tape.standing_date, False, 0),
            generated_at=generated_at,
        )
    if market_bag is None or market_bag.empty:
        return PublicEveningBrief(
            standing_date=tape.standing_date,
            status="empty",
            stop_text=tape.stop_text(),
            facts=(),
            ladder=None,
            themes=(),
            method_card=_method_card(tape.standing_date, False, 0),
            generated_at=generated_at,
        )

    public_row = _public_market_row(market_bag.rows)
    standing = str(market_bag.served_date or tape.standing_date)
    with duckdb.connect(str(market_db_path), read_only=True) as con:
        extras = _query_public_extras(con, standing)
        ladder = _query_ladder(con, standing)

    facts = (
        BriefFact("上证指数", _format_pct(public_row.get("sh_index_pct_chg")), "公开行情统计"),
        BriefFact("上证收盘", _format_int(extras.get("sh_index_close")), "公开行情统计"),
        BriefFact("两市成交", _format_amount(public_row.get("total_amount")), "公开行情统计"),
        BriefFact("成交环比", _format_pct(public_row.get("amount_vs_yesterday_pct")), "公开行情统计"),
        BriefFact(
            "涨停 / 跌停",
            f"{_format_int(public_row.get('limit_up'))} / {_format_int(public_row.get('limit_down'))}",
            "公开行情统计",
        ),
        BriefFact("上涨家数", _format_int(extras.get("advancers")), "公开行情统计"),
    )
    themes = _parse_theme_candidates(
        Path(exports_dir) / f"{standing}-theme-candidates.md"
    )
    return PublicEveningBrief(
        standing_date=standing,
        status="locked",
        stop_text=None,
        facts=facts,
        ladder=ladder,
        themes=themes,
        method_card=_method_card(standing, ladder is not None, len(themes)),
        generated_at=generated_at,
    )


_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def write_outputs(
    brief: PublicEveningBrief,
    out_dir: str | Path,
    *,
    png: bool = False,
    chrome_path: str | None = None,
) -> dict[str, str]:
    """落产物：HTML 必写；PNG 尽力而为（无 Chrome / 截图失败不红）。"""
    target = Path(out_dir) / str(brief.standing_date or "undated")
    target.mkdir(parents=True, exist_ok=True)
    html_path = target / "evening.html"
    html_path.write_text(brief.render_html(), encoding="utf-8")
    result = {"html": str(html_path)}
    if png:
        chrome = chrome_path or _CHROME
        png_path = target / "evening.png"
        try:
            subprocess.run(
                [
                    chrome,
                    "--headless=new",
                    "--disable-gpu",
                    f"--screenshot={png_path}",
                    "--window-size=750,1250",
                    "--hide-scrollbars",
                    f"file://{html_path}",
                ],
                capture_output=True,
                timeout=45,
                check=True,
            )
            result["png"] = str(png_path)
        except (OSError, subprocess.SubprocessError) as exc:
            result["png_error"] = f"{type(exc).__name__}: PNG 降级跳过，HTML 为主产物"
    return result


def write_snapshot(brief: PublicEveningBrief) -> Path:
    root = Path(
        os.environ.get("PUBLIC_BRIEF_DIR")
        or Path.home() / ".finance-runtime" / "public-brief"
    )
    target = root / str(brief.standing_date or "undated")
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = target / f"snapshot-{stamp}.json"
    path.write_text(
        json.dumps(brief.to_snapshot(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
