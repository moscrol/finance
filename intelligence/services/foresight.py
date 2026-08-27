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
import math
import re
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime, timezone
from pathlib import Path
from typing import Any

from intelligence import userspace
from intelligence.services import checkpoints, corrections, interactions, judgments, llm_refine
from intelligence.services.ask import load_theme_candidates

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = REPO_ROOT / "intelligence" / "foresight_profile.example.json"
DEFAULT_MEMORY_FILE = REPO_ROOT / "intelligence" / "foresight_memory.jsonl"
# 复盘认知框架（「思考宪法」）：发问前注入系统提示词，让 foresight 在用户方法论里推理。
# 用户可直接编辑此文件来修正方法论，无需改代码。
DEFAULT_METHODOLOGY_FILE = REPO_ROOT / "intelligence" / "foresight_methodology.md"


@dataclass(frozen=True)
class ForesightOptions:
    profile: str | Path | None = None
    user: str | None = None
    news_file: str | Path | None = None
    date: str | None = None
    exports_dir: str | Path | None = None
    kb_wiki: str | Path | None = None
    use_kb: bool = True
    kb_themes: int = 6
    n: int = 3
    candidates: int = 8
    llm_model: str | None = None
    llm_timeout: int = 60
    temperature: float = 0.8
    memory_file: str | Path | None = None
    use_memory: bool = True
    memory_window: int = 50
    interactions_file: str | Path | None = None
    use_interactions: bool = True
    interactions_window: int = 200
    affinity_half_life: float = 14.0
    affinity_boost: float = 0.2
    methodology_file: str | Path | None = None
    use_methodology: bool = True
    corrections_file: str | Path | None = None
    use_corrections: bool = True
    corrections_window: int = 20
    judgments_file: str | Path | None = None
    use_judgments: bool = True
    judgments_window: int = 10
    checkpoints_file: str | Path | None = None
    verdicts_file: str | Path | None = None
    use_calibration: bool = True
    calibration_min_n: int = 2


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
    affinity_boost: float = 0.0
    affinity_reasons: list[str] = field(default_factory=list)


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
    memory_path: str | None = None
    memory_loaded: int = 0
    memory_appended: int = 0
    interactions_path: str | None = None
    interactions_loaded: int = 0
    affinity_applied: int = 0
    kb_wiki_path: str | None = None
    kb_themes_loaded: int = 0
    methodology_path: str | None = None
    methodology_chars: int = 0
    corrections_path: str | None = None
    corrections_loaded: int = 0
    judgments_path: str | None = None
    judgments_loaded: int = 0
    calibration_scored: int = 0
    calibration_shown: int = 0
    next_watch_shown: int = 0

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


def resolve_profile(options: ForesightOptions) -> tuple[dict[str, Any], list[str]]:
    """解析生效画像：显式 ``--profile`` 单文件优先；否则按用户命名空间合并。

    无 ``--profile`` 时走 :func:`userspace.effective_profile`，即
    ``users/<user>/profile.json``（钉住）⊕ ``profile.derived.json``（派生）。
    """
    if options.profile:
        prof = load_profile(options.profile)
        warns = [str(prof["_warning"])] if prof.get("_warning") else []
        return prof, warns
    return userspace.effective_profile(userspace.user_space(options.user))


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


# --------------------------------------------------------------------------- #
# 第 3 层 · 记忆回路：本地 jsonl 累积「问过的问题」，下次自动去重
# 这是截图里「和你之前的三种情景推演对比」那种连续感的来源。
# --------------------------------------------------------------------------- #
def _memory_path(options: ForesightOptions) -> Path:
    if options.memory_file:
        return Path(options.memory_file).expanduser()
    return userspace.user_space(options.user).memory_path


def _interactions_path(options: ForesightOptions) -> Path:
    if options.interactions_file:
        return Path(options.interactions_file).expanduser()
    return userspace.user_space(options.user).interactions_path


def _load_affinity(
    options: ForesightOptions, result: "ForesightResult"
) -> list[interactions.Affinity]:
    """读取用户反馈记录并聚合成题材/个股亲和度（越用越懂）。无反馈则返回空列表。"""
    if not options.use_interactions:
        return []
    ipath = _interactions_path(options)
    result.interactions_path = str(ipath)
    records, warn = interactions.load_interactions(ipath, options.interactions_window)
    if warn:
        result.warnings.append(warn)
    result.interactions_loaded = len(records)
    affinity = interactions.compute_affinity(
        records, half_life_days=options.affinity_half_life
    )
    top = [a for a in affinity if a.score > 0][:3]
    if top:
        result.context_digest.append(
            "反馈亲和："
            + "、".join(f"{a.label}(+{round(a.score, 2)})" for a in top)
            + f"（共 {len(records)} 条反馈 → {ipath.name}）"
        )
    elif records:
        result.context_digest.append(
            f"反馈亲和：已读 {len(records)} 条反馈，暂无正向题材/个股加成"
        )
    return affinity


