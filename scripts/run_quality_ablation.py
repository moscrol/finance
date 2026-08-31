#!/usr/bin/env python3
"""质量层消融：默认盒 vs 盒减一颗，真实 LLM 答案 + 盲评 rubric，输出组件边际贡献。

开关板第 0-3 步只回答「这颗拧得动吗」（结构层）；本脚本回答「关了这颗，答案差多少分」
——设计稿预留的那份「另一份评测」（质量棘轮）。两者刻意分开：结构读数用 scripted
模型零成本可重复，质量读数要花真 LLM 调用，混在一份 artifact 里会互相污染。

臂设计：每题一个**共享基线臂**（默认全开）+ 每颗组件一个关断臂。关法用组件的
**真实生产旋钮**（env / CLI flag），不经过开关板（生产不读表）：

    reading-baseline   env FINANCE_READING_BASELINE=0   （判读基线整段不注入）
    evidence-judge     env ASK_EVIDENCE_JUDGE=off       （证据裁判关闭）
    kb-rag             flag --no-wiki-rag               （知识库 W 源关闭）

评审：每份答案**独立盲评**——judge 只见问题+答案，不见臂标签；评审顺序按种子洗牌，
防止位置效应。rubric 复用 capability_monotonicity 的五维 0-4
（directness / coverage / relevance / truth_boundary / usefulness），总分 sum/20。
judge 输出解析失败 = 该份记 unscored，不编造、不计入聚合。

**方差门（默认开）**：每题的基线答案额外重复盲评 `--calibration-repeats` 次。文本
逐字相同 → 真值 Δ 必为 0，量出来的散布就是**当次**判官复评噪声。每颗组件的边际
贡献都要跨过按该噪声算出的门槛才允许下结论，否则记 `no_call`。没实测到方差
（重复次数为 0 / 全部 unscored）时**一律 no_call**，不回退到历史噪声底。

前置（fail-closed）：需要 LLM key（建议 `. <(grep '^export ' \
~/.local/bin/start-finance-workbench)` 继承生产 provider 链与 FINANCE_WS /
KNOWLEDGE_WIKI 数据根）；无 key 直接退出，绝不产出模板答案冒充读数。

用法：
    python3 scripts/run_quality_ablation.py --dry-run          # 只打印执行计划
    python3 scripts/run_quality_ablation.py                    # 三颗 × 六题全跑
    python3 scripts/run_quality_ablation.py --components kb-rag --max-questions 2
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# 「差异小于噪声底就不许下结论」这条判定规则本仓只有一处实现，本脚本复用它而不
# 另写一份 if。两份比较规则的那天，改一处、另一处继续发旧读数。
#
# ⚠ 量纲提醒（2026-08-31 质检点名）：`ab_decision` 的第二个形参在真本源里叫
# `baseline_flip_rate`，那边传的是 0-1 的**翻转率**；这里传的是 rubric 分尺度上的
# **门槛**（σ×SE，单位是分/20）。函数体只做 `abs(delta) < floor` 的纯比较，
# 与单位无关，所以复用是对的——但两侧的量纲必须各自自洽，**不能把两边的数放一起比**。
# 名字留在上游、语义在这里收窄，故本地起一个说明单位的别名。
from intelligence.eval.variance_baseline import ab_decision as _compare_against_floor  # noqa: E402


def ab_decision(observed_delta: float, threshold_same_unit: float) -> str:
    """`variance_baseline.ab_decision` 的同单位封装：两个入参必须同尺度。"""

    return _compare_against_floor(observed_delta, threshold_same_unit)

RUBRIC_DIMENSIONS = ("directness", "coverage", "relevance", "truth_boundary", "usefulness")
_JUDGE_ANSWER_CHARS = 6000  # 声明式截断：限定语在 prompt 里排在答案之前

# rubric 一改，分数口径就变，跨版本的绝对分与分差都不可比。版本号入收据 +
# 聚合时同版校验，比「记得别混用」可靠。改判据必须提版本号。
RUBRIC_VERSION = "v3-veto-split"

# 判官 provider 的进程内句柄。放模块级是为了让 `judge_answer` 保持原签名——
# 它被 `rejudge_quality_ablation.py` 当回调注入，加参数会打断那条链。
_JUDGE_OVERRIDE: dict[str, object] = {"provider": None}

# 关断臂用生产旋钮，与开关板种子表的 close_via 一致（表是登记，这里是执行）。
COMPONENTS: dict[str, dict[str, object]] = {
    "reading-baseline": {
        "env": {"FINANCE_READING_BASELINE": "0"},
        "flags": (),
        "close_via": "env:FINANCE_READING_BASELINE=0",
    },
    "evidence-judge": {
        "env": {"ASK_EVIDENCE_JUDGE": "off"},
        "flags": (),
        "close_via": "env:ASK_EVIDENCE_JUDGE=off",
    },
    "kb-rag": {
        "env": {},
        "flags": ("--no-wiki-rag",),
        "close_via": "flag:--no-wiki-rag",
    },
}


@dataclass(frozen=True)
class Question:
    case_id: str
    text: str
    as_of: str


# 前五道与 capability_monotonicity 默认题集同源（含 as_of 锚定，跨臂可比）；
# 第六道补题材类：kb-rag / reading-baseline 在该题型上最该发力。
QUESTIONS: tuple[Question, ...] = (
    Question("rebound-duration", "昨天的反弹能持续多久（只讨论 A 股整体市场，不讨论个股）", "2026-07-22"),
    Question("index-rebound-space", "科创50你认为反弹空间有多少", "2026-07-22"),
    Question("ruihuatai-valuation", "瑞华泰的合理估值", "2026-07-22"),
    Question("weekly-market-cause", "这一周行情下跌的主要原因是什么", "2026-07-22"),
    Question("current-mainline", "目前市场的主线是什么", "2026-07-22"),
    Question("theme-liquid-cooling", "液冷服务器这个题材现在处于什么阶段", "2026-07-22"),
)

# v1 原文逐字保留：跨版噪声底对照要拿它做对照臂，旧收据复现也要它。
# 别删——删了「v2 更稳」就永远只能是推断。
_JUDGE_SYSTEM_V1 = (
    "你是金融研究答案的盲评审。你只看到问题和一份答案，不知道它出自哪个系统配置。"
    "按五个维度各打 0-4 分（0=缺失或错误，1=严重不足，2=部分达标，3=基本完整，4=完全达标）：\n"
    "directness=是否直接回答了问题；coverage=关键面是否覆盖（数据/证据/反面/验证点）；"
    "relevance=内容是否切题不注水；truth_boundary=是否诚实标注数据边界与不确定性、无编造痕迹；"
    "usefulness=对做研究决策的人是否可用。\n"
    '严格输出 JSON：{"directness":0,"coverage":0,"relevance":0,"truth_boundary":0,'
    '"usefulness":0,"justification":"一句话"}'
)

# rubric v2：把「展示深刻理解」式的抽象判断改成**可数、可核对**的锚点。
#
# 依据 ai-agent-book ch6「Rubric 四准则」（Scale AI *Rubrics as Rewards*）：
#   ① 基于专家指导 ② 全面覆盖（含 Pitfall 陷阱项）③ 重要性权重（支持 Veto）
#   ④ **自包含评估：可验证而非抽象**——写「引用≥2 个权威理论」，
#      不要写「展示深刻理解」。
#
# v1 的五个维度全是 ④ 明令避免的那类写法（「是否直接回答了问题」
# ≈「展示深刻理解」），这是判官抖动的**根源**而非症状：本仓 2026-08-01 实测
# （`agent-memory/10_knowledge/eval-harness-variance-governance.md`）同一判官下
# 数值型断言翻转 0%、措辞型断言翻转 67%——两个数量级的差距来自判据写法。
#
# 另按 ch6「LLM-as-Judge 两大偏差」加了长度偏差防护（显式声明长度不是优点）。
# 位置偏差本脚本原本就防了：评审顺序按种子洗牌。
_JUDGE_SYSTEM_V2 = (
    "你是金融研究答案的盲评审。你只看到问题和一份答案，不知道它出自哪个系统配置。\n"
    "评分前先在心里点数，再给分。**长度不是优点**：更长、更多小标题、更多套话都不加分；"
    "同等信息量下更短的答案不应低于更长的答案。\n\n"
    "五个维度各 0-4 分，按下列**可核对**的锚点判定（先找证据再给分，不要凭整体印象）：\n\n"
    "directness（结论位置与对位）：4=答案前 1/3 内有明确结论句，且问题里每个子问都被点名回应；"
    "3=前 1/3 有明确结论句，但漏了某个子问；2=有结论句但出现在后 2/3；"
    "1=没有成句的结论，要读者自己从材料里拼；0=通篇未给结论或答非所问。\n\n"
    "coverage（要件计数）：数四类要件各有没有——(a) 具体数据（带数值）"
    "(b) 数据来源或口径（表名/日期/出处）(c) 反面或风险情形 (d) 可验证的观察点。"
    "4=四类齐；3=三类；2=两类；1=一类；0=一类都没有。\n\n"
    "relevance（离题段落计数）：数与所问问题无关的段落数。4=0 段；3=1 段；"
    "2=2-3 段；1=超过一半段落离题；0=整体跑题。\n\n"
    "truth_boundary（数字与边界，**本维度是陷阱项**）：先数关键数字里有几个带来源或日期。"
    "4=关键数字全部带来源或日期，且不确定处显式标注（如「截至 X 日」「尚未验证」）；"
    "3=多数带，个别缺；2=约半数带；1=多数裸数字；"
    "0=出现下列任一即判 0（一票否决）——数字无出处且与答案内其他陈述自相矛盾、"
    "把推测写成既成事实、声称做过实际没做的检索。\n\n"
    "usefulness（可执行性）：4=给出下一步动作**且**写明触发条件或验证方式；"
    "3=给出下一步动作但无触发条件；2=只给方向性建议；1=只复述现状；0=无任何可用信息。\n\n"
    "另外单列检测到的陷阱（可为空数组）：hallucination（编造数字或来源）、"
    "sycophancy（迎合提问者预设而非依据数据）、keyword_stuffing（堆砌术语无实质）、"
    "evasion（回避问题核心）。\n\n"
    '严格输出 JSON，不要任何解释或 markdown 围栏：'
    '{"directness":0,"coverage":0,"relevance":0,"truth_boundary":0,'
    '"usefulness":0,"pitfalls":[],"justification":"一句话，点名你数到的证据"}'
)

# rubric v3：把「一票否决」从**分数**里拿出来。
#
# 2026-08-31 实测证伪了 v2 的设计（收据 ~/.finance-runtime/rubric-variance-ab.json，
# 5 题 × 3 次 × 同判官同答案，调用顺序交错）：v2 在 4/5 题上确实更紧
# （极差 2 → 1/1/1/0），**但合并 sd 反而从 1.13 涨到 1.44**，被单独一道题拉爆——
# `current-mainline` 三次打出 7/9/13，极差 6。
#
# 机制点得名：那是**唯一**一道被判 `hallucination` 的题。v2 给 truth_boundary 写了
# 「出现任一即判 0（一票否决）」，于是判官对「算不算编造」摇摆时，
# 这一维在 0 与 3 之间跳，总分跟着跳 4 分——**否决是阶跃函数，把一个二值判断的
# 抖动放大成了分数抖动**。
#
# 书（ch6 准则 ③）说 rubric 支持 Veto，但书里的 Veto 用在**安全违规的通过/失败
# 决定**上（零容忍），不是用在喂进 A/B 分差的连续分上。两者混在一起就是本例。
# v3 的拆法：陷阱项照常检测并单列（决策层照用，出现即该拦住这份读数），
# 但**不再改任何维度的分**；truth_boundary 回到自己的连续锚点。
_JUDGE_SYSTEM_V3 = _JUDGE_SYSTEM_V2.replace(
    "truth_boundary（数字与边界，**本维度是陷阱项**）：先数关键数字里有几个带来源或日期。"
    "4=关键数字全部带来源或日期，且不确定处显式标注（如「截至 X 日」「尚未验证」）；"
    "3=多数带，个别缺；2=约半数带；1=多数裸数字；"
    "0=出现下列任一即判 0（一票否决）——数字无出处且与答案内其他陈述自相矛盾、"
    "把推测写成既成事实、声称做过实际没做的检索。\n\n",
    "truth_boundary（数字与边界）：只数关键数字里有几个带来源或日期。"
    "4=全部带来源或日期，且不确定处显式标注（如「截至 X 日」「尚未验证」）；"
    "3=多数带，个别缺；2=约半数带；1=多数裸数字；0=通篇无出处。"
    "**本维度只按上面的比例给分**：即使你判定有编造，也不要因此改这一维的分——"
    "把它写进 pitfalls 即可，那一项单独记录、不折进分数。\n\n",
)
assert _JUDGE_SYSTEM_V3 != _JUDGE_SYSTEM_V2, "v3 替换没生效：v2 原文已漂"

# 版本 → prompt 的单一真本源。`RUBRIC_VERSION` 因此是个真的选择器，
# 不只是贴在收据上的标签：跨版对照与旧收据复现都从这里取。
JUDGE_SYSTEMS: dict[str, str] = {
    "v1-abstract": _JUDGE_SYSTEM_V1,
    "v2-selfcontained": _JUDGE_SYSTEM_V2,
    "v3-veto-split": _JUDGE_SYSTEM_V3,
}


def _fail(msg: str) -> "SystemExit":
    return SystemExit(f"❌ {msg}")


def require_llm_ready() -> None:
    from intelligence.services import llm_refine

    if not llm_refine.detect_providers():
        raise _fail(
            "未配置 LLM key——质量臂不许用模板答案冒充读数。"
            "先 `. <(grep '^export ' ~/.local/bin/start-finance-workbench)` 再跑。"
        )


def run_ask(
    question: Question,
    *,
    extra_env: dict[str, str],
    extra_flags: tuple[str, ...],
    exports_dir: str,
    timeout: float,
) -> dict[str, object]:
    cmd = [
        sys.executable,
        "-m",
        "intelligence.cli",
        "ask",
        question.text,
        "--date",
        question.as_of,
        "--compose",
        "--user",
        "quality-ablation",
        "--no-score",
        # 澄清短路会用 2 秒返回一句反问冒充答案，两臂都短路时分差恒 0（假读数）。
        "--no-clarify",
        "--exports-dir",
        exports_dir,
        *extra_flags,
    ]
    env = {**os.environ, **extra_env}
    started = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(REPO),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"ask 超时（>{timeout}s）", "answer": ""}
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    answer = (proc.stdout or "").strip()
    # answer_lint 质检门用非零退出码表达「已交卷但标低置信」——那是答案的属性，
    # 不是失败；判失败会把整臂丢掉。只有「没有实质答案」才算失败。
    if len(answer) < 200:
        return {
            "ok": False,
            "error": f"exit={proc.returncode} 答案过短({len(answer)}字) "
            f"stderr尾={(proc.stderr or '')[-300:]}",
            "answer": answer,
            "elapsed_sec": elapsed,
        }
    return {
        "ok": True,
        "answer": answer,
        "elapsed_sec": elapsed,
        "exit_code": proc.returncode,
        "lint_flagged": proc.returncode != 0,
    }


def _parse_judge_payload(
    payload: object, *, rubric_version: str = RUBRIC_VERSION
) -> dict[str, object] | None:
    """严格解析五维打分；任何缺失/越界返回 None（调用方决定重试或记 unscored）。"""

    if not isinstance(payload, dict):
        return None
    scores: dict[str, int] = {}
    for dim in RUBRIC_DIMENSIONS:
        try:
            value = int(payload.get(dim))
        except (TypeError, ValueError):
            return None
        if not 0 <= value <= 4:
            return None
        scores[dim] = value
    raw_pitfalls = payload.get("pitfalls")
    pitfalls = (
        [str(item)[:40] for item in raw_pitfalls if str(item).strip()]
        if isinstance(raw_pitfalls, list)
        else []
    )
    return {
        "scored": True,
        "rubric_version": rubric_version,
        "scores": scores,
        "total": sum(scores.values()),
        "normalized": round(sum(scores.values()) / 20.0, 4),
        # 陷阱项单列，不折进总分：它是**定性**信号（幻觉/迎合/堆砌/回避），
        # 折进 0-20 会被其他维度稀释掉，而这四类里任何一类出现都该被人看见。
        "pitfalls": pitfalls,
        "justification": str(payload.get("justification") or "")[:200],
    }


def provider_label(provider: object) -> str | None:
    """把 provider 压成可入 JSON 的身份串 ``name/model``。

    ``llm_refine.complete`` 回的是 ``LLMProvider`` 数据类，直接塞进收据会在
    ``json.dumps`` 那步炸——判官已经跑完、钱已经花了，收据却写不出来。
    """

    if provider is None:
        return None
    name = getattr(provider, "name", None)
    model = getattr(provider, "model", None)
    if name and model:
        return f"{name}/{model}"
    return str(name or provider)


def model_family(label: str | None) -> str:
    """从 ``name/model`` 串里取**家族**，用于判断判官与合成是否偏见正交。

    书（ch6 多源异构评判）要的是不同**家族**（「Agent 用 Claude 就用 GPT+Gemini 评」），
    不是不同端点、也不是不同型号。中转网关会同时服务多个家族，所以：
    - `zhipu/glm-5.3` vs `judge/gpt-5.6-sol` → glm vs gpt，**是异构**；
    - `custom/gpt-5.6-terra` vs `custom-judge/gpt-5.6-sol` → 都是 gpt，**不是**。

    取法：模型名去掉 provider 前缀后的第一个字母段。够用且可解释；
    认不出来时返回原串（宁可判成同族而误拦，不要误放）。
    """

    if not label:
        return ""
    model = str(label).split("/", 1)[-1].strip().lower()
    match = re.match(r"[a-z]+", model)
    return match.group(0) if match else model


def resolve_judge(*, require_independent: bool) -> dict[str, object]:
    """解析盲评判官，并回答「它和写答案的是不是同一个模型」。

    2026-08-31 实测的问题：本脚本此前直接调 ``llm_refine.complete()``，走的是
    **合成链**（``LLM_MODEL``），也就是 `gpt-5.6-terra` 既写答案又给自己打分。
    仓内早有独立判官通道（``llm_refine.judge_provider()`` →
    ``LLM_JUDGE_BACKEND=grok-cli`` 或 ``LLM_JUDGE_*``），只是消融臂没接。

    为什么这不是小事（ai-agent-book ch6「古德哈特定律」）：判官与被判者同源时，
    模型的系统性偏差会**同时**骗过创作与评审，两边的错误相关，读数看起来正常。
    书里给的缓解是「多源异构评判：Agent 用 Claude 就用 GPT+Gemini 评」——
    关键是**不同家族**，不是不同模型名。同家族同网关只降一点相关性，不解决问题。

    ``require_independent`` 默认为真且**fail-closed**：解析不出独立判官就拒跑，
    不静默退回自审。静默退回正是这个缺陷此前活了这么久的原因——
    自审跑出来的收据和独立评审的收据长得一模一样。
    """

    from intelligence.services import llm_refine

    composer = llm_refine.detect_provider(None)
    override = llm_refine.judge_provider()
    composer_label = provider_label(composer)
    judge_label = provider_label(override) if override is not None else composer_label

    if override is None:
        independence, reason = "correlated", "未配置独立判官，盲评会落回合成链（自己评自己）"
    elif composer is not None and getattr(override, "model", None) == getattr(
        composer, "model", None
    ):
        independence, reason = "correlated", "独立判官解析出的模型与合成模型同名"
    elif getattr(override, "transport", "") == "cli":
        independence, reason = "independent", "独立客户端（CLI），与 HTTP 合成链解耦"
    elif model_family(composer_label) != model_family(judge_label):
        # 书要的是**不同家族**（偏见正交），不是不同端点。同一个网关也能同时
        # 服务 glm 与 gpt——2026-08-31 实测本机就是这个配置，而本函数初版只看
        # transport，把它误判成 weak，等于用「机制」冒充「家族」。
        independence, reason = "independent", (
            f"跨模型家族：{model_family(composer_label)} vs {model_family(judge_label)}"
        )
    else:
        # 同家族不同型号：书里的「次优但仍降低相关性」。不当成独立，
        # 但也不拦——由调用方按 --judge-independence 决定。
        independence, reason = "weak", "同家族不同型号：降低相关性但非异构家族"

    if require_independent and independence != "independent":
        raise _fail(
            f"判官独立性不足（{independence}）：{reason}。\n"
            f"  合成模型={composer_label}  判官={judge_label}\n"
            "  修法一（推荐，异构家族）：export LLM_JUDGE_BACKEND=grok-cli\n"
            "  修法二：export LLM_JUDGE_API_KEY=... LLM_JUDGE_BASE_URL=... LLM_JUDGE_MODEL=...\n"
            "  确实要用相关自审跑（读数不可用于下结论）：--judge-independence allow-correlated"
        )
    return {
        "independence": independence,
        "reason": reason,
        "composer": composer_label,
        "judge": judge_label,
        "override": override,
    }


def deterministic_score(question: Question, answer: str) -> dict[str, object]:
    """确定性判据层：零 LLM、零 IO，因此**方差恒为 0**。

    本仓 2026-08-01 的结论是「先确定性判据，后语义判官」，实测同判官下
    数值型断言翻转 0% / 措辞型 67%。`finance_answer_rubric` 早就是这样一份
    确定性评分器（按股票代码/ISO 日期/引用编号/百分比/金额等**证据标记**计数），
    只是消融臂没用它。

    它测不了推理对不对，但它测得**稳**：同一份答案永远同一个分。所以它给出
    第二路无噪声信号——语义判官那路读不出来的时候，先看这一路动没动。
    """

    from intelligence.eval.finance_answer_rubric import score_answer

    score = score_answer(question.text, answer)
    return {
        "total": score.total_score,
        "max": score.max_score,
        "percent": round(score.percent, 2),
        "grade": score.grade,
        "decision_eligible": score.decision_eligible,
        "dimensions": {d.key: d.score for d in score.dimensions},
    }


def judge_answer(
    question: Question,
    answer: str,
    *,
    attempts: int = 2,
    rubric_version: str = RUBRIC_VERSION,
) -> dict[str, object]:
    """盲评一份答案；解析失败重试一次（带更硬的格式提示）。

    首轮实测：12k 字答案的评审输出偶发非 JSON，theme 题因此整题报废
    （基线未评 = 三个组件全部失去该题）。重试一次能救回大多数瞬时格式失误；
    仍失败则记 unscored——绝不编造分数。
    """

    from intelligence.services import llm_refine

    body = answer
    truncated = False
    if len(body) > _JUDGE_ANSWER_CHARS:
        body = body[:_JUDGE_ANSWER_CHARS]
        truncated = True
    header = "（以下答案已按预算截断，只保留开头部分）\n" if truncated else ""
    base_prompt = f"问题：{question.text}\n\n{header}答案：\n{body}"
    last_reason = "未尝试"
    for attempt in range(max(1, attempts)):
        prompt = base_prompt
        if attempt > 0:
            prompt = (
                "上一次输出无法解析。这次**只输出 JSON 对象本身**，"
                "不要任何解释、markdown 围栏或其他文字。\n\n" + base_prompt
            )
        messages = [
            {"role": "system", "content": JUDGE_SYSTEMS[rubric_version]},
            {"role": "user", "content": prompt},
        ]
        # 走独立判官链（若已解析）。照抄仓内既有用法
        # （`evidence_judge.py:95` 的 judge_override + provider_override）。
        override = _JUDGE_OVERRIDE.get("provider")
        if override is not None:
            with llm_refine.provider_override(override):
                content, provider, reason = llm_refine.complete(
                    messages, timeout=90.0, temperature=0.1
                )
        else:
            content, provider, reason = llm_refine.complete(
                messages, timeout=90.0, temperature=0.1
            )
        if content is None:
            # 无 key / 预算不足：重试同样会失败，直接放弃。
            return {"scored": False, "reason": reason, "attempts": attempt + 1}
        parsed = _parse_judge_payload(
            llm_refine._extract_json(content), rubric_version=rubric_version
        )
        if parsed is not None:
            parsed["attempts"] = attempt + 1
            # 记下实际出分的 provider：跨轮补评时，「这一份是谁评的」是分差
            # 可比性的成立条件，不记就只能靠假设。
            parsed["provider"] = provider_label(provider)
            return parsed
        last_reason = "judge 输出无法解析为合法五维 JSON"
    return {"scored": False, "reason": last_reason, "attempts": max(1, attempts)}


# ---------------------------------------------------------------- 方差门
#
# 为什么不引用历史噪声底（方差治理文档的 |Δ|≲2.4/20）：2026-08-28 实测
# index-rebound-space 三臂答案 md5 **逐字相同**，盲评却打出 12/13/15——同文本
# 重评的散布比历史底还大。判官模型、prompt、温度任一变动，历史底就失效，
# 而它失效的时候没有任何信号：读数照常产出，只是不再成立。
# 已确立原则（`docs/superpowers/specs/2026-08-28-shared-memory-plane-design.md`
# §6）：**每轮盲评故意塞一对相同答案实测当次方差，不引用历史噪声底。**
# 本模块是该原则在消融臂上的执行件。
#
# ⚠ 覆盖面限定（写在收据里，别在结论里含糊过去）：本底只含**判官复评**方差，
# 不含 ask 侧重跑方差（同 prompt 不同采样 → 不同答案）。所以它是噪声的
# **下界**，跨过它是下结论的必要条件、不是充分条件。
CALIBRATION_MIN_REPEATS = 2

NOISE_FLOOR_FORMULA = (
    "sd_judging = sqrt(mean(per_question_variance(重复评分总分))); "
    "sd_delta_single_question = sd_judging * sqrt(2)（两次独立评分之差）; "
    "threshold(n) = sigma * sd_delta_single_question / sqrt(n)，"
    "n = 该组件双方都 scored 的题数; "
    "|marginal_contribution_total| < threshold(n) -> no_call"
)


def judge_noise_floor(
    calibration: Sequence[Mapping[str, object]], *, sigma: float = 2.0
) -> dict[str, object]:
    """从「同一份答案重复盲评」的散布，量出当次判官噪声。

    数学逐步写出来，因为这份数字要拿来做合并决定：

    1. 每题的重复评分 → 组内样本方差；跨题合并（各题方差取均值再开方）
       → 单次评分的标准差 ``sd_judging``。
    2. 组件的每题 Δ = 关断臂一次评分 − 基线臂一次评分，是**两次独立评分之差**
       → ``sd(Δ_单题) = sd_judging × √2``。
    3. 组件边际贡献是 n 道题 Δ 的**均值** → 标准误 ``SE = sd_judging×√2 / √n``。
    4. 门槛 = ``sigma × SE``（默认 2，约 95% 双侧）。

    门槛随 n 变，所以不在这里定死一个数，由 :func:`threshold_for` 按各组件
    自己的可用题数现算——可用题少的组件本就该要更大的 Δ 才敢下结论。
    """

    per_question: list[dict[str, object]] = []
    variances: list[float] = []
    for block in calibration:
        totals = [int(x) for x in (block.get("totals") or [])]  # type: ignore[union-attr]
        row: dict[str, object] = {
            "case_id": block.get("case_id"),
            "n": len(totals),
            "totals": totals,
        }
        if len(totals) < CALIBRATION_MIN_REPEATS:
            row["usable"] = False
            per_question.append(row)
            continue
        variances.append(statistics.variance(totals))
        row.update(
            {
                "usable": True,
                "spread": max(totals) - min(totals),
                "sd": round(statistics.stdev(totals), 3),
            }
        )
        per_question.append(row)

    if not variances:
        return {
            "measured": False,
            "reason": (
                "没有任何一题拿到 ≥2 次可用重复评分：本轮未实测判官方差。"
                "按 fail-closed，所有组件一律 no_call——不回退历史噪声底。"
            ),
            "sigma": sigma,
            "questions": per_question,
        }

    sd_judging = math.sqrt(statistics.fmean(variances))
    return {
        "measured": True,
        "sigma": sigma,
        "questions_measured": len(variances),
        "sd_judging": round(sd_judging, 4),
        "sd_delta_single_question": round(sd_judging * math.sqrt(2), 4),
        "formula": NOISE_FLOOR_FORMULA,
        "covers": (
            "仅判官复评方差（同一份答案文本重复盲评）；"
            "不含 ask 侧重跑方差 → 这是噪声下界，跨过它是必要条件不是充分条件"
        ),
        "questions": per_question,
    }


def length_bias_audit(answers: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """审计「分数-长度相关性」。

    ai-agent-book ch6 列的 LLM-as-Judge 两大偏差之一是**长度偏差**（偏爱长回答），
    给的防法三条：rubric 显式惩罚冗长 / 配对前对齐长度 / **审计分数-长度相关性**。
    前一条已写进 v2 rubric，这里是第三条。

    这不是门禁，是仪表：相关系数高不代表判官有偏（长答案也可能真的更全），
    但它高到 0.7 以上时，「这颗组件涨分」就有可能只是「它让答案变长了」，
    收据里必须能看见这件事，否则没人会想到去查。
    """

    pairs = [
        (len(str(rec.get("answer") or "")), float((rec.get("judge") or {})["total"]))
        for rec in answers
        if (rec.get("judge") or {}).get("scored")
    ]
    if len(pairs) < 3:
        return {"measured": False, "reason": f"可用样本 {len(pairs)} 份，不足 3 份"}
    lengths = [p[0] for p in pairs]
    totals = [p[1] for p in pairs]
    if len(set(lengths)) < 2 or len(set(totals)) < 2:
        return {"measured": False, "reason": "长度或分数无变化，相关性无定义"}
    r = statistics.correlation(lengths, totals)
    return {
        "measured": True,
        "n": len(pairs),
        "pearson_r": round(r, 4),
        "note": (
            "分数与答案字数的相关系数。|r| 高不等于判官有偏（长答案可能真的更全），"
            "但 |r|>0.7 时「组件涨分」有可能只是「组件让答案变长」，"
            "下结论前先看同长度对照。"
        ),
        "flag": "high_length_correlation" if abs(r) > 0.7 else "",
    }


def threshold_for(noise_floor: Mapping[str, object] | None, n: int) -> float | None:
    """该组件在 n 道可用题上的判定门槛；未实测方差或无可用题时返回 None。"""

    if not noise_floor or not noise_floor.get("measured") or n <= 0:
        return None
    sigma = float(noise_floor.get("sigma") or 2.0)
    sd_delta = float(noise_floor.get("sd_delta_single_question") or 0.0)
    return round(sigma * sd_delta / math.sqrt(n), 4)


def aggregate_components(
    answers: list[dict[str, object]],
    component_ids: list[str],
    *,
    noise_floor: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """每颗组件 = 平均(关断臂总分) − 平均(同题基线总分)，只聚合双方都 scored 的题。

    补评脚本（``rejudge_quality_ablation.py``）复用同一份数学。**聚合口径只能有
    一处**：抄第二份的那天两边不会同时被改，漂了也没人发现——而这份数字是拿来
    做合并决定的。

    ``noise_floor`` 传入 :func:`judge_noise_floor` 的产物时，每颗组件额外带
    ``decision``（``callable`` / ``no_call``）。**不传 = 一律 no_call**，不是
    默认放行：读数没有方差底就不成立，这一点必须由结构而非纪律来保证。
    """

    baseline_by_case = {str(r["case_id"]): r for r in answers if r["arm"] == "baseline"}
    unknown = [cid for cid in component_ids if cid not in COMPONENTS]
    if unknown:
        raise _fail(f"未知组件，无法解析 close_via：{unknown}")
    # rubric 换版=分数口径换了，跨版的分差没有意义。混版必须拒跑，不是警告：
    # 混出来的数长得和正常读数一模一样。旧收据没有该字段，按 v1 计。
    versions = {
        str((r.get("judge") or {}).get("rubric_version") or "v1-abstract")
        for r in answers
        if (r.get("judge") or {}).get("scored")
    }
    if len(versions) > 1:
        raise _fail(f"同一份收据里混了多个 rubric 版本 {sorted(versions)}，分差不可比")
    aggregates: dict[str, object] = {}
    for cid in component_ids:
        rows = []
        for r in answers:
            if r["arm"] != cid:
                continue
            base = baseline_by_case.get(str(r["case_id"]))
            jr, jb = r.get("judge") or {}, (base or {}).get("judge") or {}
            if not (jr.get("scored") and jb.get("scored")):
                rows.append({"case_id": r["case_id"], "usable": False})
                continue
            delta_total = jr["total"] - jb["total"]
            rows.append(
                {
                    "case_id": r["case_id"],
                    "usable": True,
                    "baseline_total": jb["total"],
                    "ablated_total": jr["total"],
                    "delta_total": delta_total,
                    "delta_by_dim": {
                        d: jr["scores"][d] - jb["scores"][d] for d in RUBRIC_DIMENSIONS
                    },
                }
            )
        usable = [row for row in rows if row.get("usable")]
        # 边际贡献 = 关掉后掉的分（正数=组件在涨分）。
        edge = (
            round(-sum(row["delta_total"] for row in usable) / len(usable), 3)
            if usable
            else None
        )
        threshold = threshold_for(noise_floor, len(usable))
        if edge is None:
            decision, decision_reason = "no_call", "无双方都 scored 的题"
        elif threshold is None:
            decision, decision_reason = "no_call", str(
                (noise_floor or {}).get("reason")
                or "未传入实测判官方差；无方差底的读数不成立"
            )
        else:
            # 比较规则不在这里重写：复用方差治理的单一真本源。
            decision, decision_reason = ab_decision(edge, threshold), ""
        # 确定性层的同口径读数：零方差，所以不需要噪声门。
        # 语义判官那路判不出来时，先看这一路动没动——它测不了推理对不对，
        # 但「证据标记少了几个」是硬事实。
        det_pairs = [
            (
                (r.get("deterministic") or {}).get("total"),
                ((baseline_by_case.get(str(r["case_id"])) or {}).get("deterministic") or {}).get(
                    "total"
                ),
            )
            for r in answers
            if r["arm"] == cid
        ]
        det_usable = [(a, b) for a, b in det_pairs if a is not None and b is not None]
        aggregates[cid] = {
            "close_via": COMPONENTS[cid]["close_via"],
            "questions_usable": len(usable),
            "questions_total": len(rows),
            "marginal_contribution_total": edge,
            "noise_threshold": threshold,
            "decision": decision,
            "decision_reason": decision_reason,
            "deterministic_marginal": (
                round(-sum(a - b for a, b in det_usable) / len(det_usable), 3)
                if det_usable
                else None
            ),
            "deterministic_questions": len(det_usable),
            "marginal_by_dim": (
                {
                    d: round(-sum(row["delta_by_dim"][d] for row in usable) / len(usable), 3)
                    for d in RUBRIC_DIMENSIONS
                }
                if usable
                else None
            ),
            "rows": rows,
        }
    return aggregates


def load_questions_file(path: Path) -> tuple[Question, ...]:
    """自定义题集：JSON 数组，每项 {case_id, text, as_of}。

    定向复测用（如「主线题 5 变体 × on/off」证伪某题型假设），字段缺失即拒跑——
    题集是读数的坐标系，宁可不跑也不要坐标含糊的读数。
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise _fail(f"题集文件必须是非空 JSON 数组：{path}")
    questions: list[Question] = []
    for i, item in enumerate(payload):
        if not isinstance(item, dict):
            raise _fail(f"题集第 {i} 项不是对象")
        case_id = str(item.get("case_id") or "").strip()
        text = str(item.get("text") or "").strip()
        as_of = str(item.get("as_of") or "").strip()
        if not (case_id and text and as_of):
            raise _fail(f"题集第 {i} 项缺 case_id/text/as_of")
        questions.append(Question(case_id, text, as_of))
    ids = [q.case_id for q in questions]
    if len(ids) != len(set(ids)):
        raise _fail("题集 case_id 重复")
    return tuple(questions)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--components", default="all", help="all 或逗号分隔的组件名")
    parser.add_argument(
        "--questions-file",
        type=Path,
        default=None,
        help="自定义题集 JSON（[{case_id,text,as_of}]）；缺省用内置 6 题",
    )
    parser.add_argument("--max-questions", type=int, default=0, help="0=全部")
    parser.add_argument("--ask-timeout", type=float, default=420.0)
    parser.add_argument("--seed", type=int, default=20260826, help="盲评洗牌种子")
    parser.add_argument(
        "--calibration-repeats",
        type=int,
        default=2,
        help=(
            "每题基线答案的额外重复盲评次数（默认 2，即每题共 3 次评分）。"
            "同一份文本重评 → 真值 Δ 必为 0，量的是当次判官噪声。"
            "设 0 = 不实测方差，此时所有组件一律 no_call。只花 judge 调用，不花 ask。"
        ),
    )
    parser.add_argument(
        "--exports-dir",
        default=str(Path(os.environ.get("FINANCE_WS", REPO)) / "market_feature_store" / "exports"),
    )
    parser.add_argument(
        "--judge-independence",
        choices=("require", "allow-correlated"),
        default="require",
        help=(
            "require（默认，fail-closed）=判官必须与合成模型异构，否则拒跑；"
            "allow-correlated=允许自己评自己，此时读数不得用于下结论"
        ),
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="只打印执行计划，不调任何 LLM")
    args = parser.parse_args()

    if args.components == "all":
        component_ids = list(COMPONENTS)
    else:
        component_ids = [c.strip() for c in args.components.split(",") if c.strip()]
        unknown = [c for c in component_ids if c not in COMPONENTS]
        if unknown:
            raise _fail(f"未知组件：{unknown}（可选：{', '.join(COMPONENTS)}）")

    question_pool = (
        load_questions_file(args.questions_file) if args.questions_file else QUESTIONS
    )
    limit = args.max_questions if args.max_questions > 0 else len(question_pool)
    questions = question_pool[: max(1, limit)]
    plan = [("baseline", None, q) for q in questions] + [
        (cid, COMPONENTS[cid], q) for cid in component_ids for q in questions
    ]
    print(f"[plan] 基线 {len(questions)} 答 + 关断 {len(component_ids)}×{len(questions)} 答，"
          f"共 {len(plan)} 次 ask + 盲评")
    if args.dry_run:
        for arm, spec, q in plan:
            knob = spec["close_via"] if spec else "默认全开"
            print(f"  {arm:<18} {q.case_id:<22} {knob}")
        return 0

    require_llm_ready()
    judge_info = resolve_judge(
        require_independent=(args.judge_independence == "require")
    )
    _JUDGE_OVERRIDE["provider"] = judge_info.pop("override")
    print(
        f"[judge] 合成={judge_info['composer']} 判官={judge_info['judge']} "
        f"独立性={judge_info['independence']}"
        + (f"（{judge_info['reason']}）" if judge_info["reason"] else "")
    )

    answers: list[dict[str, object]] = []
    for arm, spec, q in plan:
        extra_env = dict(spec["env"]) if spec else {}
        extra_flags = tuple(spec["flags"]) if spec else ()
        print(f"[ask] {arm} × {q.case_id} …", flush=True)
        result = run_ask(
            q,
            extra_env=extra_env,
            extra_flags=extra_flags,
            exports_dir=args.exports_dir,
            timeout=args.ask_timeout,
        )
        answers.append({"arm": arm, "case_id": q.case_id, **result})
        print(
            f"       {'ok' if result.get('ok') else '失败: ' + str(result.get('error'))} "
            f"({result.get('elapsed_sec', 0):.0f}s, {len(str(result.get('answer') or ''))} 字)",
            flush=True,
        )

    by_case = {q.case_id: q for q in questions}

    # 确定性层先跑：零 LLM、零 IO、方差恒 0，失败了也不花钱。
    # 「先确定性判据，后语义判官」——判官只吃它够不着的那部分残差。
    for rec in answers:
        if not rec.get("ok"):
            continue
        rec["deterministic"] = deterministic_score(
            by_case[str(rec["case_id"])], str(rec["answer"])
        )

    # 盲评：洗牌后逐份独立打分，judge 不见 arm 标签（位置偏差防护）。
    order = list(range(len(answers)))
    random.Random(args.seed).shuffle(order)
    for idx in order:
        rec = answers[idx]
        if not rec.get("ok"):
            rec["judge"] = {"scored": False, "reason": "答案臂失败，未送评"}
            continue
        print(f"[judge] #{idx}（盲）…", flush=True)
        rec["judge"] = judge_answer(by_case[str(rec["case_id"])], str(rec["answer"]))

    # 方差校准：同一份基线答案重复盲评。不再跑 ask，只多花 judge 调用。
    # 放在主盲评之后，让它和被测臂共享同一个 judge / provider 状态——
    # 换了 judge 的方差底就不是这一轮的方差底。
    calibration: list[dict[str, object]] = []
    if args.calibration_repeats > 0:
        for rec in answers:
            if rec["arm"] != "baseline":
                continue
            first = rec.get("judge") or {}
            if not first.get("scored"):
                continue
            case_id = str(rec["case_id"])
            totals = [first["total"]]
            repeats: list[dict[str, object]] = []
            for k in range(args.calibration_repeats):
                print(f"[calib] {case_id} 同文本复评 #{k + 1} …", flush=True)
                again = judge_answer(by_case[case_id], str(rec["answer"]))
                repeats.append(again)
                if again.get("scored"):
                    totals.append(again["total"])
            calibration.append(
                {"case_id": case_id, "totals": totals, "repeats": repeats}
            )

    noise_floor = judge_noise_floor(calibration)
    aggregates = aggregate_components(answers, component_ids, noise_floor=noise_floor)

    artifact = {
        "kind": "quality_ablation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "rubric_version": RUBRIC_VERSION,
        "judge_note": "同一 judge 评所有臂，标签盲；分差可比，绝对分不可跨 judge 比",
        "judge_independence": judge_info,
        "length_bias": length_bias_audit(answers),
        "questions": [q.__dict__ for q in questions],
        "answers": answers,
        "calibration": calibration,
        "noise_floor": noise_floor,
        "aggregates": aggregates,
    }
    output = args.output or (
        REPO
        / "intelligence"
        / "eval"
        / "runs"
        / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-quality-ablation.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    if noise_floor.get("measured"):
        print(
            f"\n== 当次判官噪声（同文本重评 {len(calibration)} 题）==\n"
            f"  sd_judging={noise_floor['sd_judging']} /20"
            f" → 单题 Δ 的 sd={noise_floor['sd_delta_single_question']}"
            f"（sigma={noise_floor['sigma']}）"
        )
    else:
        print(f"\n== 当次判官噪声：未实测 ==\n  {noise_floor.get('reason')}")

    print("\n== 组件边际贡献（关掉后平均掉分，正=在涨分）==")
    for cid, agg in aggregates.items():
        verdict = "✅ 可下结论" if agg["decision"] == "callable" else "⚠️ 噪声内，不下结论"
        gate = (
            f"门槛±{agg['noise_threshold']}"
            if agg["noise_threshold"] is not None
            else str(agg["decision_reason"])
        )
        print(
            f"  {cid:<18} Δ={agg['marginal_contribution_total']}"
            f"（可用 {agg['questions_usable']}/{agg['questions_total']} 题）"
            f" {gate} → {verdict}"
        )
        print(
            f"  {'':<18} 确定性层 Δ={agg['deterministic_marginal']}"
            f"（{agg['deterministic_questions']} 题，零方差，无需门槛）"
        )
        print(f"  {'':<18} 分维度={agg['marginal_by_dim']}")

    lb = artifact["length_bias"]
    if lb.get("measured"):
        warn = " ⚠ 高于 0.7，先查是不是「变长了」而不是「变好了」" if lb.get("flag") else ""
        print(f"\n分数-长度相关性 r={lb['pearson_r']}（n={lb['n']}）{warn}")
    print(f"\n收据 → {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
