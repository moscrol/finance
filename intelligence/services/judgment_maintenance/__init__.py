"""判断持续维护（研究进化批次 01；spec ``docs/superpowers/specs/2026-09-13-research-evolution/01-judgment-maintenance.md``）。

沿私有判断**已绑定的证据**检查变化，回答「哪条依据变了、哪条显式条件触发了、哪里需要复核」。

三个纯函数入口（无文件 / 库 / 网络访问；归属只认经验证的 ``owner_user_id``）：

- ``assess(...)``          冻结输入 → ``MaintenanceReport``（同输入同 id；``generated_at`` 不进摘要）
- ``validate_action(...)`` 一条用户命令能否落到维护项上 → ``ActionResult``（拟追加事件，不写入）
- ``reduce_actions(...)``  已落盘事件按台账顺序折到报告上（幂等、冲突、到期恢复）

``adapters`` 把旧读取器加载出的 checkpoint / judgment / 情景树 dict 适配成合同对象；持久化、授权、
API / UI 归同批 06。哈希变化只说明「依据变了、需要复核」，**不**判原判断被推翻。
"""

from intelligence.services.judgment_maintenance import adapters, conditions, contracts
from intelligence.services.judgment_maintenance.actions import (
    Outcome,
    apply_event,
    event_from_command,
    reduce_actions,
    validate_action,
    wake_if_expired,
)
from intelligence.services.judgment_maintenance.assess import assess
from intelligence.services.judgment_maintenance.contracts import (
    ACTIONS,
    BINDING_SCHEMA_VERSION,
    CHANGE_TYPES,
    COMMANDS,
    CONDITION_ROLES,
    EPISTEMIC_STATES,
    EVENT_KINDS,
    ITEM_STATUSES,
    PIT_GRADES,
    POLICY_SCHEMA_VERSION,
    REASON_CODES,
    SCHEMA_VERSION,
    ActionCommand,
    ActionResult,
    BindingCondition,
    ConditionObservation,
    DependencyBinding,
    EvidenceVersion,
    Gap,
    MaintenanceContractError,
    MaintenanceItem,
    MaintenancePolicy,
    MaintenanceReport,
    ManagementEvent,
    ObjectRef,
    parse_report,
)

__all__ = [
    "ACTIONS",
    "BINDING_SCHEMA_VERSION",
    "CHANGE_TYPES",
    "COMMANDS",
    "CONDITION_ROLES",
    "EPISTEMIC_STATES",
    "EVENT_KINDS",
    "ITEM_STATUSES",
    "PIT_GRADES",
    "POLICY_SCHEMA_VERSION",
    "REASON_CODES",
    "SCHEMA_VERSION",
    "ActionCommand",
    "ActionResult",
    "BindingCondition",
    "ConditionObservation",
    "DependencyBinding",
    "EvidenceVersion",
    "Gap",
    "MaintenanceContractError",
    "MaintenanceItem",
    "MaintenancePolicy",
    "MaintenanceReport",
    "ManagementEvent",
    "ObjectRef",
    "Outcome",
    "adapters",
    "apply_event",
    "assess",
    "conditions",
    "contracts",
    "event_from_command",
    "parse_report",
    "reduce_actions",
    "validate_action",
    "wake_if_expired",
]
