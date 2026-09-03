# 工单：08-28 daily 工作流断点修复与补跑（P0）

- 状态：**已完成，待验收**（Cursor 2026-08-28 23:32；summary PASS，未 commit）
- 目标仓：`/Users/a77/finance-workspace-private`
- 来源：2026-08-28 欠账盘点。`daily` 工作流在 `export-increment` 步 FAIL，其后 15 步全 SKIP。
- 优先级：**P0**——不修它，之后每天的 theme-backfill 队列都会继续缺。

## 0. 一句话

`export_increment.py` 往 iCloud 目录写 tar.gz 时撞上 `Resource deadlock avoided`，整条 daily 工作流后半段（daily-review、theme-backfill 两队列、矩阵、kb-ingest-receive 等）被连锁跳过；修好导出后从断点补跑，补齐 08-28 的全部产物。

## 1. 证据

- `market_feature_store/exports/2026-08-28-daily-workflow-summary.json`：
  - `export-increment` FAIL，returncode 1，stderr 是 `tarfile.open(tar_path, "w:gz")` 抛错（iCloud 同步锁）。
  - 其后 15 步 status=SKIP。
- 失败路径：脚本默认 `--out-root ~/Library/Mobile Documents/com~apple~CloudDocs/duckdb-snapshots`（见 `skills/daily-full-review/scripts/export_increment.py` 第 40 行 `DEFAULT_OUT`），写 `<out-root>/increments/market_feature_store-inc-2026-08-28.tar.gz`。
- 旁证：08-26 工作流也曾 FAIL（`agent-daily`: content delta exceeds maximum size），08-27 PASS。08-26 的连锁后果由《kb-ingest 队列消化》工单处理，本单不管。

## 2. 范围

**做**：① 让 08-28 的增量导出成功落盘；② 从第一个 SKIP 步补跑到工作流结束；③ 确认 08-28 的 theme-backfill-queue / theme-backfill-review-queue 生成。

**不做**：不改 `export_increment.py` 的默认 out-root（把默认值挪出 iCloud 是产品决策，若判断确需改，单独立单给用户确认）；不重跑当日已 PASS 的前半段（daily-full 数据已全绿，六张 fact 表 max 均为 2026-08-28）；不提交任何 exports 产物。

## 3. 步骤

1. 开工自查：`git status --short && git branch --show-current && git worktree list`，逐条认领 status 行（exports/ 下大量 untracked 是正常产物，不要动）。
2. 直接重试一次导出（iCloud 锁常为瞬时）：
   ```bash
   python3 skills/daily-full-review/scripts/export_increment.py --date 2026-08-28
   ```
   仍报 deadlock 则改本地目录再手工挪回：`--out-root /tmp/duckdb-snapshots-0828`，挪回前确认 iCloud 目录可写（`touch` 探测）。
   完成判据：`<out-root>/increments/market_feature_store-inc-2026-08-28.tar.gz` 存在且 `tar -tzf` 可列出内容。
3. 从断点补跑（步骤名以 `--help` 与 summary json 里 SKIP 步骤的 `name` 字段为准，第一个 SKIP 步是 `daily-review`）：
   ```bash
   python3 -m intelligence.cli daily --date 2026-08-28 --skip-sync --from-step daily-review \
     --summary-json market_feature_store/exports/2026-08-28-daily-workflow-summary.json
   ```
   ⚠ 补跑期间不得并行跑任何写 DuckDB 的任务（单写连接约束）。
   完成判据：summary json 整体 status 不再是 FAIL；每一步要么 PASS 要么带合法理由的 SKIP。
4. 若补跑后 theme-backfill 两步仍缺产物，单独兜底：
   ```bash
   python3 scripts/build_theme_backfill_queue.py 2026-08-28
   python3 scripts/build_theme_backfill_review_queue.py 2026-08-28
   ```
5. 把新生成的 08-28 review 条目数通报给《theme-backfill 复核》工单的认领人。

## 4. 验收

1. `market_feature_store/exports/2026-08-28-theme-backfill-queue.json` 与 `2026-08-28-theme-backfill-review-queue.json` 存在且条目数 > 0（或明确记录当日无缺口）。
2. `复盘/daily/2026-08-28/` 下 daily-review html 存在。
3. summary json 无 FAIL 步。
4. 若 export-increment 只能靠本地目录绕过：在交接里写明 iCloud 死锁未根治，附报错原文，建议立单改默认路径或加重试。

## 5. 红线

- DuckDB 同一时间只有一个写入连接。
- exports 产物默认不 commit。
- 禁 `git add -A`；如需提交任何文档，用 pathspec。

## 6. 执行记录（2026-08-28 23:27–23:32）

开工：`main` @ `46d52c20`。脏树全是 `??`（工单 docs + exports/复盘产物 + 实验脚本），无已跟踪改动。DuckDB 无写入锁。`taskctl` 断链（`/opt/homebrew/bin/taskctl` → 缺失的 `codex-taskboard`），未走 taskboard。

1. **export-increment**：直接重试默认 iCloud 路径成功，未改 `DEFAULT_OUT`，未走 `/tmp` 绕过。
   - `30 表 / 121041 行` → `~/Library/Mobile Documents/com~apple~CloudDocs/duckdb-snapshots/increments/market_feature_store-inc-2026-08-28.tar.gz`（3.2 MB，`tar -tzf` 31 条）。
   - 21:11 的 `OSError: [Errno 11] Resource deadlock avoided` 是瞬时锁；23:27 起三次写入均过。**未根治**，建议另单加重试或改默认路径。
2. **第一次补跑**（`--from-step daily-review`，无 `L2_PAUSED`）：quality / cross-day / export / daily-review PASS；`daily-review-html` FAIL（L2 自 08-07 挂账，CLI 不读 `state/l2-paused.flag`）。其后 SKIP。
3. **第二次补跑**（`--from-step daily-review-html` + `L2_PAUSED=1`，对齐夜跑）：整段 PASS。`daily-review.md` 沿用第一次产物。编排器是 `.venv-workbench`，子命令 PATH 以 `/opt/homebrew/bin` 开头。
4. **theme-backfill**：全量队列 36 条；复核队列 **11** 条 `pending_review`（建/挂概念 5、映射暴露 1、挂证据 5）。已写入《theme-backfill 复核》工单。
5. **kb-ingest-receive**：8 条归档到 `wiki/raw/cross-repo-ingest-queue/2026-08-28/2026-08-28-kb-ingest-queue-2.json`（只 receive）。飞书告警 400，与产物无关。

未改 `export_increment.py` 默认路径；未重跑已绿同步段；未 commit exports。
