"""dream-loop transcript collector（C-1A-S0）。

把对话源（飞书 / claude-code / claude-mem / windsurf / devin）归一化成统一 schema，脱敏后写入 transcript store：

- ``<store>/<date>/<source>-<session>.jsonl``  —— 正文（已脱敏），**gitignore**，本地留存；
- ``<store>/manifest.jsonl``                    —— 每个 (date, source, session) 一条元数据，可审计、可提交；
- ``<store>/digest-<date>.md``                  —— 当天脱敏摘要，**可提交**，供推理半读取。

设计要点
========
- **归一化 schema**（每行 JSONL）：``{ts, source, session_id, role, text, repo, tags, redacted}``。
- **脱敏硬门**：:func:`redact` 对密钥 / token / 持仓 / PII 打码；命中则 ``redacted=true``。
  S0 保守地对 store 正文与 digest 都脱敏（未来阶段可在本地保留更全正文）。
- **幂等**：输出文件内容与 manifest/digest 均确定性生成（``collected_at`` 取该桶最大 ts，
  manifest 按主键 upsert 不重复），重跑产生字节一致的结果。
- 纯函数（:func:`redact` / :func:`normalize_feishu_event` / :func:`build_digest`）可离线单测，
  IO 集中在 :func:`run_collect`。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCHEMA_VERSION = "s0"
KNOWN_SOURCES = ("claude-code", "claude-mem", "windsurf", "feishu", "devin")
_DIGEST_TEXT_LIMIT = 240  # digest 中单条文本截断长度


# --------------------------------------------------------------------------- #
# 归一化 schema
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TranscriptRecord:
    """统一 transcript 记录（决策1 §3 schema）。"""

    ts: str
    source: str
    session_id: str
    role: str
    text: str
    repo: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    redacted: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "ts": self.ts,
            "source": self.source,
            "session_id": self.session_id,
            "role": self.role,
            "text": self.text,
            "repo": self.repo,
            "tags": list(self.tags),
            "redacted": self.redacted,
        }

    def to_json_line(self) -> str:
        # sort_keys 保证字节稳定（幂等）。
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


# --------------------------------------------------------------------------- #
# 脱敏硬门（纯函数，可单测）
# --------------------------------------------------------------------------- #
# 赋值式密钥（保留键名、掩码值）：api_key= / secret: / token = / password 等。
_SECRET_ASSIGN = re.compile(
    r"(?i)\b(api[_-]?key|secret|access[_-]?token|app[_-]?secret|client[_-]?secret"
    r"|token|password|passwd|pwd)\b\s*[=:：]\s*[^\s,;，；]+"
)
# 形似 token / key 的字面量。
_SECRET_TOKEN_PATTERNS: Tuple[Tuple[str, "re.Pattern[str]"], ...] = (
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")),
    ("aws_akid", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
_PII_PATTERNS: Tuple[Tuple[str, "re.Pattern[str]"], ...] = (
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("phone_cn", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("id_card_cn", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
)
# 持仓 / 仓位 / 盈亏等关键词后跟到分隔符为止的内容（用户私有持仓信息）。
_HOLDING_PATTERN = re.compile(
    r"(持仓|仓位|建仓|清仓|减仓|加仓|成本价|买入价|持有|盈亏|浮盈|浮亏)"
    r"\s*[:：]?\s*[^\n，。；;、]*"
)


@dataclass(frozen=True)
class RedactResult:
    text: str
    redacted: bool
    categories: List[str]


def redact(text: Optional[str]) -> RedactResult:
    """对一段文本做脱敏：密钥 / token / PII / 持仓命中即打码。

    返回脱敏后文本、是否命中、命中类别（去重保序）。命中标记形如 ``[REDACTED:<cat>]``。
    """
    if not text:
        return RedactResult(text or "", False, [])
    cats: List[str] = []
    out = text

    def _assign_sub(m: "re.Match[str]") -> str:
        cats.append("secret")
        return f"{m.group(1)}=[REDACTED:secret]"

    out = _SECRET_ASSIGN.sub(_assign_sub, out)
    for name, pat in _SECRET_TOKEN_PATTERNS:
        if pat.search(out):
            out = pat.sub(f"[REDACTED:{name}]", out)
            cats.append(name)
    for name, pat in _PII_PATTERNS:
        if pat.search(out):
            out = pat.sub(f"[REDACTED:{name}]", out)
            cats.append(name)

    def _hold_sub(m: "re.Match[str]") -> str:
        cats.append("holdings")
        return f"{m.group(1)}[REDACTED:holdings]"

    out = _HOLDING_PATTERN.sub(_hold_sub, out)

    seen = set()
    uniq = [c for c in cats if not (c in seen or seen.add(c))]
    return RedactResult(out, bool(uniq), uniq)


def redact_record(rec: TranscriptRecord) -> TranscriptRecord:
    """返回 ``rec`` 的脱敏副本（text 打码、redacted/tags 更新）。"""
    res = redact(rec.text)
    tags = list(rec.tags)
    if res.redacted:
        for cat in res.categories:
            tag = f"redacted:{cat}"
            if tag not in tags:
                tags.append(tag)
    return TranscriptRecord(
        ts=rec.ts,
        source=rec.source,
        session_id=rec.session_id,
        role=rec.role,
        text=res.text,
        repo=rec.repo,
        tags=tags,
        redacted=rec.redacted or res.redacted,
    )


# --------------------------------------------------------------------------- #
# 源适配：飞书（S0 唯一源）
# --------------------------------------------------------------------------- #
def normalize_feishu_event(
    raw: Dict[str, object], repo: Optional[str] = None
) -> List[TranscriptRecord]:
    """把飞书 bot 落盘的一条原始事件归一化成 0~2 条 transcript 记录。

    原始事件（``feishu_bot`` 的 ``--transcript-log`` 产物）形如::

        {"ts","message_id","chat_id","message_type","text","reply","direction"}

    - 用户消息 -> ``role=user``（非文本类型用占位文本，便于追溯类型）；
    - bot 回复 -> ``role=assistant``。
    未脱敏（脱敏在 :func:`run_collect` 内统一施加）。
    """
    ts = _as_str(raw.get("ts")) or _now_iso()
    session_id = _as_str(raw.get("chat_id")) or _as_str(raw.get("session_id")) or "feishu"
    mtype = _as_str(raw.get("message_type"))
    base_tags = ["feishu"]
    if mtype:
        base_tags.append(f"type:{mtype}")

    records: List[TranscriptRecord] = []
    user_text = _as_str(raw.get("text"))
    if not user_text and mtype and mtype not in ("text", "post"):
        user_text = f"[{mtype} 非文本消息]"
    if user_text:
        records.append(
            TranscriptRecord(ts, "feishu", session_id, "user", user_text, repo, list(base_tags))
        )
    reply = _as_str(raw.get("reply"))
    if reply:
        records.append(
            TranscriptRecord(ts, "feishu", session_id, "assistant", reply, repo, list(base_tags))
        )
    return records


def _map_role(value: Optional[str]) -> str:
    """把各源的角色名归一化到 ``user | assistant | tool``。"""
    v = (value or "").strip().lower()
    if v in ("user", "human"):
        return "user"
    if v in ("assistant", "agent", "ai", "model", "devin"):
        return "assistant"
    if v in ("tool", "tool_use", "tool_result", "function", "system"):
        return "tool"
    return "user"


def _extract_content_text(content: object) -> Optional[str]:
    """从字符串 / content-block 列表里抽取可读文本。

    支持 Anthropic / Claude Code 风格的 block 列表：``text`` 取正文，
    ``tool_use`` / ``tool_result`` 折叠成占位文本（便于 loop 知道发生过工具调用，
    又不把冗长的工具 IO 灌进 digest）。
    """
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                btype = _as_str(block.get("type"))
                if isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif btype == "tool_use":
                    name = _as_str(block.get("name"))
                    parts.append(f"[tool_use {name}]" if name else "[tool_use]")
                elif btype == "tool_result":
                    inner = _extract_content_text(block.get("content"))
                    parts.append(f"[tool_result] {inner}" if inner else "[tool_result]")
        joined = "\n".join(p for p in parts if p).strip()
        return joined or None
    return None


# --------------------------------------------------------------------------- #
# 源适配：claude-code（本地会话历史 jsonl，逐行一条 message）
# --------------------------------------------------------------------------- #
def normalize_claude_code_event(
    raw: Dict[str, object], repo: Optional[str] = None
) -> List[TranscriptRecord]:
    """把 Claude Code 会话历史里的一行（一条 message）归一化成 0~1 条记录。

    典型行形如::

        {"type":"assistant","sessionId":"…","timestamp":"…","cwd":"…",
         "message":{"role":"assistant","content":[{"type":"text","text":"…"}, …]}}

    无可读文本（如纯 summary / 系统行）则跳过。``repo`` 缺省时从 ``cwd`` basename 推导。
    """
    msg = raw.get("message")
    msg = msg if isinstance(msg, dict) else {}
    role = _map_role(_as_str(raw.get("type")) or _as_str(msg.get("role")))
    text = _extract_content_text(msg.get("content", raw.get("content")))
    if not text:
        return []
    ts = _coerce_ts(raw.get("timestamp")) or _coerce_ts(raw.get("ts")) or _now_iso()
    session_id = (
        _as_str(raw.get("sessionId")) or _as_str(raw.get("session_id")) or "claude-code"
    )
    cwd = _as_str(raw.get("cwd"))
    rec_repo = repo or (_repo_from_path(cwd) if cwd else None)
    return [TranscriptRecord(ts, "claude-code", session_id, role, text, rec_repo, ["claude-code"])]


# --------------------------------------------------------------------------- #
# 源适配：claude-mem（观察记录，每条一个 observation）
# --------------------------------------------------------------------------- #
def normalize_claude_mem_observation(
    raw: Dict[str, object], repo: Optional[str] = None
) -> List[TranscriptRecord]:
    """把一条 claude-mem 观察（``get_observations`` 产物）归一化成 0~1 条记录。

    典型形如 ``{"id":"2546","timestamp":"…","type":"feature","title":"…","text":"…","session_id":"…"}``。
    观察是 agent 侧的记忆沉淀，统一记 ``role=assistant``，并打 ``obs:<type>`` 标签便于聚类。
    """
    title = _as_str(raw.get("title"))
    body = _as_str(raw.get("text")) or _as_str(raw.get("content"))
    text = f"{title}：{body}" if (title and body) else (title or body)
    if not text:
        return []
    ts = _coerce_ts(raw.get("timestamp")) or _coerce_ts(raw.get("created_at")) or _now_iso()
    obs_id = _as_str(raw.get("id"))
    session_id = (
        _as_str(raw.get("session_id")) or _as_str(raw.get("sessionId")) or obs_id or "claude-mem"
    )
    tags = ["claude-mem"]
    otype = _as_str(raw.get("type"))
    if otype:
        tags.append(f"obs:{otype}")
    rec_repo = repo or _as_str(raw.get("repo")) or _as_str(raw.get("project"))
    return [TranscriptRecord(ts, "claude-mem", session_id, "assistant", text, rec_repo, tags)]


# --------------------------------------------------------------------------- #
# 源适配：windsurf（Cascade 历史，一条 = 一个会话，内含 messages）
# --------------------------------------------------------------------------- #
def normalize_windsurf_event(
    raw: Dict[str, object], repo: Optional[str] = None
) -> List[TranscriptRecord]:
    """把一个 Windsurf Cascade 会话归一化成 0~N 条记录。

    会话形如 ``{"id":"…","workspace":"…","messages":[{"role":"user","content":"…","timestamp":"…"}, …]}``。
    也兼容「一行就是一条消息」的扁平形态（无 ``messages`` 列表时把 ``raw`` 当单条消息）。
    """
    session_id = (
        _as_str(raw.get("id"))
        or _as_str(raw.get("conversationId"))
        or _as_str(raw.get("session_id"))
        or "windsurf"
    )
    rec_repo = repo or _as_str(raw.get("repo")) or _repo_from_path(_as_str(raw.get("workspace")) or "")
    conv_ts = _coerce_ts(raw.get("ts")) or _coerce_ts(raw.get("timestamp"))
    messages = raw.get("messages")
    if not isinstance(messages, list):
        messages = [raw]
    out: List[TranscriptRecord] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        text = _extract_content_text(m.get("content")) or _as_str(m.get("text"))
        if not text:
            continue
        role = _map_role(_as_str(m.get("role")) or _as_str(m.get("sender")))
        ts = _coerce_ts(m.get("timestamp")) or _coerce_ts(m.get("ts")) or conv_ts or _now_iso()
        out.append(TranscriptRecord(ts, "windsurf", session_id, role, text, rec_repo, ["windsurf"]))
    return out


# --------------------------------------------------------------------------- #
# 源适配：devin（Devin API/MCP 拉取的 session 详情，一条 = 一个 session）
# --------------------------------------------------------------------------- #
def _devin_role(mtype: Optional[str]) -> str:
    v = (mtype or "").strip().lower()
    if "user" in v:
        return "user"
    if "devin" in v or "assistant" in v or "agent" in v:
        return "assistant"
    return "tool"


def normalize_devin_session(
    raw: Dict[str, object], repo: Optional[str] = None
) -> List[TranscriptRecord]:
    """把一个 Devin session（含 messages 列表）归一化成 0~N 条记录。

    session 形如 ``{"session_id":"…","messages":[{"type":"user_message","message":"…","timestamp":"…"}, …]}``。
    ``user_message``→user、``devin_message``→assistant、其余（工具/系统事件）→tool。
    """
    messages = raw.get("messages")
    if not isinstance(messages, list):
        return []
    session_id = (
        _as_str(raw.get("session_id"))
        or _as_str(raw.get("sessionId"))
        or _as_str(raw.get("id"))
        or "devin"
    )
    rec_repo = repo or _as_str(raw.get("repo"))
    out: List[TranscriptRecord] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        text = (
            _as_str(m.get("message"))
            or _extract_content_text(m.get("content"))
            or _as_str(m.get("text"))
        )
        if not text:
            continue
        mtype = _as_str(m.get("type")) or _as_str(m.get("role"))
        role = _devin_role(mtype)
        ts = _coerce_ts(m.get("timestamp")) or _coerce_ts(m.get("ts")) or _now_iso()
        tags = ["devin"]
        if mtype:
            tags.append(f"type:{mtype}")
        out.append(TranscriptRecord(ts, "devin", session_id, role, text, rec_repo, tags))
    return out


_NORMALIZERS = {
    "feishu": normalize_feishu_event,
    "claude-code": normalize_claude_code_event,
    "claude-mem": normalize_claude_mem_observation,
    "windsurf": normalize_windsurf_event,
    "devin": normalize_devin_session,
}


def _as_str(val: object) -> Optional[str]:
    if isinstance(val, str):
        s = val.strip()
        return s or None
    if isinstance(val, (int, float)):
        return str(val)
    return None


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _coerce_ts(val: object) -> Optional[str]:
    """把时间字段归一化成字符串 ts。

    字符串原样返回（假定已是 ISO8601）；数字按 epoch 秒/毫秒转本地时区 ISO8601。
    """
    if isinstance(val, str):
        s = val.strip()
        return s or None
    if isinstance(val, bool):  # bool 是 int 子类，先挡掉
        return None
    if isinstance(val, (int, float)):
        secs = float(val)
        if secs > 1e12:  # 毫秒
            secs /= 1000.0
        try:
            return datetime.fromtimestamp(secs).astimezone().isoformat(timespec="seconds")
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _repo_from_path(path: str) -> Optional[str]:
    name = Path(path).name
    return name or None


def _sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", name) or "x"


# --------------------------------------------------------------------------- #
# digest（脱敏摘要，可提交）
# --------------------------------------------------------------------------- #
def build_digest(date: str, records: List[TranscriptRecord]) -> str:
    """由（已脱敏的）记录构建当日 Markdown 摘要。"""
    total = len(records)
    n_redacted = sum(1 for r in records if r.redacted)
    by_session: "Dict[str, List[TranscriptRecord]]" = {}
    sources = set()
    for r in records:
        by_session.setdefault(r.session_id, []).append(r)
        sources.add(r.source)

    lines: List[str] = []
    lines.append(f"# Transcript Digest · {date}")
    lines.append("")
    lines.append(
        "> dream-loop C-1A-S0 自动生成。正文 jsonl 已 gitignore，本摘要为**脱敏版**，可提交。"
    )
    lines.append(
        f"> 源={','.join(sorted(sources)) or '-'} · 会话={len(by_session)} · "
        f"记录={total} · 命中脱敏={n_redacted}"
    )
    lines.append("")
    lines.append("## 概览")
    lines.append("")
    lines.append("| 会话 | 记录数 | 脱敏数 |")
    lines.append("|---|---|---|")
    for sess in sorted(by_session):
        recs = by_session[sess]
        lines.append(f"| {sess} | {len(recs)} | {sum(1 for r in recs if r.redacted)} |")
    lines.append("")
    lines.append("## 对话摘录（脱敏）")
    for sess in sorted(by_session):
        lines.append("")
        lines.append(f"### 会话 `{sess}`")
        for r in by_session[sess]:
            text = r.text.replace("\n", " ").strip()
            if len(text) > _DIGEST_TEXT_LIMIT:
                text = text[:_DIGEST_TEXT_LIMIT] + "…"
            flag = " ⟨脱敏⟩" if r.redacted else ""
            lines.append(f"- `{r.ts}` **{r.role}**{flag}: {text}")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# manifest（可审计元数据）
# --------------------------------------------------------------------------- #
def _read_manifest(store: Path) -> List[Dict[str, object]]:
    path = store / "manifest.jsonl"
    if not path.is_file():
        return []
    entries: List[Dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def _manifest_key(e: Dict[str, object]) -> Tuple[str, str, str]:
    return (str(e.get("date")), str(e.get("source")), str(e.get("session_id")))


def _write_manifest(store: Path, entries: List[Dict[str, object]]) -> None:
    ordered = sorted(entries, key=_manifest_key)
    body = "".join(
        json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n" for e in ordered
    )
    (store / "manifest.jsonl").write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------- #
# 采集主流程（IO）
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CollectOptions:
    events_path: Optional[str] = None
    store_dir: Optional[str] = None
    source: str = "feishu"
    repo: Optional[str] = None
    digest_only: bool = False


def resolve_store_dir(explicit: Optional[str]) -> Path:
    """解析 transcript store 根目录。

    优先级：显式 > env ``DREAM_TRANSCRIPT_STORE`` > 知识库 ``raw/transcripts``
    （由 ``KNOWLEDGE_WIKI`` 推导或 Mac 默认路径）> 本仓 ``intelligence/dream/_local_store``（gitignore 回退）。
    """
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("DREAM_TRANSCRIPT_STORE")
    if env:
        return Path(env).expanduser()
    kb_wiki = os.environ.get("KNOWLEDGE_WIKI")
    if kb_wiki:
        return Path(kb_wiki).expanduser().parent / "raw" / "transcripts"
    default_kb = Path("/Users/lbq/Desktop/c c/知识库")
    if default_kb.exists():
        return default_kb / "raw" / "transcripts"
    return Path(__file__).resolve().parents[2] / "intelligence" / "dream" / "_local_store"


def read_events(events_path: str) -> List[Dict[str, object]]:
    """读取原始事件 jsonl（跳过空行 / 坏行）。"""
    path = Path(events_path).expanduser()
    if not path.is_file():
        raise SystemExit(f"事件文件不存在：{path}")
    out: List[Dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _affected_dates_from_store(store: Path) -> List[str]:
    if not store.is_dir():
        return []
    return sorted(
        p.name for p in store.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)
    )


def _load_date_records(store: Path, date: str) -> List[TranscriptRecord]:
    date_dir = store / date
    records: List[TranscriptRecord] = []
    if not date_dir.is_dir():
        return records
    for fp in sorted(date_dir.glob("*.jsonl")):
        for line in fp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            records.append(
                TranscriptRecord(
                    ts=str(obj.get("ts", "")),
                    source=str(obj.get("source", "")),
                    session_id=str(obj.get("session_id", "")),
                    role=str(obj.get("role", "")),
                    text=str(obj.get("text", "")),
                    repo=obj.get("repo") if isinstance(obj.get("repo"), str) else None,
                    tags=[t for t in obj.get("tags", []) if isinstance(t, str)],
                    redacted=bool(obj.get("redacted", False)),
                )
            )
    return records


def _regenerate_digest(store: Path, date: str) -> Optional[str]:
    records = _load_date_records(store, date)
    if not records:
        return None
    digest = build_digest(date, records)
    (store / f"digest-{date}.md").write_text(digest, encoding="utf-8")
    return f"digest-{date}.md"


def run_collect(options: CollectOptions) -> Dict[str, object]:
    """采集主流程：读事件 → 归一化 → 脱敏 → 写 store + manifest + digest。

    返回机器可读摘要 dict。``digest_only=True`` 时跳过 events，仅按现有 store 重建 digest。
    """
    store = resolve_store_dir(options.store_dir)
    store.mkdir(parents=True, exist_ok=True)

    if options.digest_only:
        dates = _affected_dates_from_store(store)
        digests = [d for d in (_regenerate_digest(store, dt) for dt in dates) if d]
        return {
            "store_dir": str(store),
            "mode": "digest-only",
            "dates": dates,
            "digests": digests,
        }

    if options.source not in _NORMALIZERS:
        raise SystemExit(
            f"暂不支持的源：{options.source}（可选：{', '.join(sorted(_NORMALIZERS))}）"
        )
    if not options.events_path:
        raise SystemExit("缺少 --events（原始事件 jsonl）")

    normalize = _NORMALIZERS[options.source]
    events = read_events(options.events_path)

    # 归一化 + 脱敏，按 (date, session_id) 分桶。
    buckets: "Dict[Tuple[str, str], List[TranscriptRecord]]" = {}
    for raw in events:
        for rec in normalize(raw, options.repo):
            rrec = redact_record(rec)
            date = rrec.ts[:10] if len(rrec.ts) >= 10 else _now_iso()[:10]
            buckets.setdefault((date, rrec.session_id), []).append(rrec)

    manifest = {_manifest_key(e): e for e in _read_manifest(store)}
    written: List[Dict[str, object]] = []
    affected_dates = set()

    for (date, session_id), recs in sorted(buckets.items()):
        date_dir = store / date
        date_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{options.source}-{_sanitize(session_id)}.jsonl"
        content = "".join(r.to_json_line() + "\n" for r in recs)
        (date_dir / fname).write_text(content, encoding="utf-8")
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        collected_at = max(r.ts for r in recs)
        n_redacted = sum(1 for r in recs if r.redacted)
        entry = {
            "schema": SCHEMA_VERSION,
            "date": date,
            "source": options.source,
            "session_id": session_id,
            "file": f"{date}/{fname}",
            "n_records": len(recs),
            "n_redacted": n_redacted,
            "sha256": sha,
            "collected_at": collected_at,
        }
        manifest[(date, options.source, session_id)] = entry
        written.append(entry)
        affected_dates.add(date)

    _write_manifest(store, list(manifest.values()))

    digests = [d for d in (_regenerate_digest(store, dt) for dt in sorted(affected_dates)) if d]

    return {
        "store_dir": str(store),
        "mode": "collect",
        "source": options.source,
        "events_read": len(events),
        "records_written": sum(int(e["n_records"]) for e in written),
        "records_redacted": sum(int(e["n_redacted"]) for e in written),
        "files": [e["file"] for e in written],
        "dates": sorted(affected_dates),
        "digests": digests,
    }


def render_summary(summary: Dict[str, object]) -> str:
    """人类可读摘要。"""
    lines = [f"[dream-collect] store={summary.get('store_dir')}"]
    if summary.get("mode") == "digest-only":
        lines.append(f"  仅重建 digest：{', '.join(summary.get('digests') or []) or '(无)'}")
    else:
        lines.append(
            f"  源={summary.get('source')} 读事件={summary.get('events_read')} "
            f"写记录={summary.get('records_written')} 命中脱敏={summary.get('records_redacted')}"
        )
        lines.append(f"  日期={', '.join(summary.get('dates') or []) or '(无)'}")
        lines.append(f"  digest={', '.join(summary.get('digests') or []) or '(无)'}")
    return "\n".join(lines) + "\n"
