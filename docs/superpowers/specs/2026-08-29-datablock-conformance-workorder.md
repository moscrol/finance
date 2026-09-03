# 2026-08-29 引擎 B 数据块 DataBlockProvider 符合性套件工单（占位）

> 来源：`docs/verification/2026-08-29-conformance-seam-census.md`（缝普查 P1 #3，
> 普查所见杠杆最高的未覆盖缝）。机制几乎逐字复用工具缝套件三件结构
> （`intelligence/tests/conformance_tools/`——同为「一名一实现共用壳」形状）。
>
> 状态：**已交付待验收**（2026-08-29，分支 `test/datablock-conformance`，PR 见
> gitea）。套件 `intelligence/tests/conformance_datablocks/`，读数 **193p/1xf**
> ——xfail 即首跑抓到的真缺陷阳性对照：**MARKET_DAILY 绕开 enabled_providers
> 门控**（入棘轮 `DB-6:MARKET_DAILY`，修复占位单
> `2026-08-29-market-daily-gating-workorder.md` 已随分支入库）。交接：
> `docs/handoffs/inflight/test-datablock-conformance.md`（分支上）。

缝：`ask_planner.DataBlockProvider`（L42-53：name/label/applies/collect）×
注册表 `evidence_registry.REGISTRY`（L29-57）的 20 个命名块（个数用
`PROVIDER_NAMES` 解析器数，不写死 20），装配在 `ask.py` L4178+，各块
applies/collect 闭包独立演化。产品门明确数据块是经 `enabled_providers`
门控的可开关积木。不变量草案：applies 门控为假时 collect 不得被调用；
collect 返回 `(块文本, 引用)` 形状与引用可绑定性；被 `enabled_providers`
裁剪的块零执行且留显式痕迹；空结果与缺口声明如实（不静默造文本）；块间
无隐式顺序依赖。零 IO：各块下游用探针替身。

验收：逐块参数化跑通（解析器数）；能力声明表逐块带出处；棘轮 baseline
规则同参照套件；分支独立、pathspec 提交、不合 main。
