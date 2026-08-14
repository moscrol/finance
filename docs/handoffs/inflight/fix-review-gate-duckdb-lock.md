# fix: 质检闸门撞 duckdb 写锁——有界重试 + 如实报 BLOCKED

日期：2026-08-14 ｜ 分支：fix/review-gate-lock-retry ｜ 状态：PR 待合

## 事故现场（为什么改）

2026-08-13 夜间链路两件事叠在一起，暴露了同一个缺陷：

1. 18:30 sync 段 rc=3 失败，原因是 preflight 检测到 fupanhui 未登录（CDP
   会话问题，环境瞬时故障，非本次修复对象）。
2. 手动补跑期间，backfill 进程（当时 PID 62525）持有
   `market_feature_store.duckdb` 写锁；`check_daily_review_data.py` 的只读
   连接在 `db.connect()` 处当场抛 `duckdb.IOException: Could not set lock`，
   裸 traceback 退出 rc=1。外层 `nightly_full_review.sh` 把它播报成
   「数据不完整 / L2 质量门未通过」——**检查根本没执行**，却引导人去补数。

注意：此前归档交接（2026-08-14-continuous-perspective-injection.md）把 8-13
夜间失败归因为「limit-distribution 空返回 + 写锁」双因，经核对日志修正：
18:30 的失败是 fupanhui 登录 preflight；limit-heat 空返回与写锁崩溃发生在
之后的手动 all 段补跑中。limit-heat 空返回是上游未发布时的 loud-fail 设计，
finalize 守卫本来就会拦，不加盲目重试（评估后不改）。

## 改了什么

- `market_feature_store/db.py`
  - 新增 `DatabaseLockedError`、`is_lock_conflict()`、
    `connect_read_only_with_retry(attempts, delay_seconds, opener, sleep)`。
  - 只对锁冲突（消息含 "Could not set lock" / "Conflicting lock"）重试；
    其他 IOException 原样抛出。`opener` 可注入，保住既有测试对
    `check_daily_review_data.connect` 的 monkeypatch 路径。
- `scripts/check_daily_review_data.py`
  - `check_data` / `check_l2` 改走 `_connect_read_only()`（默认 13 次 × 10s
    ≈ 2 分钟窗口；`REVIEW_GATE_LOCK_ATTEMPTS` / `REVIEW_GATE_LOCK_DELAY_SECONDS`
    可调）。
  - 重试穷尽：打印 `RESULT: BLOCKED` + 处置指引，退出码 3（`EXIT_BLOCKED`）。
    与 0=COMPLETE、1/2=INCOMPLETE 分流；程序化调用方（run_review_sync
    same-day-gate、daily_review 工作流）把非 0 一律当 fail，行为安全不变。
- `skills/daily-full-review/scripts/nightly_full_review.sh`
  - 三个闸门调用点（finalize 守卫 / L2 门 / 最终硬门）区分 rc=3：
    播报「闸门没跑成（写锁占用，非缺数），等写进程收工后重跑 finalize」，
    不再误导补数。

## 验证

- 单测 `tests/test_review_gate_lock_retry.py`（4 例）：锁冲突重试后成功、
  穷尽抛 `DatabaseLockedError`、非锁 IO 不重试、main() 撞锁返回 3 且输出
  BLOCKED。相邻套件 `test_sync_akshare_sw_l1_daily.py`、`test_pipeline_p0.py`
  与全量 `tests/` 495 通过（1 例失败为本机 shell 残留 env 污染，清掉后过）。
- 真锁演练：临时库 + 另一进程持写锁，`--phase data` 在 3×2s 窗口后
  rc=3 + BLOCKED（真实 duckdb 报错文本命中标记）；放锁后同一命令正常执行
  完整性判定。
- `bash -n` 通过；ruff 通过。

## 合并后的部署位

夜间任务从 `/Users/a77/finance-workspace-private`（主仓工作树）跑
`scripts/check_daily_review_data.py`。PR 合并后需把主仓工作树 ff 到 main，
当晚 18:30/20:40 任务才吃到该修复。
