"""最终交付门：公开正文必须自带实质内容，不能是指向别处的指引。

为什么需要这道门（2026-09-22 现场）：连续研究（Engine A）一轮真实运行里，
模型在 ``model_turn`` 的自由文本里写完了 2518 字的完整答案，却把结构化
``finish`` 的 ``draft`` 字段填成了一句**指针**——``见正文：反弹第1天+……``。
运行时把 ``draft`` 当作用户可见答案，于是：

* 用户实际收到 154 字，``report.modules == 0``；
* 77 条证据全部绑定、结构核验与语义判官双双 ``passed``；
* 唯一记下异常的 ``answer_marker_coverage`` 带着 ``observation_only: True``，
  按设计**不可阻断**交付。

结构性证据完整 ≠ 正文里真的说了那句话。这道门只回答后一个问题，且是确定性的
（无模型调用、无 IO）。

## 判据为什么是「双钥匙」

不能把「缺少某个固定关键词」直接升级成硬拦截：``task_fulfillment._MARKERS``
是子串词表，用自然段落写法、标题措辞不同但内容完整的答案会被误伤（08-01 验收
C5 就出过：24 条证据全绑定，只因 ``counterpoint`` 少一个标记词，整篇被换成缺口
模板）。所以除「正文实质为空」这一种无可争议的形状外，降级一律要求**两把
独立的钥匙同时插上**：

* 钥匙 1（形态）：正文是**悬空指针**——自称内容在别处（``见正文`` /
  ``如上所述``）；
* 钥匙 2（覆盖）：确实有必需输出没进正文（marker 可检时看 marker；判断槽无
  词表时看 ``answer_has_non_boundary_substance``）。

单独命中钥匙 2 一律放行——那正是「措辞不同但内容完整」的形状。正文长度也不是
钥匙：它只是「marker 缺失」的先验，单独用它降级等于绕过同一条约束（见
``_CHARS_PER_REQUIRED_OUTPUT`` 处的当场拍红记录）。

## 与既有件的关系

* 词表只有一处真源：``task_fulfillment.evaluate_marker_coverage``（两个引擎共用
  的同一个定义），本模块不另立第二张表。
* 缺口模板只有在没有输出契约时豁免；一旦本轮声明了必需输出，它就是可观测的
  未完成交付，必须进入降级状态并允许运行时做一次有界修复，不能把模板当答案。
* 落点走既有 ``answer_status`` 通道（``complete_report`` 取
  ``research_status`` 与 ``answer_status`` 里更差的那个），不新增终态类型。
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Sequence

from intelligence.services.task_fulfillment import (
    answer_is_gap_template,
    evaluate_marker_coverage,
)

# 正文实质字符的绝对下限。这是唯一不要求第二把钥匙的规则，所以它只能声称一件
# 毫无争议的事：实质字符不到 8 个就不是一份答案（``见正文。`` 是 4 个）。
#
# ⚠ 第一版定在 24，当场拍红 ``test_workbench_research_project``：那份夹具的
# 答案「**第1轮判断：光模块主线延续。**\n证据见公告。」只有 16 个实质字符。
# 休市罐头、极短事实题同形：一条**不需要第二把钥匙**的规则只要有一点含糊，
# 就会把短而诚实的答案一起判死。体量分布落在 ``substance_chars`` 里留待度量。
_MIN_DELIVERABLE_CHARS = 8

# 每个必需输出撑得起的正文体量下限。
#
# ⚠ 它**不是**一把独立的钥匙，只在正文已经以悬空指引开场时做第二重印证。
# 第一版把「体量不足 + marker 缺失」当成可降级组合，当场拍红四条既有编排器
# 测试：「2026Q2 单季营收 375.75 亿元」「反弹持续性取决于量能与领涨扩散……」
# 这类短而完整的答案全部被降级。长度只是「marker 缺失」的先验，把它当钥匙
# 等于绕过了「缺措辞不得硬拦」这条约束。体量分布仍落在收据的
# ``substance_chars`` 里，等数据够了再谈要不要升级——先量后改。
_CHARS_PER_REQUIRED_OUTPUT = 40

# 指向交付物**之外**的指引。「正文 / 原文 / 全文 / 完整版 / 附件」的所指不可能
# 是这份交付本身——公开答案就是正文，在正文里写「见正文」是自指空引用，与
# ``unresolved_evidence_ordinal``（引用了不在证据表里的 E 号）是同一种悬空引用。
_OUTSIDE_POINTER_RE = re.compile(
    r"(?:详见|参见|另见|见)\s*"
    r"(?:正文|原文|全文|完整(?:版|正文|分析|报告)|附件|附录)"
)

# 开头指代。正文中段的「如上所述」可能真在回指自己的上一段，只有当整份交付
# **以**回指开场时，被指的东西才必然在交付之外。
_OPENING_POINTER_RE = re.compile(
    r"^\s*(?:如上所述|如前所述|同上|"
    r"(?:详见|参见|另见|见)\s*(?:上文|前文|上述(?:分析|内容|判断)?|前述(?:分析|内容|判断)?))"
)

# 开头那句指针连同其冒号一起摘掉：这是信息保全的编辑（只删指引，不删结论），
# 与语义判官「删越界句、留硬事实」同一条纪律——不得把正文里唯一的实质内容
# 一起抹掉（2026-08-20 铝案的教训）。
_LEADING_POINTER_STRIP_RE = re.compile(
    r"^\s*(?:详见|参见|另见|见)\s*"
    r"(?:正文|原文|全文|完整(?:版|正文|分析|报告)|附件|附录)"
    r"\s*[：:，,、\-—–]*\s*"
)

_EVIDENCE_TAG_RE = re.compile(r"\[[Ee]\d{1,3}\]")
_NON_SUBSTANCE_RE = re.compile(
    r"[\s#*>`|~_\-—–\[\]()（）【】《》。，、；：;:,.!！?？\"'“”‘’]+"
)

_DISCLOSURE_PREFIX = "【交付自检】"

VERDICT_OK = "ok"
VERDICT_INCOMPLETE = "incomplete"
VERDICT_EMPTY = "empty"

_ANSWER_STATUS_BY_VERDICT = {
    VERDICT_OK: None,
    VERDICT_INCOMPLETE: "partial",
    VERDICT_EMPTY: "missing",
}


@dataclass(frozen=True)
class PublicDeliveryReceipt:
    """一次最终交付自检的收据。``text`` 是应当真正发给用户的正文。"""

    verdict: str
    text: str
    answer_status: str | None
    missing_outputs: tuple[str, ...]
    dangling_pointers: tuple[str, ...]
    substance_chars: int
    required_output_count: int
    reasons: tuple[str, ...]

    @property
    def applied(self) -> bool:
        return self.verdict != VERDICT_OK

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict,
            "answer_status": self.answer_status,
            "missing_outputs": list(self.missing_outputs),
            "dangling_pointers": list(self.dangling_pointers),
            "substance_chars": self.substance_chars,
            "required_output_count": self.required_output_count,
            "reasons": list(self.reasons),
        }


def substance_chars(text: str) -> int:
    """正文里真正承载内容的字符数（去掉证据角标、空白与纯标点）。"""

    stripped = _EVIDENCE_TAG_RE.sub("", str(text or ""))
    return len(_NON_SUBSTANCE_RE.sub("", stripped))


def dangling_pointers(text: str) -> tuple[str, ...]:
    """返回正文里指向交付物之外的悬空指引原文片段。"""

    body = str(text or "")
    found: list[str] = []
    opening = _OPENING_POINTER_RE.search(body)
    if opening is not None:
        found.append(opening.group(0).strip())
    found.extend(match.group(0) for match in _OUTSIDE_POINTER_RE.finditer(body))
    return tuple(dict.fromkeys(item for item in found if item))


def opens_with_pointer(text: str) -> bool:
    """整份交付是不是**以**「内容在别处」开场。"""

    body = str(text or "").lstrip()
    return bool(
        _OPENING_POINTER_RE.match(body) or _LEADING_POINTER_STRIP_RE.match(body)
    )


def review_public_delivery(
    text: str,
    *,
    required_outputs: Sequence[str] = (),
    descriptions: Mapping[str, str] | None = None,
) -> PublicDeliveryReceipt:
    """交付前的确定性自检。不调模型、不做 IO、不重写结论。

    ``descriptions`` 是 ``output_id -> 中文描述`` 的映射，用于把缺口写成人话。
    调用方应当直接传本轮契约里的描述（唯一真源），取不到就退回裸 id，不在这里
    另抄一张表。
    """

    body = str(text or "")
    output_ids = tuple(
        dict.fromkeys(str(item).strip() for item in required_outputs if str(item).strip())
    )
    chars = substance_chars(body)
    reasons: list[str] = []

    # 只有**没有输出契约**的自由问答才允许缺口模板整篇豁免。
    # 一旦本轮声明了 required_outputs，缺口模板仍然要经过覆盖率与体量门：
    # 否则会出现模型根本没运行、必答项全缺，却因「证据不足」模板被标成 ok。
    if answer_is_gap_template(body):
        if not output_ids:
            return PublicDeliveryReceipt(
                verdict=VERDICT_OK,
                text=body,
                answer_status=None,
                missing_outputs=(),
                dangling_pointers=(),
                substance_chars=chars,
                required_output_count=0,
                reasons=("gap_template_exempt",),
            )
        return PublicDeliveryReceipt(
            verdict=VERDICT_INCOMPLETE,
            text=body,
            answer_status="partial",
            missing_outputs=output_ids,
            dangling_pointers=(),
            substance_chars=chars,
            required_output_count=len(output_ids),
            reasons=("gap_template_with_required_outputs", "required_outputs_absent"),
        )

    coverage = evaluate_marker_coverage(output_ids, body)
    missing = tuple(str(item) for item in (coverage.get("absent") or ()))
    judgment_empty = "uncheckable_judgment_empty" in tuple(
        str(item) for item in (coverage.get("warnings") or ())
    )
    pointers = dangling_pointers(body)
    pointer_opening = opens_with_pointer(body)
    floor = _CHARS_PER_REQUIRED_OUTPUT * max(1, len(output_ids))
    below_floor = chars < floor
    coverage_gap = bool(missing) or judgment_empty

    verdict = VERDICT_OK
    if chars < _MIN_DELIVERABLE_CHARS:
        verdict = VERDICT_EMPTY
        reasons.append("no_substantive_body")
    elif pointer_opening and (coverage_gap or below_floor):
        # 正文自称「内容在别处」，而且确实没覆盖必需输出——正文没有随本轮送达。
        verdict = VERDICT_EMPTY
        reasons.append("opens_with_dangling_pointer")
    elif pointers and coverage_gap:
        verdict = VERDICT_INCOMPLETE
        reasons.append("dangling_pointer")
    elif judgment_empty:
        # 判断槽没有词表可检，正文又只剩证据边界 / 免责句：空壳出厂的既有形状。
        verdict = VERDICT_INCOMPLETE
        reasons.append("judgment_slot_empty")
    if verdict != VERDICT_OK and missing:
        reasons.append("required_outputs_absent")

    if verdict == VERDICT_OK:
        return PublicDeliveryReceipt(
            verdict=VERDICT_OK,
            text=body,
            answer_status=None,
            missing_outputs=missing,
            dangling_pointers=pointers,
            substance_chars=chars,
            required_output_count=len(output_ids),
            reasons=tuple(reasons),
        )

    projected = _strip_leading_pointer(body)
    projected = _with_disclosure(
        projected,
        verdict=verdict,
        missing=missing,
        descriptions=descriptions,
    )
    return PublicDeliveryReceipt(
        verdict=verdict,
        text=projected,
        answer_status=_ANSWER_STATUS_BY_VERDICT[verdict],
        missing_outputs=missing,
        dangling_pointers=pointers,
        substance_chars=chars,
        required_output_count=len(output_ids),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _strip_leading_pointer(text: str) -> str:
    """摘掉开头那条悬空指引，保留它后面的全部内容。"""

    body = str(text or "")
    stripped = _LEADING_POINTER_STRIP_RE.sub("", body, count=1)
    if stripped == body:
        stripped = _OPENING_POINTER_RE.sub("", body, count=1).lstrip("：:，,、 ")
    return stripped.strip() or body.strip()


def _with_disclosure(
    text: str,
    *,
    verdict: str,
    missing: tuple[str, ...],
    descriptions: Mapping[str, str] | None,
) -> str:
    notice = _disclosure_text(verdict=verdict, missing=missing, descriptions=descriptions)
    if not notice or notice in text:
        return text
    return "\n\n".join(part for part in (text.strip(), notice) if part)


def _disclosure_text(
    *,
    verdict: str,
    missing: tuple[str, ...],
    descriptions: Mapping[str, str] | None,
) -> str:
    labels = _labels(missing, descriptions)
    slots = f"未进入正文的必需输出：{'、'.join(labels)}。" if labels else ""
    if verdict == VERDICT_EMPTY:
        return (
            f"{_DISCLOSURE_PREFIX}本轮完整正文未随交付送达，以上只是指向正文的"
            f"摘要或指引。{slots}本轮结论请按未完成处理。"
        )
    return (
        f"{_DISCLOSURE_PREFIX}本轮公开正文未覆盖全部必需输出。{slots}"
        "请据此判断可用范围，或追问补齐。"
    )


def _labels(
    output_ids: tuple[str, ...],
    descriptions: Mapping[str, str] | None,
) -> tuple[str, ...]:
    table = dict(descriptions or {})
    return tuple(
        dict.fromkeys(
            str(table.get(output_id) or output_id).strip()
            for output_id in output_ids
            if str(output_id).strip()
        )
    )


def contract_output_descriptions(contract: object) -> dict[str, str]:
    """从本轮契约（对象或 ``to_dict`` 后的字典）取 ``output_id -> 描述``。

    描述的真源是契约本身（``episode_factory._OUTPUT_DESCRIPTIONS`` 构造时写进去
    的那份）。这里只做读取，不维护第二张表——抄一份就等于让两边各自漂移。
    """

    if isinstance(contract, Mapping):
        items = contract.get("required_outputs") or ()
    else:
        items = getattr(contract, "required_outputs", ()) or ()
    table: dict[str, str] = {}
    for item in items:
        if isinstance(item, Mapping):
            output_id = str(item.get("output_id") or "").strip()
            description = str(item.get("description") or "").strip()
        else:
            output_id = str(getattr(item, "output_id", "") or "").strip()
            description = str(getattr(item, "description", "") or "").strip()
        if output_id and description:
            table[output_id] = description
    return table


__all__ = [
    "PublicDeliveryReceipt",
    "VERDICT_EMPTY",
    "VERDICT_INCOMPLETE",
    "VERDICT_OK",
    "contract_output_descriptions",
    "dangling_pointers",
    "opens_with_pointer",
    "review_public_delivery",
    "substance_chars",
]
