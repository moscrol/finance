"""市场态题型的知识注入门控（2026-08-26 三轮消融实证）。

「工具扩展上下文所以总是正收益」在实测中不成立：市场态题型（问「当前主线/盘面
在干什么」——答案只该来自当日盘面数据）上，知识层注入是**稳定负贡献**：

- 判读基线全局 guidance：主线题七次读数全部 ≤0，均值 ≈ -2.3/20
  （首轮 -2、确认轮 -4、五变体定向轮 -3/-1/-1/-5/0）；
- KB W 源召回：同题型七次读数五负一正一平，均值 ≈ -1.3/20；
- 伤害形状：directness -1.4 / relevance -0.8——历史研报观点与判读规则让模型
  绕弯子、不敢直接报当天数据的结论；truth_boundary 反而 +0.8（代价已计入净账）。

收据：`intelligence/eval/runs/20260826T{101858,114208,121041}Z-quality-ablation.json`
（harness `scripts/run_quality_ablation.py`，双臂盲评）。

先例：`ask.py` 对 QUESTION_MARKET_FORECAST 早已确定性关闭 W（「通用 wiki 语义召回
既慢又容易把『市场』锚到无关公司」）——本模块是同一判断的实证化推广，并让
判读基线与 W 源共用**一个**门控点，而不是两处各写一个 if。

对照题型（不门控）的证据：估值题上 KB 两轮恒 +8、判读基线 +2/+8——知识层在
知识型题上是命脉，门控范围只限实测为负的题型，禁止顺手扩大。

回滚：env ``FINANCE_MARKET_STATE_KNOWLEDGE_GATE=0`` 整体关闭本门控（恢复门控前
行为），供 A/B 与紧急回退；缺省开启。
"""

from __future__ import annotations

import os

from intelligence.services import reading_baseline

#: 实测为负的市场态题型。两个引擎共用同一词表（answer_orchestrator / task_frame）。
#: 扩充本集合前必须先有对应题型的消融读数——「看起来也像盘面题」不算证据。
MARKET_STATE_QUESTION_TYPES = frozenset({"market_watch"})

ENV_FLAG = "FINANCE_MARKET_STATE_KNOWLEDGE_GATE"
_FALSEY = {"0", "false", "no", "off"}


def gate_enabled(env: dict[str, str] | None = None) -> bool:
    """门控总开关。缺省开启；显式设 0/false/no/off 才关（关=恢复门控前行为）。"""

    raw = (env or os.environ).get(ENV_FLAG)
    if raw is None:
        return True
    return str(raw).strip().lower() not in _FALSEY


def inject_knowledge(question_type: str, env: dict[str, str] | None = None) -> bool:
    """该题型是否注入知识层（判读基线全局 guidance / KB W 源）。

    True=照常注入（缺省行为）；False=市场态题型且门控开启，跳过注入。
    """

    if not gate_enabled(env):
        return True
    return str(question_type or "").strip() not in MARKET_STATE_QUESTION_TYPES


def reading_guidance_for(question_type: str, env: dict[str, str] | None = None) -> str:
    """给合成/episode 注入点用的判读 guidance：市场态题型返回空串（整段不注入）。

    空串语义与 ``reading_baseline.baseline_guidance()`` 关闭时一致——调用方
    已有「空则不拼段落」的处理，无需新增分支。
    """

    if not inject_knowledge(question_type, env):
        return ""
    return reading_baseline.baseline_guidance(env)
