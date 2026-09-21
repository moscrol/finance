# 独立 Spec 审核报告 — R1（恢复刷新完成性）+ I1（main 合流门控）

## 结论：PASS

仅签新片 R1 + main 合流 I1，不签原夜跑全部实现、不签 R2、不给 main/生产签字。

## 身份与边界（首尾核一致）

- 候选：`/Users/a77/.finance-runtime/reviews/research-closeout-resume-20260920/nightly-independent/spec-tree`
- 首核 HEAD=`d95b706edc6e44f3dfa54d7b8837dfdd36b16cf2`，`git status --porcelain` 空；尾核同一 HEAD、同一空状态。候选源码零改动（含 code-map 生成物）。
- 主差分 `git diff 34f49ce1...HEAD`：5 文件（`market_feature_store/cli.py` +8、`market_feature_store/sync/sync_local_sector_members.py` +11、`scripts/recover_local_review.py` +6/-1、`tests/test_stitch_refresh_completion.py` +127、`tests/test_recovery_refresh_integration.py` +205）。
- 合流背景 `git diff e51c5157...HEAD` 中本片相关源码：上述 3 文件 + `skills/daily-full-review/scripts/run_review_sync.py`（index-daily 加 `--no-fupanhui-fallback`）+ `market_feature_store/sync/sync_akshare_index_daily.py`（`allow_fupanhui_fallback` 闸）。
- 写入仅落在 spec-k3（probe_a_stitch.py / probe_b_child.py / *.log / 本报告）与 /tmp 临时目录（自动清理）。未读生产库/旧大库，未外呼行情/模型/API，未动 8792/L2/索引/夜跑配置，未读密钥。
- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（3.12.13，duckdb 1.5.4，pytest 8.3.5），白名单 env。

## 逐要求静态对应（源码位置）

1. **`--include-completed` 强制 + 旧 audit 不替本轮**：`scripts/recover_local_review.py:76-82` `recovery_stitch_command` 固定带 `--include-completed --max-baseline-age-days 180`（history_day 追加 `--no-caps`）。`sync_local_sector_members.py:482-490` 新增 `refresh_complete` 键：`not dry_run and stitched==candidates and not skipped and not failed and pending_for_provider==0 and audit is not None and audit.complete`，仅 `include_completed` 时非 None。`cli.py:702-709`：`--include-completed` 时 `refresh_complete is not True` → 打印「刷新未完成」并 `return 2`。既有返回键 candidates/stitched/skipped/failed/pending_for_provider 全部保留（`:468-481`）。
2. **重用摘要、责任边界**：`refresh_complete` 是既有 summary 字典的派生键，无第二份 freshness 台账；`completion_audit`（`sector_universe.py:958-`）全 SELECT 只读、fail-closed，审计历史不改；恢复基线 180 日硬编码在恢复命令，生产 `DEFAULT_MAX_BASELINE_AGE_DAYS=10`（`:58`）未动；基线只取窗口内最近 fupanhui 名单（`_baselines`），无未经验证名单替补。普通日更不带 `--include-completed`（`run_review_sync.py:407-411`），skip→provider 补齐合同维持；dry-run 时 CLI 返回 0 但打印「刷新预览：未写入，不认证本轮刷新完成」且 `refresh_complete` 恒 False。
3. **空候选**：`pending_for_provider = len(changed)+len(new)+skipped+len(failed)`（`:465`），0==0 之外还要求无 changed/new、无 skip/fail、审计完整；任一不满足 → rc=2。
4. **child 消费失败不认证**：`recover_local_review.py:126-130` 非 ok 且非可选 skip → 立即 `RuntimeError('...no publish')`，status.json（含 `MARKET_FEATURE_STORE_RUN_ID`）只在全部门禁+对齐通过后 `:145-147` 写出；staging publisher 既有保护保留（`sync_daily_full.py`：开工删旧 status、无 status/非本 run_id/rc∉{0,1} 均不换名；child 抛异常时无 status.json → 必拒发）。
5. **I1 合流**：`optional_skip = name in sync.HITHINK_STEPS and result['status'] == 'skip'`（`:128`）——仅计划明示的四步缺 key skip 可续，原 skip 收据（code=None、note「未更新」）在 append 后原样保留；必需步骤 skip、Hithink fail/timeout（`run_step` 映射非 0 rc→fail、TimeoutExpired→timeout）、质量门失败（`:135-139`）均阻断。`HITHINK_STEPS` 四步与 local 计划 index-daily `--no-fupanhui-fallback` 均在 `run_review_sync.py:357-403` 保留；`sync_akshare_index_daily.py:151-156` local/no-fupanhui-fallback 边界 raise 不降级。
6. **反例**：见下动态复核，全部独立复现。
7. **R2 边界**：两个差分均未触 `qa_backfill_align.py`，日期门未删；未要求本片修跨午夜归档回放。真实无人值守与生产回填未授权，不在本次签字范围。

