# Workbench 报告发布测试隔离 · 2026-09-23

## 背景

#883 记录的主干快照 `9a0227986` 全量为 14567P/1F/85S/2X。失败用例 `test_real_turn_terminal_claim_does_not_publish_an_incomplete_artifact_list` 等到了 report 写入屏障，却读到当前 run 仍为 queued；单独复跑通过。本轮在 `gitea/main@5f35da172` 新建独立分支定位，不修改 #883 的历史失败结论，不接入 claim-scope 运行时。

## 发现顺序

1. 最新基座与旧失败快照的 `app.py`、`run_store.py`、`conversation_orchestrator.py` 及失败测试逐字相同。RunStore 的元数据写入已有按 run 的锁，终态保护也存在，不能凭一个 queued 读数推断终态被回滚。
2. 测试把 `RunStore.add_artifact` 整个类替换了，只认文件名 `report.json`。`reached` 因此表示“任何任务开始写报告”，不是“本次任务已到发布阶段”。
3. 原始全量现场中，前面的 `test_sse_rejects_negative_after` 通过 POST 启动了真实回答：default 用户任务 `run_20260923_121637_707571` 在 12:17:00 写报告；失败目标 alice 任务 `run_20260923_121700_364664` 的报告在 12:17:01 写出。执行器 shutdown 使用 wait=False，已运行的 worker 可继续收尾。这支持跨用例干扰解释，但原现场没有记录唤醒屏障的 run_id，时间关联不冒充完整调用轨迹。
4. 给原用例增加确定性干扰：当前 worker 尚未 mark_running 时，先让另一存储实例写同名报告。不改原屏障的红对照为 **1P/1F**，失败精确为 queued != completed；无需制造机器高负载或加 sleep。
5. 修复只在测试：本次提交入队前，对传入的存储实例安装屏障，再核对 artifact_run_id；不再替换整个 RunStore 类。干扰报告必须正常落盘，当前任务仍要满足 completed、publication pending、report 尚未登记，释放后才变为 published。
6. 负数游标校验改用已落盘的完成态 run，不启动无关回答。保留 HTTP 422 断言，不改变产品行为。

## 选择与否决

| 方案 | 结果与理由 |
|---|---|
| 增加等待时长或轮询直到 completed | 不采用：可能掩盖屏障认错任务，原故障不是十秒等待超时 |
| 修改生产状态机或让 shutdown 等全部 worker | 不采用：尚无状态回退证据，且会改变取消、停机和阻塞 worker 的产品语义 |
| 只取消前一个测试的后台任务 | 不作为唯一修复：其他在途 worker 仍可能误触全局屏障 |
| 实例与 run_id 双重限定，加确定性干扰回归 | 采用：直接约束测试真正要观察的对象，保持原交付断言强度 |

## 已执行验证与原件

证据根 `~/.finance-runtime/reviews/run-queued-regression-20260923/`。

- `red.log` / `red-junit.xml`：旧全局屏障在新增干扰场景下稳定检出同型失败，1P/1F。
- `green.log` / `green-junit.xml`：修复后正常、干扰及负数游标三场景 3P。
- `modules.log` / `modules-junit.xml`：两个相关文件完整执行 144P；这是定向范围，不是整仓收据。
- Ruff 与提交前检查通过。实现提交 `833f4448d` 只改两个测试文件，未改生产 Python、前端或配置。
- 固定最终候选的完整门禁原件统一放 `gates/`：`runner.log`、`python.log`、`receipts/gate-*/pytest.json`、`frontend/frontend.json` 与 registry 分项日志。实际结果以这些原件和 PR 验证记录为准；检查 revision、clean、full scope 及每片叶子，缺失或失败均不算通过。本快照不预填尚未产生的全量数字。

## 后续与边界

核对本分支确切候选门禁，获得合入确认后再合；#883 文档分支另行处理。旧全量失败留存，不把本轮定向绿拼接成旧主干全绿。本轮不执行 #75 K3 独审、#76 真实模型验收、运行时接入或生产部署。

可迁移结论：异步测试的事件必须绑定被测对象身份；全局方法替换加“同名文件”不是身份。回归用受控执行顺序验证，优于扩大超时。复用现有 pytest 事件与门禁脚本，不新增通用并发框架。
