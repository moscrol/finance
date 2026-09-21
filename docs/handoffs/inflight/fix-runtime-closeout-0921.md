# Runtime 重复恢复收尾

## 这个分支做什么
接手无执行者的 #834 runtime 验收，修重复恢复丢待办/重复结算；不接管历史、ReAct、adaptive 或发布线。

## 当前状态
代码 2f98a6a1fc4e9a30d5e501e904c60974eef6b5f8 已提交并推送；WIP PR #843。
基座 main 79b11d426 + 固定 #834 cb16cd463 内容前向 squash；原 #834 分支未改。
不是完整恢复 driver；未合 main、未部署8792、未启动新付费外审。
正文/来源/验证：[日期快照](../2026-09-21-runtime-repeatability-closeout.md)。

## 决策与被否方案
- 计划不是执行：保留 phase/reserved_ids；否了计划生成就推进位置，会丢待派发工具和待解释回复。
- 合成结算仍同步保存，只前进确认前缀；否了省略写入确认。应用声明先点查已结算，防重复补写。
- 复用完整 state+ID点查，不加第二套 ResumePlan schema、不猜日志位置、不扩大续跑许可。

## 已验证
固定干净代码：Ruff绿；全量12945P/87S/2X；前端lint/typecheck/110P/build；E2E34P/2S；registry四项绿。
新增11回归（两存储、逐崩溃前缀、部分批次、ACK丢失、全新进程回读）；5新+7原保存确认变异逐项红→绿。
Python收据 ~/.finance-runtime/test-receipts/20260921T132628Z-2f98a6a1.json，精确SHA校验过。
变异 ~/.finance-runtime/runtime-closeout-0921/{repeatability,confirmation}-2f98a6a1f/results.json。
E2E隔离18891/18894已退出。以上不移签到文档tip/组合main。

## 未验证 / 已知边界
作者工程验证非独立审查；上游独立审容量中断无报告，未代签。
新进程只判计划，未杀真实运行再驱动；入口身份/单写者lease/未知效果费用对账/后续私有证据与消息现场仍缺。
保稿公开交付/判官/自然金融质量不属于本轮通过范围，旧not_passed不翻案。

## 下一步
独立验#843差异与上游组合；要付费审查先取授权。合并前冻结最新树重验并等用户确认；不自行部署。
完整driver另按上述前置推进，不能拿plan直接执行。

## 踩过的坑
原47测试只验第一次恢复；重复读才暴露跳步。旧断言清ID/进入finalizing本身有误，但fsync/ACK门不放宽。
本候选含上游75文件，不是单文件补丁；本轮原创集中episode_restore和测试/变异/门页。
