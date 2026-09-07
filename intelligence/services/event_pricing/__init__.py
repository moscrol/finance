"""事件定价第一刀：事件锚点日历 + ``EventReaction`` 事件反应回溯。

设计稿 ``docs/superpowers/specs/2026-09-07-event-pricing-slice1-calendar-reaction-design.md``。
本包只做确定性计算：编辑日历 + 官方日程 → 反应日 → 锚点标签 → 事前 / 当日 / 事后窗 → 形状标签 →
对非事件日基准过四态。路径上没有 LLM，不给概率，不写主库，产物全部落旁路库 ``history_labels.duckdb``。

日历知道**何时**，不知道**多少**：``latest_known`` 永不返回数值。
"""

from .params import EventParams, load_params
from .store import EVENT_TABLES, ensure_event_schema

__all__ = ["EVENT_TABLES", "EventParams", "ensure_event_schema", "load_params"]
