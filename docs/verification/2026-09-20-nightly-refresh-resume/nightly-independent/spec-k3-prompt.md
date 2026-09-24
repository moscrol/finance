你是独立 Spec（规格符合性）审核者，不是作者。仅审固定提交，不执行实现，不提交/push/建PR/合并/部署，不派生子agent。中文报告。

候选是你的 cwd：/Users/a77/.finance-runtime/reviews/research-closeout-resume-20260920/nightly-independent/spec-tree
必须首尾核 HEAD=d95b706edc6e44f3dfa54d7b8837dfdd36b16cf2 且 git status --porcelain 为空。只能在 /Users/a77/.finance-runtime/reviews/research-closeout-resume-20260920/nightly-independent/spec-k3 写探针/临时fixture/日志。不要修改候选源码，包括code-map生成物。
这次只签新片 R1 + main合流 I1，不签原夜跑全部实现或 R2。主要差分 git diff 34f49ce1...HEAD；合流背景 git diff e51c5157c9ea9aa86491c486663700e7d7696a6f...HEAD。新增tests可参考但不要只抄作者结论。读 AGENTS.md 和偏好卡；不需要项目记忆写回或handoff提交，回给root即可。若代码地图stale只记边界、精确读固定源码，不修改地图。

规格（来自已批准计划 2026-09-20-nightly-refresh-completion.md）：
1. recovery_stitch_command要求 --include-completed。旧 audit_complete=true 不能替本轮刷新成功。既有 stitch_sector_members 返回 candidates/stitched/skipped/failed/pending_for_provider；本轮请求重算的候选全部完成，才可向恢复调用方成功。缺合格基线、有效成员为空、数值不足、writer失败阻断恢复成功。
2. 重用摘要与责任边界，不造第二份freshness台账，不改审计历史，不放宽恢复180日基线，不借未经验证名单替补。普通非刷新日更 skip→provider补齐维持；dry-run可以返回预览成功，但绝不认证实际写入完成。
3. 空候选不能只凭0==0：无 changed/new/provider待补且审计完整才是零工作成功。其他情况拒绝。
4. 真实recovery.child消费刷新失败后不得写本run_id成功状态，不得继续派生/发布。staging publisher既有不成功不发布保护保留。
5. 合main整合I1：仅计划明示的 HITHINK_STEPS 缺key skip可继续，保留原skip/未更新收据；必需步骤skip、Hithink失败/timeout和质量门失败仍阻断。main四个Hithink步骤和原本local指数no-fupanhui-fallback均保留。
6. 反例：旧完成3板块、底价12旧成员10、无180日内基线→必须非零/刷新未完成；365日只作fixture正常对照，实际更新到12，不能改生产规则。补部分成功、空候选、writer失败、普通日更、dry-run。
7. R2保留范围外：跨午夜归档回放可能仍被qa_backfill_align日期门拒绝，不要当新缺陷要求这片修，不得删日期门。真实无人值守与生产回填未授权。

工具与安全：Python只用 /Users/a77/finance-workspace-private/.venv-workbench/bin/python。所有检查使用白名单 env -i HOME=/Users/a77 PATH=/usr/bin:/bin:/usr/sbin:/sbin LANG=C.UTF-8 TMPDIR=/tmp FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1；需要时加PYTHONPATH=候选。只造tiny DuckDB/JSON，不能读生产库/旧大库，不能外呼行情/模型/API，不能改8792/L2/索引/夜跑配置或读取密钥。审核用模型传输由外层harness管理；你不得发应用模型测试。若sandbox/依赖阻塞，如实报告，不能提升权限或降低门。

在约8分钟内完成有界审查：静态逐要求对应 + 最小独立动态复核（不跑全仓/前端）。如撤保护只能在外部副本，禁止修改候选。记录命令、rc、精确分母、首尾身份、关键证据哈希。输出 /Users/a77/.finance-runtime/reviews/research-closeout-resume-20260920/nightly-independent/spec-k3/REPORT.md，最后回复同一报告要点。结论 PASS / CHANGES_REQUESTED / BLOCKED，发现逐条源码位置+证据；不把作者测试当本次独立实跑，不给main/生产签字。先Spec通过才会另派Quality。
