# 2026-08-14 质检闸门撞 duckdb 写锁 — 已合 main

PR [#343](https://github.com/linxiaoqi5111-del/finance-workspace-private/pull/343) 已合入 `main`（merge `195d88d6`，修复提交 `fa369c81`）。**夜跑链路已生效**（该脚本由 launchd 从主仓工作树跑，主仓工作树含此提交）；与 8792 无关。

## 做了什么

`check_daily_review_data.py` 的只读连接撞上 backfill 持有的写锁时，在 `db.connect()` 处裸 traceback 退 rc=1，外层 `nightly_full_review.sh` 把它播报成「数据不完整 / L2 质量门未通过」——**检查根本没执行，却引导人去补数**。

- `market_feature_store/db.py`：新增 `DatabaseLockedError`、`is_lock_conflict()`、`connect_read_only_with_retry()`。只对锁冲突（"Could not set lock" / "Conflicting lock"）重试，其它 IOException 原样抛。
- `check_daily_review_data.py`：`check_data` / `check_l2` 走重试（默认 13 次 × 10s ≈ 2 分钟，env 可调）；穷尽后打 `RESULT: BLOCKED` 退 rc=3，与 0=COMPLETE、1/2=INCOMPLETE 分流。
- `nightly_full_review.sh`：三个闸门调用点区分 rc=3，播报「闸门没跑成（写锁占用，非缺数）」。

## 验证

- `tests/test_review_gate_lock_retry.py` 4 例；全量 `tests/` 495 通过。
- 真锁演练：另一进程持写锁 → 3×2s 窗口后 rc=3 + BLOCKED（命中真实 duckdb 报错文本）；放锁后正常判定。

## 遗留

- 归因更正已记在卡里：8-13 18:30 的失败是 fupanhui 登录 preflight（rc=3），写锁崩溃发生在之后的手动补跑；此前 `2026-08-14-continuous-perspective-injection.md` 把两者并成「双因」是错的。
- limit-heat 空返回是上游未发布时的 loud-fail 设计，finalize 守卫本就会拦，**评估后不加重试**。
- 程序化调用方（run_review_sync same-day-gate、daily_review 工作流）把非 0 一律当 fail，行为安全不变；但没有调用方单独识别 rc=3，BLOCKED 与 INCOMPLETE 在它们眼里仍是一回事。
