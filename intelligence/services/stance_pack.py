"""StancePack：用户旧账 × 站立日现价的接合核。

在 ``continuous_turn_adapter.handle()`` 之前跑完。prior 只许来自
``checkpoint_recall`` loader；现价只许 Provider 精确日查询。空袋合法。
认不出的价格数字 fail closed。本模块在 services，禁止 import runtime。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date as date_cls
from pathlib import Path
from typing import Any, Literal

from intelligence.services import checkpoint_recall, retrieval_cache
from intelligence.services.query_understanding import market_review_requested_date

PlaneName = Literal["checkpoint_verdict", "provider"]
BagStatus = Literal["hit", "empty", "unresolved"]
StanceKind = Literal["holding", "target", "trade_intent", "account"]

STANCE_KIND_TERMS: dict[StanceKind, tuple[str, ...]] = {
    "holding": ("持仓", "我有", "我的仓", "重仓", "底仓", "空仓", "空手", "满仓"),
    "target": ("目标价", "止损", "止盈", "成本价"),
    "trade_intent": (
        "该不该买",
        "该不该减",
        "要不要买",
        "加减仓",
        "现在买",
        "现在卖",
        "止损吗",
    ),
    "account": ("账户1", "账户2", "短线仓", "活钱仓"),
}

_TRADE_ADVICE = "trade_advice"
_CODE_RE = re.compile(r"\b(\d{6})(?:\.[A-Za-z]{2})?\b")
_NAME_RE = re.compile(
    r"([\u4e00-\u9fff]{2,8}?)(?:现在|目前|今天)?"
    r"(?:我持仓|我有|目标价|止损|该不该|要不要买|要不要止损|现在买|现在卖)"
)
_PRICE_LIKE_RE = re.compile(r"(?<![\d.])(\d{1,5}(?:\.\d{1,3})?)(?![\d])")
_PRIOR_PROMOTED_RE = re.compile(
    r"市场已经确认|已经兑现你的|市场证明你|市场已确认你|证实了你上次"
)
_GAP_MARK_RE = re.compile(r"缺口|推断")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？\n])")


@dataclass(frozen=True)
class PlaneBag:
    plane: PlaneName
    served_date: str | None
    entity_ids: tuple[str, ...]
    rows: tuple[dict[str, object], ...]
    status: BagStatus
    gap: str


@dataclass(frozen=True)
class StancePack:
    standing_date: str
    stance_kinds: tuple[str, ...]
    prior_bag: PlaneBag
    quote_bag: PlaneBag
    unresolved: tuple[str, ...]

    def to_receipt(self) -> dict[str, object]:
        """落进 continuous-episode.json 的瘦收据。只记 status/缺口，不抄行。"""

        return {
            "standing_date": self.standing_date,
            "stance_kinds": list(self.stance_kinds),
            "prior": {
                "status": self.prior_bag.status,
                "gap": self.prior_bag.gap,
                "entity_ids": list(self.prior_bag.entity_ids),
            },
            "quote": {
                "status": self.quote_bag.status,
                "gap": self.quote_bag.gap,
                "served_date": self.quote_bag.served_date,
                "entity_ids": list(self.quote_bag.entity_ids),
            },
            "unresolved": list(self.unresolved),
        }

    def to_prompt_block(self) -> str:
        """模型可见锁格。空袋写缺口，不得把 prior 写成已兑现。"""

        prior = _bag_prompt(self.prior_bag, empty_label="无先验")
        quote = _bag_prompt(self.quote_bag, empty_label="无站立日现价")
        kinds = "、".join(self.stance_kinds) or "（题型 trade_advice）"
        unresolved = "、".join(self.unresolved) if self.unresolved else "无"
        return (
            "## 接合锁格 [StancePack]（先验 ≠ 现价；只许引用本袋，禁止改数）\n"
            f"- 站立日：{self.standing_date}\n"
            f"- 表态种类：{kinds}\n"
            f"- 你上次（旧账 × 裁决）：{prior}\n"
            f"- 站立日现价：{quote}\n"
            f"- 未解析实体：{unresolved}\n"
            "- 使用要求：先验不是市场事实。袋外价格删除。动作只写条件，不写现在买/现在卖。"
        )


def detect_stance_kinds(query: str) -> tuple[str, ...]:
    text = str(query or "")
    hit = tuple(
        kind for kind, terms in STANCE_KIND_TERMS.items() if any(term in text for term in terms)
    )
    return hit


def should_run_stance_pack(
    *,
    lane: str,
    question_type: str | None,
    query: str,
) -> bool:
    """两道门都 fail closed。chat/meta/clarify/knowledge 不跑。"""

    qtype = str(question_type or "").strip()
    eligible_lane = lane == "research" or qtype == _TRADE_ADVICE
    stance_or_trade = qtype == _TRADE_ADVICE or bool(detect_stance_kinds(query))
    return bool(eligible_lane and stance_or_trade)


def resolve_stance_standing_date(
    query: str,
    *,
    cutoff: str | None = None,
    today: str | None = None,
) -> str:
    """显式日精确命中；隐式「今天」用 cutoff/today，禁止 ``<=`` 回落邻日。"""

    explicit = market_review_requested_date(query)
    if explicit:
        return explicit
    for candidate in (cutoff, today):
        text = str(candidate or "").strip()[:10]
        if _is_iso_date(text):
            return text
    return date_cls.today().isoformat()


def run_stance_pack(
    query: str,
    *,
    standing_date: str | None = None,
    cutoff: str | None = None,
    today: str | None = None,
    user: str | None = None,
    users_root: str | Path | None = None,
    market_db_path: str | Path | None = None,
    subject: str | None = None,
    capabilities: tuple[str, ...] = (),
    theme: str | None = None,
) -> StancePack:
    kinds = detect_stance_kinds(query)
    date = standing_date or resolve_stance_standing_date(
        query, cutoff=cutoff, today=today
    )
    mentions = _entity_mentions(query, subject)
    loaded = checkpoint_recall.recall_rows_for_query(
        query,
        theme=theme,
        entity=subject or (mentions[0] if mentions else None),
        user=user,
        users_root=users_root,
    )
    prior_bag = _prior_bag_from_rows(loaded)
    quote_bag, unresolved = _quote_bag(
        query=query,
        standing_date=date,
        mentions=mentions,
        capabilities=capabilities,
        market_db_path=market_db_path,
    )
    return StancePack(
        standing_date=date,
        stance_kinds=kinds,
        prior_bag=prior_bag,
        quote_bag=quote_bag,
        unresolved=unresolved,
    )


def render_prior_bag(
    bag: PlaneBag,
    *,
    today: str | None = None,
    data_asof: str | None = None,
) -> str:
    """V 块投影：只渲染袋里的行，不再查台账。"""

    if bag.plane != "checkpoint_verdict":
        return ""
    if bag.status != "hit" or not bag.rows:
        return ""
    matched: list[dict[str, Any]] = []
    verdicts: dict[str, dict[str, Any]] = {}
    for row in bag.rows:
        checkpoint = row.get("checkpoint")
        if isinstance(checkpoint, dict):
            matched.append(checkpoint)
        cid = str(row.get("id") or "")
        verdict_row = row.get("verdict_row")
        if cid and isinstance(verdict_row, dict):
            verdicts[cid] = verdict_row
    return checkpoint_recall.render_recall_from_rows(
        matched,
        verdicts,
        today=today,
        data_asof=data_asof,
    )


def lint_public_answer(
    answer: str,
    pack: StancePack,
    *,
    query: str = "",
) -> tuple[str, tuple[str, ...]]:
    """袋外价格删句；先验写成市场事实则记 ``prior_promoted_to_fact``。"""

    flags: list[str] = []
    if _PRIOR_PROMOTED_RE.search(answer):
        flags.append("prior_promoted_to_fact")
    allowed = _allowed_price_tokens(pack, query)
    kept: list[str] = []
    dropped = False
    for sentence in _SENTENCE_SPLIT_RE.split(answer):
        if not sentence.strip():
            kept.append(sentence)
            continue
        if _sentence_has_bag_external_price(sentence, allowed):
            dropped = True
            continue
        kept.append(sentence)
    if dropped:
        flags.append("bag_external_price")
    cleaned = "".join(kept).strip()
    return cleaned, tuple(dict.fromkeys(flags))


def bind_id_for(question_type: str, subject: str, standing_date: str) -> str:
    material = f"{question_type}\0{subject}\0{standing_date}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _prior_bag_from_rows(loaded: dict[str, Any]) -> PlaneBag:
    matched = list(loaded.get("matched") or [])
    verdicts_by_id = dict(loaded.get("verdicts_by_id") or {})
    if not matched:
        return PlaneBag(
            plane="checkpoint_verdict",
            served_date=None,
            entity_ids=(),
            rows=(),
            status="empty",
            gap="未检索到与该问句相关的可证伪旧账。不得写成「你没有旧判断所以现在可以买」。",
        )
    rows: list[dict[str, object]] = []
    entity_ids: list[str] = []
    for ck in matched:
        cid = str(ck.get("id") or "").strip()
        verdict = verdicts_by_id.get(cid)
        for stock in ck.get("stocks") or ():
            token = str(stock).strip()
            if token:
                entity_ids.append(token)
        rows.append(
            {
                "id": cid,
                "claim": ck.get("claim"),
                "due": ck.get("due"),
                "category": ck.get("category"),
                "themes": ck.get("themes"),
                "stocks": ck.get("stocks"),
                "verdict": None if verdict is None else verdict.get("verdict"),
                "reason": None if verdict is None else verdict.get("reason"),
                "checkpoint": ck,
                "verdict_row": verdict,
            }
        )
    return PlaneBag(
        plane="checkpoint_verdict",
        served_date=None,
        entity_ids=tuple(dict.fromkeys(entity_ids)),
        rows=tuple(rows),
        status="hit",
        gap="",
    )


def _quote_bag(
    *,
    query: str,
    standing_date: str,
    mentions: tuple[str, ...],
    capabilities: tuple[str, ...],
    market_db_path: str | Path | None,
) -> tuple[PlaneBag, tuple[str, ...]]:
    del query
    if "market_data" not in capabilities:
        return (
            PlaneBag(
                plane="provider",
                served_date=None,
                entity_ids=mentions,
                rows=(),
                status="empty",
                gap="未授权 market_data，现价袋未查（stance_quote_capability_absent）。公开稿不得出现具体价。",
            ),
            mentions,
        )
    if not mentions:
        return (
            PlaneBag(
                plane="provider",
                served_date=None,
                entity_ids=(),
                rows=(),
                status="unresolved",
                gap="未解析到可查行情的实体，不许猜代码。",
            ),
            ("unresolved_entity",),
        )
    rows = _load_quote_rows(market_db_path, standing_date, mentions)
    if not rows:
        return (
            PlaneBag(
                plane="provider",
                served_date=None,
                entity_ids=mentions,
                rows=(),
                status="empty",
                gap=f"{standing_date} 无该实体行情行，未回落邻日。",
            ),
            (),
        )
    return (
        PlaneBag(
            plane="provider",
            served_date=standing_date,
            entity_ids=mentions,
            rows=tuple(rows),
            status="hit",
            gap="",
        ),
        (),
    )


def _load_quote_rows(
    market_db_path: str | Path | None,
    standing_date: str,
    mentions: tuple[str, ...],
) -> list[dict[str, object]]:
    con = _connect(market_db_path)
    if con is None:
        return []
    try:
        if not _has_table(con, "fact_stock_daily"):
            return []
        found: list[dict[str, object]] = []
        seen: set[str] = set()
        for mention in mentions:
            row = con.execute(
                """
                select stock_ts_code, stock_name, close, pct_chg
                from fact_stock_daily
                where trade_date = cast(? as date)
                  and (
                    stock_name = ?
                    or stock_ts_code = ?
                    or stock_ts_code like ?
                  )
                limit 1
                """,
                [standing_date, mention, mention, f"{mention}%"],
            ).fetchone()
            if row is None:
                continue
            code = str(row[0] or "")
            if code in seen:
                continue
            seen.add(code)
            found.append(
                {
                    "stock_ts_code": code,
                    "stock_name": str(row[1] or ""),
                    "close": row[2],
                    "pct_chg": row[3],
                    "trade_date": standing_date,
                }
            )
        return found
    except Exception:
        return []
    finally:
        con.close()


def _connect(market_db_path: str | Path | None):
    if not market_db_path:
        return None
    path = Path(market_db_path).expanduser()
    if not path.exists():
        return None
    db_result = retrieval_cache.try_connect_readonly(path)
    if not db_result.available:
        return None
    return db_result.connection


def _has_table(con: Any, name: str) -> bool:
    row = con.execute(
        """
        select 1 from information_schema.tables
        where table_schema = 'main' and table_name = ?
        """,
        [name],
    ).fetchone()
    return row is not None


def _entity_mentions(query: str, subject: str | None) -> tuple[str, ...]:
    found: list[str] = []
    subject_clean = str(subject or "").strip()
    if subject_clean and subject_clean not in {"A股市场", "该问题", "已验证主体"}:
        found.append(subject_clean)
    for match in _CODE_RE.finditer(query):
        found.append(match.group(1))
    for match in _NAME_RE.finditer(query):
        found.append(match.group(1))
    return tuple(dict.fromkeys(item for item in found if item))


def _allowed_price_tokens(pack: StancePack, query: str) -> set[str]:
    allowed = {token for token in _PRICE_LIKE_RE.findall(query) if token}
    for row in pack.quote_bag.rows:
        for key in ("close", "pct_chg"):
            value = row.get(key)
            if value is None:
                continue
            allowed.add(_format_number(value))
            try:
                allowed.add(f"{float(value):.2f}")
                allowed.add(f"{float(value):.1f}")
            except (TypeError, ValueError):
                pass
    return {item for item in allowed if item}


def _format_number(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        return text[:-2]
    return text


def _sentence_has_bag_external_price(sentence: str, allowed: set[str]) -> bool:
    if _GAP_MARK_RE.search(sentence):
        return False
    if not any(marker in sentence for marker in ("价", "元", "收于", "现价", "%", "涨", "跌")):
        return False
    for token in _PRICE_LIKE_RE.findall(sentence):
        if token in allowed:
            continue
        if f"{token}0" in allowed or token.rstrip("0").rstrip(".") in allowed:
            continue
        return True
    return False


def _bag_prompt(bag: PlaneBag, *, empty_label: str) -> str:
    if bag.status == "hit" and bag.rows:
        bits = []
        for row in bag.rows[:4]:
            if bag.plane == "provider":
                bits.append(
                    f"{row.get('stock_name') or row.get('stock_ts_code')} "
                    f"收 {row.get('close')} / {row.get('pct_chg')}%"
                )
            else:
                bits.append(str(row.get("claim") or row.get("id") or ""))
        return "；".join(bit.strip() for bit in bits if bit.strip())
    return f"{empty_label}（{bag.gap}）" if bag.gap else empty_label


def _is_iso_date(value: str) -> bool:
    try:
        date_cls.fromisoformat(value)
    except ValueError:
        return False
    return True
