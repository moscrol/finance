"""潜意识模式 (subconscious mode)：会话级记忆巩固 (consolidation)。

一个**可开关**的对话模式。开启后由 ``foresight`` 主动发问、用户多轮追问；退出时把这段
对话「回读」成结构化信号，先给 diff 等用户确认，确认后**双层落盘**：

- 机器层 ``users/<id>/interactions.jsonl``（算法燃料，复用
  :func:`intelligence.services.interactions.record_interaction`，喂 foresight 亲和度）；
- 人类层 Obsidian「沉淀」vault markdown 日志（你读 / 改 / 看演化），路径走 ``--vault`` /
  env ``SUBCONSCIOUS_VAULT``，**独立于**金融 Concept 知识库 vault。

P1 规则版：信号抽取由上层 agent 在对话里**逐轮**记进 session buffer（``subconscious note``），
本模块只做**确定性**聚合 / 去重 / 落盘——零 LLM / DuckDB / 联网依赖，可离线单测。

状态文件（运行时，已 gitignore）放在 ``users/<id>/.subconscious/``：

- ``active.json``             当前开启的会话（session_id / started_at / vault）；
- ``<session>.buffer.jsonl`` 逐轮信号缓冲（确认前**不**进 interactions.jsonl）。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence import userspace
from intelligence.services import interactions, judgments

ENV_VAULT = "SUBCONSCIOUS_VAULT"
STATE_DIRNAME = ".subconscious"
VAULT_SUBDIR = "潜意识"  # vault 内存放对话日志的子目录
# session_id 约束：字母/数字开头，仅 [A-Za-z0-9._-]，杜绝路径穿越（同 userspace 风格）。
_SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(text: Any) -> str:
    """归一化用于去重：去空白 + 小写。"""
    return re.sub(r"\s+", "", str(text or "")).lower()


def _clean_terms(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for v in values or []:
        s = str(v).strip()
        if not s:
            continue
        key = _norm(s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def default_session_id(now: datetime | None = None) -> str:
    return (now or _now()).strftime("%Y-%m-%d-%H%M")


def _safe_session_id(session_id: str) -> str:
    sid = str(session_id).strip()
    if sid in {".", ".."} or "/" in sid or "\\" in sid or not _SESSION_RE.match(sid):
        raise ValueError(f"非法 session id：{session_id!r}（只允许字母数字与 . _ -，需以字母/数字开头）")
    return sid


# --------------------------------------------------------------------------- #
# 状态：active 标记 + session buffer
# --------------------------------------------------------------------------- #
def _state_dir(us: userspace.UserSpace) -> Path:
    return us.root / STATE_DIRNAME


def _active_path(us: userspace.UserSpace) -> Path:
    return _state_dir(us) / "active.json"


def _buffer_path(us: userspace.UserSpace, session_id: str) -> Path:
    return _state_dir(us) / f"{_safe_session_id(session_id)}.buffer.jsonl"


def load_active(us: userspace.UserSpace) -> dict[str, Any] | None:
    p = _active_path(us)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _resolve_session(us: userspace.UserSpace, session_id: str | None) -> str:
    if session_id:
        return _safe_session_id(session_id)
    active = load_active(us)
    if active and active.get("session_id"):
        return _safe_session_id(str(active["session_id"]))
    raise ValueError("没有进行中的潜意识会话；先 `subconscious start`（或显式 --session）")


def start_session(
    us: userspace.UserSpace,
    *,
    session_id: str | None = None,
    vault: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """开启潜意识模式：写 active 标记 + 建空 buffer。"""
    now = now or _now()
    sid = _safe_session_id(session_id) if session_id else default_session_id(now)
    sd = _state_dir(us)
    sd.mkdir(parents=True, exist_ok=True)
    _buffer_path(us, sid).touch(exist_ok=True)
    state: dict[str, Any] = {
        "session_id": sid,
        "started_at": now.isoformat(timespec="seconds"),
        "buffer": str(_buffer_path(us, sid)),
        "vault": vault or None,
    }
    _active_path(us).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def append_signal(
    us: userspace.UserSpace,
    *,
    session_id: str | None = None,
    kind: str,
    themes: list[str] | None = None,
    stocks: list[str] | None = None,
    question: str | None = None,
    quote: str | None = None,
    memo: str | None = None,
    note: str | None = None,
    weight: float | None = None,
    rating: float | None = None,
    ts: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """把一条本轮信号 append 到 session buffer（确认前**不**进 interactions.jsonl）。"""
    sid = _resolve_session(us, session_id)
    rec: dict[str, Any] = {
        "ts": ts or (now or _now()).isoformat(timespec="seconds"),
        "kind": str(kind or "").strip().lower(),
        "themes": _clean_terms(themes),
        "stocks": _clean_terms(stocks),
    }
    if question and str(question).strip():
        rec["question"] = str(question).strip()
    if quote and str(quote).strip():
        rec["quote"] = str(quote).strip()
    if memo and str(memo).strip():
        rec["memo"] = str(memo).strip()
    if note and str(note).strip():
        rec["note"] = str(note).strip()
    if weight is not None:
        rec["weight"] = float(weight)
    if rating is not None:
        rec["rating"] = float(rating)
    buf = _buffer_path(us, sid)
    buf.parent.mkdir(parents=True, exist_ok=True)
    with buf.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load_buffer(us: userspace.UserSpace, session_id: str) -> list[dict[str, Any]]:
    p = _buffer_path(us, session_id)
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


# --------------------------------------------------------------------------- #
# 回读巩固 (consolidation)：buffer -> 去重聚合 -> 记忆提案
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MemoryRow:
    """一条巩固后的记忆：某题材/个股在某 kind 上的净信号。"""

    target: str  # 'theme' | 'stock'
    label: str
    kind: str
    weight: float
    count: int
    sample_question: str | None = None
    sample_quote: str | None = None


@dataclass(frozen=True)
class Proposal:
    """退出时给用户确认的「记忆提案」（diff），review 与 commit 共用同一份内容。"""

    user_id: str
    session_id: str
    turns: int
    rows: list[MemoryRow]
    questions: list[str]
    memos: list[str]
    markdown: str
    generated_at: str
    judgments: list[dict[str, Any]] = field(default_factory=list)


def consolidate(
    buffer: list[dict[str, Any]],
    *,
    user_id: str,
    session_id: str,
    now: datetime | None = None,
) -> Proposal:
    """把 buffer「回读」成记忆提案：按 (题材/个股, kind) 去重，repeat 记 count 不叠权。"""
    now = now or _now()
    # (target, norm, kind) -> 累积
    agg: dict[tuple[str, str, str], dict[str, Any]] = {}
    questions: list[str] = []
    qseen: set[str] = set()
    memos: list[str] = []
    mseen: set[str] = set()
    judgment_items: list[dict[str, Any]] = []
    for rec in buffer:
        if not isinstance(rec, dict):
            continue
        kind = str(rec.get("kind") or "").strip().lower()
        if not kind:
            continue
        q = str(rec.get("question") or "").strip()
        if q:
            qn = _norm(q)
            if qn not in qseen:
                qseen.add(qn)
                questions.append(q)
        m = str(rec.get("memo") or "").strip()
        if m:
            mn = _norm(m)
            if mn not in mseen:
                mseen.add(mn)
                memos.append(m)
                judgment_items.append(
                    {
                        "memo": m,
                        "themes": _clean_terms(rec.get("themes")),
                        "stocks": _clean_terms(rec.get("stocks")),
                    }
                )
        quote = str(rec.get("quote") or "").strip() or None
        explicit_weight = rec.get("weight")
        rating = rec.get("rating")
        for target, fieldname in (("theme", "themes"), ("stock", "stocks")):
            for raw in rec.get(fieldname) or []:
                label = str(raw).strip()
                if not label:
                    continue
                key = (target, _norm(label), kind)
                slot = agg.get(key)
                if slot is None:
                    weight = interactions.resolve_weight(kind, weight=explicit_weight, rating=rating)
                    slot = {
                        "label": label,
                        "weight": round(float(weight), 4),
                        "count": 0,
                        "question": q or None,
                        "quote": quote,
                    }
                    agg[key] = slot
                slot["count"] += 1
                if not slot["question"] and q:
                    slot["question"] = q
                if not slot["quote"] and quote:
                    slot["quote"] = quote

    rows = [
        MemoryRow(
            target=target,
            label=slot["label"],
            kind=kind,
            weight=slot["weight"],
            count=slot["count"],
            sample_question=slot["question"],
            sample_quote=slot["quote"],
        )
        for (target, _norm_label, kind), slot in agg.items()
    ]
    # 排序：正信号在前，再按 target / label 稳定排序，确定性可复现。
    rows.sort(key=lambda r: (-r.weight, r.target, r.label, r.kind))

    proposal = Proposal(
        user_id=user_id,
        session_id=session_id,
        turns=len(buffer),
        rows=rows,
        questions=questions,
        memos=memos,
        markdown="",
        generated_at=now.isoformat(timespec="seconds"),
        judgments=judgment_items,
    )
    md = build_markdown(proposal)
    return Proposal(
        user_id=user_id,
        session_id=session_id,
        turns=len(buffer),
        rows=rows,
        questions=questions,
        memos=memos,
        markdown=md,
        generated_at=proposal.generated_at,
        judgments=judgment_items,
    )


def build_markdown(proposal: Proposal) -> str:
    """渲染人类层 Obsidian 日志（带 ``[[题材]]`` 反链，长成你的个人兴趣图谱）。"""
    date = proposal.session_id[:10]
    lines: list[str] = [
        "---",
        f"date: {date}",
        "mode: subconscious",
        f"user: {proposal.user_id}",
        f"session: {proposal.session_id}",
        f"turns: {proposal.turns}",
        f"signals: {len(proposal.rows)}",
        "---",
        "",
        f"# 潜意识对话 {date}",
        "",
    ]
    if proposal.questions:
        lines.append("## 它问我的（foresight）")
        for i, q in enumerate(proposal.questions, 1):
            lines.append(f"{i}. {q}")
        lines.append("")
    if proposal.memos:
        lines.append("## 深挖纪要")
        for i, m in enumerate(proposal.memos):
            if i:
                lines.append("")
            lines.append(m)
        lines.append("")
    lines.append("## 这轮沉淀的信号")
    if proposal.rows:
        for r in proposal.rows:
            cnt = f" ×{r.count}" if r.count > 1 else ""
            quote = f" ·「{r.sample_quote}」" if r.sample_quote else ""
            lines.append(f"- [[{r.label}]] {r.weight:+g} ({r.kind}{cnt}){quote}")
    else:
        lines.append("- （本轮无信号）")
    lines.append("")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# 落盘 (commit)：双层写入 + 归档 buffer
# --------------------------------------------------------------------------- #
def resolve_vault(us: userspace.UserSpace, *, explicit: str | None = None) -> tuple[Path, bool]:
    """解析沉淀 vault 路径：显式 > active.json > env SUBCONSCIOUS_VAULT > 回退。

    返回 ``(vault_path, is_fallback)``；回退路径在 ``users/<id>/_vault``（已 gitignore，
    仅云端合成验证用，真实落地请指 ``--vault`` / ``SUBCONSCIOUS_VAULT``）。
    """
    cand = explicit
    if not cand:
        active = load_active(us)
        if active:
            cand = active.get("vault")
    if not cand:
        cand = os.environ.get(ENV_VAULT)
    if cand:
        return Path(str(cand)).expanduser(), False
    return us.root / "_vault", True


@dataclass(frozen=True)
class CommitResult:
    interactions_path: Path
    written_records: int
    note_path: Path
    vault_is_fallback: bool
    session_id: str
    judgments_path: Path | None = None
    judgments_written: int = 0


def commit(
    us: userspace.UserSpace,
    proposal: Proposal,
    *,
    vault: str | None = None,
    now: datetime | None = None,
) -> CommitResult:
    """确认后落盘：机器层 interactions.jsonl + 核心判断台账 judgments.jsonl + 人类层 Obsidian 日志。"""
    now = now or _now()
    ts = now.isoformat(timespec="seconds")
    written = 0
    for r in proposal.rows:
        interactions.record_interaction(
            us.interactions_path,
            kind=r.kind,
            themes=[r.label] if r.target == "theme" else None,
            stocks=[r.label] if r.target == "stock" else None,
            weight=r.weight,  # 显式传：保证「确认的」与「落盘的」权重一致
            question=r.sample_question,
            note=f"subconscious#{proposal.session_id}",
            ts=ts,
        )
        written += 1

    # 核心判断台账（机器可读）：让 foresight 下轮发问能站在旧判断上往前推。
    judgments_written = 0
    judgments_path: Path | None = None
    for j in proposal.judgments:
        memo = str(j.get("memo") or "").strip()
        if not memo:
            continue
        judgments_path, _ = judgments.record_judgment(
            us.judgments_path,
            memo=memo,
            themes=j.get("themes"),
            stocks=j.get("stocks"),
            session_id=proposal.session_id,
            ts=ts,
        )
        judgments_written += 1

    vault_path, is_fallback = resolve_vault(us, explicit=vault)
    note_path = vault_path / VAULT_SUBDIR / f"{proposal.session_id}.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(proposal.markdown, encoding="utf-8")

    return CommitResult(
        interactions_path=us.interactions_path,
        written_records=written,
        note_path=note_path,
        vault_is_fallback=is_fallback,
        session_id=proposal.session_id,
        judgments_path=judgments_path,
        judgments_written=judgments_written,
    )


def archive_session(us: userspace.UserSpace, session_id: str) -> None:
    """落盘后收尾：buffer 改名归档 + 清掉 active 标记。"""
    sid = _safe_session_id(session_id)
    buf = _buffer_path(us, sid)
    if buf.exists():
        done = buf.with_suffix(".done.jsonl")
        try:
            buf.replace(done)
        except OSError:  # pragma: no cover - defensive
            pass
    active = load_active(us)
    if active and str(active.get("session_id")) == sid:
        _active_path(us).unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# 提案渲染（CLI / review / commit 预览共用）
# --------------------------------------------------------------------------- #
def render_proposal(
    proposal: Proposal,
    *,
    interactions_path: Path,
    note_path: Path,
    vault_is_fallback: bool,
    applied: bool = False,
) -> str:
    head = "已落盘" if applied else "本轮潜意识记忆提案（确认后落盘）"
    lines = [f"{head}（session {proposal.session_id}，{proposal.turns} 轮）："]
    lines.append(f"机器层 → {interactions_path}（{len(proposal.rows)} 条）")
    if proposal.rows:
        for r in proposal.rows:
            cnt = f" ×{r.count}" if r.count > 1 else ""
            sign = "+" if r.weight >= 0 else "−"
            tag = "题材" if r.target == "theme" else "个股"
            lines.append(f"  {sign} {tag} {r.label:<8} {r.kind:<8} {r.weight:+g}{cnt}")
    else:
        lines.append("  （本轮无信号）")
    fb = "（回退路径，仅验证用；真实落地请指 --vault / SUBCONSCIOUS_VAULT）" if vault_is_fallback else ""
    lines.append(f"人类层 → {note_path}{fb}")
    extras: list[str] = []
    if proposal.questions:
        extras.append(f"{len(proposal.questions)} 条发问")
    if proposal.memos:
        extras.append(f"{len(proposal.memos)} 段深挖纪要")
    if extras:
        lines.append("  日志含：" + "、".join(extras))
    if not applied:
        lines.append("")
        lines.append("确认落盘：`subconscious commit --apply`（缺省只预览）。")
    return "\n".join(lines) + "\n"
