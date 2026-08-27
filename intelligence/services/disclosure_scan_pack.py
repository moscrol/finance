"""Deterministic sector disclosure scan pack.

Universe ∩ cninfo keyword titles ∩ title tiers, before any owner/model fork.
Services-layer only: no runtime imports. Network IO is injected in tests.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Protocol
from zoneinfo import ZoneInfo

from typing import TYPE_CHECKING

from intelligence.services import retrieval_cache

if TYPE_CHECKING:  # answer_model → research_contract → …本模块，运行时循环
    from intelligence.services import answer_model

WALL_SECONDS = 45.0
PAGE_SIZE = 30
MAX_PAGES = 3
EXCLUDED_PUBLIC_CAP = 3
REQUEST_TIMEOUT_SECONDS = 10.0
REQUEST_GAP_SECONDS = 1.1
CNINFO_COLUMN = "szse"
CNINFO_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_REFERER = "https://www.cninfo.com.cn/new/disclosure"
DEFAULT_WINDOW_DAYS = 5
WEEK_WINDOW_DAYS = 6

MAIN_KEYWORDS: tuple[str, ...] = (
    "中标",
    "中选",
    "重大合同",
    "销售合同",
    "获批",
    "药品注册",
    "临床试验批准",
)
APPENDIX_KEYWORDS: tuple[str, ...] = ("回购", "增持", "业绩预增")
ALL_KEYWORDS: tuple[str, ...] = MAIN_KEYWORDS + APPENDIX_KEYWORDS

ALIAS_BUCKETS: dict[str, tuple[str, ...]] = {
    "医药": (
        "医药",
        "医药医疗",
        "生物制药",
        "医疗器械",
        "医疗服务",
        "医药商业",
    ),
    "科技": (
        "电子",
        "计算机",
        "软件服务",
        "通信",
        "通信设备",
        "半导体",
        "消费电子",
    ),
}
SECTOR_NAME_CATALOG: tuple[str, ...] = tuple(
    dict.fromkeys(name for names in ALIAS_BUCKETS.values() for name in names)
)
MAIN_TIERS = frozenset({"L_reg", "L_ind", "L_order"})
EXCLUDED_TIERS = frozenset({"L_buyback", "L_hold", "L_collect", "unclassified"})
TIER_LABELS = {
    "L_reg": "注册获批",
    "L_ind": "临床批件（临床≠上市）",
    "L_order": "合同/中选（标题未写金额则未知）",
    "L_buyback": "回购（资本运作备考）",
    "L_hold": "增持（资本运作备考）",
    "L_collect": "集采中选（量价对冲，不默认利好）",
    "L_neg": "负面/撤回",
    "unclassified": "未分类",
}

_CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
_SECTOR_HINT_RE = re.compile(
    r"(板块|行业|医药|科技|" + "|".join(re.escape(n) for n in SECTOR_NAME_CATALOG) + r")"
)
_DISCLOSURE_HINT_RE = re.compile(r"(公告|披露|中标|获批|注册证)")
_ROSTER_HINT_RE = re.compile(r"(哪些|哪家|个股|公司名单)")
_EM_RE = re.compile(r"</?em>", re.IGNORECASE)
_CODE_RE = re.compile(r"(\d{6})")
_NEG_RE = re.compile(r"(减持|立案|问询|处罚|预减|撤回注册|撤回.{0,6}注册|终止|诉讼)")
_REG_RE = re.compile(r"(药品注册证书|药品注册批准|医疗器械注册)")
_IND_RE = re.compile(r"(药物临床试验批准|临床试验批准通知书|临床试验批准)")
_COLLECT_RE = re.compile(r"(集采中选|国家集中采购|集中采购|带量采购)")
_ORDER_RE = re.compile(r"(中选通知书|重大合同|销售合同|中标)")
_BUYBACK_RE = re.compile(r"(回购进展|回购实施|注销回购|调整回购价格|律师意见书|回购)")
_HOLD_RE = re.compile(r"增持")
_TODAY_WINDOW_RE = re.compile(r"(今天|今日)")
_WEEK_WINDOW_RE = re.compile(r"(近一周|本周|这一周)")


class CninfoFetch(Protocol):
    def __call__(
        self,
        *,
        keyword: str,
        se_date: str,
        page_num: int,
        page_size: int = PAGE_SIZE,
        column: str = CNINFO_COLUMN,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
    ) -> CninfoPage: ...


@dataclass(frozen=True)
class CninfoPage:
    announcements: tuple[dict[str, Any], ...]
    total_announcement: int
    error: str | None = None


@dataclass(frozen=True)
class DisclosureBucket:
    name: str
    sector_names: tuple[str, ...]
    universe_size: int
    hit_codes: tuple[str, ...]


@dataclass(frozen=True)
class DisclosureRow:
    code: str
    name: str
    date: str
    title: str
    tier: str
    announcement_id: str
    org_id: str
    url: str
    buckets: tuple[str, ...]


@dataclass(frozen=True)
class KeywordTrace:
    keyword: str
    total_announcement: int | None
    pages_fetched: int
    page_rows: int
    truncated: bool
    status: str
    error: str | None = None


@dataclass(frozen=True)
class DisclosureScanPack:
    status: str
    as_of: str
    universe_date: str | None
    se_date_start: str
    se_date_end: str
    elapsed_ms: int
    budget_hit: bool
    buckets: tuple[DisclosureBucket, ...]
    rows: tuple[DisclosureRow, ...]
    excluded: tuple[DisclosureRow, ...]
    counter_rows: tuple[DisclosureRow, ...]
    keyword_traces: tuple[KeywordTrace, ...]
    warnings: tuple[str, ...]
    fetch_calls: tuple[dict[str, Any], ...] = ()

    def render(self) -> str:
        return render_disclosure_scan_pack(self)

    def to_dict(self) -> dict[str, Any]:
        """Internal receipt. Orchestrator persists this; tests are not a reader."""

        return {
            "status": self.status,
            "as_of": self.as_of,
            "universe_date": self.universe_date,
            "se_date_start": self.se_date_start,
            "se_date_end": self.se_date_end,
            "elapsed_ms": self.elapsed_ms,
            "budget_hit": self.budget_hit,
            "fetch_calls": list(self.fetch_calls),
            "warnings": list(self.warnings),
            "buckets": [
                {
                    "name": bucket.name,
                    "sector_names": list(bucket.sector_names),
                    "universe_size": bucket.universe_size,
                    "hit_codes": list(bucket.hit_codes),
                }
                for bucket in self.buckets
            ],
            "rows": [_row_to_dict(row) for row in self.rows],
            "excluded": [_row_to_dict(row) for row in self.excluded],
            "counter_rows": [_row_to_dict(row) for row in self.counter_rows],
            "keyword_traces": [
                {
                    "keyword": trace.keyword,
                    "total_announcement": trace.total_announcement,
                    "pages_fetched": trace.pages_fetched,
                    "page_rows": trace.page_rows,
                    "truncated": trace.truncated,
                    "status": trace.status,
                    "error": trace.error,
                }
                for trace in self.keyword_traces
            ],
        }


def is_disclosure_scan_query(query: str) -> bool:
    """板块/行业范围内要一份近期官方披露个股名单，而不是单条公告冲击。"""

    text = re.sub(r"\s+", "", str(query or "").strip())
    if not text:
        return False
    return bool(
        _SECTOR_HINT_RE.search(text)
        and _DISCLOSURE_HINT_RE.search(text)
        and _ROSTER_HINT_RE.search(text)
    )


def parse_disclosure_buckets(query: str) -> tuple[DisclosureBucket, ...]:
    """Alias buckets first; leftover exact ``sector_name`` hits stay single-sector."""

    text = re.sub(r"\s+", "", str(query or "").strip())
    occupied: list[tuple[int, int]] = []
    found: list[DisclosureBucket] = []

    def _take(term: str, start: int, end: int) -> bool:
        if any(not (end <= left or start >= right) for left, right in occupied):
            return False
        occupied.append((start, end))
        return True

    for alias, sectors in ALIAS_BUCKETS.items():
        start = 0
        while True:
            index = text.find(alias, start)
            if index < 0:
                break
            end = index + len(alias)
            if _left_ok(text, index) and _take(alias, index, end):
                found.append(
                    DisclosureBucket(
                        name=alias,
                        sector_names=sectors,
                        universe_size=0,
                        hit_codes=(),
                    )
                )
                break
            start = index + 1

    for name in sorted(SECTOR_NAME_CATALOG, key=len, reverse=True):
        start = 0
        while True:
            index = text.find(name, start)
            if index < 0:
                break
            end = index + len(name)
            if _left_ok(text, index) and _take(name, index, end):
                found.append(
                    DisclosureBucket(
                        name=name,
                        sector_names=(name,),
                        universe_size=0,
                        hit_codes=(),
                    )
                )
                break
            start = index + 1
    return tuple(found)


def classify_title(title: str) -> str:
    cleaned = strip_em(title)
    if _NEG_RE.search(cleaned):
        return "L_neg"
    if _REG_RE.search(cleaned) and "受理" not in cleaned:
        return "L_reg"
    if _IND_RE.search(cleaned):
        return "L_ind"
    if _COLLECT_RE.search(cleaned):
        return "L_collect"
    if _ORDER_RE.search(cleaned):
        return "L_order"
    if _BUYBACK_RE.search(cleaned):
        return "L_buyback"
    if _HOLD_RE.search(cleaned):
        return "L_hold"
    return "unclassified"


def strip_em(title: str) -> str:
    return _EM_RE.sub("", str(title or "")).strip()


def stock_code6(value: object) -> str | None:
    match = _CODE_RE.search(str(value or ""))
    return match.group(1) if match else None


def merge_disclosure_into_public_answer(
    text: str, pack: DisclosureScanPack | None
) -> str:
    """Empty/unsupported/error/partial receipts must still reach the public answer."""

    if pack is None:
        return text
    rendered = pack.render()
    body = text or ""
    if not rendered:
        return body
    if rendered in body:
        return body
    return f"{rendered}\n\n{body}".strip() if body else rendered


def disclosure_scan_degrade_codes(pack: DisclosureScanPack | None) -> tuple[str, ...]:
    if pack is None:
        return ()
    codes: list[str] = []
    if pack.status in {"empty", "unsupported", "error", "partial"}:
        codes.append(f"disclosure_scan_pack_{pack.status}")
    for bucket in pack.buckets:
        if bucket.universe_size > 0 and not bucket.hit_codes:
            codes.append(f"disclosure_scan_bucket_empty:{bucket.name}")
    return tuple(codes)


def _main_roster_incomplete(traces: list[KeywordTrace] | tuple[KeywordTrace, ...]) -> bool:
    """Appendix truncation is a footnote; only main-keyword cuts mean the roster did not finish."""

    for trace in traces:
        if trace.keyword not in MAIN_KEYWORDS:
            continue
        if trace.truncated or trace.status == "skipped_budget":
            return True
    return False


RESIDUAL_MAX_CHARS = 1600
RESIDUAL_TRUNCATION_NOTICE = "（残差超预算，已截断）"
# live 实测（run_20260825_200157_247884）：模型倾向逐行复述名单（20+ 个代码），
# 名单行正则（^\d{6} 【）挡不住不带档位括号的复述。归纳解读点名个股用不到 8 家。
RESIDUAL_MAX_DISTINCT_CODES = 8

DISCLOSURE_RESIDUAL_CONTRACT = (
    "本题为披露扫描题：个股名单由确定性扫描包给出，并会原样置顶在公开稿最前，"
    "你的输出只是名单后面的残差解读，不是名单本身。\n"
    "1. 只解释：各档含义（临床批件≠上市；合同/中选类标题未写金额则金额未知；"
    "回购/增持是资本运作备考，不计入经营性利好）、集采中选的量价双重性、"
    "反证行（负面/撤回）的含义、附录关键词预算截断的边界——"
    "不得把「未查完」说成「没有」。\n"
    "2. 禁止复述或改写名单：不得输出任何名单行（六位代码开头的行），"
    "不得逐行罗列名单内容；做归纳解读，点名个股不超过 8 家；"
    "不得提及扫描包之外的股票代码或公司，不得新增名单外的事实。\n"
    "3. 禁止买卖建议，禁止把「未计入比较利好」里的行升格为利好。\n"
    "4. 篇幅不超过 500 字，直接给解读正文，不要标题、不要重复名单。"
)

# 名单行形状：包渲染每行 `600276 【注册获批】…`。残差里出现这种行 = 模型在造第二份名单。
_RESIDUAL_ROSTER_LINE_RE = re.compile(r"(?m)^\s*\d{6}\s*【")
# 边界感知的六位码：公告 ID（10 位）和纯数字长串的内嵌六位不算。
_RESIDUAL_CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")


@dataclass(frozen=True)
class ResidualGateResult:
    text: str
    dropped: bool
    reason: str | None = None
    detail: str | None = None


def disclosure_residual_allowed(pack: DisclosureScanPack | None) -> bool:
    """残差只在主名单齐且非空时上场；partial/empty/unsupported/error 维持 P0 纯包。"""

    return pack is not None and pack.status == "hit" and bool(pack.rows)


def gate_disclosure_residual(
    body: str, pack: DisclosureScanPack
) -> ResidualGateResult:
    """出稿闸：包外码 / 名单行形状 → 整段丢弃（fail-closed），超预算 → 声明式截断。

    为什么整丢不逐句删：逐句删会留下指代断裂的残句，而残差整段的价值密度
    不足以值得句级修复；回 P0 纯包形状是已验证的安全态。
    """

    text = (body or "").strip()
    if not text:
        return ResidualGateResult("", dropped=False)
    allowed = {
        row.code for row in (*pack.rows, *pack.excluded, *pack.counter_rows)
    }
    mentioned = set(_RESIDUAL_CODE_RE.findall(text))
    unknown = sorted(mentioned - allowed)
    if unknown:
        return ResidualGateResult(
            "", dropped=True, reason="unknown_code", detail=unknown[0]
        )
    if _RESIDUAL_ROSTER_LINE_RE.search(text):
        return ResidualGateResult("", dropped=True, reason="roster_line")
    if len(mentioned) > RESIDUAL_MAX_DISTINCT_CODES:
        return ResidualGateResult(
            "",
            dropped=True,
            reason="roster_renarration",
            detail=str(len(mentioned)),
        )
    if len(text) > RESIDUAL_MAX_CHARS:
        return ResidualGateResult(
            text[:RESIDUAL_MAX_CHARS].rstrip() + "\n" + RESIDUAL_TRUNCATION_NOTICE,
            dropped=False,
            reason="truncated",
        )
    return ResidualGateResult(text, dropped=False)


# 巨潮标题扫描是官方披露（L3 级）：tier 以 "l3" 开头让 claim 过硬证据判定
# （is_hard_evidence_tier），措辞不被确定性治理软化，registry 排序也吃 L3 加分。
DISCLOSURE_EVIDENCE_ID = "L3-DISC"
DISCLOSURE_EVIDENCE_TIER = "l3_official_disclosure"
_DISCLOSURE_THEME = "披露扫描"

# 进 shadow 链 build_grounded_composer_messages 的 required_outputs 槽——
# 这是 grounded composer 唯一看得见的本轮契约位。P1-① 把契约放在
# prepared_synthesis_messages 里，而 shadow 链的输入完全从 answer_spec 生成，
# 模型从没见过残差约束（live R5 m 轮逐行复述 20+ 码的直接原因之一）。
DISCLOSURE_RESIDUAL_PROMPT_CONSTRAINTS: tuple[str, ...] = (
    "档位解读：解释主名单各档的含义边界"
    "（临床批件≠上市；合同/中选类标题未写金额则金额未知）",
    "排除与反证：说明「未计入比较利好」各档"
    "（回购/增持为资本运作备考、集采中选量价对冲、未分类）为何排除；"
    "有反证行时点明其含义",
    "查询边界：预算截断的关键词按「未查完」说明，不得表述为「没有」；"
    "全部跑完时说明查询窗口与宇宙即可",
    "输出形态：名单已由扫描包原样置顶，不要逐行复述名单，"
    "不要输出六位代码开头的名单行；归纳解读点名个股不超过 8 家，"
    "总篇幅不超过 500 字，不给买卖建议",
)


def _residual_row_claim(
    row: DisclosureRow,
    *,
    kind: str,
    index: int,
) -> "answer_model.Claim":
    from intelligence.services import answer_model

    label = TIER_LABELS.get(row.tier, row.tier)
    if kind == "counter":
        body = f"反证——{label}：《{row.title}》"
    elif kind == "excl":
        body = f"未计入比较利好——{label}：《{row.title}》"
    else:
        body = f"{label}：《{row.title}》"
    # 名称在前、代码进括号：即使模型贴着 claim 文本复述，也不会拼出
    # 出稿闸的名单行形状（^六位代码 【…）。
    return answer_model.make_claim(
        claim_id=f"disc:{kind}:{row.code}:{row.announcement_id or index}",
        text=f"{row.name}（{row.code}）{row.date} {body}",
        claim_type="supporting_fact" if kind != "counter" else "counter_evidence",
        theme=_DISCLOSURE_THEME,
        status=answer_model.ClaimStatus.VERIFIED,
        evidence_tier=DISCLOSURE_EVIDENCE_TIER,
        evidence_ids=(DISCLOSURE_EVIDENCE_ID,),
        company=row.name,
    )


def build_disclosure_residual_answer_spec(
    pack: DisclosureScanPack,
    *,
    query: str,
) -> "answer_model.AnswerSpec":
    """残差写手的全行 claim 集：主名单/排除/反证每行一条 + 聚合统计。

    通用 builder（``_build_base_answer_spec_from_sections``）把证据行截到
    8 条，对全名单解读题 claim 覆盖不足 = 有据校验必然越界（live R5 m 轮，
    ``run_20260825_200157_247884``）。扫描包是确定性事实源，每行都值得
    一条可绑定 claim；聚合 claim 给归纳句（「注册获批 N 行」）数字出处。
    """

    from intelligence.services import answer_model

    _ = query
    window = f"{pack.se_date_start}~{pack.se_date_end}"
    main_count = len(pack.rows)
    bucket_bits = "、".join(
        f"{bucket.name}命中 {len(bucket.hit_codes)} 家（宇宙 {bucket.universe_size} 只）"
        for bucket in pack.buckets
    )
    summary = (
        answer_model.make_claim(
            claim_id="disc:summary:1",
            text=(
                f"窗口 {window} 官方披露扫描：主名单 {main_count} 行，{bucket_bits}；"
                "名单已由扫描包原样置顶，本段只做残差解读。"
            ),
            claim_type="summary",
            theme=_DISCLOSURE_THEME,
            status=answer_model.ClaimStatus.VERIFIED,
            evidence_tier=DISCLOSURE_EVIDENCE_TIER,
            evidence_ids=(DISCLOSURE_EVIDENCE_ID,),
        ),
    )

    facts: list[answer_model.Claim] = []
    tier_counts: dict[str, int] = {}
    for row in pack.rows:
        tier_counts[row.tier] = tier_counts.get(row.tier, 0) + 1
    tier_bits = "、".join(
        f"{TIER_LABELS.get(tier, tier)} {count} 行"
        for tier, count in tier_counts.items()
    )
    if tier_bits:
        facts.append(
            answer_model.make_claim(
                claim_id="disc:agg:tiers",
                text=f"主名单共 {main_count} 行，分档：{tier_bits}。",
                claim_type="supporting_fact",
                theme=_DISCLOSURE_THEME,
                status=answer_model.ClaimStatus.VERIFIED,
                evidence_tier=DISCLOSURE_EVIDENCE_TIER,
                evidence_ids=(DISCLOSURE_EVIDENCE_ID,),
            )
        )
    if pack.excluded:
        excluded_counts: dict[str, int] = {}
        for row in pack.excluded:
            excluded_counts[row.tier] = excluded_counts.get(row.tier, 0) + 1
        excluded_bits = "、".join(
            f"{TIER_LABELS.get(tier, tier)} {count} 行"
            for tier, count in excluded_counts.items()
        )
        facts.append(
            answer_model.make_claim(
                claim_id="disc:agg:excluded",
                text=(
                    f"未计入比较利好共 {len(pack.excluded)} 行：{excluded_bits}。"
                ),
                claim_type="supporting_fact",
                theme=_DISCLOSURE_THEME,
                status=answer_model.ClaimStatus.VERIFIED,
                evidence_tier=DISCLOSURE_EVIDENCE_TIER,
                evidence_ids=(DISCLOSURE_EVIDENCE_ID,),
            )
        )
    keyword_total = len(pack.keyword_traces)
    unfinished = tuple(
        trace.keyword
        for trace in pack.keyword_traces
        if trace.truncated or trace.status == "skipped_budget"
    )
    if keyword_total:
        budget_text = (
            f"关键词 {keyword_total} 个全部跑完。"
            if not unfinished
            else (
                f"关键词 {keyword_total} 个，其中 {len(unfinished)} 个未查完"
                f"（预算截断）：{'、'.join(unfinished)}。"
            )
        )
        facts.append(
            answer_model.make_claim(
                claim_id="disc:agg:keywords",
                text=budget_text,
                claim_type="supporting_fact",
                theme=_DISCLOSURE_THEME,
                status=answer_model.ClaimStatus.VERIFIED,
                evidence_tier=DISCLOSURE_EVIDENCE_TIER,
                evidence_ids=(DISCLOSURE_EVIDENCE_ID,),
            )
        )
    facts.append(
        answer_model.make_claim(
            claim_id="disc:agg:window",
            text=(
                f"公告窗口 {window}，成分股站立日 "
                f"{pack.universe_date or pack.as_of}（trade_date ≤ {pack.as_of}）。"
            ),
            claim_type="supporting_fact",
            theme=_DISCLOSURE_THEME,
            status=answer_model.ClaimStatus.VERIFIED,
            evidence_tier=DISCLOSURE_EVIDENCE_TIER,
            evidence_ids=(DISCLOSURE_EVIDENCE_ID,),
        )
    )
    for index, row in enumerate(pack.rows, start=1):
        facts.append(_residual_row_claim(row, kind="row", index=index))
    for index, row in enumerate(pack.excluded, start=1):
        facts.append(_residual_row_claim(row, kind="excl", index=index))

    counter_claims = tuple(
        _residual_row_claim(row, kind="counter", index=index)
        for index, row in enumerate(pack.counter_rows, start=1)
    )

    gap_claims: list[answer_model.Claim] = []
    if unfinished:
        gap_claims.append(
            answer_model.make_claim(
                claim_id="disc:gap:budget",
                text=(
                    "关键词未查完（预算截断）："
                    f"{'、'.join(unfinished)}；这些词的覆盖情况未知，"
                    "不得当作「没有」。"
                ),
                claim_type="evidence_gap",
                theme=_DISCLOSURE_THEME,
                status=answer_model.ClaimStatus.MISSING,
            )
        )
    for bucket in pack.buckets:
        if bucket.universe_size > 0 and not bucket.hit_codes:
            gap_claims.append(
                answer_model.make_claim(
                    claim_id=f"disc:gap:bucket:{bucket.name}",
                    text=(
                        f"{bucket.name}桶窗口内主名单零命中"
                        f"（宇宙 {bucket.universe_size} 只）。"
                    ),
                    claim_type="evidence_gap",
                    theme=_DISCLOSURE_THEME,
                    status=answer_model.ClaimStatus.MISSING,
                )
            )

    triggers = (
        answer_model.make_claim(
            claim_id="disc:trigger:1",
            text=(
                "本扫描为标题级：金额、品种、进度等正文细节"
                "以巨潮公告原文为准。"
            ),
            claim_type="condition_boundary",
            theme=_DISCLOSURE_THEME,
            status=answer_model.ClaimStatus.INFERRED,
            evidence_tier=DISCLOSURE_EVIDENCE_TIER,
            evidence_ids=(DISCLOSURE_EVIDENCE_ID,),
        ),
    )

    spec = answer_model.AnswerSpec(
        research_spec=answer_model.ThemeResearchSpec(
            theme=_DISCLOSURE_THEME,
            pack_id="disclosure_scan_pack",
            definition="板块宇宙 ∩ 巨潮标题 ∩ 档位分层的确定性名单扫描",
            chain_stages=(),
            company_scope="",
            as_of=pack.universe_date or pack.as_of,
            evidence_requirements=(),
            counter_evidence_requirements=(),
            trigger_conditions=(),
            verification_actions=("以巨潮公告原文核对标题级结论",),
            focus_entities=(),
            requested_sections=(),
        ),
        summary=summary,
        verified_facts=tuple(facts),
        company_table=(),
        counter_evidence=counter_claims,
        gaps=tuple(gap_claims),
        triggers=triggers,
        next_actions=(),
        sources=(
            answer_model.EvidenceRef(
                evidence_id=DISCLOSURE_EVIDENCE_ID,
                source="巨潮资讯公告标题扫描（确定性扫描包）",
                detail=(
                    f"窗口 {window}；宇宙站立日 {pack.universe_date or pack.as_of}；"
                    f"主名单 {main_count} 行"
                ),
                tier=DISCLOSURE_EVIDENCE_TIER,
                source_date=pack.se_date_end,
            ),
        ),
        system_notices=(),
        prompt_constraints=DISCLOSURE_RESIDUAL_PROMPT_CONSTRAINTS,
        presentation_kind="base_finance",
        presentation_title="披露扫描残差解读",
    )
    return answer_model.finalize_answer_spec(spec)


def default_cninfo_fetch(
    *,
    keyword: str,
    se_date: str,
    page_num: int,
    page_size: int = PAGE_SIZE,
    column: str = CNINFO_COLUMN,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> CninfoPage:
    payload = urllib.parse.urlencode(
        {
            "pageNum": str(page_num),
            "pageSize": str(page_size),
            "column": column,
            "tabName": "fulltext",
            "plate": "",
            "stock": "",
            "searchkey": keyword,
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": se_date,
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        CNINFO_URL,
        data=payload,
        method="POST",
        headers={
            "User-Agent": "Mozilla/5.0 finance-workbench-disclosure-scan",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": CNINFO_REFERER,
            "Origin": "https://www.cninfo.com.cn",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return CninfoPage((), 0, error=type(exc).__name__)
    announcements = tuple(raw.get("announcements") or ())
    total = raw.get("totalAnnouncement")
    if not isinstance(total, int):
        total = len(announcements)
    return CninfoPage(announcements, total)


def run_disclosure_scan_pack(
    query: str,
    *,
    as_of: str | None = None,
    market_db_path: str | Path | None = None,
    cninfo_fetch: CninfoFetch | None = None,
    clock: Callable[[], float] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> DisclosureScanPack:
    started = (clock or time.monotonic)()
    as_of_date = _resolve_as_of(as_of)
    se_start, se_end = _window_for_query(query, as_of_date)
    buckets = parse_disclosure_buckets(query)
    warnings: list[str] = []
    fetch = cninfo_fetch or default_cninfo_fetch
    nap = sleep_fn or time.sleep
    tick = clock or time.monotonic

    if not buckets:
        return _finish(
            status="unsupported",
            query_as_of=as_of_date,
            universe_date=None,
            se_start=se_start,
            se_end=se_end,
            started=started,
            clock=tick,
            buckets=(),
            rows=(),
            excluded=(),
            counter_rows=(),
            traces=(),
            warnings=("未指定板块，本扫描不做全市场",),
            budget_hit=False,
        )

    con = _connect(market_db_path)
    if con is None:
        return _finish(
            status="unsupported",
            query_as_of=as_of_date,
            universe_date=None,
            se_start=se_start,
            se_end=se_end,
            started=started,
            clock=tick,
            buckets=tuple(
                replace_bucket(bucket, universe_size=0) for bucket in buckets
            ),
            rows=(),
            excluded=(),
            counter_rows=(),
            traces=(),
            warnings=("无可用成分股快照（市场库未连接）",),
            budget_hit=False,
        )

    universe_date = _universe_date(con, as_of_date)
    if universe_date is None:
        return _finish(
            status="unsupported",
            query_as_of=as_of_date,
            universe_date=None,
            se_start=se_start,
            se_end=se_end,
            started=started,
            clock=tick,
            buckets=tuple(
                replace_bucket(bucket, universe_size=0) for bucket in buckets
            ),
            rows=(),
            excluded=(),
            counter_rows=(),
            traces=(),
            warnings=("as_of 之前无成分股快照",),
            budget_hit=False,
        )

    membership, bucket_sizes = _load_universe(con, universe_date, buckets)
    sized_buckets = tuple(
        replace_bucket(bucket, universe_size=bucket_sizes.get(bucket.name, 0))
        for bucket in buckets
    )
    if not membership:
        return _finish(
            status="unsupported",
            query_as_of=as_of_date,
            universe_date=universe_date,
            se_start=se_start,
            se_end=se_end,
            started=started,
            clock=tick,
            buckets=sized_buckets,
            rows=(),
            excluded=(),
            counter_rows=(),
            traces=(),
            warnings=("点名板块在站立日没有成分股",),
            budget_hit=False,
        )

    se_date = f"{se_start}~{se_end}"
    traces: list[KeywordTrace] = []
    by_id: dict[str, dict[str, Any]] = {}
    budget_hit = False
    saw_request_error = False
    saw_success = False
    fetch_calls: list[dict[str, Any]] = []

    for index, keyword in enumerate(ALL_KEYWORDS):
        if tick() - started >= WALL_SECONDS:
            budget_hit = True
            traces.extend(
                KeywordTrace(kw, None, 0, 0, False, "skipped_budget")
                for kw in ALL_KEYWORDS[index:]
            )
            break
        trace, pages, calls = _fetch_keyword(
            fetch,
            keyword=keyword,
            se_date=se_date,
            started=started,
            clock=tick,
            sleep_fn=nap,
            prior_calls=len(fetch_calls),
        )
        traces.append(trace)
        fetch_calls.extend(calls)
        if trace.status == "request_error":
            saw_request_error = True
        if trace.status == "ok":
            saw_success = True
        if trace.truncated or trace.status == "skipped_budget":
            budget_hit = True
        for item in pages:
            announcement_id = str(item.get("announcementId") or "").strip()
            if announcement_id:
                by_id.setdefault(announcement_id, item)
        if tick() - started >= WALL_SECONDS:
            budget_hit = True
            remaining = ALL_KEYWORDS[index + 1 :]
            traces.extend(
                KeywordTrace(kw, None, 0, 0, False, "skipped_budget")
                for kw in remaining
            )
            break

    joined = _join_and_classify(by_id.values(), membership, sized_buckets)
    main_rows = tuple(row for row in joined if row.tier in MAIN_TIERS)
    excluded = tuple(row for row in joined if row.tier in EXCLUDED_TIERS)
    counter_rows = tuple(row for row in joined if row.tier == "L_neg")
    hit_by_bucket: dict[str, list[str]] = {bucket.name: [] for bucket in sized_buckets}
    for row in main_rows:
        for name in row.buckets:
            if name in hit_by_bucket and row.code not in hit_by_bucket[name]:
                hit_by_bucket[name].append(row.code)
    final_buckets = tuple(
        replace_bucket(bucket, hit_codes=tuple(hit_by_bucket.get(bucket.name, ())))
        for bucket in sized_buckets
    )
    if _main_roster_incomplete(traces):
        status = "partial"
    elif main_rows:
        status = "hit"
    elif saw_request_error and not saw_success and not joined:
        status = "error"
        warnings.append("巨潮请求失败，未拿到可 JOIN 的标题")
    else:
        status = "empty"
    return _finish(
        status=status,
        query_as_of=as_of_date,
        universe_date=universe_date,
        se_start=se_start,
        se_end=se_end,
        started=started,
        clock=tick,
        buckets=final_buckets,
        rows=main_rows,
        excluded=excluded,
        counter_rows=counter_rows,
        traces=tuple(traces),
        warnings=tuple(warnings),
        budget_hit=budget_hit,
        fetch_calls=tuple(fetch_calls),
    )


def render_disclosure_scan_pack(pack: DisclosureScanPack) -> str:
    lines: list[str] = []
    window = f"{pack.se_date_start}~{pack.se_date_end}"
    universe_bits = "、".join(
        f"{bucket.name}{bucket.universe_size}只" for bucket in pack.buckets
    ) or "0只"
    if pack.status == "unsupported":
        lines.append(
            "【扫描结论】未执行全市场扫描。"
            + ("；".join(pack.warnings) if pack.warnings else "未指定板块。")
        )
    elif pack.status == "error":
        lines.append("【扫描结论】巨潮查询失败，下面是收据，不是个股名单。")
    elif pack.status == "partial":
        lines.append(
            "【扫描结论】查询未跑完（预算），以下为已得行。"
            f"窗口 {window}，宇宙 {universe_bits}。"
        )
    elif pack.status == "empty":
        lines.append(
            f"【扫描结论】窗口 {window}、宇宙 {universe_bits} 没有可计入「比较利好」的官方披露。"
        )
    else:
        lines.append(
            f"【扫描结论】窗口 {window} 内，宇宙 {universe_bits} 扫到偏经营/注册类公告如下。"
        )
    for bucket in pack.buckets:
        lines.append(f"## {bucket.name}（成分股 {bucket.universe_size}）")
        bucket_rows = [row for row in pack.rows if bucket.name in row.buckets]
        if not bucket_rows:
            lines.append("本桶零命中。")
            continue
        for row in bucket_rows:
            lines.append(_format_row(row))
    if pack.excluded:
        lines.append("## 未计入比较利好")
        lines.extend(_format_excluded_public(pack.excluded))
    if pack.counter_rows:
        lines.append("## 反证")
        for row in pack.counter_rows:
            lines.append(_format_row(row))
    skipped = [
        trace.keyword
        for trace in pack.keyword_traces
        if trace.status == "skipped_budget"
    ]
    if skipped:
        lines.append(
            "附录词未查完（预算截断，不得把没查说成没有）：" + "、".join(skipped)
        )
    if pack.budget_hit:
        lines.append("墙钟或页帽预算命中，未查完的关键词见收据，不得把没查说成没有。")
    traces = [
        f"{trace.keyword}:{trace.status}:{trace.pages_fetched}页/{trace.page_rows}行"
        + ("/截断" if trace.truncated else "")
        for trace in pack.keyword_traces
    ]
    if traces:
        lines.append("关键词收据：" + "；".join(traces))
    if pack.universe_date:
        lines.append(f"成分股站立日 {pack.universe_date}（trade_date ≤ {pack.as_of}）。")
    return "\n".join(lines).strip()


def _format_row(row: DisclosureRow) -> str:
    label = TIER_LABELS.get(row.tier, row.tier)
    link = row.url or _announcement_url(row.code, row.announcement_id, row.org_id)
    return (
        f"{row.code} 【{label}】{row.name} {row.date} {row.title}"
        f" （{row.announcement_id}） {link}"
    )


def _format_excluded_public(rows: tuple[DisclosureRow, ...]) -> list[str]:
    lines: list[str] = []
    by_tier: dict[str, list[DisclosureRow]] = {}
    order: list[str] = []
    for row in rows:
        if row.tier not in by_tier:
            order.append(row.tier)
            by_tier[row.tier] = []
        by_tier[row.tier].append(row)
    for tier in order:
        group = by_tier[tier]
        for row in group[:EXCLUDED_PUBLIC_CAP]:
            lines.append(_format_row(row))
        extra = len(group) - EXCLUDED_PUBLIC_CAP
        if extra > 0:
            label = TIER_LABELS.get(tier, tier)
            lines.append(f"另 {extra} 条{label}见扫描收据，未逐条列入公开稿。")
    return lines


def _row_to_dict(row: DisclosureRow) -> dict[str, Any]:
    return {
        "code": row.code,
        "name": row.name,
        "date": row.date,
        "title": row.title,
        "tier": row.tier,
        "announcement_id": row.announcement_id,
        "org_id": row.org_id,
        "url": row.url,
        "buckets": list(row.buckets),
    }


def _left_ok(text: str, index: int) -> bool:
    if index == 0:
        return True
    left = text[index - 1]
    return left in "和与、,，/+" or not _CJK_CHAR_RE.match(left)


def _resolve_as_of(as_of: str | None) -> str:
    text = str(as_of or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()


def _window_for_query(query: str, as_of: str) -> tuple[str, str]:
    end = date.fromisoformat(as_of)
    text = re.sub(r"\s+", "", str(query or ""))
    if _TODAY_WINDOW_RE.search(text) and not _WEEK_WINDOW_RE.search(text):
        start = end
    elif _WEEK_WINDOW_RE.search(text):
        start = end - timedelta(days=WEEK_WINDOW_DAYS)
    else:
        start = end - timedelta(days=DEFAULT_WINDOW_DAYS)
    return start.isoformat(), end.isoformat()


def _connect(market_db_path: str | Path | None):
    if not market_db_path:
        return None
    path = Path(market_db_path).expanduser()
    if not path.exists():
        return None
    opened = retrieval_cache.try_connect_readonly(path)
    if opened is None or not opened.available:
        return None
    return opened.connection


def _has_relation(con: Any, name: str) -> bool:
    row = con.execute(
        """
        select 1 from information_schema.tables
        where table_schema = 'main' and table_name = ?
        """,
        [name],
    ).fetchone()
    return row is not None


def _universe_date(con: Any, as_of: str) -> str | None:
    if not _has_relation(con, "fact_sector_stock_daily"):
        return None
    row = con.execute(
        """
        select max(trade_date)::VARCHAR
        from fact_sector_stock_daily
        where cast(trade_date as date) <= cast(? as date)
        """,
        [as_of],
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return str(row[0])[:10]


def _load_universe(
    con: Any,
    universe_date: str,
    buckets: tuple[DisclosureBucket, ...],
) -> tuple[dict[str, tuple[str, tuple[str, ...]]], dict[str, int]]:
    sector_names = tuple(
        dict.fromkeys(name for bucket in buckets for name in bucket.sector_names)
    )
    placeholders = ", ".join("?" for _ in sector_names)
    rows = con.execute(
        f"""
        select stock_ts_code, stock_name, sector_name
        from fact_sector_stock_daily
        where cast(trade_date as date) = cast(? as date)
          and sector_name in ({placeholders})
        """,
        [universe_date, *sector_names],
    ).fetchall()
    membership: dict[str, tuple[str, tuple[str, ...]]] = {}
    bucket_codes: dict[str, set[str]] = {bucket.name: set() for bucket in buckets}
    sector_to_buckets = {
        sector: tuple(
            bucket.name for bucket in buckets if sector in bucket.sector_names
        )
        for sector in sector_names
    }
    for ts_code, stock_name, sector_name in rows:
        code = stock_code6(ts_code)
        if code is None:
            continue
        names = sector_to_buckets.get(str(sector_name), ())
        if not names:
            continue
        current = membership.get(code)
        merged = tuple(dict.fromkeys((*(current[1] if current else ()), *names)))
        membership[code] = (str(stock_name or ""), merged)
        for name in names:
            bucket_codes[name].add(code)
    sizes = {name: len(codes) for name, codes in bucket_codes.items()}
    return membership, sizes


def replace_bucket(
    bucket: DisclosureBucket,
    *,
    universe_size: int | None = None,
    hit_codes: tuple[str, ...] | None = None,
) -> DisclosureBucket:
    return DisclosureBucket(
        name=bucket.name,
        sector_names=bucket.sector_names,
        universe_size=bucket.universe_size if universe_size is None else universe_size,
        hit_codes=bucket.hit_codes if hit_codes is None else hit_codes,
    )


def _fetch_keyword(
    fetch: CninfoFetch,
    *,
    keyword: str,
    se_date: str,
    started: float,
    clock: Callable[[], float],
    sleep_fn: Callable[[float], None],
    prior_calls: int,
) -> tuple[KeywordTrace, list[dict[str, Any]], list[dict[str, Any]]]:
    pages: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    total = 0
    truncated = False
    for page_num in range(1, MAX_PAGES + 1):
        if clock() - started >= WALL_SECONDS:
            truncated = True
            return (
                KeywordTrace(
                    keyword, total or None, page_num - 1, len(pages), True, "skipped_budget"
                ),
                pages,
                calls,
            )
        if prior_calls + len(calls) > 0:
            sleep_fn(REQUEST_GAP_SECONDS)
        page = fetch(
            keyword=keyword,
            se_date=se_date,
            page_num=page_num,
            page_size=PAGE_SIZE,
            column=CNINFO_COLUMN,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        calls.append(
            {
                "keyword": keyword,
                "page_num": page_num,
                "column": CNINFO_COLUMN,
                "se_date": se_date,
            }
        )
        if page.error:
            return (
                KeywordTrace(
                    keyword,
                    total or None,
                    page_num - 1,
                    len(pages),
                    truncated,
                    "request_error",
                    page.error,
                ),
                pages,
                calls,
            )
        total = page.total_announcement
        pages.extend(page.announcements)
        if len(page.announcements) < PAGE_SIZE or len(pages) >= total:
            break
        if page_num == MAX_PAGES and total > MAX_PAGES * PAGE_SIZE:
            truncated = True
            break
    return (
        KeywordTrace(keyword, total, len(calls), len(pages), truncated, "ok"),
        pages,
        calls,
    )


def _join_and_classify(
    announcements: Any,
    membership: dict[str, tuple[str, tuple[str, ...]]],
    buckets: tuple[DisclosureBucket, ...],
) -> tuple[DisclosureRow, ...]:
    _ = buckets
    rows: list[DisclosureRow] = []
    seen: set[tuple[str, str]] = set()
    for item in announcements:
        code = stock_code6(item.get("secCode") or item.get("stock") or "")
        announcement_id = str(item.get("announcementId") or "").strip()
        if code is None or not announcement_id:
            continue
        member = membership.get(code)
        if member is None:
            continue
        key = (code, announcement_id)
        if key in seen:
            continue
        seen.add(key)
        name, row_buckets = member
        title = strip_em(str(item.get("announcementTitle") or ""))
        org_id = str(item.get("orgId") or "")
        rows.append(
            DisclosureRow(
                code=code,
                name=str(item.get("secName") or name),
                date=_announcement_date(item.get("announcementTime")),
                title=title,
                tier=classify_title(title),
                announcement_id=announcement_id,
                org_id=org_id,
                url=_announcement_url(code, announcement_id, org_id),
                buckets=row_buckets,
            )
        )
    return tuple(rows)


def _announcement_date(value: object) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(
            value / 1000, tz=ZoneInfo("Asia/Shanghai")
        ).strftime("%Y-%m-%d")
    text = str(value or "").strip()
    return text[:10] if text else ""


def _announcement_url(code: str, announcement_id: str, org_id: str) -> str:
    query = urllib.parse.urlencode(
        {
            "stockCode": code,
            "announcementId": announcement_id,
            "orgId": org_id,
        }
    )
    return f"https://www.cninfo.com.cn/new/disclosure/detail?{query}"


def _finish(
    *,
    status: str,
    query_as_of: str,
    universe_date: str | None,
    se_start: str,
    se_end: str,
    started: float,
    clock: Callable[[], float],
    buckets: tuple[DisclosureBucket, ...],
    rows: tuple[DisclosureRow, ...],
    excluded: tuple[DisclosureRow, ...],
    counter_rows: tuple[DisclosureRow, ...],
    traces: tuple[KeywordTrace, ...] | list[KeywordTrace],
    warnings: tuple[str, ...] | list[str],
    budget_hit: bool,
    fetch_calls: tuple[dict[str, Any], ...] = (),
) -> DisclosureScanPack:
    elapsed_ms = max(0, int((clock() - started) * 1000))
    return DisclosureScanPack(
        status=status,
        as_of=query_as_of,
        universe_date=universe_date,
        se_date_start=se_start,
        se_date_end=se_end,
        elapsed_ms=elapsed_ms,
        budget_hit=budget_hit,
        buckets=buckets,
        rows=rows,
        excluded=excluded,
        counter_rows=counter_rows,
        keyword_traces=tuple(traces),
        warnings=tuple(warnings),
        fetch_calls=fetch_calls,
    )
