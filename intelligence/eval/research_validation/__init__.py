"""spec 03 的离线 eval 适配器：只读旁路库 / replay 原件，产出登记输入，调用 service 六函数。

方向约束：eval → services 单向。``intelligence/services/research_validation`` 不反向 import 这里。
"""

from .historical_llm import forecasts_from_replay, load_replay_records
from .outcome_source import LabelsDbOutcomeSource
from .recipes import RECIPES, resolve_recipe
from .runner import build_protocol_input, run_ablation

__all__ = [
    "LabelsDbOutcomeSource",
    "RECIPES",
    "build_protocol_input",
    "forecasts_from_replay",
    "load_replay_records",
    "resolve_recipe",
    "run_ablation",
]
