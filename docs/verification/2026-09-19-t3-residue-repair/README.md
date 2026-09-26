# ARL-0005 残余反例修复 · 冻结工程证据

**工程全绿，仍 hold：本目录是业务 `6fb37a6e` 的机械证据，不是独立裁决、自然回答验收或部署记录。** 上一窗在 d46 上留红的五类线索（独立同比 12% / 样本量 120 误报，158.7bp 与「；该比率为1.587」漏检，加粗待核对标记重复插入）已修；同一份量具（SHA `34ea6608…`，未改）从 4P/10F 变为 14P/0F。

## 身份和结论边界

- 业务 `6fb37a6e191185daef832369677af15b0d56afb2`；父文档 tip `81cbbec7`；上一业务 `d46c2c3b`；量具提交 `52f6dee7` 未变。
- 冻结候选 18 项检查全 exit 0，前后树与三仓 registry 状态一致；全量 12259P/0F/87S（日志 2 xfailed）；旧探针 6/4/16；新量具 14/0；52 组变异全部拆红还原绿（新增 6 组红 20/20/4/19/12/9，基线/还原各 687）。
- 0 次模型调用、0 次自然金融会话、0 次取数；未开 PR、未合 main、未部署。
- 旧 0001～0003 有效 CR、0004 无效 PASS、0005 超时与无效 CR 原件不在本目录，也未被改写；本目录不新增任何裁决。

## 原件导航

| 路径 | 说明 |
|---|---|
| `residue-repair-closeout-outcome.json` | 本窗总账：五类修复、明确不覆盖、各项读数、卫生处理 |
| `run_frozen_checks_6fb37a6e.py.txt` / `frozen-6fb37a6e.log.txt` | 冻结管线脚本（惰性 .txt）与逐项输出 |
| `candidate-6fb37a6e/result.json` | 18 项检查的命令、exit、耗时、前后状态与三仓钉住版本 |
| `candidate-6fb37a6e/full-python-receipt.json` / `pytest-full.log.txt` | 全量收据与原始日志 |
| `candidate-6fb37a6e/frontend-*.log.txt` / `e2e.log.txt` / `e2e-deploy-ledger.jsonl` | 前端四步与 e2e |
| `candidate-6fb37a6e/registry-*.log.txt` | 固定三仓 registry 五项 |
| `candidate-6fb37a6e/*-probe.log.txt` | 四探针在管线内的输出 |
| `candidate-6fb37a6e/mutations/` | 52 组 diff、红/绿日志与 JUnit、`results.json` |
| `residue-repair-01/probe-6fb37a6e-*.json` | 提交后单独复跑的四探针（含 exit/stderr） |

## 保真规则

`manifest.json` 记录 **303 原件 / 2,507,608 字节**；本 README 与 manifest 另计。来源根 `~/.finance-runtime/convergence-20260919/retention-repair/`。历史五份归档（225+796+681+561+331＝2594 件）及其 runtime 来源逐字节核对未变。`.py/.log/.diff` 追加 `.txt` 后缀但不改字节；冻结工作树、锁、缓存、node_modules 排除；不含明文凭据。归档提交后新增的日志另留 runtime，不称已包含在本 manifest。

详见[本轮交接](../../handoffs/2026-09-19-t3-residue-repair.md)与[上一窗有界补审](../2026-09-19-t3-boundary-review-retry/README.md)。
