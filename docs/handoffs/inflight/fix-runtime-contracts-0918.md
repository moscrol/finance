# runtime-contracts-0918

## 这个分支做什么
沿OPT-08吸收行为合同、不叠框架；P0保存/截断→P1子存储/恢复/回读/插话→P2工具属性。

## 决策与被否方案
- 每棵父子树共享保存fence，否静默降级/全进程熔断；锁不包模型IO，通知不反取ledger锁。
- 唯一invocation/子ID，否显示branch-N作持久身份；启动记录确认后才执行。
- 原绝对窗口内收已收费用，窗外关闭父账交付；否无限排空/把超时当线程已停。
- 缓存发布与父账交付分闸，子稿按调用域禁公开；否全局改共享sink。
- 未对账关联树拒绝恢复，否有日志就retry；详见`docs/handoffs/2026-09-18-runtime-contracts-p1a.md`（P0另快照）。

## 当前状态
树`~/fwp-wt-runtime-contracts-0918`，枝`fix/runtime-contracts-0918`。P0代码48823062；子存储e336093e、测试补强7f6b201d已入本枝。子切片固定四叶/14变异通过，P1整体未完。未push金融枝、未合main/部署；实施授权不含上线。

## 未验证 / 已知边界
- ResumePlan尚无跨进程消费driver；根预算grant/promotion去重身份未序列化，完整证据/查询/消息现场未齐。
- `_Synthesizer`尚sync=False；任意旧finish被当终态会吞repair现场，下一片先修保存确认。
- 写后ACK丢失仍uncertain；故障收据未必落盘，超窗子费用不保证全入父账。
- 不外推任意注入client/SDK、exactly-once、真模型质量或独立复核。
- 首轮e336全量1F（call_provenance），同版局部9P、新版全量绿；根因未确认，测试补强不是该缺陷修复。

## 下一步
1. 修恢复合成冲刷/检查点确认，拒绝不完整终态；故障注入+撤保护另验。
2. 补完整恢复现场及同一loop driver；临时目录进程中断验预算不重置/消息不丢/已确认不重做。
3. E号原件回读、Workbench插话/wakeup、P2逐工具声明依次推进；合并部署另确认。

## 踩过的坑
- shared-health首轮变异存活：下一次写闸掩盖效果前缺口；用model_pending单步针独立抓住多发模型。
- 收据用精确文件/规定解释器；别枝会覆盖latest。E2E改端口同时传RE06_E2E_URL。
- 子工具缓存telemetry不能重复算费用；费用按本批新增分支终态结转。

## 已验证
7f6b201d干净独立测试树：Python11519P/81S/2X、Ruff；前端四项107P；E2E34P/2S；registry四项+crosswalk。14变异红→绿，所选三文件前后67P非全仓。证据`~/.finance-runtime/reviews/runtime-contracts-7f6b201d/`；全量收据`20260918T112340Z-7f6b201d.json`七项通过。首轮红/存活另存e336093e目录。工具包c2e3c81未合。
