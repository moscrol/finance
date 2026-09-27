# fix/re06-timer-scope-0923

## 这个分支做什么
#73 用户回复 `b`：把计时授权拆成独立 scope，不再改变研究测量同意。树 `~/fwp-wt-wave2-re06-0923`；原任务树和共享脏主树未改。

## 决策与被否方案
- 选 `activity-timer` / `workbench-activity-v2`，否只改文案或写门忽略 version。
- 读写共用 `measurement_scopes`；纯计时不算测量意愿，其余部分授权/空集/撤回不变。
- 旧 v1 仅对原控件完整自用形状作对称读取兼容；不迁移台账、不改哈希，不把 grant 冒充试点授权。
- 详情及被否理由：`docs/handoffs/2026-09-23-re06-timer-scope-b.md`。

## 当前状态
固定 base `ffd1b7f15720` + 源 `100dcb32abd7`，候选整合 `486ae9188`；本轮代码提交 `4bb3bf0cb19f0992ccb2a02bae75b6f16145d1dc`。本地候选，未 push/开 PR/合 main/部署/写生产库。

## 已验证
干净代码提交：Python 授权/API 四文件 89P，前端两文件 9P；typecheck、修改文件 ESLint/Ruff、提交门禁绿。收据 `~/.finance-runtime/test-receipts/20260923T042307Z-4bb3bf0c-1e7b698d6fd6.json`，dirty=false，非全仓。
提交前同实现扩展回归164P和195P（含重叠），去重共369项。进程内撤隔离/撤旧版兼容/绕锁内复核分别6F/1F/1F，恢复后绿。JUnit归档 `~/.finance-runtime/reviews/re06-timer-scope-20260923/`。

## 未验证 / 已知边界
完整四叶、#75 独立QC、#76/P7 真实验收均未做；17处事务同族清单未重新逐项核。12:21 load=17.74、pytest=5，不加全量。旧记录重算结果可能变化，旧收据不能移签；生产未重算。代码地图为空，未当作架构证据。

## 下一步
低负载冻结候选跑四叶；补同族清单；按#75做K3独审。完整验收通过后再请用户批准合main，部署/迁移另授权。权威INDEX在 `~/fwp-wt-closeout-workorders-0922`，同步#73为B已实现待验收。

## 踩过的坑
只改前端scope会让首次计时翻掉自用默认；必须排除纯计时意愿。不能把所有非research范围排除，否则首条blind_review等部分授权会被错误放行。锁内复核和事件时刻语义保留。
