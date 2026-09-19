"""只读证据解析器：把事件里的 run / 产物引用核到真实存储，返回缺失 / 篡改 / 跨用户原因。

为什么是「注入的解析器」而不是模块里直接开 ``RunStore``：

- 05 的纯函数不得从 cwd 或环境变量推断生产用户根（总合同 §4）；
- 06 在生产里已经持有按 owner 解析好的 ``RunStore``，注入它就不会出现「两个
  路径解析器在一个进程里各说各话」的老问题；
- 测试与离线 CLI 用 ``InMemoryEvidenceReader`` 喂夹具，报告照样标 synthetic。

真实性与成功性分开（同 ``self_use_maturity.verify_run_binding`` 的判据思想，但
**不复用它的成功门**）：这里只回答「这个 run 在不在、属不属于这个 owner、终态
是什么、有没有降级、产物哈希对不对」。失败 run 没有 report.json 照样能回答，
因为它必须进分母。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from intelligence.services.product_value.hashing import normalize_hash_ref

EVIDENCE_OK = "ok"
EVIDENCE_MISSING = "missing"
EVIDENCE_CROSS_OWNER = "cross_owner"
EVIDENCE_UNREADABLE = "unreadable"
EVIDENCE_TAMPERED = "tampered"
EVIDENCE_UNAVAILABLE = "unavailable"


class EvidenceReader(Protocol):
    def resolve_run(self, owner_user_id: str, run_id: str) -> dict[str, Any]: ...

    def resolve_ref(self, owner_user_id: str, ref: Mapping[str, Any]) -> dict[str, Any]: ...


def run_evidence(
    *,
    status: str,
    run_status: str | None = None,
    has_error: bool = False,
    degrades: list[str] | tuple[str, ...] = (),
    artifacts: Mapping[str, str] | None = None,
    created_at: str | None = None,
    finished_at: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """统一的解析结果形状。错误文本不外泄，只给布尔 ``has_error``。"""
    return {
        "status": status,
        "run_status": run_status,
        "has_error": bool(has_error),
        "degrades": sorted(str(item) for item in degrades),
        "artifacts": dict(artifacts or {}),
        "created_at": created_at,
        "finished_at": finished_at,
        "reason": reason,
    }


def _resolve_ref_via(
    resolve_run: Callable[[str, str], dict[str, Any]],
    owner_user_id: str,
    ref: Mapping[str, Any],
) -> dict[str, Any]:
    kind = ref.get("kind")
    ref_id = ref.get("id")
    if not isinstance(ref_id, str) or not ref_id:
        return {"status": EVIDENCE_MISSING, "reason": "ref_without_id", "hash_checked": False}
    if kind == "run":
        evidence = resolve_run(owner_user_id, ref_id)
        return {**evidence, "hash_checked": False}
    if kind == "artifact":
        scope = ref.get("scope") if isinstance(ref.get("scope"), Mapping) else {}
        run_id = scope.get("run_id") if isinstance(scope, Mapping) else None
        if not isinstance(run_id, str) or not run_id:
            return {"status": EVIDENCE_MISSING, "reason": "artifact_ref_without_run_scope", "hash_checked": False}
        evidence = resolve_run(owner_user_id, run_id)
        if evidence.get("status") != EVIDENCE_OK:
            return {**evidence, "hash_checked": False}
        stored = normalize_hash_ref(evidence.get("artifacts", {}).get(ref_id))
        if stored is None:
            return {"status": EVIDENCE_MISSING, "reason": "artifact_not_in_run", "hash_checked": False}
        expected = normalize_hash_ref(ref.get("version_or_hash"))
        if expected is None:
            return {"status": EVIDENCE_OK, "reason": "no_hash_declared", "hash_checked": False}
        if expected != stored:
            return {"status": EVIDENCE_TAMPERED, "reason": "artifact_hash_mismatch", "hash_checked": True}
        return {"status": EVIDENCE_OK, "reason": None, "hash_checked": True}
    # judgment / checkpoint 等其它对象归 01 / 06 的读取器；这里不假装能核，也不判篡改。
    return {"status": EVIDENCE_UNAVAILABLE, "reason": f"unsupported_ref_kind:{kind}", "hash_checked": False}


@dataclass
class InMemoryEvidenceReader:
    """夹具 / 测试用：``(owner_user_id, run_id) -> run 描述``。

    run 描述字段：``status``（run 终态）、``error``、``degrades``、``artifacts``
    （``artifact_id -> sha256``）、``created_at``、``finished_at``。
    """

    runs: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> "InMemoryEvidenceReader":
        runs: dict[tuple[str, str], dict[str, Any]] = {}
        for row in payload.get("runs") or ():
            if not isinstance(row, Mapping):
                continue
            owner = str(row.get("owner_user_id") or "")
            run_id = str(row.get("run_id") or "")
            if owner and run_id:
                runs[(owner, run_id)] = dict(row)
        return cls(runs=runs)

    def resolve_run(self, owner_user_id: str, run_id: str) -> dict[str, Any]:
        row = self.runs.get((owner_user_id, run_id))
        if row is None:
            if any(key[1] == run_id for key in self.runs):
                # 同 id 属于别的 owner：只说越界，不说属于谁。
                return run_evidence(status=EVIDENCE_CROSS_OWNER, reason="run_belongs_to_another_owner")
            return run_evidence(status=EVIDENCE_MISSING, reason="run_not_found")
        return run_evidence(
            status=EVIDENCE_OK,
            run_status=str(row.get("status") or ""),
            has_error=bool(row.get("error")),
            degrades=list(row.get("degrades") or ()),
            artifacts={str(k): str(v) for k, v in (row.get("artifacts") or {}).items()},
            created_at=row.get("created_at"),
            finished_at=row.get("finished_at"),
        )

    def resolve_ref(self, owner_user_id: str, ref: Mapping[str, Any]) -> dict[str, Any]:
        return _resolve_ref_via(self.resolve_run, owner_user_id, ref)


class RunStoreEvidenceReader:
    """生产用：通过注入的 ``store_for_owner(owner) -> RunStore | None`` 只读真实 run。

    只调用 ``RunStore.load_run``；不写、不建目录。``run.user != owner`` 判跨用户，
    且不返回任何对方对象的细节。
    """

    def __init__(self, store_for_owner: Callable[[str], Any | None]) -> None:
        self._store_for_owner = store_for_owner

    def resolve_run(self, owner_user_id: str, run_id: str) -> dict[str, Any]:
        try:
            store = self._store_for_owner(owner_user_id)
        except Exception as exc:  # noqa: BLE001 - 解析器故障要如实报 unavailable，不能变成 missing
            return run_evidence(status=EVIDENCE_UNAVAILABLE, reason=f"store_error:{type(exc).__name__}")
        if store is None:
            return run_evidence(status=EVIDENCE_UNAVAILABLE, reason="no_store_for_owner")
        try:
            run = store.load_run(run_id)
        except FileNotFoundError:
            return run_evidence(status=EVIDENCE_MISSING, reason="run_not_found")
        except (ValueError, OSError, json.JSONDecodeError, TypeError) as exc:
            return run_evidence(status=EVIDENCE_UNREADABLE, reason=f"run_unreadable:{type(exc).__name__}")
        if getattr(run, "user", None) != owner_user_id:
            return run_evidence(status=EVIDENCE_CROSS_OWNER, reason="run_belongs_to_another_owner")
        artifacts: dict[str, str] = {}
        for artifact in getattr(run, "artifacts", None) or ():
            if isinstance(artifact, Mapping) and artifact.get("artifact_id") and artifact.get("sha256"):
                artifacts[str(artifact["artifact_id"])] = str(artifact["sha256"])
        return run_evidence(
            status=EVIDENCE_OK,
            run_status=str(getattr(run, "status", "") or ""),
            has_error=bool(getattr(run, "error", None)),
            degrades=list(getattr(run, "degrades", None) or ()),
            artifacts=artifacts,
            created_at=getattr(run, "created_at", None),
            finished_at=getattr(run, "finished_at", None),
        )

    def resolve_ref(self, owner_user_id: str, ref: Mapping[str, Any]) -> dict[str, Any]:
        return _resolve_ref_via(self.resolve_run, owner_user_id, ref)


__all__ = [
    "EVIDENCE_CROSS_OWNER",
    "EVIDENCE_MISSING",
    "EVIDENCE_OK",
    "EVIDENCE_TAMPERED",
    "EVIDENCE_UNAVAILABLE",
    "EVIDENCE_UNREADABLE",
    "EvidenceReader",
    "InMemoryEvidenceReader",
    "RunStoreEvidenceReader",
    "run_evidence",
]
