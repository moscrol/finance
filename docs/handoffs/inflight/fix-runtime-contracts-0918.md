# runtime-contracts-0918

## 这个分支做什么
沿OPT-08吸收行为合同、不叠框架：P0保存/截断→P1子存储/恢复/回读/插话→P2工具属性。

## 决策与被否方案
- 每树共享保存fence，否静默降级/全进程熔断；锁仅存储IO，通知锁外。
- 唯一父子引用，启动确认后执行；原窗内结算、窗外关闭父交付，否无限排空/假称线程已停。
- 缓存与父账发布分闸，子稿调用域隔离；否全局开关sink。
- 恢复合成逐条冲刷后才给plan/closed，否依赖下一意图；ACK丢失不回滚、不授权重试。
- 终态须匹配当前检查点，旧finish不吞新repair；关联树未对账先拒绝。
- 详见`docs/handoffs/2026-09-18-runtime-restore-confirmation.md`（内链P1a/P0快照）。

## 当前状态
树`~/fwp-wt-runtime-contracts-0918`，枝`fix/runtime-contracts-0918`。P0代码48823062、子片7f6b201d、恢复确认371b0ef7均固定工程验收通过；P1整体未完。金融枝未push、未合main/部署；实施授权不含上线。工具包e15e764未合；图谱/项目索引由vault自动同步b70c748b收入。

## 未验证 / 已知边界
- ResumePlan仍无跨进程消费driver；根预算grant/promotion去重身份未序列化，授权/证据/查询/inbox完整现场与单写者未齐。
- 新闭合结果不还原完整草稿/证据/费用；一致done不证上次ACK或公开送达，写后故障收据未必落盘。
- 超窗子费用不保证全入父账；不外推SDK/任意client、exactly-once、真模型质量/独立复核。
- e336首轮call_provenance红根因未明；同版9P及后续全量绿不是修复。
- vault前后均20错误/17警告、错误集合不变；graph通过，不冒称vault全绿。

## 下一步
1. 补版本化恢复现场：完整合同/策略、预算授予/升档身份、证据E号/原件、查询准入、inbox正文/回执、绝对截止/取消。
2. 单写者/重复启动门后接同一loop driver；仅临时目录真实进程中断验已确认不重做、预算不重置、消息不丢。
3. E号回读、Workbench插话/wakeup、P2逐工具声明；合并部署另确认。

## 踩过的坑
- shared-health首变异被下一次写闸掩盖；model_pending意图后针才独立抓住多发模型。
- 收据用精确文件/规定解释器；E2E换端口须同时传RE06_E2E_URL。子缓存telemetry不可重复计费。

## 已验证
371b0ef7干净树：Python11537P/81S/2X、Ruff；前端四项107P；E2E34P/2S；registry四项+crosswalk。7变异红→绿，所选两文件前后32P非全仓。证据`~/.finance-runtime/reviews/runtime-contracts-371b0ef7/`；收据`20260918T114840Z-371b0ef7.json`七项通过。子片14变异/四叶及首轮失败保留在7f6/e336各目录。
