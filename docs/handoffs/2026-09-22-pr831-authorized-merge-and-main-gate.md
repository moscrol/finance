# #831 授权合并与正式 main 门禁红灯

## 授权与执行范围

真实用户原话“执行”，来源 pi session `2026-09-21T12-42-38-633Z_01a0c3fd-64a8-7216-baa4-fde82fbbb078.jsonl` 的用户消息 `1f861c24`，时间 `2026-09-21T15:40:06.249Z`。前一轮明确 #831 待合并授权、#846 待独立验收，因此本轮执行范围仅为合并 #831；不部署、不重启、不合 #846、不删源分支或任何工作树。

先 fetch，确认 base `028a251a1b2ca98245326a6b59376f4f7f8e5e81`、head `ea5c3a94618a15e37f914c8b1a13e271875e4337` 未漂移，merge-tree 无冲突，预览树 `c4ebdbd4d725a73588fe5990cedfc47a9702c265` 与已验候选 d97fdf77 相同；原候选收据校验通过。原独立 PASS_WITH_LIMITS 的范围不扩大，详见昨日快照。

首次合并忘了先解除标题 WIP，被 Gitea HTTP405 拒绝，未生效。原失败 `~/.finance-runtime/reviews/831-merge-gate-20260921/merge-record.json` 保留。随后用规范 guard --off 只解除 #831，确认 head 未变；再次通过 merge --expect-head/--expect-base 的完整SHA约束合并成功。成功原件 `merge-after-guard-record.json` 携带精确授权来源。PR评论5498已回读。

实际合并提交 **e82717d9a7c3dfa811a4538bd44985b61258355a**，双亲就是上述 base/head，main 指向该提交，实际 tree 与预览/候选相同。#831 已 merged，不把随后红灯回写成“未合”。#846 仍 WIP，无独立结论。

## 为什么另跑正式 main

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 用 d97fdf77 全量直接认证 main SHA | 文件树虽相同，提交身份不相同；违反正式 main 收据规则 | 否决 |
| 固定正式提交在独占树重跑全部叶子 | 成本较高，但收据确实属于已合版本 | 执行 |
| 为测试/工具补丁切生产到最新 main | main 含已回滚 K3，此补丁无需重启生产 | 否决 |

在 `~/fwp-wt-831-main-gate-0921` detached e82717d9 执行；干净env、umask022、唯一项目venv。复用昨日运行器，只变目标树和REV，前端规范runner来自 #846 作者树，记录其哈希。证据根 **`~/.finance-runtime/reviews/831-postmerge-main-20260921/`**。原 d97fdf77 候选与收据全部保留。

## 正式 main 结果：RED

- Ruff exit0；registry 五项 exit0，warning 不抹去。
- 前端 install/lint/typecheck/test/build/test:e2e 六项exit0；110单测、E2E34P/2S；complete/identity_stable=true、dirty=false。测试端口19881/19884已关闭。
- **完整pytest exit1：12509 passed / 1 failed / 85 skipped / 2 xfailed / 17 warnings，1416.56秒。** 首尾SHA/tree相同且clean。
- 失败：`intelligence/tests/test_conversation_orchestrator.py::test_ask_watchdog_returns_partial_and_suppresses_late_progress`，6342行 `worker_started.is_set()` 为False。
- 原生收据 `~/.finance-runtime/test-receipts/20260921T160947Z-e82717d9.json`，dirty=false、worktree_dirty_total=0、exit_status=1，依赖指纹3328bed61f3e21ea、Python3.12.13。
- `check_test_receipt.py` 完整SHA与base-drift-max0校验exit0；它认证的是来源与环境，**不认证测试全绿**，正文明确列出1失败。日志 `receipt-provenance-check.log`。
- `audit_evidence.py`/`evidence-audit.json` 对13份逐项日志哈希、JUnit、原生收据交叉核验；JUnit12597用例、1failure、0error、85skip+2xfail。汇总明确 `full_gate=RED`。

## 有界分诊，不用复跑涂绿

同一干净SHA无修改单例复跑 **1P/1.16秒**，收据 `20260921T161125Z-e82717d9.json`；所在完整模块复跑 **104P/8.47秒**，收据 `20260921T161251Z-e82717d9.json`。两次日志/JUnit均留证据根，均不能替换全量红灯或相加成12510P。

该测试用整轮0.2秒预算，又断言回答worker已启动；生产watchdog会在根deadline已经到期时不启动worker而返回partial。调度/前置耗时是待验证解释，不是已证根因。全量失败tmp_path `/private/tmp/pytest-of-a77/pytest-1547/test_ask_watchdog_returns_part0` 在检查时已不存在，原因未确认，本轮未清理；无法恢复原trace证明是否走了worker_started=false的早退。测试和runtime文件相对合前base零差异，也不能证明所有集成交互都无关。

历史 `fwp-wt-runtime-closeout-0921/docs/handoffs/2026-09-21-8792-switch-adcda94b5e40.md` 记录过同用例失败，旧新两树加压各6/6通过，原作者归为负载敏感；本轮仅把它作为线索，**未复现不等于证实负载因果**。没有放宽超时、删测试、改生产或反复全量凑绿。PR评论5505已完整记录并回读。

## 生产观察单独记账

23:46:37 health HTTP200、adcda94b5e40 recovery、source_dirty=false、code_matches_repo=true。本轮readiness两次分别15秒/30秒均0字节超时，curl28、无HTTP状态；不继续重试，不把23:22历史503（DB09-18/快照09-21）说成当前结果。`production-observation.json`区分历史与本轮观测。错误日志末尾是更早受损快照maintenance_launch异常及恢复PID3095启动成功，不能解释当前超时。

没有新真实问答、部署、重启、切链或行情写入；没有碰其他agent的测试。门禁进程均已结束。磁盘曾低至3.8GiB，后观察回升，不推断何人清理；本轮未删除任何树或缓存。

## 后续与禁止事项

1. #831合并已完成，但正式main发布门禁未通过。继续发布或下一批合流前先处理该红灯，不能只挑两次复跑绿报告。
2. 后续用树外持久basetemp保留失败trace，先复现/定位时序假设，再决定是否修测试的同步或生产逻辑；不直接加大时间帽掩盖问题。此次全量缺现场的限制永久保留。
3. #846仍需独立验收；当前新main基线令旧工程结果更不能冒称当前合流全绿。本轮不再调用模型审核、不解除其WIP。
4. readiness当前超时与历史行情日期差由生产/数据归属另查，未经定位不重启、不补数据凑绿。最新main含K3限制仍在。
5. 原失败/成功合并记录、两个候选树、正式main树、恢复/事故树及外部收据全部保留。本轮只复用门禁，没有新通用抽象；不动有他人修改的harness-reference。
