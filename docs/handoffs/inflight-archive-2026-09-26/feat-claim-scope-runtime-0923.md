# Claim-Scope Runtime

## 这个分支做什么
默认off、仅advisory接入；推进独审、K3 L5与有门禁部署。

## 当前状态
WIP #890未合未部署。产品候选14f885e01完整工程已绿；本次GLM三段独审PASS_WITH_LIMITS。L5改为BLOCKED_MARKET_DATA_CONSISTENCY：市场汇总09-22、快照09-23，两题仍各首发0/重发0/续问0。生产身份七字段未变。本次仅文档回写，不把14f收据移签到后续head。
证据根`~/.finance-runtime/reviews/claim-scope-runtime-20260923/continue-01/`，audit.json与131成员manifest已封存；旧红/旧绿39/33成员复核不变。过程无遗留审查进程。
续轮只读预检仍09-22/09-23不一致；夜跑东财快照失败，同花顺并行表成功不等于正式表恢复。证据`../recovery-preflight-01/`；详见`docs/handoffs/2026-09-23-claim-scope-recovery-preflight.md`。未重跑复盘或写生产。

## 决策与被否方案
- K3小载荷200但32-token下空回，不判通道不可用；按既有偏好切GLM工程独审，不改签K3专项。
- 独立15P、故意红控制1F、作者22P分账，不以作者测试补独立动态覆盖。
- 直接求值候选readiness判据仍false，保留L5首发，不靠贴日期/自行回填推进。
- 理由见`docs/handoffs/2026-09-23-claim-scope-glm-review-readiness-block.md`。

## 已验证
14f完整14643P/0F/85S/2X、前端120P/E2E34P2S/registry5项；本次仅重核完整收据，未重跑全量。GLM三段12/17/27请求，含两预探共58，无自动模型重试；独立报告三件齐全，候选只读/前后未变。入口`docs/verification/2026-09-23-claim-scope-runtime/README.md`。

## 未验证 / 已知边界
C7真实A恢复流、C8 B三个入口全链、C9终态竞争未独立动态压测；静态与作者证据不冒充独立动态。census缺键advisory可能KeyError，仅静态非阻断观察。K3专项/新L5无judge、marker、答案收据；未冻数据、无旁路/锁。生产readiness仍not_ready，回滚未验。

## 下一步
生产复盘须用户手动`/daily-full-review 2026-09-23`；勿绕调脚本或清理失败staging。恢复线他人已推进f22，旧HOLD不是新头验收。先核代码/依赖/主干漂移，新组合另冻另验。明确K3路由/凭证/剥参及judge关闭证据，再两原题首发1/重发0/续问0。全部门禁含readiness/回滚通过才合入部署。封存脚本排他创建，勿覆盖重跑。

## 踩过的坑
pi exit0可有模型timeout；极短输出预算空回不等于通道失效。AST检查须限定health_ready作用域。PR写请求超时先回读；L5全集按正式日期查冻结库，不能沿用旧20。B缺工具请求账仍显式degraded。
