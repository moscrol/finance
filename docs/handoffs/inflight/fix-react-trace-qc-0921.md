# #809 返修 → WIP #832（前向合流已测）

## 这个分支做什么
接替#809六项修复并质检返修；原#809头ac3bbd310不动，两张不分别合。隔离树，未接管主目录他人改动。

## 决策与被否方案
- 已把当时main f2c3e9e1a（#830）合入，固定a140重验；否决旧ec246收据移签或merge-tree代测。
- K3一次600秒，到期不重开、不补作者签字。
- 历史片另枝f90fd3dc3，不塞#832，不把比较假设槽当#793/#794完成。
- 背景/被否方案：`docs/handoffs/2026-09-21-react-trace-main-integration.md`；前轮缺陷见`2026-09-21-react-trace-qc.md`。

## 当前状态
代码 `a14005fc9a9d671d178da6fc91be9cb69ae67e77` 已推#832；本份为后续docs-only归档。工程通过，独立审查和自然质量仍blocked。未合main、未部署8792、未写生产。

## 已验证
- a140全量12596P/87S/2X，0F/0error，1480.30s；首尾clean/同SHA。收据`20260921T101955Z-a14005fc.json`严格校验0；与ec246的89项skip/xfail名称原因相同。
- 同SHA前端六步0（110P/E2E34P2S），Ruff+registry/crosswalk六命令0，日志hash已核。
- 真原件删句14/15回放通过，其他句子逐字不变、原件未改，模型0次。
- 原件归档`docs/verification/2026-09-21-react-trace-integration/`；完整根`~/.finance-runtime/reviews/react-trace-integration-20260921/`。

## 未验证 / 已知边界
- K3导入预检成功、21次阅读/写草稿，600秒超时143；没有行为测试、没有Spec/Quality终稿，REPORT仍IN_PROGRESS。无自动新会话。
- 自然金融会话0，原not_passed不翻：225/25及候选数字显式绑定、判官消费、板块排序/按需展开未验。
- main测试期间又前进；a140收据只覆盖f2c3e9e1a组合，不覆盖后来main或docs-only tip。
- 历史片状态看`feat/history-evidence-integration-0921`的独立inflight；不能把763项定向或离线回放当自然质量。

## 下一步
先确认独立审查范围/预算。要合入时固定新候选重验全叶并等用户批准；不要分别合#809/#832。历史产品前置完成后才按预算跑自然题。

## 踩过的坑
原磁盘满/错SHA/导入失败原件均留前轮。成功导入也不等于测试已跑；有REPORT文件也不等于完成报告。固定收据不得随移动main改签。
