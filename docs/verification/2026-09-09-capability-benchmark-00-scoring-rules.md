# 00 · 真实能力基线 · 题集与评分规则（冻结稿，2026-09-09）

- 任务合同：`docs/superpowers/plans/2026-09-09-capability-upgrade/00-capability-benchmark-goal-brief.md`（分支 `codex/docs-capability-upgrade-plan`）
- 公开题集：`intelligence/eval/fixtures/capability-benchmark-2026-09-09.questions.json`（20 题）
- 密封清单：`intelligence/eval/fixtures/capability-benchmark-2026-09-09.sealed-manifest.json`（10 道隐藏题 + 30 份判分要点的 sha256）
- 密封本体：用户本地保管目录 `~/capability-benchmark-00-sealed-20260909/`（仓外；建设者不得读取；出分后按 uq15 协议入仓公开）
- 代码：`intelligence/eval/capability_benchmark.py`（validate / overlap / run / review-pack / aggregate / seal-verify）
- 本文与题集、密封清单**在任何建设者开跑前冻结**（以 git 提交为冻结时刻）。之后只允许走勘误目录 `intelligence/eval/cases/capability_benchmark_errata/`，不改原件、不改哈希。

## 1. 题集设计

| 类别 id | 中文 | 公开 | 隐藏 | 用户可检查的成果形态 |
|---|---|---|---|---|
| feel | 盘感翻译 | 2 | 1 | 一句盘感 → 若干可核验指标 + 库内数值 + 成立/不成立 |
| material | 材料理解 | 2 | 1 | 从贴入材料提取事实、算材料内数字、指出材料没回答的问题 |
| calc | 财务计算 | 2 | 1 | 单季还原、同比/环比、敏感性表；数字可逐格复核 |
| compare | 跨公司比较 | 2 | 1 | 同维度比较表 + 排序 + 改变排序的条件 |
| chain | 产业传导 | 2 | 1 | 环节 → 公司 → 兑现路径 → 验证信号；缺口写明 |
| analog | 历史类比 | 2 | 1 | 库内先例逐条 + 之后走势 + 样本量与口径漂移声明 |
| scenario | 情景更新 | 2 | 1 | 变量表 → 情景分支（触发阈值）→ 监控信号；禁数值概率 |
| counter | 反例推翻 | 2 | 1 | 用数据找反例、指出说法错在哪、给更站得住的规则 |
| continue | 跨日续研 | 2 | 1 | 多轮：只更新增量、不重复、给下一步 |
| method | 方法验证 | 2 | 1 | 样本数 / 命中率 / 最差反例 / 能不能下结论 |

- 数据前提：DuckDB 主表截止 **2026-09-07**（`fact_market_daily` / `fact_sector_daily` / `fact_stock_daily`）；`fact_sector_daily` **缺 2026-09-03、09-04 两日**；`fact_mainline_sector_daily` 09-07 农林牧渔各板块指标为 NULL。凡题目触及这些洞，正确行为是**声明缺口**，不是硬给数。财报数字以东财 F10 2026-09-09 取数为准（冻结在密封要点里）。知识库 `~/knowledge-base-private/wiki` 最新 source 2026-09-01。
- 每题带 `as_of`（默认 2026-09-07 收盘），题面里已写清；判分只认 `as_of` 之前的事实，晚于 `as_of` 的信息出现在答案里记「时间泄漏」。
- 与既有题集零重叠：`capability_benchmark.py overlap` 对 28 题验收板、冻结 30 题、uq15、outlook-ten、longtail-15、knevo_bench6_v2 逐题比对归一化题面，交集必须为空（单测钉住）。
- 未来才知道的预测（scenario 类）：只评推演结构与条件设计，不评方向对错。

## 2. 入口与配置（层 1「同模型/同数据/同预算」）

