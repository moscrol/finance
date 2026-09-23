# #60 部署绑定准备

## 这个分支做什么
把已合 #856 的熔断接进夜跑同步根；只改四份绑定文件，不装机。

## 当前状态
PR #887 已发布，WIP 等待**本 PR 合入确认**，未合未部署。
远端候选 `99bd31c97630988092a4f328126beedc18f74bfc`；固定 base `2edbe4c46595cbea3eb3abe04fe84a7bd5afd55e`；预览 tree `247f7951741fc41b2be473fe712a0fab9454a9b2`。
本地后续交接提交不推送，不把收据移签到文档提交。

## 决策与被否方案
- 新运行根固定真实 main `2edbe4c46595`；不用旧候选或脏热补根，身份可审计。
- 装机源与运行根分开：后者模板仍指旧根，不能从它安装本次绑定。
- #61/#871 仍 open，不同批；不代合、不承诺数据恢复。
展开：`docs/handoffs/2026-09-23-eastmoney-deployment-binding-preparation.md`。

## 已验证
候选四叶绿：Python 14620P/0F/85S/2X，收集14707；Ruff、完整范围/依赖/身份/漂移0校验通过；JUnit对平，相关96项全在且通过。前端120P、E2E34P/2S、隔离registry五项通过。
真实候选dry-run、临时HOME+替身launchctl安装、运行根离线导入/熔断/单次兜底通过；生产文件hash未变。门禁树及绿色basetemp已回收，进程退出。
证据：`~/.finance-runtime/reviews/eastmoney-cb-deploy-20260922/deploy-binding-20260923/`，读 `README.md` / `summary.json`。

## 未验证 / 已知边界
未合后验收、未做干净main最终预演、未获安装授权；没打东财、没跑采集、没开生产DB。真实时序、跨进程行为及数据恢复均未验。中途高负载有观察，不作性能结论。

## 下一步
确认合入#887后，恢复上述证据目录下 `premerge/python-tree/finance-workspace-private` 到候选SHA重验收据；锁完整head/base，用现有gitea_pr合并并记录真实授权。漂移即停。
实际merge另跑四叶；从含绑定的干净main作装机源，再审计并nightly-only dry-run，方可报可部署。正式安装仍另授权。

## 踩过的坑
新根 `~/.finance-runtime/finance-sync-2edbe4c46595` 已锁定保留，尚未生效。当前生产仍adcda旧根；不热补、不复用旧Plan B。准备期文件快照不替代安装前新备份。WIP是授权闸，不是测试红。
