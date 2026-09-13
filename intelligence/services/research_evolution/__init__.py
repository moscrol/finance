"""06 · Workbench 集成：把 01–05 接进同一个用户入口。

spec ``docs/superpowers/specs/2026-09-13-research-evolution/06-workbench-integration.md``。

四层分工（本包不含业务判定）：

- ``contracts``：响应封套、动作枚举、稳定业务错误码；
- ``access``：有效 owner 与范围校验（``?user=`` 不是认证）；
- ``store``：本批新增用户态台账的**单 writer**（跨进程锁 + 幂等追加 + 不可变发布）；
- ``adapters`` / ``facade``：受控取数与组装，判定一律回调 01–05 的真函数。

本包属领域层 ``services/``：不 import ``intelligence.runtime``。API 在 ``intelligence/api/research_evolution.py``。
"""

from intelligence.services.research_evolution import access, adapters, contracts, facade, store
from intelligence.services.research_evolution.access import AccessPolicy, OwnerContext
from intelligence.services.research_evolution.adapters import (
    EvidenceCatalog,
    EvidenceSource,
    RiverEvidenceSource,
    StaticEvidenceSource,
)
from intelligence.services.research_evolution.contracts import (
    ACTIONS,
    MODULES,
    VIEW_SCHEMA,
    ApiError,
    ModuleStatus,
)
from intelligence.services.research_evolution.facade import Resources, ResearchEvolutionService
from intelligence.services.research_evolution.store import EvolutionStore

__all__ = [
    "ACTIONS",
    "MODULES",
    "VIEW_SCHEMA",
    "AccessPolicy",
    "ApiError",
    "EvidenceCatalog",
    "EvidenceSource",
    "EvolutionStore",
    "ModuleStatus",
    "OwnerContext",
    "ResearchEvolutionService",
    "Resources",
    "RiverEvidenceSource",
    "StaticEvidenceSource",
    "access",
    "adapters",
    "contracts",
    "facade",
    "store",
]
