# PR16 质检返修在途

## 这个分支做什么
基于75af45fc0隔离修比较器F1/F2，单独定位E2E追问失败；不改owner树。

## 决策与被否方案
| 选择 | 否掉 | 原因 |
|---|---|---|
| 只收显式cases | 修补summary/补猜题号 | 汇总丢失通过题身份 |
| 新--cases-json并拒坏答卷 | 改旧--json或重发模型 | 保留汇总消费者，确定性迁移 |
| E2E只定位 | 加公司名/松断言/只补别名洗绿 | 结构通过不证风险与验证答对 |
展开见 `../2026-10-02-pr16-qc-fix.md`。

## 当前状态
比较器f1e90ae3a、独立诊断a68f48bfb已本地提交；未推送/合并/部署。
F1/F2已修，E2E未修。原75af CI：Python/frontend/registry成功，E2E31P3F2S，聚合失败。
旧owner交接“Python仍运行”过时，以verification原CI报告补注为准。
新模型请求0，旧累计96未重审。无后台任务，原失败/收据保留。

## 未验证 / 已知边界
未跑本修订全仓pytest、前端或浏览器E2E，也无新远端CI；合入仍blocked。
共享httpx0.25.2不符lock0.28.1、doctor blocked，未改共享环境；code-map空。
二轮主体/owner正确，继承带direct_assessment+direct_answer；专项投影未去重，后者无claim。
旁路仅去重复旧名会complete，但产品仍missing，不能证明风险/验证质量。

## 下一步
owner可独立审阅/移入f1e90ae3a；新SHA复验，不移签旧绿。
E2E另修输出身份和真实内容覆盖，保留三视口断言；再验CI。不合并部署。
详细根因与证据见 `../../verification/2026-10-02-pr16-followup-diagnosis.md`。

## 踩过的坑
新导出也会悄悄丢陌生ID/覆盖重复ID，已补拒收；漏答仍false。
基座同失败仅限定归因，不豁免红灯。561P非全仓，91P是变异三文件套件。

## 已验证
干净a68f48bfb十一文件561P/7.33s，完整SHA收据核过；全仓Ruff/hooks过。
f1e90ae3a七项变异7/7捕获、还原91P；CLI退出1/2/3及selftest过。
提交后禁网后端探针复现同正文，真实网络/模型0；不是浏览器E2E。
证据根 `~/.finance-runtime/reviews/pr16-fix-20261002T062241Z/`。
