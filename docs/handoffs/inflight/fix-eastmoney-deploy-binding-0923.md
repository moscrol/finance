# #60 已可部署，待装机授权

## 这个分支做什么
把#856熔断修复接入夜跑同步根；部署准备完成，不执行安装。

## 当前状态
#887已授权合入 `0525e780e0435d44d0f47455ef604325e1a65258`；合后四叶、正式收据和最终dry-run均通过。**可部署，未部署**。
装机源 `~/.finance-runtime/finance-nightly-installer-0525e780e043`；同步运行根 `~/.finance-runtime/finance-sync-2edbe4c46595`（完整SHA见报告），两者均干净固定检出且已锁定保留。
新证据 `~/.finance-runtime/reviews/eastmoney-cb-deploy-20260922/binding-merge-20260923T0919/`。读 `verification.json`、`install-runbook.md`；最终总索引为 `README.md` / `summary.json`。交接只留本地，不推送改动远端候选身份。

## 决策与被否方案
- 固定真实main作装机源，否了运行根/分支/预览树安装：运行根模板仍指旧根。
- 合后另跑完整门禁，否了给候选收据换签：部署依据必须绑定实际merge。
- 安装单独授权，否了时间到点自动装：会修改已加载任务，且需新备份和空闲窗口。
展开：`docs/handoffs/2026-09-23-eastmoney-deployment-ready.md`。

## 已验证
Python14620P/0F/0E/85S/2X，完整收集14707；Ruff、依赖/身份/干净树/漂移0及JUnit对平通过，相关96项齐全。前端120P、E2E34P/2S、registry五项通过（98非阻断warning）。
真实main源dry-run两job通过；实际模板临时HOME安装、运行根离线探针均过。安装副本hash/权限不变；18:07加载参数/环境匹配旧plist，两job未运行、夜跑锁不在。验收树与绿色临时目录已清理，固定两根保留。

## 未验证 / 已知边界
未获安装授权，未安装/重载/热补/写生产库。未验证真实请求时序、跨进程行为或数据恢复。#61/#871仍open且未纳入；#60不能标生产验收完成。

## 下一步
获得安装授权后，按runbook重验固定身份、哈希、解释器/依赖、加载状态和写者；main或文件漂移即停。避开18:30/20:40窗口，新建逐文件备份后从指定装机源nightly-only安装，不kickstart。随后回读磁盘及loaded状态，另做夜跑业务验收。

## 踩过的坑
当前生产仍adcda旧根；准备快照不是安装回滚点，不用旧Plan B。恢复native收据验证时，先按原路径重建该merge的干净验收树。资源观察不作性能结论；最新状态读新证据，不改旧冻结收据。
