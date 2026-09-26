"""M 用户记忆检索块：答题时按相关性召回你自己的核心判断/纠偏原则/回检胜率。

三个已有 per-user 台账（stdlib、离线、gitignored 私有层）此前只喂 foresight 发问，
答题链（``ask.py``）完全没用上——这块把它们接进证据链：

- ``judgments.jsonl``   核心判断（潜意识深挖沉淀，带 themes/stocks 标签）；
- ``corrections.jsonl`` 纠偏原则（你显式纠正过的方法论，带 themes 标签）；
- ``checkpoints.jsonl`` + ``verdicts.jsonl`` 回检校准（哪类判断历史靠谱→兑现率）。

与 foresight「无脑取最近 N 条」不同，这里按 query（题材/实体/关键词）与记录的
标签/正文做轻量重合打分，**只召回相关的**；召回为空时返回空串（不追加块，
无记忆用户行为逐字节不变）。渲染标 [M]，让回答站在你旧判断上往前推、
遵守你纠偏过的原则，并用回检胜率标注该信多少。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from intelligence import userspace
from intelligence.services import checkpoints, corrections, judgments

DEFAULT_LOAD_WINDOW = 200
DEFAULT_LIMIT = 5
# KC-11：同类已裁决数不足 N 不展示胜率行。与 checkpoint 校准同一闸，不是召回次数。
PEER_HIT_MIN_N = checkpoints.DEFAULT_CALIBRATION_MIN_N
PEER_HIT_LINE = "同类判断历史 {hits}/{n} 命中（分母=已裁决数）"

#: W1 读侧来源契约：召回池只从这三源取条目。verdicts 不入池——它只喂回检校准
#: （calibration_text / PEER_HIT_LINE）。新增来源的流程：先在这里登记、在 PR 里
#: 声明「该源为什么不含易变事实」，再改 MemoryRecall 与 ReadSideContractTests
#: 的 slots 断言（不登记直接加槽位，契约测试先红）。来源名单只是辅助：
#: 真正的防线在证据分级（episode_tools 侧 evidence_tier="user_memory" + 先验自标），
#: 来源全对也不证明条目正文里没有旧价格、旧订单。
RECALL_SOURCES: tuple[str, ...] = ("judgments", "corrections", "methods")

# ── W3 召回降权口径（2026-09-11 定；spec: 2026-09-10-knevo-arch-delta-worklist W3）──
#: 驱动降权的指标 = **计分率**（checkpoints.CategoryStat.hit_rate = score_sum/n；
#: hit=1、partial=0.5、miss=0），与校准器同一口径。PEER_HIT_LINE 的「x/n 命中」
#: 是整命中**展示**口径，不驱动决策——两口径对同一组数据（4 hit + 6 partial）
#: 会读出 40% 与 70%，不钉死驱动口径，同一阈值会得出相反结论。
#: 分母 n = 已终态裁决数（hit/partial/miss）；unverifiable 与 hindsight 在
#: calibrate() 已排除，不进分母。
#: 生效双闸：score_rate < 阈值 且 n ≥ PEER_HIT_MIN_N（KC-11 同一闸，小样本不降权）。
#: 阈值默认 **None=功能关闭**：候选值须过 evolution 回测队列
#: （evolution/backtest-queue.md）并经人工确认后才允许填数——reading_baseline
#: 纪律：结构先行，单点阈值回测过了才升。
RELIABILITY_DOWNWEIGHT_THRESHOLD: float | None = None
RELIABILITY_WARNING_LINE = (
    "⚠ 该类判断（{category}）历史命中率低：计分率 {rate}%（partial 计 0.5，N={n}）"
    "——已降权召回，仅作反例与风险提示，不作立论起点"
)


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _query_terms(query: str, theme: str | None = None, entity: str | None = None) -> list[str]:
    terms = [t for t in re.split(r"[，,。；;、\s/？?！!（）()]+", str(query or "")) if len(t) >= 2]
    for extra in (theme, entity):
        extra = (extra or "").strip()
        if extra:
            terms.append(extra)
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        k = _norm(t)
        if k and k not in seen:
            seen.add(k)
            out.append(t)
    return out


def select_relevant(
    records: list[dict[str, Any]],
    query: str,
    theme: str | None = None,
    entity: str | None = None,
    text_keys: tuple[str, ...] = ("memo",),
    tag_keys: tuple[str, ...] = ("themes", "stocks"),
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """轻量相关性召回：标签命中权重高于正文重合；0 分记录不召回。"""
    terms = _query_terms(query, theme, entity)
    if not terms:
        return []

    def score(rec: dict[str, Any]) -> tuple[int, str]:
        tags = []
        for k in tag_keys:
            tags += [str(t).strip() for t in (rec.get(k) or []) if str(t).strip()]
        norm_tags = [_norm(t) for t in tags if _norm(t)]
        tag_hay = " ".join(norm_tags)
        text_hay = _norm(" ".join(str(rec.get(k) or "") for k in text_keys))
        s = 0
        for term in terms:
            nt = _norm(term)
            if not nt:
                continue
            # 双向子串：term⊆tag（原有）或 tag⊆term（新增）。
            # 典型场景：contract_subject = "液冷温控"，台账标签 = "液冷"，
            # "液冷温控" ∌ "液冷" 作为子串（单向失配），但 "液冷" ⊆ "液冷温控"（双向命中）。
            if nt in tag_hay or any(ntag in nt for ntag in norm_tags):
                s += 4
            if nt in text_hay:
                s += 2
        return s, str(rec.get("ts") or "")

    ranked = [(score(r), r) for r in records if isinstance(r, dict)]
    ranked = [item for item in ranked if item[0][0] > 0]
    ranked.sort(key=lambda item: (item[0][0], item[0][1]), reverse=True)
    return [r for _, r in ranked[:limit]]


def peer_hit_line(
    stat: checkpoints.CategoryStat | None,
    *,
    min_n: int = PEER_HIT_MIN_N,
) -> str | None:
    """类别已裁决数 ≥N 才出一行。只用 hit/n，不用召回次数或 confidence。"""
    if stat is None or stat.n < min_n:
        return None
    return PEER_HIT_LINE.format(hits=stat.hits, n=stat.n)


def resolve_judgment_category(
    record: dict[str, Any],
    checkpoint_rows: list[dict[str, Any]],
) -> str | None:
    explicit = str(record.get("category") or "").strip()
    if explicit:
        return explicit
    jid = str(record.get("id") or "").strip()
    jts = str(record.get("ts") or "").strip()
    for ck in checkpoint_rows:
        if jid and str(ck.get("session_id") or "") == jid:
            cat = str(ck.get("category") or "").strip()
            return cat or None
        if jts and str(ck.get("source_judgment_ts") or "") == jts:
            cat = str(ck.get("category") or "").strip()
            return cat or None
    if record.get("record_type") == "foresight_judgment":
        return "前瞻判断"
    return None


def peer_hit_for_judgment(
    record: dict[str, Any],
    checkpoint_rows: list[dict[str, Any]],
    cal: checkpoints.Calibration,
    *,
    min_n: int = PEER_HIT_MIN_N,
) -> str | None:
    category = resolve_judgment_category(record, checkpoint_rows)
    if not category:
        return None
    stat = next((item for item in cal.by_category if item.category == category), None)
    return peer_hit_line(stat, min_n=min_n)


def judgment_peer_hits(
    records: list[dict[str, Any]],
    *,
    user: str | None = None,
    users_root: str | Path | None = None,
    min_n: int = PEER_HIT_MIN_N,
) -> list[str | None]:
    _j_path, _c_path, ck_path, v_path = _ledger_paths(user, users_root)
    checkpoint_rows, _ = checkpoints.load_checkpoints(ck_path)
    cal, _ = checkpoints.load_calibration(ck_path, v_path)
    return [
        peer_hit_for_judgment(record, checkpoint_rows, cal, min_n=min_n)
        for record in records
    ]


def reliability_downweight(
    records: list[dict[str, Any]],
    checkpoint_rows: list[dict[str, Any]],
    cal: checkpoints.Calibration,
    *,
    threshold: float | None,
    min_n: int = PEER_HIT_MIN_N,
) -> tuple[list[dict[str, Any]], list[str | None]]:
    """W3：低可靠判断类沉底（稳定重排，其余相对顺序不变）并逐条给警告行。

    threshold=None（生产默认）时不重排、不出警告：阈值未经回测不得生效。
    口径见 RELIABILITY_DOWNWEIGHT_THRESHOLD 处注释：计分率驱动，小样本（n < min_n）
    与无分类（resolve_judgment_category → None）一律不降权不警告。
    """
    if threshold is None or not records:
        return list(records), [None] * len(records)
    keep: list[int] = []
    sink: list[int] = []
    warnings: dict[int, str] = {}
    for idx, rec in enumerate(records):
        category = resolve_judgment_category(rec, checkpoint_rows)
        stat = None
        if category:
            stat = next((s for s in cal.by_category if s.category == category), None)
        if stat is not None and stat.n >= min_n and stat.hit_rate < threshold:
            sink.append(idx)
            warnings[idx] = RELIABILITY_WARNING_LINE.format(
                category=category, rate=round(stat.hit_rate * 100), n=stat.n
            )
        else:
            keep.append(idx)
    order = keep + sink
    return [records[i] for i in order], [warnings.get(i) for i in order]


def judgment_reliability(
    records: list[dict[str, Any]],
    *,
    user: str | None = None,
    users_root: str | Path | None = None,
    threshold: float | None = None,
    min_n: int = PEER_HIT_MIN_N,
) -> tuple[list[dict[str, Any]], list[str | None]]:
    """工具侧（memory_lookup）入口：读该用户校准台账后套 reliability_downweight。

    台账读失败只降级为原样返回，不让记忆召回本身失败。
    """
    if threshold is None or not records:
        return list(records), [None] * len(records)
    _j_path, _c_path, ck_path, v_path = _ledger_paths(user, users_root)
    try:
        checkpoint_rows, _ = checkpoints.load_checkpoints(ck_path)
        cal, _warn = checkpoints.load_calibration(ck_path, v_path)
    except Exception:
        return list(records), [None] * len(records)
    return reliability_downweight(
        records, checkpoint_rows, cal, threshold=threshold, min_n=min_n
    )


def _judgment_lines(
    records: list[dict[str, Any]],
    peer_lines: list[str | None] | None = None,
    *,
    as_of: str | None = None,
    warning_lines: list[str | None] | None = None,
) -> list[str]:
    from intelligence.services.track_contract import downgrade_expired_text

    lines: list[str] = []
    extras = list(peer_lines or [])
    warns = list(warning_lines or [])
    for index, rec in enumerate(records):
        memo = str(rec.get("memo") or "").strip()
        if not memo:
            continue
        memo = downgrade_expired_text(
            memo,
            valid_until=str(rec.get("valid_until") or "") or None,
            as_of=as_of,
        )
        tags = [str(t).strip() for t in (rec.get("themes") or []) if str(t).strip()]
        tags += [str(s).strip() for s in (rec.get("stocks") or []) if str(s).strip()]
        date = str(rec.get("ts") or "")[:10]
        head = "、".join(tags)
        # W2 逐条归属：块内混进一条过期判断时，块级标签救不了单条——每条自带
        # 「这是你 X 日的判断」。日期从后缀移入前缀（仍逐条），过期降级不变。
        own = f"[M·你的判断 {date}]" if date else "[M·你的判断]"
        lines.append(f"- {own}{f'[{head}]' if head else ''}：{memo}")
        peer = extras[index] if index < len(extras) else None
        if peer:
            lines.append(f"  {peer}")
        warn = warns[index] if index < len(warns) else None
        if warn:
            lines.append(f"  {warn}")
    return lines


def _correction_lines(records: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for rec in records:
        correction = str(rec.get("correction") or "").strip()
        if not correction:
            continue
        principle = str(rec.get("principle") or "").strip()
        body = principle or correction
        date = str(rec.get("ts") or "")[:10]
        own = f"[M·你的纠偏原则 {date}]" if date else "[M·你的纠偏原则]"
        lines.append(f"- {own}：{body}")
    return lines


def build_memory_block(
    judgment_records: list[dict[str, Any]],
    correction_records: list[dict[str, Any]],
    calibration_text: str = "",
    peer_lines: list[str | None] | None = None,
    *,
    as_of: str | None = None,
    method_records: list[dict[str, Any]] | None = None,
    warning_lines: list[str | None] | None = None,
) -> str:
    """渲染 [M] 块；判断、纠偏与方法读数都为空时返回空串（不追加块）。"""
    j_lines = _judgment_lines(
        judgment_records, peer_lines, as_of=as_of, warning_lines=warning_lines
    )
    c_lines = _correction_lines(correction_records)
    m_lines = _method_lines(method_records or [])
    if not j_lines and not c_lines and not m_lines:
        return ""
    lines = ["## 用户记忆检索块 [M]（你自己的核心判断/纠偏原则/回检胜率/方法验证读数，非市场事实）"]
    lines += j_lines
    lines += c_lines
    lines += m_lines
    if calibration_text:
        lines.append("- 回检校准（该信多少）：")
        lines += [f"  {ln}" for ln in calibration_text.splitlines() if ln.strip()]
    lines.append(
        "- 使用要求：本块只是历史先验（prior），不是当前市场事实。它用于调整篇幅、语气、"
        "增量起点和反方重点；若用户已聊过同一标的，优先回答“相比上次发生了什么变化”，"
        "不要重跑全套模板。价格、产能、订单等易变项必须以本轮检索为准；与最新盘面/财报"
        "冲突时以硬数据块为准并显式指出冲突。"
    )
    return "\n".join(lines)


def _ledger_paths(
    user: str | None,
    users_root: str | Path | None,
) -> tuple[Path, Path, Path, Path]:
    """Resolve the four per-user ledger paths (judgments/corrections/checkpoints/verdicts).

    ``users_root`` exists so callers -- notably tests -- can point at a temporary
    fixture directory instead of the real, private user ledgers.
    """

    if users_root is not None:
        root = Path(users_root).expanduser()
        return (
            root / "judgments.jsonl",
            root / "corrections.jsonl",
            root / "checkpoints.jsonl",
            root / "verdicts.jsonl",
        )
    us = userspace.user_space(user)
    return (
        us.judgments_path,
        us.corrections_path,
        us.checkpoints_path,
        us.verdicts_path,
    )


class MemoryRecall:
    """Structured recall result: the records themselves plus their provenance.

    ``memory_block_for_query`` renders these into one ``[M]`` markdown string,
    which is the right shape for prompt injection but the wrong shape for a
    tool: a caller that needs per-record evidence (each with its own locator
    and content hash) cannot recover the individual records from the rendered
    text. This type is that missing seam, so both callers share one recall
    implementation instead of forking the relevance logic.
    """

    __slots__ = (
        "judgments",
        "corrections",
        "judgments_path",
        "corrections_path",
        "methods",
    )

    def __init__(
        self,
        *,
        judgments: list[dict[str, Any]],
        corrections: list[dict[str, Any]],
        judgments_path: Path,
        corrections_path: Path,
        methods: list[dict[str, Any]] | None = None,
    ) -> None:
        self.judgments = judgments
        self.corrections = corrections
        self.judgments_path = judgments_path
        self.corrections_path = corrections_path
        # 方法验证立场（能力升级 07）：该用户自己实验目录下的固定方法读数——历史演练 / 真实前向
        # 分开标注，只在问题命中方法关键词时召回；别的用户的收据不会进来。
        self.methods = list(methods or [])

    def __bool__(self) -> bool:
        return bool(self.judgments or self.corrections or self.methods)

    @property
    def total(self) -> int:
        return len(self.judgments) + len(self.corrections) + len(self.methods)


def _method_records(
    query: str,
    user: str | None,
    users_root: str | Path | None,
    *,
    strict: bool = False,
) -> list[dict[str, Any]]:
    """方法验证立场召回；默认容错，开口预取须显式区分失败与空命中。"""
    try:
        from intelligence.services.method_validation import flywheel

        return flywheel.recall_for_query(query, user=user, users_root=users_root)
    except Exception:
        if strict:
            raise OSError("method memory unavailable") from None
        return []


def _method_lines(records: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for record in records:
        date = str(record.get("date") or "")[:10]
        own = f"[M·方法验证读数 {date}]" if date else "[M·方法验证读数]"
        lines.append(f"- {own}（{record.get('title') or record.get('method_id')}）：")
        lines += [f"  {ln}" for ln in (record.get("lines") or []) if str(ln).strip()]
    return lines


def relevant_memory_records(
    query: str,
    theme: str | None = None,
    entity: str | None = None,
    user: str | None = None,
    limit: int = DEFAULT_LIMIT,
    users_root: str | Path | None = None,
    *,
    strict: bool = False,
) -> MemoryRecall:
    """Recall relevant judgments/corrections as records, not rendered markdown."""

    j_path, c_path, _ck_path, _v_path = _ledger_paths(user, users_root)
    read_options = {"strict": True} if strict else {}
    j_records, j_warning = judgments.load_judgments(j_path, window=DEFAULT_LOAD_WINDOW, **read_options)
    c_records, c_warning = corrections.load_corrections(c_path, window=DEFAULT_LOAD_WINDOW, **read_options)
    if strict and (j_warning or c_warning):
        raise OSError("user memory ledger unavailable")
    return MemoryRecall(
        judgments=select_relevant(
            j_records,
            query,
            theme,
            entity,
            text_keys=("memo",),
            limit=limit,
        ),
        corrections=select_relevant(
            c_records,
            query,
            theme,
            entity,
            text_keys=("correction", "original", "principle"),
            tag_keys=("themes",),
            limit=limit,
        ),
        judgments_path=j_path,
        corrections_path=c_path,
        methods=_method_records(query, user, users_root, strict=strict),
    )


def memory_block_for_query(
    query: str,
    theme: str | None = None,
    entity: str | None = None,
    user: str | None = None,
    limit: int = DEFAULT_LIMIT,
    users_root: str | Path | None = None,
) -> str:
    """加载三源台账→相关性召回→渲染 [M]；台账缺失/无相关记录时返回空串。"""
    _j_path, _c_path, ck_path, v_path = _ledger_paths(user, users_root)
    recall = relevant_memory_records(
        query,
        theme,
        entity,
        user,
        limit=limit,
        users_root=users_root,
    )
    j_hit = recall.judgments
    c_hit = recall.corrections
    calibration_text = ""
    peer_lines: list[str | None] = []
    warning_lines: list[str | None] = []
    if j_hit or c_hit:
        try:
            checkpoint_rows, _ = checkpoints.load_checkpoints(ck_path)
            cal, _warn = checkpoints.load_calibration(ck_path, v_path)
            calibration_text = checkpoints.render_calibration_for_prompt(cal)
            # W3：先降权重排（阈值模块级读取，默认 None=关闭），再按新序配胜率行。
            j_hit, warning_lines = reliability_downweight(
                j_hit,
                checkpoint_rows,
                cal,
                threshold=RELIABILITY_DOWNWEIGHT_THRESHOLD,
            )
            peer_lines = [
                peer_hit_for_judgment(record, checkpoint_rows, cal)
                for record in j_hit
            ]
        except Exception:
            calibration_text = ""
            peer_lines = []
            warning_lines = []
    return build_memory_block(
        j_hit,
        c_hit,
        calibration_text,
        peer_lines,
        method_records=recall.methods,
        warning_lines=warning_lines,
    )
