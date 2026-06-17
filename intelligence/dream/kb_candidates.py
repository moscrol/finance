"""dream-loop C-1C / 7B：KB 事实回写候选 payload 生成器（保守、suggest-only）。

设计依据 decision1 §5「事实回写候选」+ 仓内 AGENTS.md「Raw Full 回填专用规则」：
把（**已脱敏的**）digest / lessons 候选条目转成保守的 KB 事实回写候选 payload，
供人工 review 后再决定是否经知识库 ``scripts/ingest.py`` 写入。

payload 结构对齐 ``<知识库>/wiki/raw/entity-delta-backfill/*.entity-delta.json``
的 ``updates`` 条目真实 schema（company/code/date/title/judgment/concepts/role/
chain_layer/tier/confidence/evidence_layer/exposure_only/graph_only/bullets/evidence）。

红线（写死，绝不可被输入覆盖）：
- ``graph_only=True`` / ``exposure_only=True``（只进图谱与暴露索引，绝不写 entity 正文）
- ``update_type="review_candidate"``（候选，待人工复核）
- ``evidence_layer="L1_L3_candidate"``
- ``tier="peripheral"``（AGENTS 的 core/related/peripheral「strength」，候选一律最弱）
- ``create_missing=False``（绝不由 dream 候选自动新建 entity 页）
- ``validate_payload`` 拒绝任何试图写硬正文 / 翻转上述红线的 payload，并做泄漏扫描。

⚠️ schema 待 KB 访问后最终校验（本仓与 ``scripts/ingest.py`` 非同步 clone）；输出统一带
``schema_status="pending-kb-verify"``，且文件后缀用 ``.dream-candidate.json``（**不**匹配
人工回填的 ``*.entity-delta.json`` glob，绝不会被 ``--apply`` 误吃）。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from intelligence.dream import collector

# --------------------------------------------------------------------------- #
# 红线常量（写死）
# --------------------------------------------------------------------------- #
RED_LINES: Dict[str, object] = {
    "graph_only": True,
    "exposure_only": True,
    "update_type": "review_candidate",
    "evidence_layer": "L1_L3_candidate",
    "tier": "peripheral",
    "confidence": "medium",
}
# 顶层红线：dream 候选绝不自动新建 entity 页。
CREATE_MISSING = False

ALLOWED_CHAIN_LAYERS = {
    "upstream_materials",
    "upstream_equipment",
    "midstream",
    "downstream",
    "ecosystem",
}
DEFAULT_CHAIN_LAYER = "midstream"

# 任何试图写「硬正文 / 实体 markdown / 硬事实」的键，validate 一律拒绝。
FORBIDDEN_BODY_KEYS = {
    "entity_markdown",
    "entity_body",
    "markdown",
    "body",
    "md",
    "hard_fact",
    "hard_delta",
    "delta",
    "section",
}

DEFAULT_KB_SUBDIR = "intelligence/dream/_kb_candidates"
CANDIDATE_SUFFIX = ".dream-candidate.json"
MANIFEST_NAME = "dream-candidates-manifest.jsonl"

_SLUG_RE = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff_-]+")


# --------------------------------------------------------------------------- #
# 输入
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CandidateInput:
    """单条 KB 回写候选输入（应已脱敏；builder 仍会再脱敏一次兜底）。"""

    company: str
    judgment: str  # 边际判断 / 线索（已脱敏文本）
    concepts: List[str] = field(default_factory=list)
    chain_layer: str = DEFAULT_CHAIN_LAYER
    code: str = ""
    role: str = ""  # 在产业链中的角色（自由文本，弱描述）
    title: str = ""
    bullets: List[str] = field(default_factory=list)
    date: Optional[str] = None
    evidence: str = ""  # 溯源（digest/transcript 的 raw 路径或 manifest key）


# --------------------------------------------------------------------------- #
# 泄漏扫描（复用 collector 脱敏硬门）
# --------------------------------------------------------------------------- #
def scan_leaks(text: Optional[str]) -> List[str]:
    """返回文本命中的脱敏类别（密钥/token/PII/持仓）；空列表表示无泄漏。"""
    res = collector.redact(text)
    return list(res.categories) if res.redacted else []


def _redact(text: Optional[str]) -> str:
    return collector.redact(text).text


# --------------------------------------------------------------------------- #
# 构建候选
# --------------------------------------------------------------------------- #
def build_candidate(inp: CandidateInput) -> Dict[str, object]:
    """把一条输入转成红线写死的候选 update 条目（文本字段兜底脱敏）。"""
    chain_layer = inp.chain_layer if inp.chain_layer in ALLOWED_CHAIN_LAYERS else DEFAULT_CHAIN_LAYER
    today = inp.date or _date.today().isoformat()
    candidate: Dict[str, object] = {
        "company": _redact(inp.company),
        "code": inp.code,
        "date": today,
        "title": _redact(inp.title) or _redact(inp.judgment)[:40],
        "judgment": _redact(inp.judgment),
        "concepts": [_redact(c) for c in inp.concepts],
        "role": _redact(inp.role),
        "chain_layer": chain_layer,
        "bullets": [_redact(b) for b in inp.bullets],
        "evidence": _redact(inp.evidence),
        # 红线（写死，覆盖任何输入）
        "tier": RED_LINES["tier"],
        "confidence": RED_LINES["confidence"],
        "evidence_layer": RED_LINES["evidence_layer"],
        "update_type": RED_LINES["update_type"],
        "exposure_only": RED_LINES["exposure_only"],
        "graph_only": RED_LINES["graph_only"],
    }
    return candidate


def build_payload(
    inputs: List[CandidateInput],
    source_name: str,
    source_date: Optional[str] = None,
    raw_sources: Optional[List[str]] = None,
    source_file: str = "",
    concept: str = "",
) -> Dict[str, object]:
    """把若干输入打包成顶层候选 payload（含 dream-loop 溯源与红线标记）。"""
    sdate = source_date or _date.today().isoformat()
    updates = [build_candidate(i) for i in inputs]
    payload: Dict[str, object] = {
        "source_name": source_name,
        "source_date": sdate,
        "source_file": source_file,
        "raw_sources": list(raw_sources or []),
        "report_context": {
            "source_name": source_name,
            "source_date": sdate,
            "concept": concept,
        },
        "create_missing": CREATE_MISSING,
        "updates": updates,
        "watchlist": [],
        # dream-loop 溯源 + 红线/校验状态标记
        "generator": "dream-loop/kb_candidates",
        "schema_status": "pending-kb-verify",
    }
    return payload


# --------------------------------------------------------------------------- #
# 校验（红线硬门 + 泄漏扫描）
# --------------------------------------------------------------------------- #
def validate_candidate(candidate: Dict[str, object]) -> List[str]:
    """逐条校验候选 update；返回错误列表（空=通过）。"""
    errors: List[str] = []
    if not isinstance(candidate, dict):
        return ["candidate 不是 dict"]

    # 禁止任何写硬正文的键
    for key in candidate:
        if key.lower() in FORBIDDEN_BODY_KEYS:
            errors.append(f"出现禁止的硬正文键：{key}")

    # 红线字段必须严格等于写死值
    for key, expected in RED_LINES.items():
        if candidate.get(key) != expected:
            errors.append(f"红线 {key} 必须为 {expected!r}，实际 {candidate.get(key)!r}")

    if candidate.get("chain_layer") not in ALLOWED_CHAIN_LAYERS:
        errors.append(f"chain_layer 非法：{candidate.get('chain_layer')!r}")

    if not candidate.get("company"):
        errors.append("company 不能为空")

    # 泄漏扫描：拼接所有文本字段
    blob_parts: List[str] = []
    for key in ("company", "title", "judgment", "role", "evidence"):
        val = candidate.get(key)
        if isinstance(val, str):
            blob_parts.append(val)
    for key in ("concepts", "bullets"):
        val = candidate.get(key)
        if isinstance(val, list):
            blob_parts.extend(str(x) for x in val)
    leaks = scan_leaks("\n".join(blob_parts))
    if leaks:
        errors.append(f"泄漏扫描命中：{','.join(leaks)}")

    return errors


def validate_payload(payload: Dict[str, object]) -> List[str]:
    """校验顶层 payload：create_missing 红线 + 每条 update + 全局泄漏扫描。"""
    errors: List[str] = []
    if not isinstance(payload, dict):
        return ["payload 不是 dict"]

    if payload.get("create_missing", False) is not False:
        errors.append("红线 create_missing 必须为 False（dream 候选不得自动新建 entity 页）")

    for key in payload:
        if key.lower() in FORBIDDEN_BODY_KEYS:
            errors.append(f"payload 顶层出现禁止的硬正文键：{key}")

    updates = payload.get("updates")
    if not isinstance(updates, list) or not updates:
        errors.append("updates 为空或非 list")
    else:
        for idx, upd in enumerate(updates):
            for err in validate_candidate(upd):
                errors.append(f"updates[{idx}]：{err}")

    # 全局泄漏兜底：整体序列化再扫一遍
    leaks = scan_leaks(json.dumps(payload, ensure_ascii=False))
    if leaks:
        errors.append(f"payload 整体泄漏扫描命中：{','.join(leaks)}")

    return errors


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #
def resolve_kb_dir(explicit: Optional[str]) -> Path:
    """解析候选输出目录。

    优先级：显式 ``--kb-dir`` > env ``KB_CANDIDATES_DIR`` > 本仓 gitignore staging
    目录 ``intelligence/dream/_kb_candidates``（默认，安全回退）。

    默认**不**自动指向真实知识库 ``<知识库>/wiki/raw/entity-delta-backfill``——
    需写入真实库时由操作者显式传 ``--kb-dir`` 指过去（候选后缀 ``.dream-candidate.json``
    不会被人工回填 ``--apply`` 的 ``*.entity-delta.json`` glob 误吃）。
    """
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("KB_CANDIDATES_DIR")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parents[2] / DEFAULT_KB_SUBDIR


def _slug(text: str) -> str:
    s = _SLUG_RE.sub("-", (text or "").strip()).strip("-")
    return s[:60] or "candidate"


def write_payload(payload: Dict[str, object], kb_dir: Optional[str] = None) -> Dict[str, object]:
    """校验通过后写出 payload 到 ``<kb_dir>/<slug>.dream-candidate.json`` + 追加 manifest。

    校验不过则**不写文件**，返回 ``{"written": False, "errors": [...]}``。
    """
    errors = validate_payload(payload)
    summary: Dict[str, object] = {
        "written": False,
        "path": None,
        "errors": errors,
        "kb_dir": None,
        "updates": len(payload.get("updates") or []) if isinstance(payload, dict) else 0,
    }
    if errors:
        return summary

    out_dir = resolve_kb_dir(kb_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary["kb_dir"] = str(out_dir)

    sname = str(payload.get("source_name") or "candidate")
    sdate = str(payload.get("source_date") or _date.today().isoformat())
    fname = f"{sdate}-{_slug(sname)}{CANDIDATE_SUFFIX}"
    out_path = out_dir / fname
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = out_dir / MANIFEST_NAME
    rec = {
        "file": fname,
        "source_name": sname,
        "source_date": sdate,
        "updates": len(payload.get("updates") or []),
        "schema_status": payload.get("schema_status"),
        "generator": payload.get("generator"),
    }
    with manifest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    summary["written"] = True
    summary["path"] = str(out_path)
    return summary


# --------------------------------------------------------------------------- #
# 输入文件加载（CLI 用）
# --------------------------------------------------------------------------- #
def load_inputs(spec: Dict[str, object]) -> Tuple[List[CandidateInput], Dict[str, object]]:
    """从输入 JSON dict 解析候选列表 + 顶层元信息。

    spec 形如：``{source_name, source_date?, raw_sources?, source_file?, concept?,
    candidates: [{company, judgment, concepts?, chain_layer?, code?, role?, title?,
    bullets?, date?, evidence?}, ...]}``。
    """
    raw_items = spec.get("candidates")
    if not isinstance(raw_items, list):
        raise ValueError("输入缺少 candidates 列表")
    inputs: List[CandidateInput] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        inputs.append(
            CandidateInput(
                company=str(item.get("company", "")),
                judgment=str(item.get("judgment", "")),
                concepts=[str(c) for c in (item.get("concepts") or [])],
                chain_layer=str(item.get("chain_layer", DEFAULT_CHAIN_LAYER)),
                code=str(item.get("code", "")),
                role=str(item.get("role", "")),
                title=str(item.get("title", "")),
                bullets=[str(b) for b in (item.get("bullets") or [])],
                date=item.get("date"),
                evidence=str(item.get("evidence", "")),
            )
        )
    meta = {
        "source_name": str(spec.get("source_name", "dream-candidate")),
        "source_date": spec.get("source_date"),
        "raw_sources": [str(r) for r in (spec.get("raw_sources") or [])],
        "source_file": str(spec.get("source_file", "")),
        "concept": str(spec.get("concept", "")),
    }
    return inputs, meta


def render_summary(summary: Dict[str, object]) -> str:
    lines = [
        f"[dream-kb-candidates] written={summary.get('written')} updates={summary.get('updates')}",
        f"  kb_dir={summary.get('kb_dir')}",
        f"  path={summary.get('path')}",
    ]
    errors = summary.get("errors") or []
    if isinstance(errors, list) and errors:
        lines.append(f"  errors（已拒绝，未写）：")
        for e in errors:
            lines.append(f"    - {e}")
    return "\n".join(lines)
