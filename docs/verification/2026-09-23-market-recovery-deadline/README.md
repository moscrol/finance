# 行情恢复 QC：查询绝对截止修复与新候选门禁

结论：**HOLD**。预算正确性修复已提交，原查询超时测试在新完整门禁中通过；Python 全仓另有 4 项失败，前端完整单测另有 2 项超时。定向诊断通过不替换这两张红收据。未 push、合并、部署、执行真实恢复 staging、换库或写生产。

## 固定身份

- 修复提交：`f22cd22b63a9278ff7d631f10f9efbac1c69899d`。
- 验证候选：`5213e9344b77e4094221734722b478705611a865`。
- 基座：`626d8a508c1c988ff094110b371987e6afdcdd15`；候选 tree：`97070f9b4da710185f743e6891df9dc2c5da70ef`。
- 保留 ref：`refs/verification/market-recovery-deadline-626d8a508-20260923`。
- 原件根：`/Users/a77/.finance-runtime/reviews/market-recovery-qc-20260923/timeout-followup/`。
- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；Python 3.12.13；依赖指纹 `3328bed61f3e21ea`。
- Python 与前端分别在同 revision 的两棵干净 detached 工作树运行。它们隔离文件，不隔离共享宿主的 CPU、内存和磁盘。14:25 UTC 收据校验及 14:29 UTC 收尾观察均为基座零漂移。

## 修复与证据等级

`FinanceQuery.run` 复用 `ResearchDeadline.bounded_stage`，连接前固定绝对截止时间，保留父预算的合成预留；连接后和线程启动后重验预算与取消；监控不再从实际启动时重新计算相对时长；关闭后拒绝迟到成功。

这修的是预算不续期与结果不超窗成功，不保证操作系统实时调度，也不强行抢占阻塞的连接建立或关闭。旧候选那次约 1.105 秒失败的具体原因仍未证明；不能从本轮单次 0.037 秒推导性能提升。原 `<0.5s` 断言未改。

| 检查 | 实际结果 | 边界 |
|---|---|---|
| 最初受控时钟反例 | 旧实现 7F / 2P | 作者构造的 9 项反例，不是独立审查 |
| 最终截止/取消回归 | 14 项，包含于相关模块 151P | 固定候选再验 151P；不叠加计数 |
| 最终探针对旧候选回退 | 10 个行为失败 / 4P | 历史敏感度，不是正常版失败 |
| Python 完整门禁 | **14903P / 4F / 85S / 2XFAIL；14994 collected；0 error** | pytest 4997.85 秒，外层 5006.787 秒，exit 1；无超时或磁盘保护中断 |
| 原查询超时用例 | 完整门禁中通过，JUnit time=0.037 秒 | 单次读数，不归因旧失败 |
| Ruff、注册表五项 | 通过 | 解析、registry、文档表、views、ledger crosswalk |
| 完整前端 | install / lint / typecheck / build 通过；单测 **118P / 2F** | 两项均超过原 5000ms 测试期限 |
| E2E | **34P / 2S** | 测试入口，不是生产恢复验收 |
| 前端定向诊断 | 2P / 79S | 单文件、筛选两项、1 worker，Python 全仓当时仍在运行；不替整组红灯 |
| RAG 定向诊断 | 4P，外层 3.021 秒 | 原预热期限未改；不替 Python 全仓红灯 |
| 行情恢复旧独立探针重放 | F1 5P / F2 16P / F3 6P；作者 28 / 75 / 28P；3 阳性对照检出 | 27 探针与 131 作者测试分账；零新模型请求，不产生新审核结论 |

## 剩余失败

Python 四项全部停在 `worker.prewarm`，尚未走到各自所测的恢复、代际或保活行为：

- `intelligence/tests/test_rag_worker.py::test_recovery_respects_cooldown`：2 秒预热超时。
- `intelligence/tests/test_rag_worker.py::test_second_consecutive_timeout_kills_and_self_heals`：2 秒预热超时。
- `intelligence/tests/test_rag_worker_generation.py::test_single_bad_query_does_not_reclassify_worker_as_retired`：3 秒预热超时。
- `intelligence/tests/test_rag_worker_keepalive.py::test_close_stops_keepalive_thread`：2 秒预热超时。

前端 `src/components/components.test.tsx`：

- `keeps polling a cancelled run until its exact message publication is visible`。
- `keeps polling while completed ownership precedes delivery`。

相关 RAG 源码、三个 RAG 测试文件及整个前端相对固定 main 基座无差异。宿主高负载和换页是观察背景，不足以认定六项失败全是环境原因；一次定向通过也不能排除套件交互、进程生命周期或调度问题。未修改这些组件、预热期限或前端测试阈值。

## 读取顺序

- `files/summary.json`：全仓、前端、原超时用例及四项完整 traceback。
- `files/closeout.json`：四项诊断、源码范围对照、进程与零漂移核验。
- `files/full-gate/gate-zfvXYYlB/pytest.json`：完整范围的红收据。
- `files/receipt-check/stdout.txt`：身份、解释器、依赖、完整范围、收集对账与零漂移均通过；**checker exit 0 只表示红收据可采信，不表示测试绿**。
- `files/frontend-receipt/`、`files/frontend-two-diagnostic/`、`files/rag-diagnostic/`：完整执行与诊断分账。
- `files/recovery-replay/`、`files/recovery-replay-f3/`：原探针及沙箱执行；首次 F3 外层 120 秒中断原件保留，不计覆盖，新目录内完整执行才计数。

恢复四个核心文件与旧已审候选 `50330cf` 一致，但整个候选不等同旧版。旧 GLM 三项 `PASS_WITH_LIMITS` 仍只签旧输入；本轮未给新的截止修复做模型独审。旧审查边界见 `../2026-09-23-market-recovery-glm/README.md`。

## 封存与清理

`manifest.json` 覆盖 129 个成员，连同自身共 130 个机器归档文件；`raw-manifest.json` 记录 129 个原件。机器清单不包含本 README 或交接。原件中的完整 JUnit XML 超过归档大小阈值，仅保留原路径与哈希；本目录保存完整失败 testcase 和原超时 testcase 摘录。脚本、日志和沙箱配置以 `.txt` 后缀封存，避免被仓库测试或 lint 当作产品代码。

候选树、验证 refs、全仓失败 scratch 和诊断 scratch 保留。所有本轮测试/审核执行进程已结束。前端 `node_modules` 已确认不存在；清理脚本随后因误猜 `.next` 被 ignore 检查拒绝，原失败与部分状态保留，真实 Vite 输出 `intelligence/api/static` 未删。宿主空闲空间回升不归功于本轮清理。

可选整图审计的控制器被宿主 80 秒期限截断；退出码未知，不计整图通过。其进程在收尾检查前已结束，未发清理信号。见 `files/capability-graph-interruption.json`。固定候选门禁控制器与日志均未受这次辅助审计中断影响。

## 下一步与授权

先协调共享宿主压力，再分诊 RAG 启动预热和前端整组轮询；需要准入时按届时固定 revision 重跑完整失败叶子，若代码或基座改变则重新组合并跑完整门禁，不移签旧收据。五问 (a)-(e)、三合同、5553/5565 股票范围及 53 只公司行动处置仍待确认；真实 nightly、恢复 CLI、staging、换库与生产验收未执行。
