"""02 · 下一步研究排序：用有限时间核查最重要的判断。

两个纯接口（spec §4）：

* ``adapt_candidates(source_records, context)`` —— 只读地把 01 维护项、研究项目投影、
  现役研究队列、补数请求转成 ``research-task/v1`` 候选；
* ``prioritize(candidates, policy, budget, evaluation_at)`` —— 确定性分组、合并、
  贪心预算，产出 ``research-priority/v1`` 报告；``render_view`` / ``render_markdown``
  投影给 06。

包内不读文件、数据库、网络或系统时钟；来源读取、授权、点击执行与落盘归 06。
"""

from .adapters import (
    SOURCE_DATA_REQUEST,
    SOURCE_MAINTENANCE_ITEM,
    SOURCE_MAINTENANCE_REPORT,
    SOURCE_RESEARCH_PROJECT,
    SOURCE_RESEARCH_QUEUE,
    adapt_candidates,
)
from .contracts import (
    POLICY_VERSION,
    SCHEMA_CANDIDATES,
    SCHEMA_REPORT,
    SCHEMA_TASK,
    SCHEMA_VIEW,
    Budget,
    ContractError,
    Policy,
    identity_key,
    task_id_for,
    validate_task,
)
from .ranker import prioritize
from .render import render_markdown, render_view

__all__ = [
    "POLICY_VERSION",
    "SCHEMA_CANDIDATES",
    "SCHEMA_REPORT",
    "SCHEMA_TASK",
    "SCHEMA_VIEW",
    "SOURCE_DATA_REQUEST",
    "SOURCE_MAINTENANCE_ITEM",
    "SOURCE_MAINTENANCE_REPORT",
    "SOURCE_RESEARCH_PROJECT",
    "SOURCE_RESEARCH_QUEUE",
    "Budget",
    "ContractError",
    "Policy",
    "adapt_candidates",
    "identity_key",
    "prioritize",
    "render_markdown",
    "render_view",
    "task_id_for",
    "validate_task",
]
