# #60 固定f47已验，发布范围待确认，未部署

## 这个分支做什么
#856修复与#887绑定已合入；本轮推进到部署准备，尚未授权正式安装。

## 当前状态
固定装机源 `~/.finance-runtime/finance-nightly-installer-f47d464eb7af` 的完整四叶、native/JUnit、最终dry-run及loaded回读通过。但main继续合入其他批次，19:46核验时已至626d8a508c1c988ff094110b371987e6afdcdd15；含新报表代码/门禁，不仅是文档。当前main准入exit1，ready=false。
已结束本会话门禁并清理临时验收树/绿色basetemp，固定源和运行根保留。未对后续main继续自动重跑。远端候选仍99bd31c97630，交接只作本地提交、不推送。
证据 `~/.finance-runtime/reviews/eastmoney-cb-deploy-20260922/current-main-f47d464e-20260923/summary.json`；正文 `docs/handoffs/2026-09-23-eastmoney-release-scope-blocked.md`。

## 决策与被否方案
- 收据只证明固定revision；不移签、不因base-drift上限而免除current-main SHA全等。旧0525/b59各自通过，只作各自证据。
- 暂停自动追tip：连续多次并发推进改变对象，后续又有运行代码，需用户明确发布范围或协调窗口。
- 装机源f47与运行根2ed分开：运行根 `~/.finance-runtime/finance-sync-2edbe4c46595` 模板旧，不能从它安装。

## 下一步
请用户选择：明确固定f47为#60本次发布版（建议，后续main不自动纳入），或暂停并发合入后验选定的新main。不得擅自改变原current-main准入条件。版本冻结确认仍不等于安装授权。
实际安装另需明确授权，重核身份/依赖/hash、空闲窗口与写者、逐目标新备份；计划在证据目录 `install-runbook.md`。

## 已验证
f47 SHA f47d464eb7af32157c331bf2a6bf1b337acbb43f：14621P/0F/0E/85S/2X、collected14708；前端120P、E2E34P/2S、registry5项及98非阻断warning。相关96项/timeout两态均实跑。
fixed-revision-verification.json只签f47；current-main-admission-rejection.log保留拒绝。两任务四目标dry-run零复制/服务变更；六个生产文件hash/mode跨三轮相同。19:44观察任务idle/无锁，只是当时状态。

## 未验证 / 已知边界
无安装/重载/kickstart/热补/8792切换/生产写库。真实时序、跨进程、行情恢复未验，#61未捆绑，#60不可标生产验收完成。

## 踩过的坑
准备快照非安装回滚点，禁旧Plan B；时间到点不是授权。最新main增加了代码，不可用f47的绿代表它；也不可反过来否认f47本身已完成的验证。