- 唯一入口：Workbench 真实对话门 `POST /api/conversations` → `POST /api/conversations/{id}/messages`（`skill_mode=auto`，`perspective_mode` 默认 neutral）→ 轮询消息终态。判据：run 目录存在 `continuous-episode.json`；没有的记 `engine_missing`，该题不计能力分。
- 多轮题：前序用户轮**真实投放**由系统作答，再投放本轮问题；前序 assistant 参考稿只给评审看，不注入模型。
- 每臂开跑前从种子重置评测用户 `cb00-baseline` 的台账（种子 = 真实用户台账 2026-09-09 快照，sha256 见 artifact）。种子不入仓。
- 被测 revision 由 sidecar `/api/health` 三读（`source_revision` / `source_dirty=false` / `code_matches_repo=true`）写入 artifact；模型以 run 产物 `model_turn.served_model` 为准（不认 backend 名、不认 env 名）。
- 预算：沿生产 `WORKBENCH_RESEARCH_TIER=max`、`WORKBENCH_TOOL_AUTHORIZATION=all`、单轮 900 s。各臂必须同参；改预算就是另一臂。
- 层 2「各自正常产品配置比较体验」：竞品答案由用户按 `knevo_bench6_v2._protocol` 顺序（先本地后竞品、当日冻结）粘贴入 `docs/learning/knevo-distill/cb00/<case_id>.md`。**没有同题竞品样本的类别不报告竞品胜负。**

## 3. 主表（每题 × 每臂）

| 字段 | 取值 | 判法 |
|---|---|---|
| task_completed | yes / partial / no | 用户要的成果形态是否交付（表、数、清单齐不齐）；缺数据时诚实声明缺口且交付其余部分 = partial，不 = no |
| correct_useful_points | 整数 | 命中密封要点数 + 评审认可的额外正确且有用点；每点须能引答案原文 |
| wrong_facts | 整数 | 与密封要点或库内数据矛盾的事实/数字；口径不同但已声明口径的不算错 |
| calc_correct | yes / no / na | 计算题：全部关键数在容差内为 yes；容差写在要点里（默认 ±1% 或 ±0.1pp） |
| ranking_with_conditions | yes / no / na | 比较题：有排序且写了会反转排序的条件 |
| followup_advances | yes / no / na | 多轮题：本轮相对前轮**有增量**且不重复前轮正文 |
| over_refusal | true / false | 数据在库内可得却拒答或整篇降级 |
| invalid_tool_calls | 整数 | `outcome.usage.invalid_actions` |
| elapsed_s / tokens_in / tokens_out | 数值 | run.json 时间差；`model_turn` 事件 token 求和；无金额口径（仓内无 cost 埋点，网关按配额不按 token 计费） |

## 4. 配对评审

- 两臂盲配：每题臂标签按 `seed + case_id` 洗成 X / Y，映射表哈希入 artifact、出分后公开。评审只见问题、成果要求、两份答案。
- 胜/平/负一票，附一句依据（必须引原文）。**优先序固定：正确完成任务 > 研究增量 > 速度与费用。** 任一臂在可核验要点上有错数或未完成任务，不得仅因流畅度获胜。
- 至少 20%（30 题取 6 题，按 seed 抽）由第二评审独立复核；报告一致率与分歧清单，分歧交检阅方裁决，评审不得自裁。
- 独立模型只能做辅助（摘要、对数），不能出胜负票；用了要写型号。
- 失败题全文、随机重复样本（同题同臂第二跑）全部保留在 artifact 里，不 cherry-pick。

## 5. 反向验证（每次正式汇总前必做）

- 评审包生成时向随机一题插入第三臂 Z：一份文风流畅但**关键数算错或任务未完成**的答案（`review-pack --decoy`）。
- `aggregate` 断言 Z 不得被记为胜方；若胜，汇总以非零退出、结果不得发布，先修评审流程再重跑。
- 恢复（去掉 Z）后再出正式汇总。

## 6. 不做的事

- 不做显著性宣称：`ab_sample_design.py` 已锁 v=0.1375，30 题需 15 次重复才分辨 5pp；本单单跑只出「同题差分 + 失败题全文 + 方向」，写明 n。
- 不把 CLI `ask` / `live_probe ask` 的读数混进来（它们不经过判官）。
- 不报告没有同题真实样本的竞品胜负；旧对比只作失败样本引用。
- 不删测试、不放宽题目、不隐藏失败、不固定答案。
