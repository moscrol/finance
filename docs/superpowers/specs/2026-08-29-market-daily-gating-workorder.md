# 2026-08-29 MARKET_DAILY 绕开 enabled_providers 门控修复工单（占位）

> 来源：datablock 符合性套件（`intelligence/tests/conformance_datablocks/`，
> 工单 #14）首跑装配对账抓到的真缺陷，已入棘轮 baseline（`DB-6:MARKET_DAILY`，
> strict xfail）。状态：**待认领**。

现象：`evidence_registry.REGISTRY` 注册了 `MARKET_DAILY`（"最新市场总览"），
注册表公开承诺「调用方只通过 `AskOptions.enabled_providers` 限制哪些块参与
门控」；但该块既不经 `DataBlockProvider` 构造面，全仓也**无任何**
`provider_enabled(options, "MARKET_DAILY")` 调用——块文本在 ask.py ~L1929
（`presentation_profile == "mainline_current"` 的 agent 取数路径）直接生成。

后果：`without_providers("MARKET_DAILY")`、LLM 检索计划（`ASK_PLANNER_MODE=llm`
写 enabled_providers）、任何编排器裁剪都**关不掉**这个块——「仪表上可配置、
实际不接线」，与 MOC 已确立原则「授予的额度必须真的传到最下游执行者」同族。

修法方向（认领者定）：给该生成点接上 `provider_enabled` 门控（语义=被裁剪时
该路径不产 MARKET_DAILY 块并留缺口声明）；或若判定它本就不该受此门控，从
REGISTRY 摘除并改注册表 docstring——两个方向都要先查 `mainline_current` 档
的消费方是否依赖该块必然存在。

判据：修后 datablock 套件 `DB-6:MARKET_DAILY` 从 baseline 清账（strict xfail
转 xpass 会自动逼删行）；`without_providers("MARKET_DAILY")` 下该块真实不产出
且留痕；`mainline_current` 现有通过面不回归。

红线：不弱化 DB-6 断言本身；不顺手改其他块的门控。
