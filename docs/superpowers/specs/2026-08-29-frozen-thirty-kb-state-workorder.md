# 2026-08-29 冻结三十题验收对 KB 解析态不封闭工单（占位）

> 来源：2026-08-29 conformance 双套件（#504/#505）批次门禁 1F 归因（台账 2026-08-29 行；
> 收据 `20260829T074556Z-85e4b1fd`）。状态：**已修复（同日收口，台账行 `R-20260829-01`，
> 分支 `fix/frozen-thirty-kb-state`）**。修法=方向 B（dry-run 钉解析态：`KB_VAULT` 钉夹具
> `intelligence/eval/fixtures/frozen-thirty-wiki` + 哨兵实体防密封静默失效）**加**一处工单
> 未预判的第二层根因：benchmark 缺口计算缺 canonical 别名归一（`_LEGACY_OUTPUT_ALIASES`），
> 字面比较把同义覆盖误报成缺口——详见台账行。题面/真值/生产代码零改动。

现象：`test_frozen_thirty.py::test_thirty_set_dry_run_has_no_contract_gaps` 自 08-29 起红，
08-28 22:48 门禁 @`572f1df9` 同代码尚绿。隔离复跑 `c3514529` / `b77df25c` 同红 → 非任何
代码合并引入。

根因（已实证）：A3 题「2026-07-23 收盘，立新能源怎么看」的冻结验收清单
（`direct_answer`/`evidence_boundary`）按「主体解析不到 → general_finance_qa → 通用输出」
时代标定；`wiki/entities/立新能源.md` 于 08-29 00:05 由 IMA 个股夜队列灌入后，主体解析翻
company → `stock_deep_dive`，frame 输出变 `direct_assessment`/`supporting_evidence`/
`counterpoint`，与冻结清单交集为空 → 合同缺口。注意：**新行为更对，是测试数据晾旧**。
同族风险：其余 29 题任何主体被后续 ingest 建页都会重演——冻结集对活 KB 不封闭 = 冻结不彻底。

修法方向（认领者定，倾向 B）：
- A. 更新 A3 验收清单至当前解析态并重冻结（治标，下一次建页再犯）；
- B. dry-run 钉住解析态（resolver 夹具或 KB 快照注入），让「冻结」对数据态真正封闭——
  与「题面/真值冻结先于运行」同一条原则的补全。

判据：该测试在任意 KB 数据态下确定性；A3 断言重新有效；不得弱化「合同零缺口」断言本身；
不得改生产解析逻辑迁就测试。
