# 在途交接 · RAG 探针诊断与并发优化

## 这个分支做什么
安全诊断 + 同配置重叠 help 去重；保持单次5秒、无重试/结果缓存、失败503。

## 决策与被否方案
- 同 key single-flight 完成即删；否了全局慢IO锁、缓存、延长超时。
- 09-22 按用户要求做**一次** readiness 实跑并先声明其恢复/建目录副作用；否了继续用 help 冒充实跑，也否了轮询求绿。
- 保持 503 与原始日期；否了改快照日期、放松一致性门、部署本候选求绿——探针去重不生产行情事实。
- 行情恢复仍归 `fwp-wt-market-recovery-0921`；本枝不写库、不发布。
- 详情见 `../2026-09-22-rag-readiness-live-resume.md` 及同目录 09-21/09-22 旧快照。

## 当前状态
实现仍 `3451c1d65`，其后只有文档。#844 open/WIP、未合未部署，远端 head `18c6215791e5`；本地 `894ad9f65`、`a25cf7e24` 及本轮文档**未推送**。生产仍 adcda94b / GLM-5.3-flash / 判官缺省 llm，没有本候选的新字段。

## 已验证
09-22 17:58 单次 `GET /api/readiness`：HTTP **503**、780.664ms、`missing_critical=["market_data_consistency"]`；RAG 必要四参数齐（五可选缺，legacy），worker ready/active=1/recoveries=0（queries_served=6 是进程累计）。只读 DuckDB：五张关键 fact 最新均 **09-18**，09-21/09-22 全 0 行；快照已到 **09-22**（契约 PASS）。09-18 主线 71 行 today_pct/amount/strength 全空——`compute_mainline_local` 本就只写名单，不是新损坏。索引元数据门通过（年龄 3.86d<14、chunk_profile 一致、向量/BM25 对齐）。干净 `a25cf7e24` 定向 **226P/0F/0S**（env -i 隔离），八文件 Ruff 通过。采样前后保护文件/主库 SHA256/进程不变。证据 `docs/verification/2026-09-22-rag-readiness/summary.json`，33 份原件在 `~/.finance-runtime/reviews/rag-readiness-resume-20260922T175900/`（勿删）。

## 未验证 / 已知边界
未发真实 query/模型题：逐页内容新鲜度、召回质量、worker 内部加载身份、fallback/恢复全未验；元数据对齐≠内容新鲜。n=1 不证明历史间歇 timeout 消失，780ms 是旧版端到端 HTTP，非新探针性能。226P 与前轮 230P/4S 分母不同，不是 merge gate：全仓/前端/E2E/registry/独立外审未跑。另有 fact 表停在 09-02/09-08/09-15 或为空，未逐表归因。

## 下一步
先推进行情恢复（历史日 09-21 走回填规程、09-22 走当日盘后正门，均需用户显式调用技能并按阶段授权），数据到位后再复验 readiness。#844 需目标 tip 完整门禁 + 独立审核 + 合并/部署授权；先 RAG 受控部署，再单独 K3/judge-off，不宣称超时已修复。

## 踩过的坑
readiness GET 不是纯读；curl rc0 只表示收到响应，不代表就绪。行数≠字段可用（主线空列）。health 指纹只在启动算；RSS 不证明模型卸载。共享 KB 有他人改动/冲突，勿碰。
