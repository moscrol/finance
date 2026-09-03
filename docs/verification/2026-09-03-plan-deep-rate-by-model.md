# deep 升档为何 08-22 后归零：模型换了，GLM 几乎不交 PLAN（2026-09-03）

子代理 spec（`2026-09-03-subagent-tool-design.md` §1.3 / §7）的前置问题。离线只读，数据：生产 users 根
`~/.local/share/finance-workbench/users/*/runs/run_*/{continuous-episode.json,report.json}`（815 run）。
PLAN 判据 = `outcome.plan` 非空；模型 = `report.json.llm.model`；deep 判据 = `mode_decision.effective_mode == "deep"`。

## 结论先说

**升档链是 模型交 PLAN → `govern_mode` → `mode_governor.decide` 批 deep → 起分支。PLAN 是模型自愿输出的结构块，
GLM 几乎不输出，链就从第一环断了。** 与代码无关：PLAN 指令原文自 08-07 起一字未动（`episode_protocol.py` 「第一轮可以先只输出一个
kind=PLAN 的 JSON 对象…也可以在任务简单时直接调用已授权工具」）；08-22 的 `46053d3f` diff 里没有一行碰 PLAN——
spec §1.3 那条 [推断] **撤回**。

## 读数

同日、同代码、不同模型（生产在 08-13 / 08-16 两天两种模型都跑过）：

| 日 | 模型 | PLAN / run |
|---|---|---|
| 08-13 | gpt-5.6-terra | **24 / 80 = 30%** |
| 08-13 | glm-5.2 | **0 / 20 = 0%** |
| 08-16 | gpt-5.6-terra | **44 / 154 = 29%** |
| 08-16 | glm-5.2 | **0 / 12 = 0%** |

全量按模型（批 deep 的 run / 总 run）：gpt-5.6-terra **48 / 417**；glm-5.2 **2 / 272**；glm-5.3 **0 / 113**；gpt-5.6-sol 0 / 2。

按日：08-12～08-16 生产主模型 gpt-5.6-terra，PLAN 率 25–45%；**08-17 起生产换 glm-5.2**（08-26 起 glm-5.3），此后 ~450 run 只有
3 个 PLAN（08-19 ×1、08-22 ×2）。最后一次 deep/分支 = 08-22，正是 GLM 偶发交 PLAN 的那两次。

按题型（全量）：general_finance_qa 44/338、theme_analysis 44/219、market_watch 11/44、valuation_estimate 7/14、stock_deep_dive 7/94——
分子基本都来自 gpt 时期。

## 这意味着什么

1. **子代理工具在 GLM 生产上不可达**（spec §4：只在 deep 装得下；deep 依赖 PLAN；GLM 不交 PLAN）。要么升档不再依赖模型自愿交 PLAN
   （治理侧按可观察信号自己判——`mode_governor` 已有 `observable_conditions`，缺的是一个不经 PLAN 的入口），要么对复杂题型把 PLAN 写成
   必填而不是「可以」，要么接受 deep 在 GLM 下就是零。三条都是预算线/协议级的决定，**待用户拍**。
2. **P4 的混杂变量多一个**：任何把 gpt 时期读数（08-12～16）与 GLM 时期比的结论，都混着 30% 对 0% 的 PLAN 率与 11.5% 对 0% 的 deep 率。
   `sdk_glm` 对 `continuous_glm` 两臂都是 GLM，这一项相同；但 spec §3.5.3 的四项拆分外要加一条「PLAN/deep 率」并列写出。
3. 「模型自愿输出的结构块」不能当治理路径的唯一入口——换模型即静默失效，且所有门禁全绿（进 10_knowledge）。

## 不成立的结论

- 不能说 GLM「不会」交 PLAN：glm-5.2 有 2/272；是频率极低，不是能力缺失。
- 不能从这份数据说 gpt 时期的 deep 有用——那要看分支证据进答案的比例，本文没量。
- 模型切换的时间（08-17）取自 `report.json.llm.model` 的日分布，切换原因未查（当天台账应有记录）。
