# 能力整包集成 · 验收记录（滚动）

> Spec：`docs/superpowers/specs/2026-09-09-capability-integration-and-live-research-design.md`
> 进度台账：`docs/superpowers/plans/2026-09-09-capability-integration/PROGRESS.md`
> 本文件只记「跑过的命令 + 返回码 + 原件路径」，不复述计划。

## I1 · 00 污染归因（2026-09-09 22:15，工程+真实重审完成）

**提交**：`feat/i1-availability-attribution` @ 01de7e94（基于 `baseline/capability-benchmark-00` b044b61c；已推 gitea）。改动面：`intelligence/eval/capability_benchmark.py`、`intelligence/tests/test_capability_benchmark.py`。题面、密封判分点、评分权重、通过阈值未动（题库指纹不变：questions `d987df999f866873`、sealed-manifest `4ef1fd08f5db09cf`）。

**判据**（spec §I1 四行表的实现）：episode 事件链上游失败证据（`model_error` / `repair_model_retry` / `model_turn` 带 `error`）+ 最终有效回答（`outcome.draft` 非空）联合分类 → `clean` / `recovered`（接受，保留失败与耗时记录）/ `unavailable_final`（隔离，允许按原条件续跑，不因 stop_reason 改名漏掉）/ `product_failure`（接受并判败，不许重跑洗分）。判官不可用/降级逐轮明示（`judge_status`、`exc_class`、实际 `served_models`；`exc_class=None` 照样列出）。resume 与 review-pack 共用 `case_service_isolated`（有 run 目录现读 episode 权威面，读不到退回旧 `quota_tainted` 标记）。所有尝试计入 `summary.availability_class` 与 `attempts` 分母。

**红→绿**：

```
# 旧实现（git stash 后）：6 failed, 17 passed
# 新实现：
cd /Users/a77/fwp-wt-i1-attribution
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_capability_benchmark.py -q      # → 23 passed, rc=0
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check \
  intelligence/eval/capability_benchmark.py intelligence/tests/test_capability_benchmark.py  # → 0
```

**真实原件重审**（reclassify 派生新报告，旧件只读保留；派生件目录 `~/.finance-runtime/capability-integration/i1/`）：

```
python -m intelligence.eval.capability_benchmark reclassify --artifact <旧件> --output <派生件>   # rc=0 ×3
```

| 旧件（`~/.finance-runtime/capability-benchmark-00/runs/`） | 存档口径 | 重审四类 | 变化 |
|---|---|---|---|
| `20260909T125222Z-cb00-baseline-372d047c0b0f.json`（20:53） | completed 6（含 tainted 1）+ skipped 24 | recovered 2 + unavailable_final 4 + skipped 24 | **calc-01 / material-01 / material-02 由「干净」翻隔离**（同为 `model_turn_error=LLM 调用 HTTP 502`、draft=0、终态 `invalid_repair_finish` 类改名）；feel-01/02 为真实恢复样本（中途 502、终稿 900+ 字），保留失败记录照常评审 |
| `20260909T103255Z-…​.json`（18:33） | tainted 1（feel-01） | unavailable_final 1（一致，无翻转） | 判官不可用 1 轮明示 |
| `20260909T080447Z-…a6a7c10e.quota-tainted.json`（16:04 废件） | tainted 25 + engine_missing 4 | unavailable_final 22 + unclassified_no_episode 4（run 目录已被移走，退回旧标）+ engine_missing 4 | **calc-01 在废件里同形漏标**（changed=[cb00-calc-01]）；判官不可用 27 轮明示 |

**spec 四类反例逐条对账**：calc-01 漏判（真实 `run_20260909_205227_971715`）→ 单测 `test_renamed_terminal_failure_…` + 上表两件实锤；恢复成功 feel 样本 → `test_recovered_case_…` + 20:53 件 feel-01/02；真实产品失败对照 → `test_product_failure_without_service_excuse_…`（空稿无服务借口→照常判败）；判官不可用 → `test_reclassify_…` 的 judge_flags（exc_class=None 也列）+ 真件 27 轮明示。

**移交（→00 车道）**：当前在跑的 cb00-baseline 批次链上带着上述 3 题假干净；批次停下后下一次 `--resume` 用 01de7e94 代码跑（新判据不搬假干净题、按原条件重跑），最终基线件再 reclassify 归档。见 BLOCKED W5。

## I5 · 方法日程实际开始运行（2026-09-09 22:36，工程完成+生产接线验证）

