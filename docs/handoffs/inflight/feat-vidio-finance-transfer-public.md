## 这个分支做什么
完整交付树审 vidio 20 连并安全迁回 finance；接日常历史镜头。停在草稿 PR #75，不合并/部署/写生产。

## 决策与被否方案
| 选用 | 否决 / 原因 |
|---|---|
| 补丁树审、main对照、公开净差异 | main零命中不判缺失，不推私人历史 |
| 旧D10与river并列 | 不按名次嫁接不同窗口后续收益 |
| 整块INFERRED占位 | 拆表丢限制、升事实凑准入；12K装不下降级 |
| 合法AnswerSpec测试夹具 | 不在生产吞缺字段；另验真实registry补写 |
展开：同日快照`river-history-consumption.md`、`river-repair-ci-followup.md`，均在`docs/handoffs/`。

## 当前状态
发布树`~/fwp-wt-vidio-finance-public`。接线7389549bc、测试修复0154b06d1；4cdefadc1已推且本机完整门通过，后续文档HEAD另记账。A首发/B合成及补写接口收到镜头，不等于利用。旧738/1a全量CI九例夹具合同红保留，已修非删测。06:41 CST：4cdefad的registry/frontend/E2E过，Python在跑（run37695980107）。最新完整收据/CI终态以PR正文评论按HEAD回读，不沿用旧绿。

## 已验证
锁定Python3.12.13：4cdefad净树完整21071P/78S/2X；收据根`~/.finance-runtime/reviews/river-consumption-20261008/`下`fulfillment-full/gate-V8uh5wnU/pytest.json`全量/版本校验过。前端214P、E2E52P/2S，Ruff及registry五项过；Node26≠CI22。0154两文件51P；基线补写16P、修前9F/7P；撤占位2F、恢复绿。原件仅本地。

## 未验证 / 已知边界
后续文档HEAD的同SHA完整门/CI终态须回读PR，不移签4c结果。完整TurnOrchestrator、B generic owner、真实模型利用/答案质量未验。教学缺数/旧schema未修；tf特征、判断台账、剧本命名持久化/回检未接镜头。逐日strict与单cutoff不同；拟合含当前窗。deadline只守启动，不取消DuckDB；许可门非全工具修复。

## 下一步
回读PR当前HEAD完整工程收据/CI；文档快照是当时观察，非最新终态。若红按ID归属，不删测或改领域判据。教学版本/PIT、剧本时间/持久化合同先于回检；允许无剧本。真实/付费模型、生产升级/构建/回填及部署分别授权。

## 踩过的坑
只推公开分支，禁推原导入与清理前引用；别回导入树发布。prepared不等于请求，读取失败不是无相似。定向漏补写组，不能代全量；首次变异trylast在测试后生效，无效绿留档。collect-only、dirty日志、旧CI不移签；字段投影不授披露权。
