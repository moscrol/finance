"""06 · Workbench 集成的交换合同：响应封套、请求 schema、稳定业务错误码。

spec ``docs/superpowers/specs/2026-09-13-research-evolution/06-workbench-integration.md`` §4.4 / §5。

原则（总合同 §5）：

- 各模块内容保持自己的 schema（01 ``judgment-maintenance/v1`` / 02 ``research-priority-view/v1`` /
  04 ``research-diagnostics/v1`` / 03 ``method-validation-receipt/v1`` / 05 ``measurement-receipt/v1``），
  封套只加 ``module_status`` 与 ``gaps``，不压成一个含糊总分；
- ``generated_at`` 是生成时间，不进任何内容摘要；
- 缺模块 = ``unavailable``，缺输入 = ``unknown`` / ``pending``，服务错误 = ``error``；错误不能被空数组掩盖；
- 字段名一律字符串字面量声明，供前端 / CLI / 别的进程按 JSON 读取。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

# --------------------------------------------------------------------------- #
# schema 名
# --------------------------------------------------------------------------- #
VIEW_SCHEMA = "research-evolution-view/v1"
BINDING_REQUEST_SCHEMA = "research-evolution-binding-request/v1"
BINDING_RECORD_SCHEMA = "research-evolution-binding-record/v1"
ACTION_REQUEST_SCHEMA = "research-evolution-action-request/v1"
ACTION_RECORD_SCHEMA = "research-evolution-action-record/v1"
ACTION_RESULT_SCHEMA = "research-evolution-action-result/v1"
EVENTS_REQUEST_SCHEMA = "research-evolution-events-request/v1"
EVENTS_RESULT_SCHEMA = "research-evolution-events-result/v1"
RECEIPT_REF_SCHEMA = "research-evolution-receipt-ref/v1"
PILOT_REGISTRATION_SCHEMA = "research-evolution-pilot-registration/v1"
CONTINUATION_SCHEMA = "research-evolution-continuation/v1"

# 自用测量事件的协议版本：明确不是试点协议，别的东西也不该拿它当试点读数。
# （facade 与 run_observer 共用；05 summarize 按 pilot_id 分区，自用事件混不进真人试点。）
SELF_USE_PROTOCOL_VERSION = "workbench-self-use/v1"

# --------------------------------------------------------------------------- #
# 模块状态（封套 module_status.<module>.status）
# --------------------------------------------------------------------------- #
STATUS_OK = "ok"  # 真模块真实计算
STATUS_UNAVAILABLE = "unavailable"  # 模块缺失 / import 失败 / 未接线
STATUS_UNKNOWN = "unknown"  # 输入不足，无法判定；不是「没有问题」
STATUS_PENDING = "pending"  # 未来未到 / 等待外部条件
STATUS_ERROR = "error"  # 服务错误，其余模块照常
STATUS_WIRING = "wiring_in_progress"  # 夹具阶段：只能报「接线开发中」
MODULE_STATUSES = (STATUS_OK, STATUS_UNAVAILABLE, STATUS_UNKNOWN, STATUS_PENDING, STATUS_ERROR, STATUS_WIRING)
MODULES = ("maintenance", "priority", "diagnostics", "validation_receipts", "product_value_receipts")

# --------------------------------------------------------------------------- #
# 动作种类（POST …/actions 的 action 字段）
# --------------------------------------------------------------------------- #
# 01 用户命令：开始复核 / 稍后处理 / 继续核查 / 核对后判断未变
ACTION_CLAIM = "claim"
ACTION_SNOOZE = "snooze"
ACTION_REJUDGE = "rejudge"
ACTION_REVIEWED_NO_CHANGE = "reviewed_no_change"
# 06 系统关联：把「继续核查」产生的真实 run 终态折回维护项（用户点「关联结果」或前端在 run 终态后调用；
# 服务端只认 RunStore 里的真实状态，不信前端自报）
ACTION_LINK_RUN = "link_run"
# 02 任务选择：只记录选择与点击载荷，不改任何判定
ACTION_SELECT_TASK = "select_task"
# 04 练习：揭示前先经 03 record_exposure 原子登记；提交答案走确定性评卷
ACTION_REVEAL_EXERCISE = "reveal_exercise"
ACTION_SUBMIT_EXERCISE = "submit_exercise"
# 取消一次已发起的复核：消息入口拒绝 / 用户反悔时把维护项从 rejudgment_requested 退回 open，
# 不留「请求挂着、永远没有 run」的假进行态（01 系统事件 rejudgment_cancelled）。
ACTION_CANCEL_REJUDGE = "cancel_rejudge"
# 读收据原件：03 方法验证收据经 03 read_receipt（内部先登记曝光）；05 测量收据 / 试点总结经 06 store 验权读。
ACTION_READ_RECEIPT = "read_receipt"
MAINTENANCE_ACTIONS = (ACTION_CLAIM, ACTION_SNOOZE, ACTION_REJUDGE, ACTION_REVIEWED_NO_CHANGE)
ACTIONS = MAINTENANCE_ACTIONS + (
    ACTION_LINK_RUN,
    ACTION_SELECT_TASK,
    ACTION_REVEAL_EXERCISE,
    ACTION_SUBMIT_EXERCISE,
    ACTION_CANCEL_REJUDGE,
    ACTION_READ_RECEIPT,
)

# --------------------------------------------------------------------------- #
# 稳定业务错误码（API 直接透传；只能追加不能改名）
# --------------------------------------------------------------------------- #
ERR_INVALID_REQUEST = "invalid_request"
ERR_UNKNOWN_SCHEMA = "unknown_schema"
ERR_OWNER_FORBIDDEN = "owner_forbidden"  # 本机未认证模式拒绝任意换 user；越界引用同码，不回显对方对象
ERR_NOT_FOUND = "not_found"  # 会话 / 对象 / run 不存在或不属于本用户：同一个码，不泄漏存在性
ERR_VERSION_CONFLICT = "version_conflict"  # 409：expected_item_version / expected_management_revision 过期
ERR_IDEMPOTENCY_MISMATCH = "idempotency_payload_mismatch"  # 409：同 idempotency_key 不同载荷
ERR_ACTION_REJECTED = "action_rejected"  # 01 validate_action 给出 rejected（非法迁移 / 终态 / snooze 到过去…）
ERR_MODULE_UNAVAILABLE = "module_unavailable"  # 503：动作依赖的真模块缺失
ERR_STORE_CORRUPT = "store_corrupt"  # 500：台账损坏，拒绝继续业务写入
ERR_BINDING_REJECTED = "binding_rejected"  # 01 parse_binding 拒绝，detail.code 带 01 的稀疏码
ERR_REF_UNRESOLVABLE = "ref_unresolvable"  # 受控引用解析不到真实 hash / 版本
ERR_EVENT_REJECTED = "event_rejected"  # 05 validate_event 拒绝或类型不允许来自 frontend
ERR_EXPOSURE_CONFLICT = "exposure_conflict"  # 03 同 operation_id 异意图
ERR_RUN_NOT_TERMINAL = "run_not_terminal"  # link_run：run 尚未结束，不能折成 linked / failed
ERR_DEPENDENCY_MISSING = "dependency_missing"  # 动作依赖的对象（维护项 / 任务 / 练习）不在当前视图中
ERR_RUN_BINDING_MISMATCH = "run_binding_mismatch"  # link_run：run 或新判断不属于本会话的这次复核
ERR_INVALID_TRANSITION = "invalid_transition"  # 用原判断引用冒充新判断：版本血统不前进，等于没有重判
ERR_SOURCE_UNAVAILABLE = "source_unavailable"  # 503：run 来源身份读取失败——保持待复核，恢复后重试，不折算成裸 run

_HTTP_BY_CODE = {
    ERR_INVALID_REQUEST: 400,
    ERR_UNKNOWN_SCHEMA: 400,
    ERR_BINDING_REJECTED: 400,
    ERR_REF_UNRESOLVABLE: 400,
    ERR_EVENT_REJECTED: 400,
    ERR_ACTION_REJECTED: 400,
    ERR_RUN_NOT_TERMINAL: 400,
    ERR_DEPENDENCY_MISSING: 400,
    ERR_OWNER_FORBIDDEN: 403,
    ERR_NOT_FOUND: 404,
    ERR_VERSION_CONFLICT: 409,
    ERR_IDEMPOTENCY_MISMATCH: 409,
    ERR_EXPOSURE_CONFLICT: 409,
    ERR_STORE_CORRUPT: 500,
    ERR_MODULE_UNAVAILABLE: 503,
    ERR_SOURCE_UNAVAILABLE: 503,
}


class ApiError(Exception):
    """带稳定业务码的错误；API 层按 ``http_status`` 转 HTTP，正文 ``{"code", "message", "detail"}``。"""

    def __init__(self, code: str, message: str, *, detail: Mapping[str, Any] | None = None, http_status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = dict(detail or {})
        self.http_status = http_status if http_status is not None else _HTTP_BY_CODE.get(code, 400)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "detail": self.detail}


class StoreCorrupt(ApiError):
    def __init__(self, message: str, *, detail: Mapping[str, Any] | None = None) -> None:
        super().__init__(ERR_STORE_CORRUPT, message, detail=detail)


# --------------------------------------------------------------------------- #
# 摘要与时间
# --------------------------------------------------------------------------- #
# 绝对路径一律不出现在响应里：本仓已有测试断言 ``"/Users/" not in response.text``，
# 而本批的 gap detail 常来自底层异常串（库路径、用户目录）。在边界统一擦。
_ABS_PATH_RE = re.compile(r"(?:/Users/|/home/|/private/var/|/var/folders/|/tmp/)[^\s'\"）)，,;:]*")


def scrub_paths(value: Any) -> Any:
    """递归把绝对路径替换成 ``<path>``。只改展示，不改任何判定。"""
    if isinstance(value, str):
        return _ABS_PATH_RE.sub("<path>", value)
    if isinstance(value, list):
        return [scrub_paths(item) for item in value]
    if isinstance(value, tuple):
        return [scrub_paths(item) for item in value]
    if isinstance(value, dict):
        return {scrub_paths(k) if isinstance(k, str) else k: scrub_paths(v) for k, v in value.items()}
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest(value: Any) -> str:
    return sha256_hex(canonical_json(value))


def stable_id(prefix: str, payload: Any, *, length: int = 16) -> str:
    return f"{prefix}-{digest(payload)[:length]}"


def ensure_aware(now: Any, *, where: str = "now") -> datetime:
    if isinstance(now, datetime):
        if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
            raise ApiError(ERR_INVALID_REQUEST, f"{where} 必须带时区", detail={"where": where})
        return now
    if isinstance(now, str) and now.strip():
        try:
            parsed = datetime.fromisoformat(now.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ApiError(ERR_INVALID_REQUEST, f"{where} 不是 ISO 时刻", detail={"where": where}) from exc
        if parsed.tzinfo is None:
            raise ApiError(ERR_INVALID_REQUEST, f"{where} 必须带时区", detail={"where": where})
        return parsed
    raise ApiError(ERR_INVALID_REQUEST, f"{where} 缺失", detail={"where": where})


def utc_iso(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "+00:00")


def day_of(now: datetime, tz: Any) -> str:
    return now.astimezone(tz).date().isoformat()


# --------------------------------------------------------------------------- #
# 封套
# --------------------------------------------------------------------------- #
@dataclass
class ModuleStatus:
    status: str
    reason: str | None = None
    synthetic: bool = False
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        if self.status not in MODULE_STATUSES:
            raise ValueError(f"非法 module status {self.status!r}")
        out: dict[str, Any] = {"status": self.status, "reason": self.reason, "synthetic": bool(self.synthetic)}
        if self.detail:
            out["detail"] = dict(self.detail)
        return out


# 摘要要覆盖「这次给用户看到的判断内容」，不覆盖「这次是几点算的」。
# 这四个键全是**取数时刻**或**由取数时刻派生**的：``generated_at`` 是本次生成时间；
# 02 的 ``evaluation_at`` 是服务端可信时钟，``report_id`` / ``input_digest`` 由它算出。
# 不剔掉它们，同样的内容每秒都会得到一个新摘要，GET 的报告摘要就不再稳定
# （spec §4.4「GET 的报告摘要稳定，generated_at 可更新」），前端也没法拿它做「内容变没变」的判据。
# 剔掉它们不丢信息：被派生的那些任务、缺口、状态本身都在摘要里。
_DIGEST_VOLATILE_KEYS: frozenset[str] = frozenset({"generated_at", "evaluation_at", "report_id", "input_digest"})


def stable_projection(value: Any) -> Any:
    """递归去掉取数时刻及其派生 id，得到可用于内容摘要的投影。"""
    if isinstance(value, dict):
        return {k: stable_projection(v) for k, v in value.items() if k not in _DIGEST_VOLATILE_KEYS}
    if isinstance(value, (list, tuple)):
        return [stable_projection(item) for item in value]
    return value


def envelope(
    *,
    owner_user_id: str,
    conversation_id: str,
    generated_at: str,
    maintenance: Any,
    priority: Any,
    diagnostics: Any,
    receipt_refs: Mapping[str, Any],
    module_status: Mapping[str, ModuleStatus],
    gaps: list[dict[str, Any]],
    inputs: Mapping[str, Any],
    view_version: str,
) -> dict[str, Any]:
    """spec §4.4 响应封套。``view_digest`` 只覆盖内容，不含取数时刻与其派生 id。"""

    statuses = {name: module_status[name].to_dict() for name in MODULES}
    body = {
        "schema_version": VIEW_SCHEMA,
        "owner_user_id": owner_user_id,
        "conversation_id": conversation_id,
        "view_version": view_version,
        "maintenance": maintenance,
        "priority": priority,
        "diagnostics": diagnostics,
        "receipt_refs": dict(receipt_refs),
        "module_status": statuses,
        "gaps": list(gaps),
        "inputs": dict(inputs),
    }
    body["view_digest"] = digest(stable_projection(body))
    body["generated_at"] = generated_at
    return body


def gap(reason: str, *, ref: str | None = None, checked_at: str, retryable: bool, detail: str = "", module: str) -> dict[str, Any]:
    """封套层 gap；与 01 / 02 的 ``{reason, ref, checked_at, retryable}`` 同形，多一个 ``module``。"""
    return {"module": module, "reason": reason, "ref": ref, "checked_at": checked_at, "retryable": bool(retryable), "detail": detail}


__all__ = [name for name in globals() if name.isupper()] + [
    "ApiError",
    "ModuleStatus",
    "StoreCorrupt",
    "canonical_json",
    "day_of",
    "digest",
    "ensure_aware",
    "envelope",
    "gap",
    "scrub_paths",
    "sha256_hex",
    "stable_projection",
    "stable_id",
    "utc_iso",
]
