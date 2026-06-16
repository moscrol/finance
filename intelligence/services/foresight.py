"""猜你想问 / 潜意识 —— 主动追问问题生成器 (proactive question generation).

给定 (a) 已提交的「盘面现实」快照、(b) 用户关注画像、(c) 可选的实时情报，
生成 N 条用户「还没想到但最该问」的追问：二阶思维 / 跨领域 / 高度具体 /
前瞻且可证伪。这就是截图里那种「猜你想问」效果的可跑实现。

与 ``ask.py`` 同一套哲学：
- 现实锚定在已提交的 ``market_feature_store/exports/*-theme-candidates.json``
  快照上（不依赖 DuckDB、不依赖联网），所以离线即可运行。
- LLM 层可选且优雅降级：没有 key 时，只输出「上下文摘要 + 待发送提示词」，
  机制完全可审，命令仍正常返回（exit 0）。配上 key 后立即真正生成问题。
- 真实数据接线靠的是同仓已有的盘面快照；联网情报走可插拔的 ``--news-file``
  输入（把今天的财经日历 / 新闻贴进去即可），无则跳过。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path
from typing import Any

from intelligence.services import llm_refine
from intelligence.services.ask import load_theme_candidates

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = REPO_ROOT / "intelligence" / "foresight_profile.example.json"


@dataclass(frozen=True)
class ForesightOptions:
    profile: str | Path | None = None
    news_file: str | Path | None = None
    date: str | None = None
    exports_dir: str | Path | None = None
    kb_wiki: str | Path | None = None
    n: int = 3
    candidates: int = 8
    llm_model: str | None = None
    llm_timeout: int = 60
    temperature: float = 0.8


@dataclass
class Question:
    question: str
    rationale: str = ""
    domains: list[str] = field(default_factory=list)
    leading_indicator: str = ""
    horizon: str = ""
    novelty: float = 0.0
    relevance: float = 0.0
    score: float = 0.0


@dataclass
class ForesightResult:
    trade_date: str | None = None
    profile_name: str | None = None
    questions: list[Question] = field(default_factory=list)
    context_digest: list[str] = field(default_factory=list)
    prompt_preview: str = ""
    llm_used: bool = False
    llm_provider: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "PASS" if self.questions else "WARN"


# --------------------------------------------------------------------------- #
# 上下文层：把「它知道的一切」拼起来（盘面现实 + 画像 + 实时情报）
# --------------------------------------------------------------------------- #
def load_profile(path: str | Path | None) -> dict[str, Any]:
    p = Path(path).expanduser() if path else DEFAULT_PROFILE
    if not p.exists():
        return {"name": None, "_warning": f"画像文件不存在：{p}（用默认空画像）"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        return {"name": None, "_warning": f"画像解析失败：{exc}"}
    return data if isinstance(data, dict) else {"name": None, "_warning": "画像不是对象"}


def _read_text(path: str | Path | None) -> tuple[str, str | None]:
    if not path:
        return "", None
    p = Path(path).expanduser()
    if not p.exists():
        return "", f"情报文件不存在：{p}（已跳过实时情报层）"
    try:
        return p.read_text(encoding="utf-8").strip(), None
    except Exception as exc:  # pragma: no cover - defensive
        return "", f"情报读取失败：{exc}"


def _top_candidates(doc: dict[str, Any], n: int) -> list[dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    for key in ("deep_candidates", "watch_candidates", "candidates"):
        for c in doc.get(key, []) or []:
            if isinstance(c, dict):
                pool.append(c)
        if pool:
            break
    out: list[dict[str, Any]] = []
    for c in pool[:n]:
        companies = []
        for comp in (c.get("candidate_companies") or [])[:5]:
            if isinstance(comp, dict) and comp.get("company"):
                companies.append(str(comp.get("company")))
        out.append(
            {
                "theme": c.get("canonical_concept") or c.get("market_theme"),
                "tier": c.get("candidate_tier"),
                "score": c.get("priority_score"),
                "sw_l1": c.get("sw_l1"),
                "triggers": c.get("trigger_types") or [],
                "companies": companies,
            }
        )
    return out


def build_context(options: ForesightOptions) -> tuple[dict[str, Any], list[str], list[str]]:
    warnings: list[str] = []
    loaded = load_theme_candidates(options.exports_dir, options.date)
    doc = loaded["doc"] if loaded["found"] else {}
    if not loaded["found"]:
        warnings.extend(loaded.get("warnings", []))

    mc = doc.get("market_context") or {}
    caps = "、".join(
        f"{s.get('name')}({s.get('ratio')}%)"
        for s in (mc.get("capacity_sectors") or [])[:3]
        if isinstance(s, dict)
    )
    hot = _top_candidates(doc, 10)

    profile = load_profile(options.profile)
    if profile.get("_warning"):
        warnings.append(str(profile["_warning"]))

    intel, intel_warn = _read_text(options.news_file)
    if intel_warn:
        warnings.append(intel_warn)

    context = {
        "today": date_cls.today().isoformat(),
        "trade_date": doc.get("trade_date"),
        "market_context": {
            "market_stage": mc.get("market_stage"),
            "total_amount": mc.get("total_amount"),
            "advancers": mc.get("advancers"),
            "limit_up": mc.get("limit_up"),
            "limit_down": mc.get("limit_down"),
            "capacity_sectors": caps,
        },
        "signal_summary": doc.get("signal_summary"),
        "hot_candidates": hot,
        "profile": {
            "name": profile.get("name"),
            "style": profile.get("style"),
            "horizon": profile.get("horizon"),
            "focus_themes": profile.get("focus_themes") or [],
            "watchlist": profile.get("watchlist") or [],
            "recent_questions": profile.get("recent_questions") or [],
        },
        "realtime_intel": intel,
    }

    digest: list[str] = []
    digest.append(f"今天={context['today']}；盘面日期={context['trade_date'] or '—'}")
    if mc:
        digest.append(
            f"市场环境：{mc.get('market_stage') or '—'}，成交 {mc.get('total_amount')}，"
            f"涨停 {mc.get('limit_up')}/跌停 {mc.get('limit_down')}，容量前三 {caps or '—'}"
        )
    if context["signal_summary"]:
        digest.append("信号汇总：" + json.dumps(context["signal_summary"], ensure_ascii=False))
    if hot:
        digest.append(
            "盘面热门候选："
            + "；".join(
                f"{h['theme']}({h['tier']}/{h['score']}/{'+'.join(h['triggers'][:3])})"
                for h in hot[:6]
                if h.get("theme")
            )
        )
    prof = context["profile"]
    digest.append(
        f"画像「{prof['name'] or '—'}」：{prof['style'] or '—'}｜视野 {prof['horizon'] or '—'}"
    )
    if prof["focus_themes"]:
        digest.append("关注题材：" + "、".join(map(str, prof["focus_themes"])))
    if prof["watchlist"]:
        digest.append("自选股：" + "、".join(map(str, prof["watchlist"])))
    if intel:
        digest.append(f"实时情报：已加载 {len(intel)} 字")
    else:
        digest.append("实时情报：无（可用 --news-file 贴入今日财经日历/新闻）")
    return context, digest, warnings


# --------------------------------------------------------------------------- #
# 生成层：强角色 + 强约束提示词，逼模型做二阶 / 可量化 / 可证伪
# --------------------------------------------------------------------------- #
_SYSTEM_PROMPT = (
    "你是一位顶尖宏观对冲基金的研究主管，擅长逆向 / 非共识思维。"
    "任务：基于用户给出的「盘面现实 + 用户画像 + 实时情报」，生成若干条用户"
    "「还没想到但最该问」的追问。目标不是总结已知，而是把思考往前推一层。\n"
    "每条问题必须满足：\n"
    "1) 二阶思维：不要问显而易见的事，问「由此推出的下一层后果」；\n"
    "2) 跨领域连接：把两个看似不相关的领域勾连起来（如 AI×通胀、当下×历史类比、产业×宏观）；\n"
    "3) 高度具体：必须带 具体时间窗口 + 具体可量化指标 + 具体人名/事件/公司；\n"
    "4) 前瞻且可证伪：能在未来被验证对错，最好点明可提前判断的「领先指标 / 拐点 / 触发条件」；\n"
    "5) 呼应上下文：尽量与用户的关注题材、自选股或盘面热门候选相关，体现连续性。\n"
    "禁止：宽泛问题、能一句话答完的问题、纯定义类问题、与 recent_questions 重复的问题。\n"
    "严格只输出 JSON，不要任何额外文字，格式："
    '{"questions":[{"question":"...","rationale":"为什么这是用户没想到但该问的",'
    '"domains":["领域A","领域B"],"leading_indicator":"可提前判断的领先指标/可证伪点",'
    '"horizon":"时间窗口","novelty":0.0-1.0,"relevance":0.0-1.0}]}'
)


def _build_user_prompt(context: dict[str, Any], n_candidates: int) -> str:
    return (
        f"请基于以下 JSON 上下文，生成 {n_candidates} 条候选问题"
        f"（之后我会自己按 新颖度/相关度/多样性 排序取前几条，所以候选之间要尽量互不重复、覆盖不同角度）。\n"
        f"novelty=问题有多非共识/出人意料；relevance=与用户画像和当前盘面有多相关。\n\n"
        f"```json\n{json.dumps(context, ensure_ascii=False, indent=2)}\n```\n\n"
        f"只输出 JSON。"
    )


def _parse_question(obj: dict[str, Any]) -> Question | None:
    q = str(obj.get("question") or "").strip()
    if not q:
        return None
    domains = obj.get("domains")
    return Question(
        question=q,
        rationale=str(obj.get("rationale") or "").strip(),
        domains=[str(d).strip() for d in domains if str(d).strip()] if isinstance(domains, list) else [],
        leading_indicator=str(obj.get("leading_indicator") or "").strip(),
        horizon=str(obj.get("horizon") or "").strip(),
        novelty=_clamp01(obj.get("novelty")),
        relevance=_clamp01(obj.get("relevance")),
    )


def _clamp01(value: Any) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, f))


# --------------------------------------------------------------------------- #
# 排序去重层：MMR 式贪心，combined = 0.4*新颖 + 0.4*相关 + 0.2*多样
# --------------------------------------------------------------------------- #
def _bigrams(text: str) -> set[str]:
    s = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(text).lower())
    if len(s) < 2:
        return {s} if s else set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def _sim(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def rank_questions(
    raw: list[Question],
    asked: list[str],
    n: int,
    dedup_threshold: float = 0.6,
) -> list[Question]:
    asked_grams = [_bigrams(a) for a in asked if a]
    pool = [q for q in raw if all(_sim(_bigrams(q.question), g) < dedup_threshold for g in asked_grams)]

    selected: list[Question] = []
    while len(selected) < n:
        # Hard-suppress near-duplicates of anything already picked, then pick the
        # highest combined score (diversity still rewards mild novelty of angle).
        eligible = [
            q
            for q in pool
            if all(_sim(_bigrams(q.question), _bigrams(s.question)) < dedup_threshold for s in selected)
        ]
        if not eligible:
            break
        best: Question | None = None
        best_val = -1.0
        for q in eligible:
            if selected:
                diversity = 1.0 - max(_sim(_bigrams(q.question), _bigrams(s.question)) for s in selected)
            else:
                diversity = 1.0
            val = 0.4 * q.novelty + 0.4 * q.relevance + 0.2 * diversity
            if val > best_val:
                best_val, best = val, q
        assert best is not None
        best.score = round(best_val, 3)
        selected.append(best)
        pool.remove(best)
    return selected


# --------------------------------------------------------------------------- #
# 编排
# --------------------------------------------------------------------------- #
def generate(options: ForesightOptions) -> ForesightResult:
    context, digest, warnings = build_context(options)
    result = ForesightResult(
        trade_date=context.get("trade_date"),
        profile_name=(context.get("profile") or {}).get("name"),
        context_digest=digest,
    )
    result.warnings.extend(warnings)

    user_prompt = _build_user_prompt(context, options.candidates)
    result.prompt_preview = _SYSTEM_PROMPT + "\n\n---- user ----\n\n" + user_prompt

    content, provider, reason = llm_refine.complete(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model_override=options.llm_model,
        timeout=options.llm_timeout,
        temperature=options.temperature,
    )
    if content is None:
        result.warnings.append(
            (reason or "LLM 不可用")
            + "（已降级：只输出上下文摘要 + 待发送提示词；配置 LLM key 后即可真正生成问题）"
        )
        return result

    obj = llm_refine._extract_json(content)
    questions_raw = obj.get("questions") if isinstance(obj, dict) else None
    if not isinstance(questions_raw, list):
        result.warnings.append('LLM 返回无法解析为 {"questions":[...]}，已降级为仅摘要')
        return result

    parsed = [q for q in (_parse_question(item) for item in questions_raw if isinstance(item, dict)) if q]
    if not parsed:
        result.warnings.append("LLM 未给出任何有效问题，已降级为仅摘要")
        return result

    asked = (context.get("profile") or {}).get("recent_questions") or []
    result.questions = rank_questions(parsed, asked, options.n)
    result.llm_used = True
    result.llm_provider = provider.name if provider else None
    return result


def render(result: ForesightResult) -> str:
    lines: list[str] = ["# 猜你想问 / 潜意识"]
    meta = [
        f"盘面日期={result.trade_date or '—'}",
        f"画像={result.profile_name or '—'}",
        f"LLM={result.llm_provider or '未启用'}",
        f"状态={result.status}",
    ]
    lines.append("> " + " | ".join(meta))
    if result.warnings:
        lines.append("> 警告：" + "；".join(result.warnings))

    if result.questions:
        for i, q in enumerate(result.questions, 1):
            lines.append("")
            lines.append(f"## {i}. {q.question}")
            if q.rationale:
                lines.append(f"- 为什么你没想到：{q.rationale}")
            if q.domains:
                lines.append(f"- 跨域连接：{' × '.join(q.domains)}")
            if q.leading_indicator:
                lines.append(f"- 领先指标 / 可证伪点：{q.leading_indicator}")
            tail = []
            if q.horizon:
                tail.append(f"时间窗口 {q.horizon}")
            tail.append(f"新颖 {q.novelty} / 相关 {q.relevance} / 综合 {q.score}")
            lines.append("- " + "｜".join(tail))
    else:
        lines.append("")
        lines.append("## 上下文摘要（喂给模型的「现实锚定」）")
        lines.extend(f"- {d}" for d in result.context_digest)
        lines.append("")
        lines.append("## 待发送提示词（配置 LLM key 后即可真正生成问题）")
        lines.append("```")
        lines.append(result.prompt_preview)
        lines.append("```")
    return "\n".join(lines) + "\n"


def result_to_dict(result: ForesightResult) -> dict[str, Any]:
    return {
        "trade_date": result.trade_date,
        "profile_name": result.profile_name,
        "llm_used": result.llm_used,
        "llm_provider": result.llm_provider,
        "status": result.status,
        "warnings": result.warnings,
        "questions": [
            {
                "question": q.question,
                "rationale": q.rationale,
                "domains": q.domains,
                "leading_indicator": q.leading_indicator,
                "horizon": q.horizon,
                "novelty": q.novelty,
                "relevance": q.relevance,
                "score": q.score,
            }
            for q in result.questions
        ],
    }
