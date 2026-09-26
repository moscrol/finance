# #60 固定f47准备完成，未安装

## 这个分支做什么
#856修复与#887绑定已合入；本轮按用户“继续推进”承接上一条固定f47建议，只到部署准备，不含实际安装。

## 当前状态
固定发布版技术准入通过：ready_for_deployment=true，但ready_to_install_now=false、installed=false。后续main不自动纳入，不声明最新main全绿；原规程/校验器与历史拒绝未改。
20:46只读观察finalize正在运行(PID24960)、夜跑锁存在；sync未运行。不得打断任务或删锁腾窗口。两固定根干净且锁定，六个安装配置hash/mode未变。
新证据 `~/.finance-runtime/reviews/eastmoney-cb-deploy-20260922/release-f47-20260923T1243/summary.json`，原话/范围见同目录authorization.json；正文 `docs/handoffs/2026-09-23-eastmoney-fixed-release-ready.md`。记录只作本地文档提交，不推送。

## 决策与被否方案
- 固定装机源f47，运行根2ed，#887实际merge0525分开；运行根模板旧，不可从运行根安装。
- 同版本/同依赖复核原全量，不重复追移动main，也不改旧收据身份；完整范围、精确SHA及固定发布基线零漂移保留。对最新main负向对照仍exit1。
- 技术准备与安装授权/窗口分开：不因ready而自动安装或停夜跑。

## 下一步
单独获得安装授权后，等自然空闲窗口，重新核两job/锁/其他写者及身份、依赖、hash，制作并验证两plist/两launcher逐目标新备份，按新证据目录install-runbook.md执行。不能沿用20:46观察；不自动kickstart。
装机源 `~/.finance-runtime/finance-nightly-installer-f47d464eb7af`，精确SHA f47d464eb7af32157c331bf2a6bf1b337acbb43f；运行根 `~/.finance-runtime/finance-sync-2edbe4c46595`。

## 已验证
原88份证据哈希全过；原完整14621P/0F/0E/85S/2X、collected14708复核有效，非本轮重跑。解释器/依赖/干净树/原运行结构/JUnit、前端120P/E2E34P及2跳过/六日志hash、registry5项与98非阻断warning对平。新跑离线探针、真实模板隔离模拟、两任务四目标dry-run均过。

## 未验证 / 已知边界
无安装/重载/kickstart/热补/8792切换/生产DB打开或写入。自然夜跑可自行改业务数据，本轮只认证安装配置未变。真实时序/跨进程/行情恢复未验，#61不捆绑，#60不标生产验收完成。

## 踩过的坑
显式check_test_receipt支持同版本跨树复核，别为适配路径改收据；原shell gate树身份仍保留。准备快照非回滚备份，禁止旧Plan B；后续main不能自动替换固定源。
