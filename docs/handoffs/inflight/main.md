# 在途交接 · main

更新：2026-08-13 13:40 CST · 全面审查现场取证（inflight 原写「ready」已漂）

## 这个分支做什么

生产基线。夜间修复 PR 已全部合入。无在途修 bug PR。

## 当前状态

- 8792 loaded `02028b29`（#313 合并点），LaunchAgent running，runtime **clean**。
  `/api/health` = healthy，agent ready，中转 `gpt-5.6-terra`。
- **`/api/readiness` = 503 not_ready**，唯一缺项 `rag_worker`：
  `state=failed last_error=TimeoutError active=0`，`prewarm_latency_ms=145143`
  （启动预热成功残留；查询超时杀进程后状态停住）。
- origin/main = `6d9c6328`（#314/#315 + 交接文档）。生产未切这些 SHA——
  全是测试/文档，运行时等价。不要用 Mac 开发区 `d4832797` 判生产。
- 唯一 open PR：**#307**（他人 draft，勿动）。

## 未验证 / 已知边界

- RAG 查询超时会 `_mark_failed` + 杀进程；`TimeoutError` **不回退 CLI**。
  下次查询会重生，但加载约 145s、查询窗默认 90s → **懒恢复实际走不通**，
  readiness 会一直红。要恢复现在只能 kickstart（未做，需确认）。
- R15 knevo 对照 9 wins / 2 tie / 0 WB：根因是核验合成层把已抓证据删空。
  C1 日历缺口已由 #313 在 R19 补上，对照包未重评。

## 下一步

1. **现活**：确认后 `launchctl kickstart -k` 救 RAG；不要当设计项搁置。
2. 耐久：超时后后台按 240s 预热窗重生，或 TimeoutError 回退 CLI。
3. 设计：核验合成层预算（质量最大瓶颈）、governor 升档。
4. flaky：`citations_survive_run_context_reload`（测试间泄漏，非今晚引入）。
5. 清理（需确认）：12 个 runtime worktree 留 2–3；杀 8795/8796/8801
   （8/5–8/6 起的旧 uvicorn）。

## 踩过的坑

- health 绿 ≠ readiness 绿。inflight 写 ready 必须打 `/api/readiness` 正文。
- 预热 240s、查询 90s：杀进程后懒恢复会二次超时，不是「等下次查询就好」。

## 已验证

- R20 A 组 10/10 completed、9/10 无降级、0 零证据（A3=13）。
- R19 C1 休市披露通过。R14 #306、R16 #308、R17 #312 路由通过。
- #314/#315 已合；双端真产品红 0。Mac 干净读数以 runtime worktree 为准。
