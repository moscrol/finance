"""个人判断台账导出（终局 spec §9「用户退出后可导出个人判断记录」、§10 验收 8）。

## 为什么单独一个模块

台账散在六七个 jsonl 里（判断、可证伪点、回检、观察剧本、纠偏、经验卡、画像），
用户要走的时候得能**一次拿全**。散着让人自己去 `users/<id>/` 底下捡，等于没有导出：
他不知道哪些文件是他的、哪些是派生物、哪些根本不该带走。

## 三条纪律

1. **只导出这个用户目录里的东西。** 导出不去别处取数——不合并共享层、不带别人的行。
   这既是隐私边界，也让导出物可以直接给用户看：里面每一行都是他自己写下的。
2. **带 manifest，且写明没带什么。** 只给数据不给清单，用户无法判断这份导出是否完整；
   写明「没带什么以及为什么」比默默省略诚实（派生画像 `profile.derived.json` 是可重算的
   派生物，不是他的记录；共享层方法与授课框架不属于他）。
3. **不解释、不加工。** 逐行原样搬。导出物里出现台账里没有的字段，用户就没法拿它对账。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 导出哪些台账：(键, UserSpace 属性名, 一句人话)
LEDGER_PARTS: tuple[tuple[str, str, str], ...] = (
    ("judgments", "judgments_path", "核心判断（含 pending 提案）"),
    ("checkpoints", "checkpoints_path", "可证伪点：陈述 + 到期日 + 机检规格"),
    ("verdicts", "verdicts_path", "回检打分"),
    ("observation_scripts", "observation_scripts_path", "观察剧本：变量与升级/放弃条件"),
    ("corrections", "corrections_path", "你对 agent 的纠偏"),
    ("experience_cards", "experience_cards_path", "从低分回答与纠偏压缩出的经验卡"),
    ("answer_scores", "answer_scores_path", "你给回答打的分"),
    ("interactions", "interactions_path", "提问与互动记录"),
)

# 刻意**不**导出的，以及理由。写进 manifest——省略比说明更不诚实。
EXCLUDED: tuple[tuple[str, str], ...] = (
    ("profile.derived.json", "派生画像：由上面这些台账重算得到，不是你写下的记录"),
    ("shared/*", "共享层方法与授课框架不属于个人，导出它等于把别人的东西带走"),
    ("foresight_memory.jsonl", "语义记忆索引是派生物，重建即可（原始互动已在 interactions 里）"),
)


@dataclass(frozen=True)
class ExportResult:
    user_id: str
    exported_at: str
    parts: dict[str, list[dict[str, Any]]]
    counts: dict[str, int]
    profile: dict[str, Any] | None
    missing: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": {
                "user_id": self.user_id,
                "exported_at": self.exported_at,
                "counts": self.counts,
                "total_records": sum(self.counts.values()),
                "missing_files": list(self.missing),
                "excluded": [{"what": w, "why": y} for w, y in EXCLUDED],
                "note": (
                    "本文件只含该 user_id 目录下的记录，不含共享层、不含其他用户。"
                    "每一行都按台账原文搬运，未做解释或加工。"
                ),
            },
            "profile": self.profile,
            **self.parts,
        }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            # 坏行不静默丢：原样带走，让用户看得见台账里确实有这么一行。
            out.append({"_unparsed_line": line})
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def export_ledger(us: Any, *, now: str | None = None) -> ExportResult:
    """把一个用户的判断台账整份读出来。**只读**，不改任何文件。"""
    parts: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    missing: list[str] = []
    for key, attr, _desc in LEDGER_PARTS:
        path = getattr(us, attr, None)
        if not isinstance(path, Path):
            missing.append(f"{key}（本版本无此台账）")
            continue
        if not path.exists():
            missing.append(path.name)
        rows = _read_jsonl(path)
        parts[key] = rows
        counts[key] = len(rows)

    profile: dict[str, Any] | None = None
    ppath = getattr(us, "profile_path", None)
    if isinstance(ppath, Path) and ppath.exists():
        try:
            loaded = json.loads(ppath.read_text(encoding="utf-8"))
            profile = loaded if isinstance(loaded, dict) else None
        except json.JSONDecodeError:
            missing.append(f"{ppath.name}（解析失败，未导出）")

    return ExportResult(
        user_id=str(getattr(us, "user_id", "")),
        exported_at=now or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        parts=parts,
        counts=counts,
        profile=profile,
        missing=tuple(missing),
    )


def render(result: ExportResult) -> str:
    """人读摘要。导出后先让用户看清「带走了什么」，再决定要不要留档。"""
    lines = [f"# 个人判断台账导出 · {result.user_id} · {result.exported_at}", ""]
    for key, _attr, desc in LEDGER_PARTS:
        n = result.counts.get(key)
        if n is None:
            continue
        lines.append(f"  {key:<20} {n:>6} 条   {desc}")
    lines.append("")
    lines.append(f"  合计 {sum(result.counts.values())} 条" + ("（画像已附）" if result.profile else ""))
    if result.missing:
        lines += ["", "  台账文件不存在（= 你还没产生过这类记录，不是导出失败）："]
        lines += [f"    - {m}" for m in result.missing]
    lines += ["", "  刻意未导出："]
    lines += [f"    - {w}：{y}" for w, y in EXCLUDED]
    return "\n".join(lines)