## 独立动态复核（非作者测试抄件；fixture 自建、板块代码/日期/数值自取）

探针 A（`probe_a_stitch.py`，内存 DuckDB + 生产 API 自建 fixture：D1=2026-03-01/D2=2026-09-17 相隔 200 天，2 板块，旧 stitch 成功行 price=10，当日真值 000001.SZ=12）：**27/27 PASS**，rc=0。要点：

- 180 日窗 + 过期基线 → rc=2、`refresh_complete=False`、skipped={no_baseline:2}、旧值 10 保持、`audit_complete=True` 不被改写（反例核心）。
- 365 日窗（仅 fixture 对照）→ rc=0、`refresh_complete=True`、值真改写为 12；生产规则未改。
- dry-run → rc=0 但不认证、不写入、消息含「不认证」。
- 普通日更（无 --include-completed）→ rc=0、`refresh_complete=None`、`pending_for_provider=2` 维持。
- 空候选四组合：仅「无 pending + 审计完整」rc=0；changed/new pending 或审计不完整均 rc=2。
- writer 失败 → rc=2、failed 列表在案；恢复命令含 `--include-completed`+180，`--no-caps` 仅 history_day。

探针 B（`probe_b_child.py`，真实 `recovery.child` 控制流 + 真实 `build_local_plan`/`sync_hithink_step` + 自有 tiny staging 库与 JSONL/JSON，run_step/run_release_steps/write_runlog 为 recording stub）：**18/18 PASS**，rc=0。要点：

- 全 ok → 写本 run_id（probe-run-42）成功状态；stitch 子命令实捕 argv 含 `--include-completed`+`180`；index-daily 实捕 argv 含 `--no-fupanhui-fallback`。
- 四 Hithink 缺 key → rc=0，8 张 skip 收据原样（code=None、note 含「未更新」），未起子进程。
- 必需步骤 skip（index-daily）、stitch fail、Hithink fail/timeout、质量门 fail → 全部 RuntimeError「no publish」、status.json 不存在；stitch 失败后无任何下游派生调用（sector-daily-local/same-day-gate 未调用）。

作者新增测试独立复跑（不作为本次结论来源，仅佐证）：`pytest tests/test_stitch_refresh_completion.py tests/test_recovery_refresh_integration.py -q` → **29 passed**（分母 17+12）。`ruff check` 5 个改动文件 → All checks passed。

## 命令与证据

| 命令（均白名单 env） | rc |
|---|---|
| `pytest tests/test_stitch_refresh_completion.py tests/test_recovery_refresh_integration.py -q` | 0（29 passed） |
| `python spec-k3/probe_a_stitch.py`（PYTHONPATH=候选） | 0（27/27） |
| `python spec-k3/probe_b_child.py` | 0（18/18） |
| `ruff check <5 改动文件>` | 0 |

sha256：差分 34f49ce1...HEAD = `66d4230e…151be`；I1 相关 5 文件合流差分 = `6f1608c1…e632`；probe_a_stitch.py = `cc44cd89…bb22f`，probe_b_child.py = `86380eda…1adc4`，probe_a.log = `416ba860…9076c9`，probe_b.log = `2279bca5…f43583`。

## 备注（非缺陷）

- dry-run + `--include-completed` 返回 rc=0 是规格明示允许的预览语义（消息明示不认证；恢复链路从不传 `--dry-run`）。
- child 抛 RuntimeError 时进程 rc=1，publisher 原则上允许 rc=1 换名，但「无 status.json 必拒发 + run_id 绑定 + 开工删旧 status」三重保护使失败恢复无法发布——既有机制，本片未削弱。

Spec 通过；Quality 审核另派。
