"""问答经验卡片：把一次回答评分压缩成下次可复用的思考规则。

经验卡片和知识库事实不同：它记录的是「以后该怎么回答/怎么检查」，不是公司或
产业的客观事实。因此默认放在 ``users/<id>/experience_cards.jsonl``，由问答链路按
问题相关性注入提示词。

生命周期：``candidate`` → ``promoted`` / ``methodology``（常驻注入）→
``promoted_to_code``（原则已进编排/契约/质检门，``load_cards`` 跳过）。
``invalidated`` 是另一条出口：教训被证伪，同样不注入。

统计门（2026-09-04，设计稿 methodology-backtest §3.4 P1）：卡若能映射到一条方法论规则
（``rule_id``），晋升到常驻 / 固化态的前置条件是该规则**最近一次回测收据为 ``supported``**；
标 ``invalidated`` 的前置条件是 ``refuted``。映射不到规则的卡走原流程——门只加在能被
历史数据检验的那部分上，不拦住经验本身。一次纠偏只能给事件集加一行，改不了收据结论，
所以也改不了一张卡的晋升资格；这就是「不能因为一次错误就否定一套方法」落在经验卡上的形状。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.eval.finance_answer_rubric import FinanceAnswerScore

DEFAULT_WINDOW = 12
RESIDENT_PROMOTIONS = frozenset({"promoted", "methodology"})
# 已固化进编排/契约/质检门的卡：留在 jsonl 可回放，但不再注入 prompt。
# 与 invalidated 不同——那些是错的；这些是对的，再喂一遍是重复供给。
ARCHIVED_PROMOTIONS = frozenset({"promoted_to_code"})
DEFAULT_RESIDENT_LIMIT = 5

# 带 rule_id 的卡：这些晋升态要求规则最近收据的四态结论 == 对应值。candidate 不设门。
GATED_PROMOTIONS: dict[str, str] = {
    "promoted": "supported",
    "methodology": "supported",
    "promoted_to_code": "supported",
}
INVALIDATION_REQUIRES = "refuted"


@dataclass(frozen=True)
class PromotionGate:
    allowed: bool
    reason: str
    rule_id: str | None
    verdict: str | None
    receipt: str | None


class PromotionGateError(ValueError):
    """晋升 / 失效请求没过统计门。带 ``gate`` 供调用方渲染原因。"""

    def __init__(self, gate: PromotionGate):
        self.gate = gate
        super().__init__(gate.reason)


def gate_promotion(
    promotion: str,
    *,
    rule_id: str | None,
    verdict: str | None,
    receipt: str | None = None,
    invalidated: bool = False,
) -> PromotionGate:
    """纯函数：给定卡要去的状态与规则最近收据的结论，判能不能去。

    ``verdict`` 为 None 表示该规则还没有任何收据——没有证据不等于支持，晋升一律拒；
    ``candidate`` 与无 ``rule_id`` 的卡永远放行。
    """
    rid = str(rule_id or "").strip() or None
    promo = str(promotion or "candidate").strip() or "candidate"
    if rid is None:
        return PromotionGate(True, "无 rule_id，走原流程（不经统计门）", None, verdict, receipt)
    if invalidated:
        if verdict == INVALIDATION_REQUIRES:
            return PromotionGate(True, f"规则 {rid} 最近收据为 {verdict}，允许标 invalidated", rid, verdict, receipt)
        return PromotionGate(
            False,
            f"规则 {rid} 最近收据为 {verdict or '无收据'}，不是 {INVALIDATION_REQUIRES}：一次落空不构成证伪，不能标 invalidated",
            rid,
            verdict,
            receipt,
        )
    required = GATED_PROMOTIONS.get(promo)
    if required is None:
        return PromotionGate(True, f"{promo} 不设统计门", rid, verdict, receipt)
    if verdict == required:
        return PromotionGate(True, f"规则 {rid} 最近收据为 {verdict}，允许晋升为 {promo}", rid, verdict, receipt)
    hint = "先跑 scripts/methodology_backtest.py run 出收据" if verdict is None else "只能以 candidate 落卡，等规则累积到 supported"
    return PromotionGate(
        False,
        f"规则 {rid} 最近收据为 {verdict or '无收据'}，不是 {required}：拒绝晋升为 {promo}；{hint}",
        rid,
        verdict,
        receipt,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "").lower())


def _clean_terms(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        s = str(value).strip()
        if not s:
            continue
        key = _norm(s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _query_intent_terms(query: str) -> set[str]:
    """把自然语言问题归一成可匹配经验卡片的意图词。

    经验卡片记录的是「回答行为」，用户问题里常出现的是股票名。
    例如「深挖汇成股份」不会字面命中「深挖裕太微」这张卡，所以这里
    补一层轻量意图映射。
    """
    text = str(query or "")
    terms: set[str] = set()
    if any(word in text for word in ["深挖", "怎么看", "分析一下", "研究一下"]):
        terms.update(["个股深挖", "第一性原理", "产业链分析", "二阶导", "市场结构推演路径"])
    if any(word in text for word in ["上涨空间", "还能涨", "还有空间"]):
        terms.update(["个股上涨空间判断", "上涨空间判断", "市场结构推演路径", "生命周期判断", "个股逻辑生命周期"])
    if any(word in text for word in ["科技", "题材", "方向", "细分"]):
        terms.update(["题材方向判断", "上涨空间判断", "双红题材", "市场风格"])
    if any(word in text for word in ["二阶导", "产业链", "暴露", "瓶颈"]):
        terms.update(["二阶导", "产业链分析", "产业链暴露", "第一性原理"])
    if any(word in text for word in ["双红", "MA5", "情绪", "生命周期"]):
        terms.update(["市场结构推演路径", "MA5情绪", "生命周期判断", "个股逻辑生命周期", "策略方法论"])
    if any(word in text for word in ["分析路径", "切入视角", "哪些视角", "固定了吗", "四个核心问题", "生命周期四问", "市场价值", "CAR", "半衰期"]):
        terms.update([
            "个股完整分析路径",
            "公司本体",
            "产业链暴露",
            "证据层",
            "高位主线反证",
            "大盘流动性",
            "市场风格",
            "行业容量",
            "题材结构",
            "个股相对强度",
            "逻辑生命周期四问",
            "市场价值成绩单",
            "二阶导",
            "条件化结论",
        ])
    if any(word in text for word in ["daily agent", "agent-daily", "盘面验证", "旧逻辑唤醒", "新逻辑候选", "升温验证", "加速定价"]):
        terms.update(["daily-agent底层逻辑", "逻辑-盘面匹配", "生命周期判断", "盘面验证", "研究队列"])
    if any(word in text for word in ["反向解读", "反证", "第一性原理", "底层方法论", "全量复盘数据", "市场选择"]):
        terms.update(["盘面反向解读", "第一性原理", "全量复盘映射", "市场真实选择", "强板块弱个股", "反证推导"])
    if any(word in text for word in ["质检", "检查通过", "反驳", "反问", "影子agent", "影子 agent", "模板化", "回答质量", "审稿"]):
        terms.update([
            "回答质检器",
            "用户影子反驳",
            "反方审稿",
            "第一性原理",
            "防模板化",
            "完整分析路径",
            "二阶导",
            "条件化结论",
        ])
    if any(word in text for word in ["申万", "周均线", "偏离度", "全量复盘", "涨停个股", "新高", "加权涨幅", "流动性"]):
        terms.update(["全量复盘映射", "申万一级映射", "周均线偏离度", "新高集群", "涨停结构", "个股流动性", "加权涨幅"])
    if any(word in text for word in ["客户证据", "收入结构", "业务结构", "财务结构", "板块生命周期", "强反证", "证据硬度表", "飞凯"]):
        terms.update([
            "客户证据硬度表",
            "收入结构",
            "财务传导",
            "板块生命周期",
            "强反证",
            "个股深挖",
            "证据层",
            "逻辑生命周期四问",
        ])
    if any(word in text for word in ["卖方", "晚间研报", "晚间卖方", "机构胜率", "胜率高", "研报发散", "覆盖密度", "T+5", "T+10"]):
        terms.update([
            "晚间卖方发散",
            "机构胜率",
            "覆盖密度",
            "证据硬度",
            "盘面位置",
            "二阶导",
            "产业瓶颈",
            "兑现风险",
        ])
    if any(word in text for word in ["高位主线", "AI硬件", "CPO", "PCB", "光模块", "半导体", "存储", "缩量", "拥挤", "兑现", "分歧", "事件锚点", "长鑫", "海力士", "玻璃桥"]):
        terms.update([
            "高位主线反证",
            "边际预期",
            "产业瑕疵审查",
            "事件锚点",
            "主线生命周期",
            "拥挤度",
            "缩量轮动",
            "顺势分歧",
            "第一性原理",
            "市场结构推演路径",
        ])
    return terms


def build_card_from_score(
    score: FinanceAnswerScore,
    *,
    answer: str | None = None,
    corrected_principle: str | None = None,
    applies_to: list[str] | None = None,
    prompt_rule: str | None = None,
    user_feedback: str | None = None,
    local_sources: list[str] | None = None,
    promotion: str = "candidate",
    ts: str | None = None,
    rule_id: str | None = None,
    rule_verdict: str | None = None,
    rule_receipt: str | None = None,
) -> dict[str, Any]:
    """从确定性评分结果生成一张机器可读经验卡片。

    给了 ``rule_id`` 就过统计门：``promoted / methodology / promoted_to_code`` 要求
    ``rule_verdict == "supported"``，否则抛 ``PromotionGateError``（不落卡）。卡上留
    ``rule_id / rule_verdict / rule_receipt`` 三个溯源字段。
    """
    gate = gate_promotion(promotion, rule_id=rule_id, verdict=rule_verdict, receipt=rule_receipt)
    if not gate.allowed:
        raise PromotionGateError(gate)
    weak_dims = [
        {
            "key": dim.key,
            "label": dim.label,
            "score": dim.score,
            "max_score": dim.max_score,
            "misses": list(dim.misses),
            "reason": dim.reason,
        }
        for dim in score.dimensions
        if dim.score < dim.max_score
    ]
    failure_modes = [
        f"{d['label']}：{'；'.join(d['misses']) if d['misses'] else d['reason']}"
        for d in weak_dims
        if d["score"] / d["max_score"] < 0.75
    ]
    strengths = [dim.label for dim in score.dimensions if dim.score == dim.max_score]
    card: dict[str, Any] = {
        "ts": ts or _now().isoformat(timespec="seconds"),
        "source": "answer-score",
        "question": score.question,
        "answer_score": score.total_score,
        "grade": score.grade,
        "failure_modes": failure_modes,
        "weak_dimensions": weak_dims,
        "strengths": strengths,
        "applies_to": _clean_terms(applies_to),
        "promotion": str(promotion or "candidate").strip() or "candidate",
        "local_sources": _clean_terms(local_sources),
    }
    if answer and str(answer).strip():
        card["answer_excerpt"] = str(answer).strip()[:800]
    if corrected_principle and str(corrected_principle).strip():
        card["corrected_principle"] = str(corrected_principle).strip()
    if prompt_rule and str(prompt_rule).strip():
        card["prompt_rule"] = str(prompt_rule).strip()
    if user_feedback and str(user_feedback).strip():
        card["user_feedback"] = str(user_feedback).strip()
    if gate.rule_id:
        card["rule_id"] = gate.rule_id
        card["rule_verdict"] = gate.verdict
        if gate.receipt:
            card["rule_receipt"] = gate.receipt
    return card


def record_card(path: str | Path, card: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    """Append 一张经验卡片到 JSONL。"""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(card, ensure_ascii=False) + "\n")
    return p, card


def load_cards(path: str | Path, window: int = DEFAULT_WINDOW) -> tuple[list[dict[str, Any]], str | None]:
    """读取最近 ``window`` 张经验卡片。文件不存在时返回空列表。

    带 ``invalidated`` 标记的卡片会被跳过，不参与召回和规则生成：教训一旦被证明
    来自坏指标（而非真实缺陷），继续喂进 prompt 就是在教系统去迎合那个坏指标。
    ``promotion=promoted_to_code`` 同样跳过：原则已固化进管线，再注入是重复供给。
    记录本身保留在 jsonl 里，便于回查「这条教训当时为什么被判为假 / 为何退役」。
    """
    p = Path(path).expanduser()
    if not p.exists():
        return [], None
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception as exc:  # pragma: no cover - defensive
        return [], f"经验卡片读取失败：{exc}"
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if not isinstance(obj, dict) or not str(obj.get("question") or "").strip():
            continue
        if obj.get("invalidated"):
            continue
        if str(obj.get("promotion") or "").strip() in ARCHIVED_PROMOTIONS:
            continue
        out.append(obj)
    if window and window > 0:
        out = out[-window:]
    return out, None


def select_relevant_cards(cards: list[dict[str, Any]], query: str, *, limit: int = 3) -> list[dict[str, Any]]:
    """按问题文本/适用场景的轻量关键词重合选择相关卡片。"""
    q = _norm(query)
    intent_terms = _query_intent_terms(query)
    terms = {t for t in re.split(r"[，,。；;、\s/]+", str(query)) if t}
    terms.update(intent_terms)

    def card_score(card: dict[str, Any]) -> tuple[int, str]:
        hay = _norm(
            " ".join(
                [
                    str(card.get("question") or ""),
                    " ".join(str(x) for x in card.get("applies_to") or []),
                    str(card.get("corrected_principle") or ""),
                    str(card.get("prompt_rule") or ""),
                ]
            )
        )
        score = 0
        if q and (q in hay or hay in q):
            score += 6
        for term in terms:
            nt = _norm(term)
            if nt and nt in hay:
                score += 3 if term in intent_terms else 2
        if card.get("promotion") in {"promoted", "methodology"}:
            score += 2
        if card.get("prompt_rule"):
            score += 1
        return score, str(card.get("ts") or "")

    ranked = [(card_score(card), card) for card in cards]
    ranked = [item for item in ranked if item[0][0] > 0 or len(cards) <= limit]
    ranked.sort(key=lambda item: (item[0][0], item[0][1]), reverse=True)
    return [card for _, card in ranked[:limit]]


def select_resident_cards(
    cards: list[dict[str, Any]],
    *,
    limit: int = DEFAULT_RESIDENT_LIMIT,
) -> list[dict[str, Any]]:
    """常驻概览：已晋升/方法论卡每次都带着，不靠本轮 query 命中。"""
    resident = [
        card
        for card in cards
        if str(card.get("promotion") or "").strip() in RESIDENT_PROMOTIONS
    ]
    resident.sort(key=lambda card: str(card.get("ts") or ""), reverse=True)
    return resident[: max(0, int(limit))]


def merge_cards_for_prompt(
    resident: list[dict[str, Any]],
    relevant: list[dict[str, Any]],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """常驻在前、相关在后，按 ts+question 去重。"""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for card in [*resident, *relevant]:
        key = f"{card.get('ts') or ''}|{card.get('question') or ''}"
        if key in seen:
            continue
        seen.add(key)
        out.append(card)
        if len(out) >= limit:
            break
    return out


def render_for_prompt(cards: list[dict[str, Any]]) -> str:
    """把经验卡片渲染成可注入 LLM 的简短规则块。"""
    lines: list[str] = []
    for card in cards:
        rule = str(card.get("prompt_rule") or card.get("corrected_principle") or "").strip()
        if not rule:
            failures = "；".join(str(x) for x in card.get("failure_modes") or [] if str(x).strip())
            if failures:
                rule = f"避免同类扣分：{failures}"
        if not rule:
            continue
        question = str(card.get("question") or "").strip()
        score = card.get("answer_score")
        prefix = f"「{question}」" if question else "经验卡片"
        tail = f"（历史得分 {score}）" if score is not None else ""
        lines.append(f"- {prefix}{tail}：{rule}")
    return "\n".join(lines)
