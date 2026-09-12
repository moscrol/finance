# docs/qc-method-607f53a6 · 独立质检

## 这个分支做什么
只审 `feat/method-closed-loop@607f53a6`（包含 a7aa227d 及后三笔），不代改实现。
完整发现：`docs/handoffs/2026-09-12-method-closed-loop-607f53a6-review.md`。

## 当前状态
**不放行**：不是只缺全量，有四组实测缺陷。质检文档独立留在本分支；原分支未动，未推送、合并或部署。

## 决策与被否方案
- 固定提交独立树；否了主检出/共享分支直接测，避免混树。
- 两组定向共 165 项通过只作局部证据；否了以局部绿覆盖全量红。
- 保留旧 CLI 兼容但区分「能力不存在」与「探针失败」；否了 grep false 一概回退。

## 未验证 / 已知边界
1. **P1** `active.json=[]/null` → 未捕获 AttributeError → rc=1 → 夜跑默认协议且无告警；目录/悬空软链指针同样误判 unset。
2. **P2** help 进程失败被报成「CLI 无 active」，回退默认；应停止并保留故障原因。
3. **P2** protocol.json 损坏时 active --print-dir=0，active JSON=2；两种展示必须共用完整性验证。
4. **P2** 迁移 status --user / capture 缺 labels-db 不可执行；脚本 100644 不可直接执行，§4.1 重号/步骤漂移。
- 「旧 CLI active --help 也为0」实测错误：2efdff46 上 active/activate --help 均2。
- 未做全量、生产迁移、封存存量待验结算或新的断电模型试验。

## 下一步
由用户指定单一收口人，另一会话明确停止写该分支；先修缺陷及真实 shell 行为回归，再冻结最终提交、约静默窗口跑整树。原 inflight 20279 字节，应由写入者压缩至≤3KB。

## 已验证
- 干净 607f53a6：method_validation / CLI / flywheel **78P**；methodology_backtest **87P**；相关 ruff、zsh语法过。
- 封存 daily/capture rc2、新增文件0；常规坏JSON/封存绑定的真实 shell 方法步停止并告警。
- 原全量收据核实 9429P/1F、9430P/3F；三项重跑3P不改判。20ms deadline/10s轮询不可统称 wait(1)/wait(2)。高负载不是唯一原因证明。
- 临时探针与输出 `/tmp/method-qc-607f53a6-evidence/`；收据 `20260912T094532Z-607f53a6.json`、`20260912T094701Z-607f53a6.json`。

## 踩过的坑
spy 用 zsh 会被宿主 .zshenv 覆盖隔离用户根；该轮结果废弃，改 bash spy 后重跑。实际被测绑定仍由 zsh 执行。临时探针是本次语义取证，正式回归由实现方接入现有测试，不另造通用工具。
