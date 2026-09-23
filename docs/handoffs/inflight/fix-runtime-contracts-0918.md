# runtime-contracts-0918

## 这个分支做什么
沿OPT-08吸收行为合同、不叠框架：P0保存/截断→P1恢复/回读/插话→P2工具属性。

## 决策与被否方案
- 每树共享保存fence，否静默降级；锁仅存储IO、通知锁外，快照编码失败也阻新效果。
- 完整授权须入口当前context/registry精确重验，否磁盘自授/旧日志旁路；终态一致只读例外。
- 升档先确认再启子效果，但保原phase/预留ID/retry/cancel；否用planning抹执行位置。
- 预算保授予身份/原捕获位置，否按policy补满；补日志不等费用已对账，超时不退已执行槽。
- 理由/首红：`docs/handoffs/2026-09-18-runtime-authorization-snapshot.md`，内链旧片。

## 当前状态
树`~/fwp-wt-runtime-contracts-0918`，枝`fix/runtime-contracts-0918`。授权代码6b70e540固定验收通过（含576d4764），补丁枝已ff收入，无需重做；P1整体未完。金融未push/合main/部署。工具包8e5d4fe未合；vault自动同步ea510789收录，未手工push。

## 未验证 / 已知边界
- ResumePlan仍无跨进程driver；入口身份、证据/查询/inbox现场、单写者与未知效果对账待补。声明摘要不是代码/用户签名。
- 预算捕获位置非事务计费水位；进程内唯一根非跨进程lease。关联树恢复仍拒绝，closed未还原完整稿/证据/费用。
- 一致done不证旧ACK/公开送达；超窗子费用未必归齐。无真实进程中断/SDK等价/exactly-once/模型质量/独立复核结论。
- e336 provenance首红根因未明；后续绿非修复。vault20错误/17警告集合未变，graph通过不等全绿。

## 下一步
1. 补入口绑定、证据E号/owner/日期/原件、查询准入、inbox正文/回执、截止/取消，不再重复开发授权快照。
2. 单写者/重复启动及父子未知效果对账后接同loop driver；临时目录真实中断验已确认不重做、预算不重置、消息不丢。
3. E号回读、Workbench插话/wakeup、P2逐工具属性；合并部署另确认。

## 踩过的坑
- 真checkpoint前缀恢复，不能拼最终余额与旧日志；升档只改许可不抹位置。
- 首冻11F是非法query_scope=turn夹具，改query不放宽门；两格位置漏洞先红后修。
- 用精确收据/规定解释器，E2E换端口同步RE06_E2E_URL；全量期间不改被测树。

## 已验证
6b70干净四叶：Python11687P/81S/2X、Ruff、前端107P、E2E34P/2S、registry/crosswalk，目录/字段门通过。新22变异（前后89P）及旧P0/子/恢复/预算13/14/7/17项红→绿，各数不相加。证据`~/.finance-runtime/reviews/runtime-contracts-6b70e540/`；收据`20260918T154311Z-6b70e540.json`七项通过。
