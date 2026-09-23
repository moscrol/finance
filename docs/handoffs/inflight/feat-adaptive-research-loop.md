# feat/adaptive-research-loop 在途

## 这个分支做什么
#72/PR #868、#75双轴独审、#76 L6。WIP，未push/合/部署。

## 决策与被否方案
- 金额仅明确货币字段换算；身份归控制器；下一题须精确Episode内容审计PASS。
- 旧失败不续跑/倒写，不扩deadline或检索120秒预算。
- 本次补阶段观测、覆盖门和检索结果核验，不据一次绿归因旧超时。
- 详见 `../2026-09-23-adaptive-admission-diagnostic.md`；上批见 `../2026-09-23-adaptive-repaired-verification.md`。

## 当前状态
最新代码fe548838b：HTTP启动/发送/回收观测，严格探针拒未进入目标阶段，检索逐阶段日志/周期栈及有效shape核验；独审提示优先必红控制/作者测试。main最后fetch仍626d8a508。
新离线根 `~/.finance-runtime/reviews/pr868-admission-diagnostic-20260923-2218/` 已封存25份原件；归档 `docs/verification/2026-09-23-admission-diagnostic/README.md`。无新#75/#76、付费模型0、自然题0；成功basetemp已清，进程/19897-19899无遗留。
上批#75共65请求，Spec PASS_WITH_LIMITS、Quality BLOCKED_INCOMPLETE_EVIDENCE；总态BLOCKED_INCOMPLETE_INDEPENDENT_EVIDENCE。上批L6 BLOCKED_PREFLIGHT、首发0/0/0；旧自然NOT_PASSED不变。2115 QC/2118 L6封存根不可续跑。

## 未验证 / 已知边界
两轴作者测试/必红控制未执行；Spec C3/C5/C6及第五HTTP调用点缺覆盖。取消探针宿主诊断为probe_bug（未触发cancel），不改原reviewer报告或代签。
旧body_stall 1.378s且HTTP0、旧RAG120s超时均未重现，根因未证实；高负载不免责。本次dirty诊断四模块哈希等同fe548838b，不冒充正式干净准入。
自然修订保真、迟到判官拒收与题间屏障未通过；当前完整/最新main联合门禁未跑。历史全量不移签。

## 下一步
1. 固定新候选，以新根/输入/预算记录安排#75，实际执行作者测试与必红对照并补行为覆盖，两轴互不见结论。
2. 新题/新正式准入再开#76；失败即停，重发/续问0，不能用本次诊断代自然验收。
3. 补完整工程与最新main联合树门禁，合入仍需用户确认。

## 已验证
fe548838b干净七文件411P/0F/0E/0S，收据20260923T142411Z-fe548838-63d172dd3cd2经checker核验；全仓Ruff/diff check过。
一次严格13场景无越窗/覆盖缺口；一次真实BGE-m3总墙钟38.41s、worker31.10s、shape(1,1024)。两次内存撤保护预期1F/5F、0error；不混计411P。原金额/屏障328P仅签ac11027fa。

## 踩过的坑
exit0不等于ready；无换行流不能在行迭代体内触发cancel。缓存只读避免每批强制冷编译。harness-reference/BUILD.md有他人改动，未碰。
