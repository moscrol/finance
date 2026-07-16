# Workbench P0.5 Runtime and Readiness Verification

- 日期：2026-07-16
- 分支：`fix/workbench-product-maturity-p0`
- 结论：P0.5 本地验收通过；未合并 main，未部署 canonical 8792

## Runtime

移除了 Owner DAG 的 `ThreadPoolExecutor + future.cancel()`。原因是 Python 无法取消已经
运行的线程，旧实现会先返回 timeout、后台仍继续修改状态。

现在 stage 与父调用使用结构化收束：父调用返回前 stage 必须结束；超过预算的结果被丢弃、
不写 cache，timeout artifact 记录：

```json
{
  "termination_mode": "joined",
  "background_work_remaining": false
}
```

故障注入用例在 stage 结束时写入 mutation，断言 DAG 返回后继续等待不会出现第二次变化。
29 项 owner skill 测试通过。

边界说明：这修复的是“幽灵线程”，不宣称 Python 能安全强杀任意函数。HTTP 和 subprocess
继续使用各自 timeout；BGE-m3 等长任务在 P1 进入独立 worker 后，才具备进程重启式硬终止。

## Snapshot readiness

统一规则：

- `quality=complete` 且 `freshness=fresh|historical`、结构契约无警告 → ready。
- `partial/degraded`、缺 quality/freshness → WARN + not ready。
- `failed` → FAIL + not ready。

AkShare partial 快照现在写 `freshness=degraded`，不再出现
`quality=partial + freshness=fresh`。API `/api/readiness` 消费 contract.ready，目录存在但
数据不可用于决策时返回 503，并暴露 status/date/quality/freshness/错误原因。

## 验证

```text
P0.5 snapshot/API focused: 77 passed
Owner focused: 29 passed
Full Python: 1802 passed, 1 skipped
Playwright E2E: 15 passed（desktop/tablet/mobile）
```

结论只覆盖 P0.5；常驻 RAG worker、AkShare 独立 venv/定时生产仍属于 P1。
