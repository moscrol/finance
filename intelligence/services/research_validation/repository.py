"""按 owner 隔离的不可覆盖原件仓（spec 03 §4 / §8）。

存储原语只有一个：**tmp 文件 + ``os.link`` 原子发布**。``link`` 在目标已存在时失败
（``FileExistsError``），这一步同时完成「唯一键预占」与「原件发布」——没有先检查再
写入的竞态窗口，两个进程同时发布同一路径时恰有一个创建成功，另一个拿回原件。
调用方拿到 ``(stored, created)`` 后自己比语义：同意图 → 幂等返回；异意图 → ``ConflictError``。

为什么不是 ``os.replace``：那是覆盖，覆盖会毁掉门禁需要的证据（「取最新」不等于
「删旧的」）。可变绑定（指针 / 缓存）本轨一个都没有，所以这里没有任何覆盖路径。

布局（``root`` 由 06 以 ``userspace.user_space(user).root / "research_validation"`` 注入；
本模块不从 cwd / 环境变量推断任何路径）::

    <root>/studies/<study_id>/protocol.json
    <root>/studies/<study_id>/forecasts/<case_id>/<arm_id>.json      # (study, case, arm) 唯一键即路径
    <root>/studies/<study_id>/observations/<forecast_id>/<obs_id>.json # 追加，不覆盖
    <root>/studies/<study_id>/receipts/<receipt_id>.json
    <root>/exposures/<operation_id>.json                               # owner 全局曝光台账

任何路径分量是软链 → 拒绝；对象归属 ≠ 仓 owner → 拒绝。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .contracts import (
    ContractError,
    OwnerMismatch,
    canonical_bytes,
    validate_content_id,
    validate_exposure_record,
    validate_forecast_record,
    validate_frozen_protocol,
    validate_observation_record,
    validate_operation_id,
    validate_owner,
)

_ARM_FILE_SUFFIX = ".json"


class Repository:
    """一个 owner 的原件仓。所有写入都是「只增不改」。"""

    def __init__(self, root: str | Path, owner_user_id: str) -> None:
        self.owner_user_id = validate_owner(owner_user_id)
        path = Path(root).expanduser()
        if path.is_symlink():
            raise ContractError(f"repository root 不能是软链：{path}")
        self.root = path

    # ------------------------------------------------------------------ #
    # 路径
    # ------------------------------------------------------------------ #
    @property
    def studies_dir(self) -> Path:
        return self.root / "studies"

    @property
    def exposures_dir(self) -> Path:
        return self.root / "exposures"

    def study_dir(self, study_id: str) -> Path:
        return self.studies_dir / validate_content_id(study_id, field_name="study_id")

    def protocol_path(self, study_id: str) -> Path:
        return self.study_dir(study_id) / "protocol.json"

    def forecast_path(self, study_id: str, case_id: str, arm_id: str) -> Path:
        if not isinstance(arm_id, str) or not arm_id or "/" in arm_id or arm_id.startswith("."):
            raise ContractError(f"非法 arm_id：{arm_id!r}")
        return (
            self.study_dir(study_id)
            / "forecasts"
            / validate_content_id(case_id, field_name="case_id")
            / f"{arm_id}{_ARM_FILE_SUFFIX}"
        )

    def observations_dir(self, study_id: str, forecast_id: str) -> Path:
        return (
            self.study_dir(study_id)
            / "observations"
            / validate_content_id(forecast_id, field_name="forecast_id")
        )

    def receipts_dir(self, study_id: str) -> Path:
        return self.study_dir(study_id) / "receipts"

    def exposure_path(self, operation_id: str) -> Path:
        return self.exposures_dir / f"{validate_operation_id(operation_id)}.json"

    # ------------------------------------------------------------------ #
    # 原语
    # ------------------------------------------------------------------ #
    def _guard(self, path: Path) -> None:
        """路径必须落在 root 内，且 root 到目标之间没有任何软链分量。"""
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise ContractError(f"路径越界：{path} 不在 {self.root} 内") from exc
        current = self.root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ContractError(f"路径含软链分量，拒绝：{current}")

    def _ensure_parent(self, path: Path) -> None:
        self._guard(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._guard(path.parent)

    @staticmethod
    def _fsync_dir(directory: Path) -> None:
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _read(self, path: Path) -> dict[str, Any]:
        self._guard(path)
        if path.is_symlink():
            raise ContractError(f"原件不能是软链：{path}")
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractError(f"原件读不出：{path}（{exc.__class__.__name__}）") from exc
        if not isinstance(loaded, dict):
            raise ContractError(f"原件不是 JSON 对象：{path}")
        canonical_bytes(loaded)  # 非有限数在这里炸
        return loaded

    def publish(self, path: Path, value: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """原子发布。返回 ``(落盘内容, 是否本次创建)``；已存在时返回原件，不覆盖、不报错。"""
        data = canonical_bytes(value)
        self._ensure_parent(path)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pending-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
                created = True
            except FileExistsError:
                created = False
            self._fsync_dir(path.parent)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        if created:
            return json.loads(data.decode("utf-8")), True
        return self._read(path), False

    def _list_json(self, directory: Path) -> list[Path]:
        if not directory.is_dir() or directory.is_symlink():
            return []
        self._guard(directory)
        out: list[Path] = []
        for child in sorted(directory.iterdir()):
            if child.is_symlink():
                raise ContractError(f"原件目录里出现软链，拒绝：{child}")
            if child.is_file() and child.suffix == ".json" and not child.name.startswith("."):
                out.append(child)
        return out

    def _list_dirs(self, directory: Path) -> list[Path]:
        if not directory.is_dir() or directory.is_symlink():
            return []
        self._guard(directory)
        out: list[Path] = []
        for child in sorted(directory.iterdir()):
            if child.is_symlink():
                raise ContractError(f"原件目录里出现软链，拒绝：{child}")
            if child.is_dir():
                out.append(child)
        return out

    def _own(self, record: dict[str, Any], *, what: str) -> dict[str, Any]:
        if record.get("owner_user_id") != self.owner_user_id:
            raise OwnerMismatch(f"{what} 归属 {record.get('owner_user_id')!r} ≠ 仓 owner {self.owner_user_id!r}")
        return record

    # ------------------------------------------------------------------ #
    # 协议
    # ------------------------------------------------------------------ #
    def publish_protocol(self, protocol: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        validated = validate_frozen_protocol(protocol, owner=self.owner_user_id)
        stored, created = self.publish(self.protocol_path(validated["study_id"]), validated)
        return validate_frozen_protocol(stored, owner=self.owner_user_id), created

    def load_protocol(self, study_id: str) -> dict[str, Any]:
        path = self.protocol_path(study_id)
        if not path.exists():
            raise ContractError(f"study {study_id} 不存在")
        protocol = validate_frozen_protocol(self._read(path), owner=self.owner_user_id)
        if protocol["study_id"] != study_id:
            raise ContractError("协议目录名与 study_id 不符")
        return protocol

    def list_studies(self) -> list[str]:
        return [d.name for d in self._list_dirs(self.studies_dir) if (d / "protocol.json").is_file()]

    # ------------------------------------------------------------------ #
    # 预测
    # ------------------------------------------------------------------ #
    def publish_forecast(self, forecast: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        validated = validate_forecast_record(forecast, owner=self.owner_user_id)
        path = self.forecast_path(validated["study_id"], validated["case_id"], validated["arm_id"])
        stored, created = self.publish(path, validated)
        return validate_forecast_record(stored, owner=self.owner_user_id), created

    def read_forecast(self, study_id: str, case_id: str, arm_id: str) -> dict[str, Any] | None:
        path = self.forecast_path(study_id, case_id, arm_id)
        if not path.exists():
            return None
        return validate_forecast_record(self._read(path), owner=self.owner_user_id)

    def list_forecasts(self, study_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for case_dir in self._list_dirs(self.study_dir(study_id) / "forecasts"):
            for path in self._list_json(case_dir):
                record = validate_forecast_record(self._read(path), owner=self.owner_user_id)
                if record["study_id"] != study_id or record["case_id"] != case_dir.name:
                    raise ContractError(f"预测原件位置与内容不符：{path}")
                if path.stem != record["arm_id"]:
                    raise ContractError(f"预测文件名与 arm_id 不符：{path}")
                out.append(record)
        out.sort(key=lambda f: (f["as_of"], f["case_id"], f["arm_id"]))
        return out

    # ------------------------------------------------------------------ #
    # 结果观察（追加）
    # ------------------------------------------------------------------ #
    def append_observation(self, observation: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        validated = validate_observation_record(observation, owner=self.owner_user_id)
        path = self.observations_dir(validated["study_id"], validated["forecast_id"]) / f"{validated['id']}.json"
        stored, created = self.publish(path, validated)
        return validate_observation_record(stored, owner=self.owner_user_id), created

    def list_observations(self, study_id: str, forecast_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in self._list_json(self.observations_dir(study_id, forecast_id)):
            record = validate_observation_record(self._read(path), owner=self.owner_user_id)
            if record["forecast_id"] != forecast_id or record["id"] != path.stem:
                raise ContractError(f"观察原件位置与内容不符：{path}")
            out.append(record)
        out.sort(key=lambda o: (o["observed_at"], o["id"]))
        return out

    # ------------------------------------------------------------------ #
    # 收据
    # ------------------------------------------------------------------ #
    def publish_receipt(self, receipt: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        self._own(receipt, what="receipt")
        rid = validate_content_id(receipt.get("id"), field_name="receipt.id")
        study_id = validate_content_id(receipt.get("study_id"), field_name="receipt.study_id")
        stored, created = self.publish(self.receipts_dir(study_id) / f"{rid}.json", receipt)
        return self._own(stored, what="receipt"), created

    def list_receipts(self, study_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in self._list_json(self.receipts_dir(study_id)):
            record = self._own(self._read(path), what="receipt")
            if record.get("id") != path.stem or record.get("study_id") != study_id:
                raise ContractError(f"收据原件位置与内容不符：{path}")
            out.append(record)
        out.sort(key=lambda r: (str(r.get("generated_at")), str(r.get("id"))))
        return out

    # ------------------------------------------------------------------ #
    # 曝光台账（owner 全局）
    # ------------------------------------------------------------------ #
    def publish_exposure(self, exposure: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        validated = validate_exposure_record(exposure, owner=self.owner_user_id)
        stored, created = self.publish(self.exposure_path(validated["operation_id"]), validated)
        return validate_exposure_record(stored, owner=self.owner_user_id), created

    def list_exposures(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in self._list_json(self.exposures_dir):
            record = validate_exposure_record(self._read(path), owner=self.owner_user_id)
            if f"{record['operation_id']}.json" != path.name:
                raise ContractError(f"曝光原件文件名与 operation_id 不符：{path}")
            out.append(record)
        out.sort(key=lambda e: (e["accessed_at"], e["operation_id"]))
        return out


def iter_owner_repositories(roots: Iterable[tuple[str, Path]]) -> Iterable[Repository]:
    """给 06 用的便利迭代器：``(owner, root)`` → ``Repository``。不扫目录、不猜路径。"""
    for owner, root in roots:
        yield Repository(root, owner)


__all__ = ["Repository", "iter_owner_repositories"]
