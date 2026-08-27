# 2026-08-26f · #417 fd 泄漏根治 + #418 宽度共振袋 验收合并与 8792 切换

- 验收方：QC session（独立复算，规程 `docs/workflows/acceptance-workflow.md`）；执行方交付见两张 PR 描述与 `~/.finance-runtime/boundary-probe-20260826/one-page-report.md`。
- 队列：#417 `fix/workbench-db-fd-leak`@`501defbb`（优先，生产在漏）→ #418 `feat/width-resonance-bag`@`e8024dd9`。两分支同基 `ef2d8427`、互不堆叠、merge-tree 均零冲突。

## 验收读数（非抄执行方数字）

- **#417**：红侧在 `ef2d8427` 基线树复现 2 failed（30 次 RunStore 实例化泄 61 fd）；分支绿 35 passed（hygiene+workbench_db+conversation_store，收据 `20260826T101626Z-501defbb.json`）。代码走查：全调用点 `with self._connect()` 形态，仓内非测试代码无第二处裸 `sqlite3.connect`（预注册失败形状预排除）。
- **#418**：定向 107 passed（宽度袋 9 钉 + asof_prefetch/market_watch/switchboard，收据 `20260826T101644Z-e8024dd9.json`）；9 钉与工单 §P1 一一对应；判语零输出、`sw_l1_pct` 显式 `is None` 判缺数（0.0% 不误标）、免责声明前置；开关板行与 #415 同款（登记不进臂）。
- 裁决全文在 PR 评论（#417/#418），台账见 `docs/prediction-ledger.md` 当日三行。

## 批次门禁（main tip `c0226f34`，验收树 `/Users/a77/fwp-wt-qc-0826`）

- python 叶：ruff 全过；pytest **6594 passed / 12 skipped / 0 failed**（收据 `20260826T102544Z-c0226f34.json`；对照上一门禁行 5935 只增不减）。
- frontend 叶：pnpm lint / typecheck / test 67 / build 全绿。
- e2e 叶：15 passed。⚠ 8791 被一个跑了 8 天的散装 `python -m http.server`（pid 56137）占用，走正规逃生口 `WORKBENCH_E2E_PORT=8811`；**该进程未动**，是否回收由用户定。
- registry-check：`ws/daily-full-review`、`ws/perspective-distill` 两处哈希漂移为**存量**（`ef2d8427` 同红；罪魁 `b78ae4e4` #411 收编改了 SKILL.md 未重扫），本单 `scan` 修复、check 转绿。
- data-quality-check：paths 未触发，不算数。

## 切换（链切五步）与验证

- 快照 `~/.finance-runtime/finance-workspace-c0226f34da4d`；回滚 `~/.finance-runtime/cutover-20260826f-rollback-8792.txt`（回 `fbdbbfd2`，目录保留）。首次 bootstrap 撞 launchd EIO（bootout 未沉降的已知竞态），3 秒后重试成功。
- health 三读：`c0226f34da4d` / dirty=false / match=true ×3。
- readiness **12/13**：唯一红 `market_data_consistency`（快照 08-26 vs 库 08-25）为**数据侧存量**——快照 16:15 已翻 08-26（早于 18:29 切换），夜跑 18:45 same-day gate 发现库无 08-26 板块行情后 rc=2 fail-closed（staging 未动生产库，`logs/daily-full-review.out.log`）。**与本次代码切换无关**，等夜跑重试补齐后自愈；若今晚未自愈需人工跑 daily-full。
- grounded：长电探针（`live-probe-traceability/cutover-20260826f-changdian/`）completed、站立日 08-25==库内最新、无「本轮没有连接本地市场数据」；宽度袋 6 行与 DuckDB 原表**逐位一致**（最硬 grounding）。
- 备份：`~/backups/gitea-20260826-post418.tar.gz`（2.3GB）。

## 正对照（两发全过，读数已回写台账）

- **R-20260826-03 → confirmed**：切后 fd 基线 11，10 分钟 240 次轮询 20 个采样点全程 11、增长 0、非 200=0（`cutover-20260826f-8792/fd-curve.log`）。自然对照：切换前旧码被 UI 轮询 2h16m 从 14 灌回 **225/256**——不切当晚必然复撞。
- **R-20260826-02 → confirmed（带成立条件）**：双态分叉成立——有袋臂消费袋（E6）并按画像降权（「不升级为新主线」），无袋臂对 +4.89% 异动零提及；失败形状未现。成立条件：sw_l1 映射缺口（08-25 仅 119/403，top6 概念 `dim_sector`/`fact_sector_daily` 均 NULL），「概念涨×行业负」精确形状未观测，解读侧 n=1。

## 遗留 / 候选（未做，待认领或用户拍板）

1. **sw_l1 映射回填**（数据侧候选工单）：概念板块→申万一级映射覆盖 119/403，补齐后宽度袋对照价值才完全兑现；组件侧无需改动（fail-closed 行为正确）。
2. 开关板 `market.width_resonance` 行 `positive_control` 补引 R-20260826-02 回读（小改动分支：fixture+默认盒重生成+测试）。
3. B4（未注册口径 fail-closed）/B5（写请求声明只读边界）收进常驻验收题集；B3 复跑（边界报告建议 1/3）。
4. launchd plist 提 `NumberOfFiles`（纵深防御冗余，需用户点头——修复已使泄漏归零）。
5. 工单 §P0 待做：daily-full skill 完成判据加 market_snapshot 产物条款（归 daily-full 树）。
6. 主名单 600536 被排除行按 query 加权挤出（26e 遗留，动 spec 另开一轮）。
7. 夜跑 18:45 失败为上游 08-26 数据未就绪；今晚若无重试成功记录，需人工补跑并核 readiness 回 13/13。

## 本轮沉淀的可迁移件

- `with sqlite3.connect(...)` 只管事务不关连接——「事务+finally close」contextmanager 化调用点零改动，是任何 sqlite 服务的通用修法（BUILD 候选零件）。
- fd 类资源泄漏的验收正对照三件套：gc.disable 单测钉（确定性）+ 轮询曲线（live）+ 切换前旧码自然对照（机制），比单看单测绿硬一个量级。
- 「数据缺口挡住组件价值」与「组件失效」要分层记账：宽度袋 fail-closed 是对的，缺的是映射数据——结论携带成立条件，别把数据侧欠账记成代码回归。
