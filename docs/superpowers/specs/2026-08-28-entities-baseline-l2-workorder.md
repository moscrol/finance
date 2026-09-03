# 工单：Entities baseline（L2）回填——重建队列 + 首批消化（P1）

- 状态：**已执行（树 `/Users/a77/kb-wt-baseline-rebuild-0828`，分支 `baseline/rebuild-queue-0828` @ `a2df431f`；P0 + orphan P1/P2 已消化，P3 八家游标；未合 main）**
- 目标仓：`/Users/a77/knowledge-base-private`
- 来源：2026-08-28 欠账盘点。用户确认 entities baseline 未补齐。
- 优先级：**P1**

## 0. 一句话

磁盘上的 baseline 回填队列（644 条）已过期——现场重建实测只剩约 108 条；先重建队列拿真实欠账数，再按 P0/P1 分批消化，另有 orphan code 队列 69 条 pending（P1 6 家）。

## 1. 证据

- 主队列：`wiki/raw/ifind-baseline/baseline-backfill-queue.json`（+ `.md`）。磁盘版 644 条（P0 188 / P1 157 / P3 299），2026-08-28 现场重建得约 108 条——**磁盘数是旧的，以重建后为准**。
- 生成器：`scripts/build_baseline_backfill_queue.py`，读 `relations/entity_exposures.json`。⚠ **无 argparse，一跑即覆盖写盘**，跑前先 `git status` 确认队列文件干净。
- orphan code 队列：`wiki/raw/theme-radar/orphan-code-baseline-queue.json`，69 条全 `baseline_status=pending`（P1 6 / P2 13 / MANUAL 4 / P3 46）。P1 六家：东方财富、协创数据、大为股份、居然智家、环旭电子、远光软件。
- 历史跑批痕迹：`wiki/raw/baseline-queue/baseline-next-state.json`（停在 batch 221，`next_pending=[]`）——旧一轮已收尾，本单是新一轮。
- **边界**：全 A 缺页年报 L2 是另一条在途线（agent-memory 看板 `doing`，wave96 待合，下一批嘉益股份 301004，交接在 `<kb>/docs/handoffs/inflight/cursor-annual-r3-*.md`），**本单不碰它**，避免两条线写同一批实体页。

## 2. 范围

**做**：① 重建主队列；② 消化 P0 全部 + orphan P1 六家（如重建后 P0 量大，先做前 3-5 批并在交接里留游标）；③ 每批 3-5 家。

**不做**：不动年报 wave 线的实体页；不给缺基线的公司写占位文本；P2/P3 只留游标不展开。

## 3. 步骤

1. 开工自查：`git status --short && git branch --show-current && git worktree list`。开分支 `baseline/<批次>`。
2. 重建队列：
   ```bash
   python3 scripts/build_baseline_backfill_queue.py
   ```
   完成判据：队列文件 mtime 更新，向用户/交接报告新的总数与 P0/P1/P3 分布（不要沿用 644 这个旧数）。
3. 按优先级切批（每批 3-5 家），每家：
   - 取数源优先 iFinD / AKShare / 年报 / 公告 / 官网等真实基础资料；写入主营业务、主营产品、收入结构、毛利率、行业分类等**稳定事实**。
   - 用 `python3 scripts/ingest.py ...`（入库口径见 concept-ingest / entity-delta-ingest skill）或既有 baseline writer 路径写入；`baseline_source_type` 必须与真实来源一致（禁把 AKShare/人工核验标成 iFinD）。
   - 数据源返回超限/空/报错（如「用户使用工具已超限」）：该来源该批**立即停**，不许手工编 baseline 顶上。
   完成判据（每批）：目标实体页出现 L2 基线段、relations 里 `evidence_layer=L2`、`update_type=baseline`、来源标注真实。
4. orphan P1 六家同流程；MANUAL 4 家只登记不处理（需人工判断映射）。
5. 每批结束跑质量自查再开下一批（**不要盲跑下一批**）：抽查本批 payload、实体页、relations 各 1 份。
6. 提交：pathspec 只提本批文件；批间 commit，方便中断回滚。

## 4. 验收

1. 队列文件为重建后版本，且已消化条目在队列/状态里可辨识（游标明确）。
2. 抽查任意 2 家：实体页 L2 段、relations 记录、来源标注三者一致。
3. 交接写明：新队列总数、已消化数、下一批游标、遇到的源超限情况。

## 5. 红线

- baseline 只写稳定事实；短期催化、新闻、研报判断、unsupported `core` 一律不进 baseline。
- 弱映射统一 `弱相关，待验证`，不硬编产业链角色。
- 429/超限即停批。
- 禁 `git add -A`；不合 main 不推。
