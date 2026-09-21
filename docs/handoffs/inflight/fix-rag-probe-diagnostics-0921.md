# 在途交接 · RAG 探针诊断与并发优化

## 这个分支做什么
安全诊断 + 同配置重叠 help 去重；保持单次5秒、无重试/结果缓存、失败503。

## 决策与被否方案
- 同 key single-flight 完成即删；否了全局慢IO锁、缓存、延长超时。
- 保留查询依赖导入，否了全懒加载；代码变化 code_changed，公开字段白名单不扩。
- 生产 readiness 会恢复worker/创建目录，本轮不调用；只读复算行情判据，沙箱单次help。
- 生产指纹另算，不只信启动快照；dirty-source不直接判整库死。理由/收据：`../2026-09-22-production-readonly-readiness.md`；实现证据：`../2026-09-21-rag-probe-singleflight.md`。

## 当前状态
实现3451c1d65，只读交接894ad9f65；#844保留WIP，未合未部署。09-22 00:17核验：8792仍adcda94b recovery / GLM-5.3-flash，判官缺省llm；行情一致性false（主库09-18，快照09-21）。09-21同步遇RemoteDisconnected，质量门拒绝staging晋升，finalize中止。后续“执行”依CLAUDE.md停在手动技能门，未补库/改配置/重启/切模型。

## 已验证
前轮定向230P/4S、Ruff/diff/pre-commit通过；两变异6/1项失败；8并发子进程8→1，非单次CLI提速。
00:17 health healthy；当前代码指纹匹配启动值、受跟踪文件干净；快照契约PASS。沙箱单次help309ms/rc0，必要参数齐，可选过滤/receipt仍缺；保护项哈希/主库stat未变。随后显式read_only复查：主库五张关键fact的09-21均0行；staging仅fact_market_daily 1行，其余四表0行。latest/meta均served=09-21。审计用库内日历，missing=0不证目标日齐；本次未另封存收据。

## 未验证 / 已知边界
未调用HTTP readiness、真实query或模型；worker仅证进程存活，内部状态未知。help环境有只读/离线约束，n=1不是生产重放或历史超时根因证明。索引元数据对齐不等于内容新鲜。全仓/前端/E2E/外审、BGE质量、fallback/恢复未验。single-flight仅同进程，5秒非端到端deadline。
原件：`tmp/production-readonly-20260922/` receipt/manifest及受限原始日志；前轮`tmp/rag-probe-singleflight/`110文件证据与失败原件保留，勿删。

## 下一步
请用户手动调用 `/daily-full-review 补齐2026-09-21行情` 后再抓源/写staging；不绕技能门、直写生产或改日期标签求绿，保留失败staging。跨午夜先验源实际交易日；recover_local_review要求两日输入，不直接套单日。审#844，等合并/部署授权及目标tip门禁；先RAG受控部署，再单独K3/judge-off，不宣称超时已修复。

## 踩过的坑
readiness GET不是纯读；新进程status看不到生产worker。health指纹只在启动算；RSS不证明模型卸载。日志CR会让splitlines行号偏移。adcda94b本来支持maintenance_launch，旧目录为文件漂移，别归因启动器自动恢复。共享KB有他人改动/冲突，勿碰。
