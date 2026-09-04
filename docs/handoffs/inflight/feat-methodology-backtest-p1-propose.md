# feat/methodology-backtest-p1-propose

树 `/Users/a77/fwp-wt-methodology-backtest-p1b`，基座 `feat/methodology-backtest-p1-gate`=`1be840f8`（PR #576 的分支尖；#576 合入后本支对 main 只多 3 个提交）。
设计稿 `2026-09-04-methodology-backtest-structured-history-design.md` §3.4 第三行 + P0 交接「已知边界」里的基准率一条。解释器 `.venv-workbench/bin/python`。

## 这个分支做什么
P1 第二刀，两件都是**加法、不改既有运行时行为**：
1. **纠偏 → 候选规则登记入口** `scripts/methodology_backtest.py propose`：人写谓词短句（`dual_red_streak@1 >= 3`、`market:market_stage in 主升阶段,主升`）和 success 短句（`fwd_return 5 > 0`），
   程序解析、过白名单校验、把 `corrections.jsonl` 里那条记录的 id / ts / 原文钉进规则的 `provenance` 块，落 `methodology/rules/<rule_id>.v<version>.json`（已存在拒绝覆盖）。
   不做自动翻译——LLM 即时写规则等于把不确定性塞进度量本身（设计稿 §3.2 否掉的第四条路）。
2. **日期精确配对基准率** `baseline.kind = same_universe_event_days`：只取事件发生的那些交易日里的全体实体，把择时效应剥掉只检验选择。
   规则声明哪种口径定结论，runner 每次同时算另一种作对照列（收据 `baseline_alt`：n / k / p0 / lift / 若以此定结论的四态）。

## 真库读数（旁路库 2026-09-02，只读）
| 规则 | N | p | p0 全日期 | lift | p0 事件日 | lift | 结论（两种都） |
|---|---:|---:|---:|---:|---:|---:|---|
| dual_red_streak3_continuation | 88 | 68.2% | 58.0% | +10.1% | **69.2%** | **−1.0%** | not_distinguishable |
| diff_ratio_turn_up_5d | 27,186 | 54.1% | 55.1% | −1.0% | 54.9% | −0.8% | not_distinguishable |
| limit_heat_rank_jump_3d | 13,006 | 57.6% | 57.0% | +0.6% | 56.8% | +0.8% | not_distinguishable |

规则 1 那 10 个点的「提升」全是择时（触发日本身就是强势日，随便一个板块 5 日上涨概率 69%），没有选择效应。这就是对照列存在的意义。

## 决策与被否方案
- 对照列每次都算、不参与结论 / 否只算声明的那种 / 两种读数并排才看得出「提升来自择时还是选择」，多一条查询几十毫秒
- 事件日日期走绑定参数（个数 <= 日历长度 413）/ 否把事件集 CTE 再拼一遍 / 前者简单可审，参数个数有上界
- provenance 进规则 JSON 而不是另开台账 / 否 `methodology/candidates.jsonl` / 规则文件已是真本源，再开一张表就得进 ledger-map 且多一个写入者
- `propose` 不带 `--run` / 否登记完直接跑 / 登记与回测是两个动作，收据目录也可能不在同一台机器

## 已验证（本树）
- `test_methodology_backtest.py` 39 例 + `test_experience_cards.py` 19 例绿（新增 5：谓词语法、组装 + 溯源 + 拒覆盖、CLI propose 端到端、事件日 SQL 绑定、对照列互为镜像）
- selftest 12/12；`propose --dry-run` 真环境可用；ruff 0；`unread-fields` 无新增；pre-commit 全过
- 全量主门禁：见末尾追加行

## 未验证 / 已知边界
- `propose` 只登记不翻译；谓词短句里的值类型按字面猜（true/false / 数字 / 文本），合法性靠白名单
- 事件日口径在事件很少时 p0 的样本也少（每个事件日只贡献一天的 universe），此时两种口径都可能 `insufficient_n`，是正确输出
- `provenance.ref` 只存 id / ts 字符串，不校验那条纠偏记录是否仍存在（记录可被 memory_status 归档）

## 下一步
1. #576 合入后本支开 PR、跑门禁、合入（加法，无运行时行为变化）
2. 剩余 P1：个股标签（`limit_up / first_board / new_high_1y`，需给个股建价格序列）；`lifecycle_stage` 人工对照集
3. P2：`finance_query` 暴露 `methodology_verdicts` 数据集；Beta 后验对照列；相似历史日

## 踩过的坑
- 门禁在 A 树跑全量 pytest 时不能在 A 树改代码（收据会 dirty）；也不能在 B 树跑 pytest 到门禁收尾那几秒（`conftest` 把 `latest.json` 写死在同一目录）。做法：另开树写代码，pytest 挑门禁刚起步时跑
- 用 `( … ) &` 在工具 shell 里起长任务会随 shell 退出被带走，要用工具自己的后台机制
