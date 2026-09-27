# 历史研究收尾：原件链与地图门禁

设计源：`docs/superpowers/specs/2026-09-20-research-closeout-design-review.md`。在 `c9bd82ff` 的独占补丁树执行，保留原 PR783 和旧失败收据。先完成财务修复的独立复核，再由新实施者按本计划推进。使用 subagent-driven-development，修后 Spec → Quality；禁止合 main、调用真实模型或写生产数据。

## Task 1：同一根参照的合法父件可继续消费

- [ ] 改前用实际 HistorySession / Registry / RunStore 跑 rank → 扩窗 sector trace → 读取原件 → 同窗 stock trace。第三次引用扩窗原件应重现选择冲突；引用原排名应成功。输入/断言不改，保留红证据。
- [ ] `WindowSelection.reserve()` 的稳定身份采用 `root_query_id`、`root_sample_id`、`ranking_start`、`ranking_end`。保留直接父件逐边验证、原件送达、授权扩窗、观察终点一致性、并发预占及失败释放。不从显示文字推断窗口。
- [ ] 在现有 `test_history_window_binding.py` 补同根混合父引用通过；不同根/排名窗/观察终点、未读原件、非法扩窗仍拒绝；并行合法兄弟调用和首调用失败释放保留。复跑相邻 history anatomy/live seams 测试。
- [ ] 在隔离临时副本撤回稳定身份，新增链式断言必须失败；记录新旧源码指纹。原独立探针只复制，不覆盖。

## Task 2：修复原正式全量的地图结构探针

原件：`docs/verification/2026-09-20-research-closeout/history-design/code-map-diagnosis.json` 与外部 `history-window-c9bd82ff-checks/python.txt`。这是两层故障：PATH 缺 uvx，以及 `daily-full` 与源码符号 `daily_full` 不匹配。不能只改 PATH 或删断言。

- [ ] `scripts/code_map.py` 沿现有图查询入口支持命令连字符到 Python 下划线的有限别名；保留原查询命中，对别名结果按稳定来源/符号去重，保持有界查询与总命中上限。不能用硬编码 `market_feature_store` 命中冒充图查询，也不能新增索引器。
- [ ] 缺 uvx 时给出明确、可断言的结构层不可用状态/原因，不把执行失败报告成正常零命中；不得回退空图架构结论。保留 doors/narrative 与图状态的区别。
- [ ] 用可控 CRG 响应证明 `daily-full` 确实派发原查询和符号别名、去重且保持命中上限；普通查询不额外派发；缺后端和合法零命中可区分。
- [ ] 在独占树用实际 uvx 构建/刷新图，再跑原 `test_structure_probe_daily_full`，明确它被执行且通过。完整门禁的 PATH 显式包含 uvx；不要以跳过该探针充当修复。

## 交付

- [ ] 相关 Ruff/定向检查通过、提交只用 pathspec；两项可分代码提交，共用最终候选。
- [ ] 更新 PR783 已实现/待业务验收的过期交接；新补丁分支写 ≤3KB inflight，保留旧四题 `fbd8f2a6` 失败所属版本。#791 聚合/排序、各自启动锚的控制研究和四题真实会话没有完成时不能改写为闭环。
- [ ] 冻结最终干净 HEAD，独立 Spec 与 Quality，之后再合当前 main 到候选、在新 SHA 跑全叶；提交分支供审批，不自行合回 main。
