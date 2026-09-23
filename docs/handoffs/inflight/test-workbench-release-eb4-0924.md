## 这个分支做什么
独立回放 owner 的 eb4ec08f0680f9ba8cdaf5f3e8a95be34861b12a；不接管恢复、换库或发布。本分支后续仅加交接文档，收据仍只签 eb4。

## 决策与被否方案
- 沿用 owner 的三态历史名称修复；本地等价提案 96adae797 仅归档，不合入第二套实现。
- 未知身份不能当未涨停；只在连板真正消费时拒绝。名称格式合格不代表日期来源已认证。
- 不以自然问答成功替代数据准入，不把旧版本收据移签。
- 最新：`docs/handoffs/2026-09-24-eb4-gates-and-name-scope.md`，内链初始验收快照。

## 当前状态
仍 HOLD 数据发布；eb4 完整工程门已完成：15084P/85S/2X，15171 collected，精确收据 checker 通过；前端六项和 registry 五项全绿。
生产数据未改、未合 main、未部署。自有控制器和 19051 sidecar 已退出，临时变异树已清理；生产 DB 身份和启动器哈希稳定。

## 已验证
- eb4 名称边界及旧统计回放 118P；三项名称变异 28F/7F/4F，恢复 109P。
- sidecar 2、启动恢复 16、传输 12、交付状态 2 项变异全部抓红并恢复绿。与名称合计 35 项，非全仓测试。
- 状态接线三例通过；0e66b 的两个文件已随 2ddd 纳入，blob 相同，不再列未集成。
- 真 BGE-m3 冷启动 46.958s；两次非缓存 hybrid 各 6 条 fresh，模型只加载一次。
- 自然会话 run_20260924_033645_080673：GLM-5.3-flash、completed、语义通过、泄漏扫描 0；Episode 20 事件，RAG served 1→7。

## 未验证 / 已知边界
readiness 前后 503，唯一 critical 为 market_data_consistency。缺名/缺行、停牌分区及正式恢复仍由 owner 闭合。相关判官不是独立金融 QC；N=1 不作性能结论。索引 source_dirty=true，旧 CLI 缺可选 receipt。
审查者写过未选用并行提案，不是盲审。owner 后续 ffc67575 仅加文档，不能移签 eb4 收据。

## 下一步
1. #900/6712 已确认新浪09-22原窗口的5564条展示名证据可采信，70页封存链核对通过；不是官方名册。补301686.SZ、689009.SH、920229.BJ，声明分母仍5567。
2. owner 明示扩展名称来源，完成数据、正式 staging、三道数据门，再复验 readiness 与同版本自然入口；不增设官方全集前置门。
3. 本分支加文档后 HEAD 不再等于 eb4；重跑用干净 eb4 树和新证据目录。

## 踩过的坑
证据根 `~/.finance-runtime/reviews/workbench-release-20260924-independent/eb4-live/`，看 sealed-evidence.json。
旧外置状态夹具 1F/2P 是混淆 research/business；另一份 error 是 cwd 导入主树，均保留并隔离，不算运行时回归。外置测试须绑定 cwd、代码树、测试来源。查门只读根级文件，勿扫进嵌套夹具。
