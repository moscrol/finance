# tool_hunger 遥测普查：模型没有在要新工具（2026-09-03）

能力放大线交接「下一步 ③：翻 `tool_hunger` 遥测决定加什么工具」。跑的是现成 CLI：
`python -m intelligence.cli tool-hunger --runs-dir ~/.local/share/finance-workbench/users --since all`，
产物 `intelligence/eval/measurements/tool-hunger-2026-09-03-all.{json,md}`。

## 读数

- 扫 **1218 个 run**（生产 users 根，全历史），饥饿事件 **12 条**，分布在 **9 个 run**，时间 08-27 20:34 ～ 08-30 01:52。
- 三类事件里：`unknown_tool` **0**、`capability_denied` **0**、`finance_query_rejected` **12**。
- 12 条全是 `failure_code=invalid_query`（结构化查询参数校验不过），dataset 分布：`theme_limit_heat_daily` 4、`market_daily` 2、
  `sector_daily` 2、`stock_daily` 2、`leader_height_daily` 1、`sector_stock_daily` 1——全是盘面表。
- 08-30 之后零事件（含 09-03 的切流探针与两臂）。

## 怎么读

1. **模型没有点过注册表里没有的工具名，也没被拒过能力**。按 §3.6「其余记形状不排期」的口径，遥测给不出「该加哪个工具」的信号；
   `graph_lookup` 实体解析契约与 `finance_shareholders`（交接 ⑥「视 ③ 而定」）**本轮不排期**，形状继续留在 spec 表里。
2. 12 条 `invalid_query` 是**参数面**问题（模型写的 dataset / 字段 / 日期范围不合法），不是工具缺口；且集中在 08-27～28 的盘面题批次，
   之后没再出现——先当已收敛，不动。
3. **遥测的盲区**：它只量「模型点了名的需求」。今天腾讯题里 `financial_data` 对非 A 股主体根本不在授权集，模型看不见就不会点，
   遥测也就记不到——「够不着」与「没想到用」都不在这份账里。所以「0 饥饿」≠「工具面够用」，只能说「没有被点名的缺口」。
   要量后者得用另一把尺（如 spec §1.1 的未见题弃权率，或按 question_type × 授权集做覆盖普查）。

## 不成立的结论

- 不能从 0 `unknown_tool` 推出「模型从不幻觉工具名」——注册表只挂 `authorized_specs`，模型看到的 `tools` 数组就是全集，幻觉空间本来就小。
- 9/1218 有事件的 run 占比不是「饥饿率」：sink 只在首次事件时建文件，没事件的 run 没有文件是正常的。
