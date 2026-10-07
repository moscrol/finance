## 这个分支做什么
完整交付树审 vidio 20 连并安全迁回 finance；再接日常历史镜头。停在草稿 PR #75，不合并/部署/写生产。

## 决策与被否方案
| 选用 | 否决 / 原因 |
|---|---|
| 补丁树审、main对照、公开净差异 | 搜main判缺失或推私人历史，均不成立 |
| 旧D10与river并列 | 不按名次嫁接不同窗口的后续收益 |
| 整块INFERRED原子占位 | 拆表丢限制、升事实凑准入；12K装不下就降级 |
展开：`docs/handoffs/2026-10-08-river-history-consumption.md`；公开隔离见同日`vidio-finance-transfer-public`快照。

## 当前状态
本树`~/fwp-wt-vidio-finance-public`继续发布。代码`7389549bc`已推，基线`82de3fb73`；后续文档提交单独记账，接手核HEAD/status。A预取/B compose D10共享只读接缝，来源、日期、逐维数与限制到模型接口；不等于模型利用。05:37 CST观察代码CI：registry/frontend过，python/e2e仍运行。最新HEAD以PR回读为准，旧545fb全绿不移签。

## 已验证
`.venv-workbench/bin/python`3.12.13净树代码：1785P/44S/19229未选、Ruff/提交门过。`~/.finance-runtime/reviews/river-consumption-20261008/fixed-code-receipt.json`经revision/依赖/净树/漂移0校验；非全仓。33例覆盖A真实loop首发截获、B默认/旧合成及拥挤/超预算。只读真库两块可出；原件仅本地。地图结构ready，召回未验。

## 未验证 / 已知边界
本机完整pytest/前端/E2E组合门未跑；完整TurnOrchestrator、B generic owner、真实模型利用/答案质量未验。教学缺数/旧schema未修，tf特征、用户判断及剧本命名持久化/回检未接镜头。逐日strict与单cutoff标记不同；拟合含当前窗，非训练留出检验。deadline只守启动，不硬取消DuckDB；历史许可门非全工具授权修复。

## 下一步
回读最新HEAD CI与文档收据，补工程/完整入口验收。先定教学版本/PIT及剧本时间/持久化合同，再接观察回检；允许无剧本。真实/付费模型、生产升级/构建/回填及部署分别授权。

## 踩过的坑
只推公开分支；禁推完整导入与清理前本地引用。别回导入树发布，后期修复在本树。prepared不等于发过请求；读取失败不是无相似行情。collect-only的0执行收据、dirty日志和旧CI都不能代签；来源投影不授披露权，真库原件不公开。
