"""开关板：并列原子能力的机器可读登记表。

只做三件事：读表、按 id 解析、算出哪些行够格进实验臂。**不**执行拧动——
拧动发生在 runner 的 composition root（`scripts/run_capability_switchboard.py`，
第 1 步才建），生产路径永远不读本模块。

设计稿：`docs/superpowers/specs/2026-08-22-capability-switchboard-design.md`（工具/
核验/提示词零件）与 `…-domain-predicate-coupling-design.md`（`predicate.*` 一族）。
两族同表不同 prefix。

fail closed 是本模块的存在理由：认不出的 id 抛错，不静默忽略——静默忽略会让一次
拼错的差量跑出一份「看起来正常」的收据。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "intelligence"
    / "eval"
    / "fixtures"
    / "capability_switchboard.json"
)

# operator/pack/probe 是 2026-08-26 扩容批的登记 kind：新架构（四袋/查询算子/替补探针）
# 的组件登记行。生产不读本表；这三类默认被 generate_default_switch_box 排除在盒外
# （棘轮 #3：进盒需另一次对照 + 用户确认）。
# lane 是 2026-08-31 补的：标记**选走哪条执行路**的分叉（确定性快路 / 修复链）。
# 不归进 parameter——那类是 CLI argparse 默认值，描述的是「某条命令的缺省实参」。
#
# ⚠ lane ≠ 有运行时开关。本批两行的关法都是 **route / 代码级**，各自的 notes 里
# 记着实测证伪过程：`fast-path-runner` 的构造注入产出的是中止不是换路，
# `repair-chain` 的 cap=0 被 fail-safe 归一化回默认帽。
# 本注释初版写的「关法是 composition root 的构造注入」是同一批里被推翻的说法，
# 与 `test_fast_path_constructor_injection_is_abort_not_off` 直接打架——
# 2026-08-31 质检点名，已改。**改 close_via 时记得回头看这里**：
# 枚举的注释和行的 close_via 是两处，会各自漂。
KINDS = frozenset(
    {
        "capability",
        "composer",
        "verifier",
        "prompt",
        "predicate",
        "parameter",
        "operator",
        "pack",
        "probe",
        "lane",
    }
)
STATUSES = frozenset({"active", "welded", "pending-other-branch", "retired"})
DEFAULTS = frozenset({"on", "off", "ambient"})
CANONICALS = frozenset({"exists", "missing", "contested", "other-branch"})

_REQUIRED = (
    "id",
    "kind",
    "status",
    "seam",
    "close_via",
    "default",
    "singleton_when_on",
    "chassis_survives",
    "positive_control",
    "notes",
)


class SwitchboardError(ValueError):
    """表本身不合法。"""


class UnknownSwitchError(KeyError):
    """认不出的开关 id。第 0 步的 fail-closed 就是这一条。"""


@dataclass(frozen=True)
class SwitchRow:
    id: str
    kind: str
    status: str
    seam: str
    close_via: tuple[str, ...]
    default: str
    singleton_when_on: bool
    chassis_survives: bool
    positive_control: str
    notes: str
    canonical: str | None = None

    @property
    def seam_path(self) -> str:
        """`seam` 的文件部分（`path::symbol` 里的 path）。"""

        return self.seam.split("::", 1)[0]

    @property
    def eligible_for_arm(self) -> bool:
        """够不够格进第一期实验臂。

        四个条件缺一不可。前两条区分的是两种完全不同的「关不了」：
        `welded` 是关了底盘会散，`canonical != exists` 是压根没有正典可关——
        原稿把两者都标 welded，落到表里就分不出哪些行可拧。
        """

        if self.status != "active":
            return False
        if self.kind == "predicate" and self.canonical != "exists":
            return False
        if self.kind == "predicate":
            # 正典在、面没接到生产缝 = 还没得关。进臂会让 runner 用恒真正控刷 ✅。
            from intelligence.services.predicate_faces import OWNERSHIP

            owner = OWNERSHIP.get(self.id)
            if owner is None or not owner.declared_faces:
                return False
        if not self.chassis_survives:
            return False
        return bool(self.positive_control.strip())


@dataclass(frozen=True)
class Switchboard:
    switch_set: str
    revision: str
    rows: tuple[SwitchRow, ...]

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for row in self.rows:
            if row.id in seen:
                raise SwitchboardError(f"duplicate switch id: {row.id}")
            seen.add(row.id)

    def resolve(self, switch_id: str) -> SwitchRow:
        """按 id 取行；认不出就抛，不返回 None。"""

        wanted = str(switch_id).strip()
        for row in self.rows:
            if row.id == wanted:
                return row
        raise UnknownSwitchError(wanted)

    def ids(self) -> tuple[str, ...]:
        return tuple(row.id for row in self.rows)

    def of_kind(self, kind: str) -> tuple[SwitchRow, ...]:
        return tuple(row for row in self.rows if row.kind == kind)

    def arm_ids(self) -> tuple[str, ...]:
        return tuple(row.id for row in self.rows if row.eligible_for_arm)


def _row_from_mapping(raw: Mapping[str, Any]) -> SwitchRow:
    missing = [field for field in _REQUIRED if field not in raw]
    if missing:
        raise SwitchboardError(
            f"row {raw.get('id', '<no id>')!r} missing fields: {','.join(missing)}"
        )
    kind = str(raw["kind"])
    if kind not in KINDS:
        raise SwitchboardError(f"row {raw['id']!r} has unknown kind: {kind}")
    status = str(raw["status"])
    if status not in STATUSES:
        raise SwitchboardError(f"row {raw['id']!r} has unknown status: {status}")
    default = str(raw["default"])
    if default not in DEFAULTS:
        raise SwitchboardError(f"row {raw['id']!r} has unknown default: {default}")

    canonical = raw.get("canonical")
    if kind == "predicate":
        # 谓词行必须自报正典状态：没有它就分不出「关不掉」和「没得关」。
        if canonical is None:
            raise SwitchboardError(f"predicate row {raw['id']!r} must declare canonical")
        if str(canonical) not in CANONICALS:
            raise SwitchboardError(
                f"row {raw['id']!r} has unknown canonical: {canonical}"
            )
    elif canonical is not None:
        raise SwitchboardError(f"non-predicate row {raw['id']!r} must not set canonical")

    close_via = raw["close_via"]
    if not isinstance(close_via, list) or not close_via:
        raise SwitchboardError(f"row {raw['id']!r} needs a non-empty close_via list")

    return SwitchRow(
        id=str(raw["id"]),
        kind=kind,
        status=status,
        seam=str(raw["seam"]),
        close_via=tuple(str(item) for item in close_via),
        default=default,
        singleton_when_on=bool(raw["singleton_when_on"]),
        chassis_survives=bool(raw["chassis_survives"]),
        positive_control=str(raw["positive_control"]),
        notes=str(raw["notes"]),
        canonical=None if canonical is None else str(canonical),
    )


def load_switchboard(path: Path | None = None) -> Switchboard:
    source = Path(path) if path is not None else _FIXTURE
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise SwitchboardError("switchboard fixture must be a JSON object")
    raw_rows: Iterable[Any] = payload.get("rows") or ()
    if not isinstance(raw_rows, list) or not raw_rows:
        raise SwitchboardError("switchboard fixture must contain a non-empty rows list")
    return Switchboard(
        switch_set=str(payload.get("switch_set") or ""),
        revision=str(payload.get("revision") or ""),
        rows=tuple(_row_from_mapping(row) for row in raw_rows),
    )