def load_asked_memory(path: str | Path, window: int = 50) -> tuple[list[str], str | None]:
    """读取本地「问过的问题」记忆 (jsonl)，返回最近 ``window`` 条去重后的问题文本。"""
    p = Path(path).expanduser()
    if not p.exists():
        return [], None
    try:
        raw_lines = p.read_text(encoding="utf-8").splitlines()
    except Exception as exc:  # pragma: no cover - defensive
        return [], f"记忆读取失败：{exc}"
    questions: list[str] = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        q = str(rec.get("question") or "").strip() if isinstance(rec, dict) else ""
        if q:
            questions.append(q)
    recent = questions[-window:] if window and window > 0 else questions
    seen: set[str] = set()
    out: list[str] = []
    for q in reversed(recent):  # keep the most recent occurrence on dedup
        key = re.sub(r"\s+", "", q)
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    out.reverse()
    return out, None


def append_asked_memory(
    path: str | Path,
    questions: list["Question"],
    trade_date: str | None = None,
) -> tuple[int, str | None]:
    """把本次选中的问题追加到记忆文件（每行一条 JSON）。"""
    items = [q for q in questions if isinstance(q, Question) and q.question.strip()]
    if not items:
        return 0, None
    p = Path(path).expanduser()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for q in items:
                fh.write(
                    json.dumps(
                        {
                            "question": q.question,
                            "trade_date": trade_date,
                            "asked_at": now,
                            "score": q.score,
                            "novelty": q.novelty,
                            "relevance": q.relevance,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    except Exception as exc:  # pragma: no cover - defensive
        return 0, f"记忆写入失败：{exc}"
    return len(items), None


def _merge_recent_questions(profile_recent: list[Any], memory_qs: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for q in [*(profile_recent or []), *(memory_qs or [])]:
        s = str(q).strip()
        if not s:
            continue
        key = re.sub(r"\s+", "", s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


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


def _load_kb_themes(
    options: ForesightOptions,
) -> tuple[list[dict[str, Any]], str, list[str]]:
    """读取知识库 ``relations/theme_signals.json``，取认知最靠前的若干题材当发问素材。

    复用 :func:`refresh_profile.derive_from_kb` 的排序（近期 > ★ 多 > 进度 > 热度）。
    知识库缺失/不可读时优雅降级：返回空列表 + 警告，绝不抛栈。
    """
    # 局部 import：refresh_profile 只在顶层依赖 KnowledgeAdapter（无 duckdb），安全。
    from intelligence.services import refresh_profile
    from intelligence.adapters.knowledge import KnowledgeAdapter

    wiki_path = str(KnowledgeAdapter(wiki_root=options.kb_wiki).resolved_wiki_root)
    out = refresh_profile.derive_from_kb(
        refresh_profile.RefreshOptions(kb_wiki=options.kb_wiki, top=options.kb_themes)
    )
    if not out.get("ok"):
        return [], wiki_path, list(out.get("warnings") or [])
    themes: list[dict[str, Any]] = []
    for item in (out.get("themes") or [])[: max(options.kb_themes, 0)]:
        sig = item.get("signals") or {}
        themes.append(
            {
                "theme": item.get("theme"),
                "stars": sig.get("stars"),
                "stage_position": sig.get("stage_position"),
                "tier": sig.get("tier"),
                "last_event": sig.get("last_event"),
            }
        )
    return themes, wiki_path, []


def build_context(
    options: ForesightOptions,
) -> tuple[dict[str, Any], list[str], list[str]]:
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

    profile, profile_warnings = resolve_profile(options)
    warnings.extend(profile_warnings)

    intel, intel_warn = _read_text(options.news_file)
    if intel_warn:
        warnings.append(intel_warn)

    kb_themes: list[dict[str, Any]] = []
    kb_wiki_path: str | None = None
    if options.use_kb:
        kb_themes, kb_wiki_path, kb_warns = _load_kb_themes(options)
        if kb_warns:
            warnings.append(
                "知识库题材未接入："
                + "；".join(kb_warns)
                + "（设 KNOWLEDGE_WIKI 或 --kb-wiki 指向知识库 wiki 根即可调用）"
            )

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
        "kb_themes": kb_themes,
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
    context["_kb_wiki_path"] = kb_wiki_path

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
    if kb_themes:
        digest.append(
            "知识库题材（认知发酵）："
            + "；".join(
                f"{t['theme']}(★{t.get('stars') or 0}"
                f"/进度{t.get('stage_position') or 0}"
                f"/Tier{t.get('tier') if t.get('tier') is not None else '—'}"
                f"/{t.get('last_event') or '—'})"
                for t in kb_themes
                if t.get("theme")
            )
        )
    elif options.use_kb:
        digest.append(
            "知识库题材：未接入（设 KNOWLEDGE_WIKI 或 --kb-wiki 指向知识库 wiki 根即可调用）"
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
    "5) 呼应上下文：尽量与用户的关注题材、自选股、盘面热门候选或「知识库题材」相关，"
    "体现连续性；「知识库题材 kb_themes」是用户自己沉淀的认知/发酵进度，"
    "可优先围绕其中认知阶段靠前（★ 多）或近期有新事件的题材做二阶追问。\n"
    "禁止：宽泛问题、能一句话答完的问题、纯定义类问题、与 recent_questions 重复的问题；"
    "也不要把本仓已有数据块能直接回答的问题当成二阶追问——"
    "不要问「有没有历史上类似的情绪环境」（市场情绪类比 D10 已覆盖）、"
    "不要问「这个题材处于哪个生命周期阶段」（题材时间线已覆盖）、"
    "不要问「上期结论有什么变化」（跟踪契约已覆盖）。"
    "二阶追问必须建立在这些事实之上，问下一层后果、跨域传导、证伪后的动作分层。\n"
    "严格只输出 JSON，不要任何额外文字，格式："
    '{"questions":[{"question":"...","rationale":"为什么这是用户没想到但该问的",'
    '"domains":["领域A","领域B"],"leading_indicator":"可提前判断的领先指标/可证伪点",'
    '"horizon":"时间窗口","novelty":0.0-1.0,"relevance":0.0-1.0}]}'
)


def _methodology_path(options: ForesightOptions) -> Path:
    if options.methodology_file:
        return Path(options.methodology_file).expanduser()
    return DEFAULT_METHODOLOGY_FILE


def load_methodology(options: ForesightOptions) -> tuple[str, str | None, str | None]:
    """读取「思考宪法」方法论文件。返回 ``(text, path, warning)``；缺失/关闭则文本为空。"""
    if not options.use_methodology:
        return "", None, None
    p = _methodology_path(options)
    if not p.exists():
        return "", None, f"方法论文件不存在：{p}（发问将不带复盘认知框架）"
    try:
        text = p.read_text(encoding="utf-8").strip()
    except Exception as exc:  # pragma: no cover - defensive
        return "", None, f"方法论文件读取失败：{p}（{exc}）"
    return text, str(p), None


def _corrections_path(options: ForesightOptions) -> Path:
    if options.corrections_file:
        return Path(options.corrections_file).expanduser()
    return userspace.user_space(options.user).corrections_path


def _judgments_path(options: ForesightOptions) -> Path:
    if options.judgments_file:
        return Path(options.judgments_file).expanduser()
    return userspace.user_space(options.user).judgments_path


def _checkpoint_paths(options: ForesightOptions) -> tuple[Path, Path]:
    us = userspace.user_space(options.user)
    cpath = Path(options.checkpoints_file).expanduser() if options.checkpoints_file else us.checkpoints_path
    vpath = Path(options.verdicts_file).expanduser() if options.verdicts_file else us.verdicts_path
    return cpath, vpath


def _compose_system_prompt(options: ForesightOptions, result: ForesightResult) -> str:
    """基线人设 + 思考宪法（方法论）+ 纠偏记录，拼成本轮真正发给 LLM 的系统提示词。

    方法论与纠偏都做成**可编辑文件**：用户改文件即改发问脑子，无需动代码。
    """
    prompt = _SYSTEM_PROMPT
    text, mpath, mwarn = load_methodology(options)
    if mwarn:
        result.warnings.append(mwarn)
    if text:
        result.methodology_path = mpath
        result.methodology_chars = len(text)
        prompt += (
            "\n\n==== 复盘认知框架（思考宪法，务必据此推理与发问）====\n" + text
        )
    if options.use_corrections:
        cpath = _corrections_path(options)
        result.corrections_path = str(cpath)
        recs, cwarn = corrections.load_corrections(cpath, options.corrections_window)
        if cwarn:
            result.warnings.append(cwarn)
        result.corrections_loaded = len(recs)
        rendered = corrections.render_for_prompt(recs)
        if rendered:
            prompt += (
                "\n\n==== 纠偏记录（我曾纠正过你，发问前务必避免重犯同类错误）====\n"
                + rendered
            )
    if options.use_judgments:
        jpath = _judgments_path(options)
        result.judgments_path = str(jpath)
        jrecs, jwarn = judgments.load_judgments(jpath, options.judgments_window)
        if jwarn:
            result.warnings.append(jwarn)
        result.judgments_loaded = len(jrecs)
        jrendered = judgments.render_for_prompt(jrecs)
        if jrendered:
            prompt += (
                "\n\n==== 我近期的核心判断（承接这些判断往前推一层或找它的反例，别从零重述）====\n"
                + jrendered
            )
    if options.use_calibration:
        cpath, vpath = _checkpoint_paths(options)
        cal, cal_warns = checkpoints.load_calibration(cpath, vpath)
        result.warnings.extend(cal_warns)
        result.calibration_scored = cal.scored
        cal_rendered = checkpoints.render_calibration_for_prompt(cal, options.calibration_min_n)
        if cal_rendered:
            result.calibration_shown = sum(1 for s in cal.by_category if s.n >= options.calibration_min_n)
            prompt += (
                "\n\n==== 你的二阶推演校准（哪类判断历史靠谱/偏差，发问时据此加权信任或质疑）====\n"
                + cal_rendered
            )
        from intelligence.services.track_contract import (
            open_next_watch_records,
            render_next_watch_for_prompt,
        )

        watch_rows, watch_warn = checkpoints.load_checkpoints(cpath)
        watch_verdicts, verdict_warn = checkpoints.load_verdicts(vpath)
        if watch_warn:
            result.warnings.append(watch_warn)
        if verdict_warn:
            result.warnings.append(verdict_warn)
        open_watch = open_next_watch_records(watch_rows, watch_verdicts)
        watch_rendered = render_next_watch_for_prompt(open_watch)
        if watch_rendered:
            result.next_watch_shown = len(open_watch)
            prompt += (
                "\n\n==== 下期关注对照（上次跟踪留下的强制输入，先对照再发问）====\n"
                + watch_rendered
            )
    return prompt


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
# 排序去重层：MMR 式贪心
#   combined = 0.4*新颖 + 0.4*相关 + 0.2*多样 + 反馈加成（越用越懂，可解释）
# 反馈加成 = boost_weight * tanh(Σ 命中题材/个股的亲和度)，有界且可逐条溯源。
# --------------------------------------------------------------------------- #
def _norm_match(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _affinity_boost(
    question: str,
    affinity: list[interactions.Affinity],
    boost_weight: float,
) -> tuple[float, list[str]]:
    """对一条问题计算反馈加成 + 可解释理由（命中近期被互动过的题材/个股）。"""
    if not affinity or boost_weight == 0.0:
        return 0.0, []
    qnorm = _norm_match(question)
    matched: list[interactions.Affinity] = [a for a in affinity if a.norm and a.norm in qnorm]
    if not matched:
        return 0.0, []
    raw = sum(a.score for a in matched)
    component = boost_weight * math.tanh(raw)
    matched.sort(key=lambda a: (-abs(a.score), a.kind, a.label))
    reasons = [
        f"{'题材' if a.kind == 'theme' else '个股'} {a.label}"
        f"({'+' if a.score >= 0 else ''}{round(a.score, 2)})"
        for a in matched[:3]
    ]
    return round(component, 4), reasons


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
    affinity: list[interactions.Affinity] | None = None,
    boost_weight: float = 0.2,
) -> list[Question]:
    asked_grams = [_bigrams(a) for a in asked if a]
    pool = [q for q in raw if all(_sim(_bigrams(q.question), g) < dedup_threshold for g in asked_grams)]

    # 反馈加成对每条问题是常量（不随选择顺序变），先一次性算好 + 标注理由。
    affinity = affinity or []
    boosts: dict[int, tuple[float, list[str]]] = {
        id(q): _affinity_boost(q.question, affinity, boost_weight) for q in pool
    }

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
            boost, _ = boosts.get(id(q), (0.0, []))
            val = 0.4 * q.novelty + 0.4 * q.relevance + 0.2 * diversity + boost
            if val > best_val:
                best_val, best = val, q
        assert best is not None
        b_boost, b_reasons = boosts.get(id(best), (0.0, []))
        best.affinity_boost = b_boost
        best.affinity_reasons = b_reasons
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
    # 本地路径不进提示词：从 context 取出后移除，避免被序列化进发送给 LLM 的 JSON。
    result.kb_wiki_path = context.pop("_kb_wiki_path", None)
    result.kb_themes_loaded = len(context.get("kb_themes") or [])

    # 第 3 层 · 记忆回路：并入「曾问过的问题」用于去重，体现连续性。
    if options.use_memory:
        mem_path = _memory_path(options)
        result.memory_path = str(mem_path)
        mem_questions, mem_warn = load_asked_memory(mem_path, options.memory_window)
        if mem_warn:
            result.warnings.append(mem_warn)
        result.memory_loaded = len(mem_questions)
        prof = context.setdefault("profile", {})
        prof["recent_questions"] = _merge_recent_questions(
            prof.get("recent_questions") or [], mem_questions
        )
        result.context_digest.append(
            f"历史记忆：并入 {len(mem_questions)} 条曾问过的问题用于去重（{mem_path.name}）"
            if mem_questions
            else f"历史记忆：暂无（首次运行，问题将写入 {mem_path.name}）"
        )

    # 越用越懂：把近期反馈聚合成题材/个股亲和度（在 LLM 调用前载入，降级时也能展示）。
    affinity = _load_affinity(options, result)

    # 思考宪法（方法论）+ 纠偏记录拼进系统提示词，让它在用户框架里发问。
    system_prompt = _compose_system_prompt(options, result)
    user_prompt = _build_user_prompt(context, options.candidates)
    result.prompt_preview = system_prompt + "\n\n---- user ----\n\n" + user_prompt

    content, provider, reason = llm_refine.complete(
        [
            {"role": "system", "content": system_prompt},
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
    result.questions = rank_questions(
        parsed, asked, options.n, affinity=affinity, boost_weight=options.affinity_boost
    )
    result.affinity_applied = sum(1 for q in result.questions if q.affinity_boost)
    result.llm_used = True
    result.llm_provider = provider.name if provider else None
    if options.use_memory and result.questions:
        appended, append_warn = append_asked_memory(
            _memory_path(options), result.questions, trade_date=result.trade_date
        )
        result.memory_appended = appended
        if append_warn:
            result.warnings.append(append_warn)
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
    if result.memory_path:
        lines.append(
            f"> 记忆：并入 {result.memory_loaded} 条历史提问去重 · 本次新增 "
            f"{result.memory_appended} 条 → {result.memory_path}"
        )
    if result.interactions_loaded:
        lines.append(
            f"> 反馈：读入 {result.interactions_loaded} 条互动记录 · "
            f"{result.affinity_applied} 条问题获得亲和加成"
        )
    if result.kb_themes_loaded:
        lines.append(f"> 知识库：调入 {result.kb_themes_loaded} 个题材当发问素材")
    if result.methodology_chars or result.corrections_loaded:
        parts = []
        if result.methodology_chars:
            parts.append(f"注入思考宪法 {result.methodology_chars} 字")
        if result.corrections_loaded:
            parts.append(f"带 {result.corrections_loaded} 条纠偏")
        lines.append("> 方法论：" + " · ".join(parts))
    if result.judgments_loaded:
        lines.append(
            f"> 旧判断：承接 {result.judgments_loaded} 条核心判断往前推（不从零重述）"
        )
    if result.calibration_shown:
        lines.append(
            f"> 校准：按你 {result.calibration_shown} 类二阶推演的历史胜率加权信任/质疑"
            f"（已回检 {result.calibration_scored} 条）"
        )
    if result.next_watch_shown:
        lines.append(
            f"> 下期关注：对照上次跟踪留下的 {result.next_watch_shown} 条观察项再发问"
        )
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
            if q.affinity_reasons:
                lines.append(
                    f"- 反馈加成（近期你在看）：{'、'.join(q.affinity_reasons)} → +{q.affinity_boost}"
                )
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
        "memory_path": result.memory_path,
        "memory_loaded": result.memory_loaded,
        "memory_appended": result.memory_appended,
        "interactions_path": result.interactions_path,
        "interactions_loaded": result.interactions_loaded,
        "affinity_applied": result.affinity_applied,
        "kb_wiki_path": result.kb_wiki_path,
        "kb_themes_loaded": result.kb_themes_loaded,
        "methodology_path": result.methodology_path,
        "methodology_chars": result.methodology_chars,
        "corrections_path": result.corrections_path,
        "corrections_loaded": result.corrections_loaded,
        "judgments_path": result.judgments_path,
        "judgments_loaded": result.judgments_loaded,
        "calibration_scored": result.calibration_scored,
        "calibration_shown": result.calibration_shown,
        "next_watch_shown": result.next_watch_shown,
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
                "affinity_boost": q.affinity_boost,
                "affinity_reasons": q.affinity_reasons,
            }
            for q in result.questions
        ],
    }
