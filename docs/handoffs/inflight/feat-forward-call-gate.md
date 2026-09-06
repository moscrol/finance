# 在途交接 · feat/forward-call-gate（已合 #612 → main `ed22039a`，8792 已切）

## 这个分支做什么
出口硬门：「明天哪个方向 / 会怎么走」这类问法的答案不得是领涨或方向判断；`validate_episode_finish` 命中即拒收 `forward_direction_call`（SUBSTANCE，回灌可修正提示：改写成观察剧本——2–4 个指数/板块/题材级变量 + 升级/降级条件 + 「不是投资建议」）。词表住 `compliance_gate`（`E_FORWARD_CALL`、`forward_call_hits`、`is_next_day_direction_question`）。依据：09-07 D9 读数（收据 §2.1）；用户「按超限加约束」原则下第一条按读数加回的约束。

## 决策与被否方案
- 落在 `admit_finish`（`validate_episode_finish`）/ 否判官侧 / 09-02 纪律「出口唯一硬层」，且判官是 LLM、本就放行了 D9。
- 只对问句命中「明天 + 方向/走势」的题开门 / 否按 question_type / D9 的 frame 是 `general_finance_qa`，题型不可靠；「长电怎么看」里写「次日更容易高开分歧」不归它管。
- 子句级条件免检（若/如果/一旦/视为…）/ 否整段扫 / 观察剧本自己的升级/降级条件天然长成「若明天开盘 X 高开」。
- 拒收类别 SUBSTANCE（回灌 + 可恢复）/ 否 INTEGRITY 硬拒 / 越线是内容形状问题，模型一稿就能改。
- `E_FORWARD_CALL` 不进 `OBSERVATION_SCRIPT_CODES` / 否一并进 / 剧本登记门的既有行为与夹具不动，另案。
- 门禁两条计时类新红判负载敏感（单跑 2/2、两文件 109/109 绿）/ 否等空载重跑 / 机器被 Devin/Codex/Spotlight 占满；改动面与它们无关。

## 当前状态
8792=`ed22039a`，三读一致、readiness 全绿、账本 ok；回滚锚 `cutover-20260907c-fwdgate-rollback-8792.txt`（回 `a11d76ca`）。live 同题：首稿被拒 1 次，终稿四组变量 + 升级/降级条件 + 「不是投资建议」，终稿零命中；收据 `docs/verification/2026-09-07-forward-call-gate-live.md`。

## 未验证 / 已知边界
- 拒收率 / 误拦 / 二稿通过率只有 n=1；读数源 = `invalid_action code=forward_direction_call` 事件。
- 词表三族冻结，不预扩；漏拦形态（如「看好 X 明天表现」）等读数。
- 切流时 load 200+（Devin/Codex/mdworker）：耗时读数 278s 不可比。

## 下一步
1. 自用 1–2 周后扫 `forward_direction_call` 事件：拒收率、误拦、连拒两次落 recover 的 run。
2. 「明天买什么」类问法：现在同门（问句判据含「买什么」），看模型二稿是否也成剧本。
3. 剧本登记门要不要也收 `E_FORWARD_CALL`：看 guided_reading 产出的剧本里有没有命中再定。

## 踩过的坑
- 条件免检那层要有「去掉条件词就命中」的承重对照，否则变异不红（首版就是这样漏的）。
- 主检出树是旧 revision，别在那里 import 新符号验 live（`compliance_gate.forward_call_hits` 在生产树才有）。

## 已验证
`test_forward_call_gate.py` 29 绿，三个变异各击杀 ≥3；门禁 7972P 非降；切流三项验证；live 一次拒收后终稿零命中。
