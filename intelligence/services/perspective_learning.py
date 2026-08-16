"""Perspective Lab 学习闭环 (P1)：文章 → 结构化认知卡片 → 画像 patch → 人工确认写回。

设计文档：``docs/superpowers/specs/2026-07-03-perspective-lab-design.md`` §7.3 / §16 P1。
P0 的确定性核心（``perspective_lab.py``）保持不动，本模块只做「学」的那半边：

1. **卡片抽取**（``extract_cards``）：LLM 把单篇文章还原成可验证的决策规则
   （claims / reasoning_moves / risk_notes / profile_updates 候选）。
   无 LLM key 或输出无法解析时**明确报错、不写半成品**——绝不用确定性规则
   伪造一张"看起来像抽取结果"的卡片。
2. **patch 聚合**（``propose_patches``）：只聚合**引文逐字核验通过**的画像候选，
   按 (field, value) 去重成 pending patch。核验不过的候选留在卡片里供人工看，
   但不进入确认流（证据卫生：认不出来就 fail closed）。
3. **人工确认**（``review_patch``）：approve 才写 profile，并在 profile 的
   ``patch_history`` 留溯源；reject 只改 patch 状态。LLM 的输出永远只是候选，
   与 spec §13.3 的胜率驱动自动修正共用同一"人工门禁"原则。

数据落点（均在 ``perspectives/`` 内，gitignore 不进仓库）：

- ``articles/<pid>/cards/<article_id>.json``   单篇认知卡片（schema_version=1）
- ``patches/<pid>/<patch_id>.json``            画像 patch（pending/approved/rejected）

LLM 依赖通过 ``llm_complete`` 参数注入（默认走 ``llm_refine.complete``），
单测传假实现即可离线跑全链路。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from intelligence.userspace import UserSpace
from intelligence.services import perspective_lab

CARD_SCHEMA_VERSION = 1
PATCH_SCHEMA_VERSION = 1

# 只允许 LLM 候选进入这四个"字符串列表"画像字段。market_lenses / reasoning_patterns /
# evidence_hierarchy 是带结构或带顺序的字段，追加语义不成立，仍走人工编辑 JSON。
ALLOWED_PATCH_FIELDS = (
    "opportunity_preferences",
    "risk_triggers",
    "anti_patterns",
    "falsification_style",
)
_CLAIM_TYPES = ("market_phase", "theme", "stock", "risk", "method")
_ARTICLE_ID_RE = re.compile(r"^pa-[0-9a-f]{12}$")
PATCH_STATUSES = ("pending", "approved", "rejected")

# 抽取 prompt 里原文的上限。超过则截断，且截断声明写在正文**之前**
# （BUILD.md 模式：限定语排在被限定内容之前，模型先知道自己看到的是节选）。
MAX_ARTICLE_PROMPT_CHARS = 16000

# 引文核验的最短长度（空白归一后）。「复盘」「的」这类超短子串几乎在任何
# 文章里都能命中，逐字核验会形同虚设——引文太短等于没有出处。
MIN_QUOTE_CHARS = 6

_EXTRACT_SYSTEM_PROMPT = (
    "你是研究方法论蒸馏器。任务：从一篇市场观察/复盘文章中抽取作者的「认知框架」"
    "（怎么判断、看什么变量、如何证伪），不是复述文章内容，不学口癖。硬性要求："
    "1) 只依据原文，禁止补写原文没有的判断或数字；"
    "2) claims：抽取作者的核心判断，每条含 claim（一句话）、claim_type"
    "（market_phase/theme/stock/risk/method 之一）、evidence_used（作者支持该判断"
    "所引用的证据，数组）、falsifiers（作者给出的证伪条件，数组，原文没有就留空数组）；"
    "3) reasoning_moves：按出现顺序列出作者的推理步骤（先看什么、再看什么）；"
    "4) risk_notes：作者提示的风险或降权信号；"
    "5) profile_updates：从本文能提炼出的**可迁移**方法论条目，field 只能取 "
    "opportunity_preferences / risk_triggers / anti_patterns / falsification_style，"
    "value 是一条脱离本文具体个股也成立的规则，supporting_quote 必须是原文中"
    "逐字连续的一段（不超过 80 字，不得改写）；提炼不出就留空数组；"
    "6) 严格输出单个 JSON 对象："
    '{"claims":[],"reasoning_moves":[],"risk_notes":[],"profile_updates":[]}，'
    "不要输出 JSON 以外的任何文字。"
)

# llm_complete 契约：messages -> (content|None, provider_name, model_name, reason)。
# content 为 None 时 reason 解释原因（无 key / HTTP 失败 / 超时），调用方报错不落盘。
LlmComplete = Callable[[list[dict]], tuple[str | None, str, str, str]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_llm_complete(messages: list[dict]) -> tuple[str | None, str, str, str]:
    from intelligence.services import llm_refine

    content, provider, reason = llm_refine.complete(messages, temperature=0.1)
    return (
        content,
        provider.name if provider is not None else "",
        provider.model if provider is not None else "",
        reason,
    )


# --------------------------------------------------------------------------- #
# 路径：全部收口在 users/<user>/perspectives/ 内
# --------------------------------------------------------------------------- #
def cards_dir(us: UserSpace, perspective_id: str) -> Path:
    return perspective_lab.articles_dir(us, perspective_id) / "cards"


def card_path(us: UserSpace, perspective_id: str, article_id: str) -> Path:
    aid = str(article_id or "").strip()
    if not _ARTICLE_ID_RE.match(aid):
        raise ValueError(f"非法 article id：{article_id!r}（形如 pa-<12位hex>）")
    return cards_dir(us, perspective_id) / f"{aid}.json"


def patches_dir(us: UserSpace, perspective_id: str) -> Path:
    pid = perspective_lab.resolve_perspective_id(perspective_id)
    return perspective_lab.perspectives_root(us) / "patches" / pid


def patch_path(us: UserSpace, perspective_id: str, patch_id: str) -> Path:
    pid = str(patch_id or "").strip()
    if not re.match(r"^pp-[0-9a-f]{12}$", pid):
        raise ValueError(f"非法 patch id：{patch_id!r}（形如 pp-<12位hex>）")
    return patches_dir(us, perspective_id) / f"{pid}.json"


# --------------------------------------------------------------------------- #
# 卡片抽取
# --------------------------------------------------------------------------- #
def _parse_json_object(text: str) -> dict | None:
    """从 LLM 输出中解出单个 JSON 对象；解不出返回 None（调用方 fail closed）。"""
    text = str(text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _validate_card_payload(
    obj: dict[str, Any],
    article_text: str,
) -> tuple[dict[str, Any], list[str]]:
    """把 LLM 输出清洗成卡片正文；返回 (payload, issues)。

    - claim 缺正文的条目直接丢；claim_type 不在枚举内降为 ``other``；
    - profile_updates 的 field 不在白名单、value 为空的条目丢弃（记 issue）；
    - supporting_quote 做**逐字核验**（空白归一后必须是原文子串，且不短于
      ``MIN_QUOTE_CHARS``——超短子串在任何文章里都能命中，不构成出处），结果写进
      ``quote_verified``——核验不过的候选保留在卡片里供人工看，但 propose 阶段不采纳。
    """
    issues: list[str] = []
    claims: list[dict[str, Any]] = []
    for raw in obj.get("claims") if isinstance(obj.get("claims"), list) else []:
        if not isinstance(raw, dict):
            continue
        claim = str(raw.get("claim") or "").strip()
        if not claim:
            issues.append("丢弃一条缺 claim 正文的条目")
            continue
        ctype = str(raw.get("claim_type") or "").strip()
        claims.append(
            {
                "claim": claim,
                "claim_type": ctype if ctype in _CLAIM_TYPES else "other",
                "evidence_used": _str_list(raw.get("evidence_used")),
                "falsifiers": _str_list(raw.get("falsifiers")),
            }
        )

    norm_text = _norm(article_text)
    updates: list[dict[str, Any]] = []
    raw_updates = obj.get("profile_updates")
    for raw in raw_updates if isinstance(raw_updates, list) else []:
        if not isinstance(raw, dict):
            continue
        field = str(raw.get("field") or "").strip()
        value = str(raw.get("value") or "").strip()
        quote = str(raw.get("supporting_quote") or "").strip()
        if field not in ALLOWED_PATCH_FIELDS:
            issues.append(f"丢弃非白名单字段的画像候选：{field or '(空)'}")
            continue
        if not value:
            issues.append(f"丢弃 value 为空的画像候选（field={field}）")
            continue
        norm_quote = _norm(quote)
        if len(norm_quote) < MIN_QUOTE_CHARS:
            quote_verified = False
            issues.append(
                f"画像候选引文过短（field={field}，<{MIN_QUOTE_CHARS} 字），"
                "短引文不构成出处，仅存档不进入确认流"
            )
        elif norm_quote not in norm_text:
            quote_verified = False
            issues.append(f"画像候选引文核验未通过（field={field}），仅存档不进入确认流")
        else:
            quote_verified = True
        updates.append(
            {
                "field": field,
                "value": value,
                "supporting_quote": quote,
                "quote_verified": quote_verified,
            }
        )

    payload = {
        "claims": claims,
        "reasoning_moves": _str_list(obj.get("reasoning_moves")),
        "risk_notes": _str_list(obj.get("risk_notes")),
        "profile_updates": updates,
    }
    return payload, issues


def _article_prompt(record: dict[str, Any], text: str) -> str:
    total = len(text)
    if total > MAX_ARTICLE_PROMPT_CHARS:
        body = text[:MAX_ARTICLE_PROMPT_CHARS]
        header = f"文章原文（共 {total} 字，以下仅为前 {MAX_ARTICLE_PROMPT_CHARS} 字，已截断）："
    else:
        body = text
        header = f"文章原文（共 {total} 字，完整）："
    meta = " / ".join(
        str(record.get(key) or "")
        for key in ("date", "source", "title")
        if str(record.get(key) or "").strip()
    )
    return f"文章元信息：{meta or '未标注'}\n{header}\n{body}\n\n请据此输出 JSON。"


def _load_article_records(
    us: UserSpace,
    perspective_id: str,
) -> list[dict[str, Any]]:
    """从 manifest 取文章记录并核验 raw_path 仍在用户命名空间内。"""
    records: list[dict[str, Any]] = []
    root = perspective_lab.perspectives_root(us).resolve()
    for record in perspective_lab._read_manifest(
        perspective_lab.manifest_path(us, perspective_id)
    ):
        article_id = str(record.get("article_id") or "")
        if not _ARTICLE_ID_RE.match(article_id):
            continue
        raw_path = Path(str(record.get("raw_path") or ""))
        try:
            raw_path.resolve().relative_to(root)
        except (OSError, ValueError):
            continue
        if raw_path.is_file():
            records.append(record)
    return records


def extract_card(
    us: UserSpace,
    perspective_id: str,
    record: dict[str, Any],
    *,
    llm_complete: LlmComplete | None = None,
) -> dict[str, Any]:
    """抽取单篇文章的认知卡片并落盘；LLM 失败/输出为空时抛错、不写文件。"""
    profile = perspective_lab.load_profile(us, perspective_id)
    article_id = str(record.get("article_id") or "")
    path = card_path(us, str(profile["id"]), article_id)
    text = Path(str(record["raw_path"])).read_text(encoding="utf-8")
    call = llm_complete or _default_llm_complete
    content, provider_name, model_name, reason = call(
        [
            {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": _article_prompt(record, text)},
        ]
    )
    if content is None:
        raise RuntimeError(f"LLM 抽取失败：{reason or '未知原因'}")
    obj = _parse_json_object(content)
    if obj is None:
        raise RuntimeError("LLM 返回无法解析为 JSON 对象，本篇不落卡片")
    payload, issues = _validate_card_payload(obj, text)
    if not any(payload[key] for key in ("claims", "reasoning_moves", "risk_notes", "profile_updates")):
        raise RuntimeError("LLM 抽取结果四个字段全空，本篇不落卡片")
    card = {
        "schema_version": CARD_SCHEMA_VERSION,
        "article_id": article_id,
        "perspective_id": profile["id"],
        "title": str(record.get("title") or ""),
        "date": str(record.get("date") or ""),
        "source": str(record.get("source") or "") or None,
        **payload,
        "validation_issues": issues,
        "extractor": {"provider": provider_name, "model": model_name},
        "extracted_at": _now_iso(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return card


def extract_cards(
    us: UserSpace,
    perspective_id: str,
    *,
    article_id: str | None = None,
    limit: int | None = None,
    force: bool = False,
    llm_complete: LlmComplete | None = None,
) -> dict[str, Any]:
    """批量抽取：跳过已有卡片（除非 force），单篇失败不阻断后续。

    留出集（holdout）文章不抽取——留出文章必须保持「没喂过蒸馏」的状态，
    否则 verify 测的是记忆不是解释力。
    """
    profile = perspective_lab.load_profile(us, perspective_id)
    pid = str(profile["id"])
    records = _load_article_records(us, pid)
    held = load_holdout(us, pid)
    if held:
        records = [r for r in records if r.get("article_id") not in held]
    if article_id is not None:
        records = [r for r in records if r.get("article_id") == article_id]
        if not records:
            raise ValueError(f"文章不存在或原文缺失：{article_id}")
    extracted: list[str] = []
    skipped: list[str] = []
    failed: list[dict[str, str]] = []
    for record in records:
        aid = str(record["article_id"])
        if not force and card_path(us, pid, aid).exists():
            skipped.append(aid)
            continue
        if limit is not None and len(extracted) >= limit:
            break
        try:
            extract_card(us, pid, record, llm_complete=llm_complete)
        except (RuntimeError, OSError) as exc:
            failed.append({"article_id": aid, "reason": str(exc)})
            continue
        extracted.append(aid)
    return {
        "perspective_id": pid,
        "articles": len(records),
        "extracted": extracted,
        "skipped_existing": skipped,
        "failed": failed,
    }


def load_cards(us: UserSpace, perspective_id: str) -> list[dict[str, Any]]:
    root = cards_dir(us, perspective_id)
    if not root.exists():
        return []
    cards: list[dict[str, Any]] = []
    for path in sorted(root.glob("pa-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            cards.append(data)
    return cards


# --------------------------------------------------------------------------- #
# patch 聚合与人工确认
# --------------------------------------------------------------------------- #
def _patch_id(perspective_id: str, field: str, value: str) -> str:
    digest = hashlib.sha256(f"{perspective_id}|{field}|{_norm(value)}".encode()).hexdigest()
    return f"pp-{digest[:12]}"


def _profile_has_value(profile: dict[str, Any], field: str, value: str) -> bool:
    existing = profile.get(field) or []
    target = _norm(value)
    return any(_norm(str(item)) == target for item in existing if isinstance(item, str))


def propose_patches(us: UserSpace, perspective_id: str) -> dict[str, Any]:
    """聚合卡片里 quote_verified 的画像候选 → pending patch 文件（幂等）。

    同一 (field, value) 的 patch id 是确定性哈希：重复 propose 命中同一文件，
    已存在（无论何种状态）就跳过，不会把 rejected 的候选复活。

    留出集文章的卡片同样不聚合——即使历史已抽过卡（先 holdout 后改主意的场景），
    留出证据也不进候选流。
    """
    profile = perspective_lab.load_profile(us, perspective_id)
    pid = str(profile["id"])
    held = load_holdout(us, pid)
    grouped: dict[str, dict[str, Any]] = {}
    for card in load_cards(us, pid):
        if held and str(card.get("article_id") or "") in held:
            continue
        for update in card.get("profile_updates") or []:
            if not isinstance(update, dict) or not update.get("quote_verified"):
                continue
            field = str(update.get("field") or "")
            value = str(update.get("value") or "").strip()
            if field not in ALLOWED_PATCH_FIELDS or not value:
                continue
            patch_id = _patch_id(pid, field, value)
            entry = grouped.setdefault(
                patch_id,
                {"field": field, "value": value, "evidence": []},
            )
            entry["evidence"].append(
                {
                    "article_id": str(card.get("article_id") or ""),
                    "title": str(card.get("title") or ""),
                    "date": str(card.get("date") or ""),
                    "quote": str(update.get("supporting_quote") or ""),
                }
            )

    created: list[str] = []
    skipped_in_profile: list[str] = []
    skipped_existing: list[str] = []
    patches_dir(us, pid).mkdir(parents=True, exist_ok=True)
    for patch_id, entry in sorted(grouped.items()):
        if _profile_has_value(profile, entry["field"], entry["value"]):
            skipped_in_profile.append(patch_id)
            continue
        path = patch_path(us, pid, patch_id)
        if path.exists():
            skipped_existing.append(patch_id)
            continue
        patch = {
            "schema_version": PATCH_SCHEMA_VERSION,
            "patch_id": patch_id,
            "perspective_id": pid,
            "field": entry["field"],
            "value": entry["value"],
            "status": "pending",
            "supporting_article_count": len(entry["evidence"]),
            "evidence": entry["evidence"],
            "created_at": _now_iso(),
            "reviewed_at": None,
            "review_note": "",
        }
        path.write_text(json.dumps(patch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        created.append(patch_id)
    return {
        "perspective_id": pid,
        "candidates": len(grouped),
        "created": created,
        "skipped_already_in_profile": skipped_in_profile,
        "skipped_existing_patch": skipped_existing,
    }


def list_patches(
    us: UserSpace,
    perspective_id: str,
    *,
    status: str | None = None,
) -> list[dict[str, Any]]:
    if status is not None and status not in PATCH_STATUSES:
        raise ValueError(f"非法 patch 状态：{status!r}（可用：{'/'.join(PATCH_STATUSES)}）")
    root = patches_dir(us, perspective_id)
    if not root.exists():
        return []
    patches: list[dict[str, Any]] = []
    for path in sorted(root.glob("pp-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if status is None or data.get("status") == status:
            patches.append(data)
    return patches


def review_patch(
    us: UserSpace,
    perspective_id: str,
    patch_id: str,
    *,
    approve: bool,
    note: str = "",
) -> dict[str, Any]:
    """人工确认一条 pending patch。approve 写 profile + patch_history 溯源。"""
    profile = perspective_lab.load_profile(us, perspective_id)
    pid = str(profile["id"])
    path = patch_path(us, pid, patch_id)
    if not path.is_file():
        raise FileNotFoundError(f"patch 不存在：{path}")
    patch = json.loads(path.read_text(encoding="utf-8"))
    if patch.get("status") != "pending":
        raise ValueError(f"patch 已是 {patch.get('status')}，不可重复评审：{patch_id}")
    now = _now_iso()
    patch["reviewed_at"] = now
    patch["review_note"] = str(note or "").strip()
    if approve:
        field = str(patch.get("field") or "")
        value = str(patch.get("value") or "").strip()
        if field not in ALLOWED_PATCH_FIELDS or not value:
            raise ValueError(f"patch 内容非法（field={field!r}），不可写入画像")
        applied = not _profile_has_value(profile, field, value)
        if applied:
            profile.setdefault(field, []).append(value)
        history = profile.setdefault("patch_history", [])
        history.append(
            {
                "patch_id": patch_id,
                "field": field,
                "value": value,
                "action": "approved",
                "applied": applied,
                "at": now,
            }
        )
        perspective_lab._save_profile(us, profile)
        patch["status"] = "approved"
        patch["applied"] = applied
    else:
        patch["status"] = "rejected"
    path.write_text(json.dumps(patch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return patch


# --------------------------------------------------------------------------- #
# Held-out 验收：留出文章不进蒸馏（extract/propose 双侧排除），验证画像对该篇解释力
# --------------------------------------------------------------------------- #
HOLDOUT_SCHEMA_VERSION = 1
HOLDOUT_VERIFY_SCHEMA_VERSION = 1
HOLDOUT_MIN_ECHO_RATIO = 0.5  # 过线：有回声的信号条目 / 信号条目总数


def holdout_path(us: UserSpace, perspective_id: str) -> Path:
    pid = perspective_lab.resolve_perspective_id(perspective_id)
    return perspective_lab.perspectives_root(us) / "holdout" / f"{pid}.json"


def holdout_verify_path(us: UserSpace, perspective_id: str) -> Path:
    pid = perspective_lab.resolve_perspective_id(perspective_id)
    return perspective_lab.perspectives_root(us) / "holdout" / f"{pid}.verify.jsonl"


def load_holdout(us: UserSpace, perspective_id: str) -> dict[str, dict[str, Any]]:
    """留出集：article_id -> {title, date, note, added_at}。文件缺失视为空集。"""
    path = holdout_path(us, perspective_id)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}


def _write_holdout(us: UserSpace, pid: str, data: dict[str, dict[str, Any]]) -> None:
    path = holdout_path(us, pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_holdout(
    us: UserSpace, perspective_id: str, article_id: str, *, note: str = ""
) -> dict[str, Any]:
    """把已 ingest 的文章标记为留出（蒸馏侧跳过，verify 侧检验）。幂等。"""
    profile = perspective_lab.load_profile(us, perspective_id)  # 角色必须存在
    pid = str(profile["id"])
    records = {r.get("article_id"): r for r in _load_article_records(us, pid)}
    if article_id not in records:
        raise ValueError(f"文章不存在或不在该角色名下：{article_id}")
    record = records[article_id]
    data = load_holdout(us, pid)
    entry = data.get(article_id) or {
        "title": str(record.get("title") or ""),
        "date": str(record.get("date") or ""),
        "added_at": _now_iso(),
    }
    entry["note"] = str(note or "").strip() or entry.get("note", "")
    data[article_id] = entry
    _write_holdout(us, pid, data)
    return entry


def remove_holdout(us: UserSpace, perspective_id: str, article_id: str) -> bool:
    profile = perspective_lab.load_profile(us, perspective_id)
    pid = str(profile["id"])
    data = load_holdout(us, pid)
    if article_id not in data:
        return False
    del data[article_id]
    _write_holdout(us, pid, data)
    return True


def list_holdout(us: UserSpace, perspective_id: str) -> list[dict[str, Any]]:
    profile = perspective_lab.load_profile(us, perspective_id)
    data = load_holdout(us, str(profile["id"]))
    return [
        {"article_id": aid, **entry}
        for aid, entry in sorted(data.items(), key=lambda kv: str(kv[1].get("added_at") or ""))
    ]


def _signal_entries(profile: dict[str, Any]) -> list[tuple[str, str]]:
    """画像信号条目（字段, 条目），与 patch 白名单同集合——verify 只检验闭环可写的字段。"""
    out: list[tuple[str, str]] = []
    for field in ALLOWED_PATCH_FIELDS:
        for item in profile.get(field) or []:
            if isinstance(item, str) and item.strip():
                out.append((field, item.strip()))
    return out


def _entry_echoes(entry: str, norm_text: str) -> bool:
    """条目回声：条目词元（复用检索分词）至少 1 个出现在留出文章正文。"""
    return any(t and t in norm_text for t in perspective_lab._search_terms(entry))


def verify_holdout(us: UserSpace, perspective_id: str, *, save: bool = True) -> dict[str, Any]:
    """确定性回声检验：画像信号条目在留出文章正文的解释力。

    PASS 条件：每篇留出文章的回声条目占比 ≥ HOLDOUT_MIN_ECHO_RATIO。
    画像无信号条目 / 留出集为空都判 fail——验收不能空转通过。
    结果追加落 ``holdout/<pid>.verify.jsonl``（schema_version=1）。
    """
    from intelligence.services import framework_interpretation

    profile = perspective_lab.load_profile(us, perspective_id)
    pid = str(profile["id"])
    entries = _signal_entries(profile)
    held = load_holdout(us, pid)
    records = {r.get("article_id"): r for r in _load_article_records(us, pid)}

    articles: list[dict[str, Any]] = []
    if entries and held:
        for aid, meta in sorted(held.items()):
            record = records.get(aid)
            if record is None:
                articles.append({"article_id": aid, "status": "missing_raw", "ratio": 0.0})
                continue
            norm_text = re.sub(r"\s+", "", Path(str(record["raw_path"])).read_text(encoding="utf-8"))
            echoed = [entry for _f, entry in entries if _entry_echoes(entry, norm_text)]
            ratio = round(len(echoed) / len(entries), 4)
            articles.append(
                {
                    "article_id": aid,
                    "title": str(record.get("title") or meta.get("title") or ""),
                    "date": str(record.get("date") or meta.get("date") or ""),
                    "echo_entries": len(echoed),
                    "signal_entries": len(entries),
                    "ratio": ratio,
                    "status": "pass" if ratio >= HOLDOUT_MIN_ECHO_RATIO else "fail",
                }
            )
    status = (
        "pass"
        if articles and all(a.get("status") == "pass" for a in articles)
        else "fail"
    )
    result = {
        "schema_version": HOLDOUT_VERIFY_SCHEMA_VERSION,
        "perspective_id": pid,
        "framework_version": framework_interpretation.framework_version(profile),
        "signal_entries": len(entries),
        "holdout_articles": len(held),
        "min_echo_ratio": HOLDOUT_MIN_ECHO_RATIO,
        "articles": articles,
        "status": status,
        "reason": ""
        if articles
        else ("画像无信号条目（先蒸馏/编辑四个白名单字段）" if not entries else "留出集为空（先 holdout add 一篇）"),
        "checked_at": _now_iso(),
    }
    if save:
        vpath = holdout_verify_path(us, pid)
        vpath.parent.mkdir(parents=True, exist_ok=True)
        with vpath.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result, ensure_ascii=False) + "\n")
    return result