**改动面**：
- `scripts/method_validation.py`：两个中断恢复点（spec I5 必须实测的①②）。
  - ① `_capture_once`：`already_captured` 分支原本直接 `return {…checkpoint: None}`，capture 落盘但 checkpoint 未登记时重跑**永不补登**、也从不暴露「无信号」与「漏登记」的区别。改为并入同一登记段：沿原观察（不改 capture 文件、不改 `captured_at`）做幂等 `register_observation_checkpoint`，补出**唯一**登记；无信号仍只留 capture 记录。
  - ② `cmd_daily` 的 recheck 已结算集：`data_insufficient`（可恢复的补数缺口）不再被当作终态永久列为「已结算」；本次重建把旁路库推到新水位时，**沿同一观察再次回检**（旧不足记录与 unverifiable verdict 保留在案）。`pending`/`supported`/`method_error`/`stage_not_applicable`/`no_signal`/`environment_change` 仍按终态处理。
- `skills/daily-full-review/scripts/nightly_full_review.sh`（规范源，已 `cp` 到部署 `~/.local/bin/`，diff 一致；旧件备份 `~/.local/bin/nightly_full_review.sh.bak-pre-i5-20260909`）：新增 `run_method_flywheel` / `skip_method_flywheel`，仅在**最终硬门通过后**跑 `method_validation.py daily`（数据到位才动作）；任一守卫/段失败夜写「原因 + 下一次既有执行机会」不做假；method 失败不断夜、nightly 退出码不变。

**红→绿**：两个新恢复点测试在旧实现上 2 failed（`git stash`），新实现 15 passed（`test_method_flywheel.py`）+ `test_method_validation_cli.py` 全绿，ruff 0。

**真实元件**（`condition_gate_shapes` 对账：主库 `max(trade_date)=2026-09-09`、labels/outcomes 同 09-09，三水位一致）。

```
# 手动接线验证（生产三元组，主检出无此脚本故用集成树脚本 + 生产 study/库）：
cd /Users/a77/fwp-wt-capability-integration
.venv/bin/python scripts/method_validation.py daily \
  --study-dir /Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/method_validation/475597e2e017a2eedd3886700cd41d394d3694eba3487e205b8ddc91723b5a2f \
  --labels-db /Users/a77/finance-workspace-private/db/history_labels.duckdb \
  --db-path /Users/a77/finance-workspace-private/db/market_feature_store.duckdb \
  --user linxiaoqi5111
# 首跑 rc=0: rebuilt=true（旁路库 09-07→09-09），capture skipped「前向起点 2026-09-10 未到」，
#   selection downgrade（历史 2 共同日：连续组 -0.56pp/-1.90pp，反证多于支持，min_n 20 不到）。
# 二跑 rc=0: rebuilt=skipped（水位已一致），capture/recheck 各按条件门 skip，幂等。
```

**七类日收据**（spec §I5）：前向起点未到（capture skipped「前向起点 2026-09-10 未到」）/ 数据落后（rebuild「旁路库水位落后主库」或「旁路库水位 ≠ 今天」）/ 未到 15:00 / 旁路库水位 ≠ 今天 / 无信号（only capture）/ 重复执行（already_captured，幂等）/ 到期缺结果（data_insufficient，恢复点②）。隔离故障只作用于测试域——验收目录 `~/.finance-runtime/cap07-users`，生产用 `--user linxiaoqi5111` 且未对生产写入。

**恢复点实测**（两个新测试覆盖，均为红→绿）：① capture 落盘 + `--no-checkpoint` 复现中断 → 重跑补齐唯一登记、capture 字节不变、`ts==captured_at`；② D+1..5 只有行情无板块 → 「数据不足」回检记录 → 水位未动不重复刷噪声 → 板块行回填 + 重建 → 沿同一观察重试 `supported/hit`，旧不足记录保留。

**尚未完成的段**：① 装入 LaunchAgent 接夜跑（本机有权装 launchd；任务书「调度安装沿原授权」——留 `--export` 单文件 + 最小登记命令，未越过授权自动启用）；② 生产首日真实 `daily` 在**主检出包含本单**后由夜跑触发（现在主检出缺 `method_validation.py`）；③ 09-17 前后首个观察结算或等 03:50 `checkpoint-recheck` 到期回检；④ I4 的八个 `.TI` 补数完成后验证恢复点②生产形状。

**下一步**（I5）：见 PROGRESS 状态表与 BLOCKED；`method-validation-daily.log` 在 `logs/`。
