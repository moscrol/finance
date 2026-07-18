# Workbench P0.5 Runtime and Readiness Implementation Plan

**目标：** 消除 owner stage 超时后的“幽灵线程”，并让 market snapshot 的结构、质量与 readiness 使用同一份判定。

**执行方式：** 用户已选择当前任务内联执行；继续采用 TDD。

## 技术取舍

Python 线程不能被安全强杀，`future.cancel()` 也不能取消已经运行的线程。现有实现返回
timeout 后 `adapter.execute` 仍在后台继续，是错误的结构化并发语义。

本批采用两层边界：

1. Owner DAG 不再创建可被遗弃的单线程 executor；stage 与父调用同步 join，超过预算则丢弃结果并记录 timeout，保证返回时没有后台 stage。
2. 网络、RAG CLI 等真正可能阻塞的工作继续由已有 HTTP/subprocess timeout 终止；P1 常驻 worker 再提供可重启的独立进程硬边界。

替代方案是 `multiprocessing` 强杀，但现有 adapter 是捕获 `self/options/context` 的嵌套闭包，
不能可靠 spawn/pickle；在多线程 Web 服务里强制 fork 也不安全。因此本批先修复“提前返回但任务仍跑”的确定性 bug，不伪称能安全杀任意 Python 函数。

快照侧采用 `contract result.ready` 单一来源：目录存在不等于数据可用；只有结构通过、
`quality=complete` 且 freshness 合法才 ready。`partial` 可保存用于降级展示，但不能进入关键 readiness。

## Task 1：Owner stage 结构化超时

**文件：**

- 修改：`intelligence/workbench_skills/owner_dag.py`
- 修改：`intelligence/tests/test_workbench_research_owner_skills.py`

步骤：

1. 新增故障注入测试：slow stage 在 timeout 后修改标记；断言 DAG 返回时修改已结束，继续等待不再变化。
2. 删除 `ThreadPoolExecutor/future.cancel()`。
3. 同步执行 adapter；若实际耗时超过 `min(stage timeout, absolute deadline)`，生成 timeout artifact，payload 写入：
   `termination_mode=joined`、`background_work_remaining=false`，不缓存超时结果。
4. 异常仍转 failed artifact；成功结果仍可缓存。
5. 运行 owner skill 聚焦测试。

## Task 2：Snapshot quality contract

**文件：**

- 修改：`intelligence/services/akshare_market_snapshot.py`
- 修改：`intelligence/services/market_snapshot_contract.py`
- 修改：`intelligence/tests/test_akshare_market_snapshot.py`
- 修改：`tests/test_market_snapshot_contract.py`

步骤：

1. 先写失败测试：partial snapshot `ready=false`；failed quality 为 FAIL；缺 quality/freshness 为 WARN 且不 ready。
2. AkShare 完整快照使用 `fresh/historical`；partial 使用 `degraded`，不再出现 `quality=partial + freshness=fresh`。
3. Contract 输出 `ready`、summary.quality、summary.freshness；规则：
   - complete + fresh/historical + 结构无错误/警告 → PASS + ready；
   - partial/degraded/字段缺失 → WARN + not ready；
   - failed → FAIL + not ready。
4. 保留 partial daily 文件和 `SnapshotSyncResult.ok=true` 的“生产完成但质量降级”语义；消费 readiness 只看 contract.ready。

## Task 3：API readiness 复用 contract

**文件：**

- 修改：`intelligence/api/app.py`
- 修改：`intelligence/tests/test_workbench_api.py`

步骤：

1. 测试空目录、partial snapshot 均返回 503；完整合法 snapshot 返回 200。
2. `dependency_checks` 保留 `market_snapshot_dir` 可观测项，新增 contract probe。
3. critical.market_snapshot 绑定 `snapshot_contract.ready`，payload 暴露精简 quality/status/date，避免前端只看到布尔值无法解释。

## Task 4：验收

运行：

```bash
python -m pytest intelligence/tests/test_workbench_research_owner_skills.py -q
python -m pytest intelligence/tests/test_akshare_market_snapshot.py tests/test_market_snapshot_contract.py intelligence/tests/test_workbench_api.py -q
python -m pytest -q
```

完成定义：

- timeout 后没有后台 stage 继续修改状态；timeout 结果不进 cache。
- partial/degraded/缺质量字段均不 ready。
- API 不再用“目录存在”代表 market snapshot ready。
- 全仓 Python、前端契约与 E2E 通过。
