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
发布树`~/fwp-wt-vidio-finance-public`。接线`7389549bc`，测试修复`0154b06d1`已提交，后续文档另记HEAD。A首发/B默认及旧合成收到镜头，不等于利用。CI终态：7389549bc与1a055b87全量Python均9F；旧补写夹具object()缺candidate_facts，本次修复并增2例。738的E2E安装超时未测；1a的registry/frontend/E2E过。最新CI不能沿用旧绿。

## 已验证
本树`.venv-workbench/bin/python`3.12.13：738/1a各净树定向1785P/44S；0154净树两文件51P，收据`~/.finance-runtime/reviews/river-consumption-20261008/fulfillment-fixed-code-receipt.json`校验过；Ruff/提交门过。基线补写16P，对照1a为9F/7P；撤占位2F、还原51P。35例消费测试含A真实loop首发/B接口及补写替身。原件只本地。

## 未验证 / 已知边界
最新HEAD完整pytest/前端/E2E/registry组合门与CI待跑/回读。完整TurnOrchestrator、B generic owner、真实模型利用/答案质量未验。教学缺数/旧schema未修；tf特征、判断台账、剧本命名持久化/回检未接镜头。逐日strict与单cutoff不同；拟合含当前窗。deadline只守启动，不取消DuckDB；许可门非全工具修复。

## 下一步
固定文档HEAD后跑完整门并更新PR正文，收据按SHA分开；若红按ID归属，不能删测或改领域判据。教学版本/PIT、剧本时间/持久化合同先于回检；允许无剧本。真实/付费模型、生产升级/构建/回填及部署分别授权。

## 踩过的坑
只推公开分支，禁推原导入与清理前引用；别回导入树发布。prepared不等于请求，读取失败不是无相似。定向漏补写组，不能代全量；首次变异trylast在测试后生效，无效绿留档。collect-only、dirty日志、旧CI不移签；字段投影不授披露权。
