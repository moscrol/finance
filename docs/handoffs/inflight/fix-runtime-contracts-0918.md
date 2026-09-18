# runtime-contracts-0918

## 这个分支做什么
沿OPT-08吸收行为合同、不叠框架：P0保存/截断→P1子存储/恢复/回读/插话→P2工具属性。

## 决策与被否方案
- 每树共享保存fence，否静默降级；锁仅存储IO、通知锁外，快照编码失败也熔断。
- 唯一父子引用、启动确认后执行；原窗内结算/窗外关闭父交付，否无限排空/全局sink开关。
- 恢复补写逐条确认后给plan；终态匹配当前检查点，旧finish不吞新repair；ACK丢失不回滚。
- 根预算存余额+授予/升档身份+原捕获位置，否policy重发/子视图独立铸币。补中断日志不等于预算已对账。
- 工具先扣账再步点/检查点；时间超支不退已执行槽位。
- 理由/首红见`docs/handoffs/2026-09-18-runtime-root-budget-snapshot.md`，内链旧片。

## 当前状态
树`~/fwp-wt-runtime-contracts-0918`，枝`fix/runtime-contracts-0918`。根预算代码610dcbeb固定验收通过；前置P0/子存储/恢复确认已验，P1整体未完。金融未push/合main/部署；授权不含上线。工具包e2c249b未合，vault756fe35d本机回写未手工push。

## 未验证 / 已知边界
- ResumePlan仍无跨进程driver；完整授权/策略/证据/查询/inbox现场、单写者与未知效果对账未齐。
- 预算捕获位置不是事务性计费水位；根快照不消除日志/扣账间崩溃窗口。进程内唯一根不是跨进程lease，旧日志/child view无快照不能补猜。
- 新closed不还原完整草稿/证据/费用；一致done不证上次ACK/公开送达。超窗子费用未必完整归父；不外推SDK/exactly-once/真模型质量/独立复核。
- e336首轮provenance红根因未明；后续绿不是修复。vault20错误/17警告未变，graph通过不等于vault全绿。

## 下一步
1. 补版本化完整授权/策略与registry重验、证据E号/owner/日期/原件、查询准入、inbox正文/回执、截止/取消。
2. 单写者/重复启动及父子未知效果对账后接同一loop driver；只在临时目录真实进程中断验已确认不重做、预算不重置、消息不丢。
3. E号回读、Workbench插话/wakeup、P2逐工具属性；合并部署另确认。

## 踩过的坑
- 使用真实checkpoint前缀，不能拿最终余额配手工删尾旧日志。
- 收据用精确文件/规定解释器；E2E换端口同时传RE06_E2E_URL；子缓存不重复计费。

## 已验证
610dcbeb干净树：Python11598P/81S/2X、Ruff、前端四项107P、E2E34P/2S、registry/crosswalk。新17变异红→绿（单文件前后61P）；旧P0/子/恢复13/14/7项同版复验通过，各数不相加。证据`~/.finance-runtime/reviews/runtime-contracts-610dcbeb/`；收据`20260918T130950Z-610dcbeb.json`七项通过。
