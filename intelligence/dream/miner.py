"""dream-mine：Workbench 会话夜间挖掘（提案-only，dream loop 重定向 P0）。

设计稿：``docs/superpowers/specs/2026-08-26-dream-loop-repoint-design.md``。

数据流::

    conversations/conv_*/{conversation.json,messages.jsonl}   （只读）
      → collector workbench 源（归一化 + 脱敏硬门 + store/manifest/digest，全复用）
      → miner（LLM 严格 JSON 挖 user 侧判断/兴趣；水位=updated_at；预算+声明式截断）
      → 提案：潜意识 buffer（session=dream-<date>）+ vault 人读 md + mining-manifest 游标
      → 人工 `subconscious review/commit --session dream-<date> --apply` 才落台账

红线（写死，选项不可翻转）：

- 挖掘输入只来自已脱敏 transcript store（:func:`collector.session_store_files`），
  miner 从结构上摸不到原文；
- suggest-only：本模块**绝不**写 judgments / interactions / corrections / 画像，
  只 append 潜意识 buffer（:func:`subconscious.append_signal` 显式 session，不动 active 标记）；
- 无 LLM key 不编造：降级为只采集入库，提案数 0，降级标记写进 vault md；
  降级/失败的会话**不更新水位**，下晚自动重试；
- 不碰 git、不碰 DuckDB、不读 workbench.sqlite3。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from intelligence import userspace
from intelligence.dream import collector
from intelligence.services import llm_refine, subconscious

MINING_MANIFEST = "mining-manifest.jsonl"
PROPOSAL_VAULT_SUBDIR = "潜意识提案"
NOTE_PREFIX = "dream-mine conv:"
_ALLOWED_KINDS = ("judgment", "ask", "skip")
_MAX_SIGNALS_PER_CONVERSATION = 3
_ASSISTANT_HEAD_CHARS = 80
_MAX_TERMS = 5

# 与 forecast_learning 同一注入模式：测试/调用方可换掉真实 LLM。
LLMComplete = Callable[..., Tuple[Optional[str], Any, str]]

_SYSTEM_PROMPT = (
    "你是个人研究台账的记忆挖掘器。输入是一段人机对话的脱敏节选，"
    "你只从「用户:」开头的发言里提取值得长期记住的信号；"
    "「助手(片段):」行只用来理解上下文，绝不把助手观点当用户判断。\n"
    '输出严格 JSON：{"signals":[{"kind":"judgment|ask|skip",'
    '"memo":"一句话判断（judgment 必填，用用户口径改写）",'
    '"question":"用户关心的问题（ask 必填）",'
    '"themes":["题材"],"stocks":["个股"],'
    '"quote":"逐字引用的用户原话（含 [REDACTED:*] 掩码时原样保留）",'
    '"confidence":0.0}]}\n'
    "规则：1) judgment=用户表达了自己的市场判断/方法论/纠偏；"
    "ask=用户反复或明确关心的问题；skip=用户明确否定/不看的方向（必须带 themes 或 stocks）。"
    '2) 拿不准就不要输出；没有信号输出 {"signals":[]}。'
    "3) 不输出寒暄、操作指令、与研究无关的内容。4) 每段对话最多 3 条。"
)


@dataclass(frozen=True)
class MineOptions:
    conversations_dir: str
    # 显式必填：resolve_store_dir 默认链含陈旧硬编码路径，部署不得依赖（设计稿 §7）。
    store_dir: str
    user: Optional[str] = None
    vault: Optional[str] = None
    since_days: int = 7
    max_sessions: int = 40
    max_signals: int = 10
    max_chars_per_conversation: int = 4000
    date: Optional[str] = None
    use_llm: bool = True
    dry_run: bool = False


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _clean_terms(values: Any) -> List[str]:
    out: List[str] = []
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
        if len(out) >= _MAX_TERMS:
            break
    return out


# --------------------------------------------------------------------------- #
# 挖掘水位（mining manifest）：按 (conversation_id, updated_at) 判增量
# --------------------------------------------------------------------------- #
def _read_mining_manifest(store: Path) -> Dict[str, Dict[str, Any]]:
    path = store / MINING_MANIFEST
    if not path.is_file():
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        cid = str(obj.get("conversation_id") or "").strip()
        if cid:
            out[cid] = obj
    return out


def _write_mining_manifest(store: Path, entries: Dict[str, Dict[str, Any]]) -> None:
    lines = [
        json.dumps(entries[cid], ensure_ascii=False, sort_keys=True) for cid in sorted(entries)
    ]
    text = "\n".join(lines) + ("\n" if lines else "")
    (store / MINING_MANIFEST).write_text(text, encoding="utf-8")


def scan_conversation_index(conversations_dir: str) -> List[Dict[str, str]]:
    """扫会话目录出 (conversation_id, updated_at) 索引；conversation.json 损坏的跳过。"""
    root = Path(conversations_dir).expanduser()
    if not root.is_dir():
        raise SystemExit(f"会话目录不存在：{root}")
    out: List[Dict[str, str]] = []
    for conv_dir in sorted(p for p in root.glob("conv_*") if p.is_dir()):
        meta = collector.read_conversation_meta(conv_dir)
        if meta is None:
            continue
        cid = str(meta.get("conversation_id") or conv_dir.name)
        updated = str(meta.get("updated_at") or meta.get("created_at") or "")
        out.append({"conversation_id": cid, "updated_at": updated})
    return out


def _select_sessions(
    index: List[Dict[str, str]],
    manifest: Dict[str, Dict[str, Any]],
    *,
    since_days: int,
    max_sessions: int,
    now: datetime,
) -> List[Dict[str, str]]:
    cutoff = now - timedelta(days=since_days) if since_days > 0 else None
    picked: List[Dict[str, str]] = []
    for entry in index:
        cid = entry["conversation_id"]
        updated = entry["updated_at"]
        if cutoff is not None:
            parsed = collector.parse_iso(updated)
            if parsed is not None and parsed < cutoff:
                continue
        mined = manifest.get(cid)
        if mined and str(mined.get("updated_at") or "") == updated:
            continue  # 水位一致 = 已挖过且无更新
        picked.append(entry)
    picked.sort(key=lambda e: e["updated_at"], reverse=True)
    return picked[:max_sessions]


# --------------------------------------------------------------------------- #
# 提示词构建（只喂已脱敏 store 正文；声明式截断，限定语在前）
# --------------------------------------------------------------------------- #
def _load_session_records(store: Path, session_id: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for fp in collector.session_store_files(store, "workbench", session_id):
        for line in fp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                records.append(obj)
    records.sort(key=lambda r: str(r.get("ts") or ""))
    return records


def _conversation_prompt(
    conv_id: str, records: List[Dict[str, Any]], *, max_chars: int
) -> Optional[str]:
    """把一段会话渲染成挖掘输入；没有任何用户侧发言时返回 None（跳过，不调 LLM）。"""
    lines: List[str] = []
    has_user = False
    for rec in records:
        role = str(rec.get("role") or "")
        text = str(rec.get("text") or "").strip()
        if not text:
            continue
        if role == "user":
            has_user = True
            lines.append(f"用户: {text}")
        elif role == "assistant":
            head = text[:_ASSISTANT_HEAD_CHARS]
            suffix = "…" if len(text) > _ASSISTANT_HEAD_CHARS else ""
            lines.append(f"助手(片段): {head}{suffix}")
    if not has_user:
        return None
    header = (
        f"会话 {conv_id}（以下为脱敏节选，已按预算截断："
        "用户侧发言完整保留，助手侧只保留片段开头）\n"
    )
    body = "\n".join(lines)
    if len(body) > max_chars:
        body = body[:max_chars] + "\n（节选到此截断）"
    return header + body


# --------------------------------------------------------------------------- #
# LLM 输出解析与校验（严格 JSON，解析失败=该会话零信号，绝不编造）
# --------------------------------------------------------------------------- #
def _parse_signals(content: str, conv_id: str) -> List[Dict[str, Any]]:
    payload = llm_refine._extract_json(content)
    raw_signals = payload.get("signals") if isinstance(payload, dict) else None
    if not isinstance(raw_signals, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw_signals[:_MAX_SIGNALS_PER_CONVERSATION]:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        if kind not in _ALLOWED_KINDS:
            continue
        memo = str(item.get("memo") or "").strip() or None
        question = str(item.get("question") or "").strip() or None
        quote = str(item.get("quote") or "").strip() or None
        themes = _clean_terms(item.get("themes"))
        stocks = _clean_terms(item.get("stocks"))
        if kind == "judgment" and not memo:
            continue
        if kind == "ask" and not question:
            continue
        if kind == "skip" and not (themes or stocks):
            continue
        try:
            confidence = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        out.append(
            {
                "conv_id": conv_id,
                "kind": kind,
                "memo": memo,
                "question": question,
                "quote": quote,
                "themes": themes,
                "stocks": stocks,
                "confidence": confidence,
            }
        )
    return out


def _dedup_key(kind: str, text: str, conv_id: str) -> Tuple[str, str, str]:
    return (str(kind), _norm(text), str(conv_id))


def _candidate_key(cand: Dict[str, Any]) -> Tuple[str, str, str]:
    text = cand.get("memo") or cand.get("question") or cand.get("quote") or ""
    return _dedup_key(cand["kind"], str(text), cand["conv_id"])


def _buffer_key(rec: Dict[str, Any]) -> Tuple[str, str, str]:
    note = str(rec.get("note") or "")
    conv_id = ""
    if NOTE_PREFIX in note:
        conv_id = note.split(NOTE_PREFIX, 1)[1].strip()
    text = rec.get("memo") or rec.get("question") or rec.get("quote") or ""
    return _dedup_key(str(rec.get("kind") or ""), str(text), conv_id)


# --------------------------------------------------------------------------- #
# vault 人读 md（确定性生成：由 buffer 当前全量重建，重跑字节一致）
# --------------------------------------------------------------------------- #
def _build_proposal_markdown(
    date: str,
    session_id: str,
    user_id: str,
    buffer: List[Dict[str, Any]],
    *,
    degraded_reason: Optional[str],
) -> str:
    lines: List[str] = [
        f"# 潜意识提案 · {date}",
        "",
        "> dream-mine 夜间从 Workbench 会话自动挖掘的候选信号（**未落台账**，suggest-only）。",
        f"> 复核：`python3 -m intelligence.cli subconscious review --session {session_id} --user {user_id}`",
        f"> 采纳：`python3 -m intelligence.cli subconscious commit --session {session_id} --user {user_id} --apply`",
        "",
    ]
    if degraded_reason:
        lines += [f"⚠ 降级：{degraded_reason}（本晚仅采集入库，未产新提案）", ""]
    if not buffer:
        lines += ["（暂无候选）", ""]
        return "\n".join(lines)
    kind_label = {"judgment": "判断", "ask": "关注", "skip": "排除"}
    for i, rec in enumerate(buffer, 1):
        kind = str(rec.get("kind") or "")
        label = kind_label.get(kind, kind)
        targets = "、".join(
            [*(rec.get("themes") or []), *(rec.get("stocks") or [])]
        )
        head = f"## {i}. [{label}] {targets}".rstrip()
        lines.append(head)
        memo = str(rec.get("memo") or "").strip()
        question = str(rec.get("question") or "").strip()
        quote = str(rec.get("quote") or "").strip()
        note = str(rec.get("note") or "").strip()
        if memo:
            lines.append(f"- 候选判断：{memo}")
        if question:
            lines.append(f"- 关心的问题：{question}")
        if quote:
            lines.append(f"- 原话（已脱敏）：> {quote}")
        if note:
            lines.append(f"- 溯源：{note}")
        lines.append("")
    return "\n".join(lines)


def _write_vault_note(
    us: "userspace.UserSpace",
    explicit_vault: Optional[str],
    date: str,
    session_id: str,
    buffer: List[Dict[str, Any]],
    *,
    degraded_reason: Optional[str],
) -> str:
    vault_path, _is_fallback = subconscious.resolve_vault(us, explicit=explicit_vault)
    note_path = vault_path / PROPOSAL_VAULT_SUBDIR / f"{date}.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        _build_proposal_markdown(
            date, session_id, us.user_id, buffer, degraded_reason=degraded_reason
        ),
        encoding="utf-8",
    )
    return str(note_path)


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def run_mine(
    options: MineOptions,
    *,
    llm_complete: Optional[LLMComplete] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or datetime.now().astimezone()
    date = options.date or now.strftime("%Y-%m-%d")
    session_id = f"dream-{date}"
    ts = now.isoformat(timespec="seconds")
    us = userspace.user_space(options.user)
    us.ensure_dir()
    store = Path(options.store_dir).expanduser()

    # 1) 采集：归一化 + 脱敏 + store/manifest/digest（幂等，全复用 collector）。
    collect_summary = collector.run_collect(
        collector.CollectOptions(
            store_dir=str(store),
            source="workbench",
            conversations_dir=options.conversations_dir,
            since_days=options.since_days,
        )
    )

    # 2) 选会话：updated_at 水位 + 窗口 + 上限。
    index = scan_conversation_index(options.conversations_dir)
    manifest = _read_mining_manifest(store)
    selected = _select_sessions(
        index,
        manifest,
        since_days=options.since_days,
        max_sessions=options.max_sessions,
        now=now,
    )

    # 3) 逐会话挖掘（输入只来自已脱敏 store）。
    complete = llm_complete or llm_refine.complete
    candidates: List[Dict[str, Any]] = []
    mined_entries: Dict[str, Dict[str, Any]] = {}
    degraded_reason: Optional[str] = None
    if not options.use_llm:
        degraded_reason = "--no-llm：跳过挖掘（仅采集入库）"
    else:
        for entry in selected:
            cid = entry["conversation_id"]
            records = _load_session_records(store, cid)
            prompt = _conversation_prompt(
                cid, records, max_chars=options.max_chars_per_conversation
            )
            if prompt is None:
                mined_entries[cid] = {
                    "conversation_id": cid,
                    "updated_at": entry["updated_at"],
                    "mined_at": ts,
                    "signals": 0,
                    "reason": "no-user-text",
                }
                continue
            content, _provider, reason = complete(
                [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                timeout=90.0,
                temperature=0.1,
            )
            if content is None:
                # 无 key / 预算不足 / 全 provider 失败：剩余会话不标水位，下晚重试。
                degraded_reason = reason or "LLM 不可用"
                break
            signals = _parse_signals(content, cid)
            candidates.extend(signals)
            mined_entries[cid] = {
                "conversation_id": cid,
                "updated_at": entry["updated_at"],
                "mined_at": ts,
                "signals": len(signals),
            }

    # 4) 全局截断（宁缺勿滥）+ 对既有 buffer 去重。
    candidates.sort(key=lambda c: (-c["confidence"], c["conv_id"]))
    capped = candidates[: options.max_signals]
    existing_keys = {_buffer_key(rec) for rec in subconscious.load_buffer(us, session_id)}
    accepted: List[Dict[str, Any]] = []
    for cand in capped:
        key = _candidate_key(cand)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        accepted.append(cand)

    # 5) 落提案（dry_run 全跳过）：buffer + 水位 + vault md。台账一个不碰。
    vault_note: Optional[str] = None
    if not options.dry_run:
        for cand in accepted:
            subconscious.append_signal(
                us,
                session_id=session_id,
                kind=cand["kind"],
                themes=cand["themes"],
                stocks=cand["stocks"],
                question=cand["question"],
                quote=cand["quote"],
                memo=cand["memo"],
                note=f"{NOTE_PREFIX}{cand['conv_id']}",
                ts=ts,
            )
        if mined_entries:
            manifest.update(mined_entries)
            _write_mining_manifest(store, manifest)
        buffer_after = subconscious.load_buffer(us, session_id)
        vault_note = _write_vault_note(
            us,
            options.vault,
            date,
            session_id,
            buffer_after,
            degraded_reason=degraded_reason,
        )

    return {
        "date": date,
        "session_id": session_id,
        "user": us.user_id,
        "store_dir": str(store),
        "collected_records": collect_summary.get("records_written", 0),
        "sessions_indexed": len(index),
        "sessions_selected": len(selected),
        "sessions_mined": len(mined_entries),
        "signals_candidates": len(candidates),
        "signals_appended": len(accepted),
        "degraded_reason": degraded_reason,
        "vault_note": vault_note,
        "dry_run": options.dry_run,
        "proposals": accepted,
    }


def render_mine_summary(summary: Dict[str, Any]) -> str:
    lines = [
        f"[dream-mine] {summary.get('date')} session={summary.get('session_id')} "
        f"user={summary.get('user')}",
        f"  采集记录={summary.get('collected_records')} "
        f"会话：索引 {summary.get('sessions_indexed')} / 入选 {summary.get('sessions_selected')} "
        f"/ 已挖 {summary.get('sessions_mined')}",
        f"  提案：候选 {summary.get('signals_candidates')} / 新增 {summary.get('signals_appended')}"
        + ("（dry-run 未落盘）" if summary.get("dry_run") else ""),
    ]
    if summary.get("degraded_reason"):
        lines.append(f"  ⚠ 降级：{summary.get('degraded_reason')}")
    if summary.get("vault_note"):
        lines.append(f"  提案清单：{summary.get('vault_note')}")
    if summary.get("signals_appended"):
        sid = summary.get("session_id")
        lines.append(
            f"  复核采纳：subconscious review/commit --session {sid} --apply（不 commit 不落台账）"
        )
    return "\n".join(lines) + "\n"
