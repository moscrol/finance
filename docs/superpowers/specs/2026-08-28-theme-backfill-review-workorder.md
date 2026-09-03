# 工单：theme-backfill 复核 + theme-radar 质量队列消化（P1）

- 状态：**已交付待确认**（知识库分支 `theme-radar/backfill-review-0828`，交接 `wiki/raw/theme-radar/2026-08-28-backfill-review-handoff.md`）
- 目标仓：`/Users/a77/finance-workspace-private`（复核队列所在）+ `/Users/a77/knowledge-base-private`（写入落点）
- 来源：2026-08-28 欠账盘点。
- 优先级：**P1**。依赖：08-28 的 review 队列已由《08-28 工作流补跑》于 23:31 生成（11 条 `pending_review`）。

## 0. 一句话

金融仓 08-26/27/28 三天的 theme-backfill 复核队列共 29 条全部停在 `pending_review`（08-26 11 + 08-27 7 + 08-28 11；建/挂概念、映射暴露、挂证据三类动作），知识库仓另有 vertical-slice 10 条、quality 队列 52+30 条待消化——都是「人审后小步写入」型任务。

## 1. 证据

**金融仓复核队列**（人审入口，动作落到知识库仓）：
- `market_feature_store/exports/2026-08-26-theme-backfill-review-queue.json`：11 条 `pending_review`（建/挂概念 4、映射暴露 2、挂证据 5）。`.md` 版可读。
- `market_feature_store/exports/2026-08-27-theme-backfill-review-queue.json`：7 条（建/挂概念 3、挂证据 4）。
- `market_feature_store/exports/2026-08-28-theme-backfill-review-queue.json`：**11** 条 `pending_review`（建/挂概念 5：乡村振兴/粮食概念/ChatGPT概念/海峡西岸/机械设备；映射暴露 1：粮食概念；挂证据 5：乡村振兴/化工原料/粮食概念/化肥概念/AIGC概念）。上游全量队列 36 条。通报时间 2026-08-28 23:32，补跑工单已关。
- 上游全量队列（复核队列的来源，只作参考不逐条做）：08-26 43 条 / 08-27 26 条 / 08-28 36 条 `*-theme-backfill-queue.json`。

**知识库仓质量队列**：
- `wiki/raw/theme-radar/theme-vertical-slice-queue.json`：待补 10（P1 4：储能、AI基础设施与国产算力、铜、算力租赁；P2 6：硅光、超级电容、光芯片、封测、光通信、创新药）。契约：`<kb>/docs/theme-vertical-slice-contract.md`。
- `wiki/raw/theme-radar/theme-radar-quality-queue.json`：52 条全 P1（创新药 39 + 无人驾驶 13）。
- `wiki/raw/theme-radar/theme-radar-quality-queue-超级电容.json`：P1 30。
- `wiki/raw/theme-radar/concept-graph-ingest-queue.json`：候选 30（无 status 字段，视为待处理）。

## 2. 范围

**做**：① 18（+08-28 新增）条复核逐条给结论（approve → 执行写入 / reject → 记理由）；② vertical-slice P1 四个题材补齐；③ quality 队列按题材成批处理（先创新药 39）。

**不做**：不逐条消化上游 43+26 条全量队列（复核队列就是它的筛选结果）；vertical-slice P2、无人驾驶、超级电容旁路量大，本单只做到留游标；concept-graph-ingest 30 条若涉图谱批写，先出 dry-run 清单给用户过目再写。

## 3. 步骤

1. 开工自查两仓 git 状态；知识库仓开分支 `theme-radar/backfill-review-0828`。
2. 复核 18 条：逐条读 review 队列里的 action 与证据，按知识库仓对应管线执行：
   - 建/挂概念 → concept-ingest 流程（8/16 口径：过宽题材只观察不建页）。
   - 映射暴露 → entity_exposures 更新（`chain_layer`/`evidence_layer`/`strength` 齐全，弱映射标 `弱相关，待验证`）。
   - 挂证据 → evidence 索引更新，来源路径可追溯。
   每条完成后把 status 从 `pending_review` 更新为终态（approved-done / rejected-理由）。
   完成判据：两个（补跑后三个）review 队列文件里没有 `pending_review` 残留。
3. vertical-slice P1 四题材：按契约文档逐项补切片，跑 `python3 scripts/build_theme_vertical_slice_queue.py` 重建确认状态翻转为 ready/maintain。
4. quality 队列创新药 39 条：跑 `python3 scripts/audit_theme_radar_quality_queue.py` 了解判定口径，逐条修复后重跑审计确认清零；无人驾驶/超级电容留游标。
5. 提交：知识库仓 pathspec 分批 commit；金融仓 review 队列文件的状态更新不 commit（exports 惯例不入库），终态汇总写进交接。

## 4. 验收

1. 08-26/27（及 08-28）review 队列零 `pending_review`，每条有终态与理由。
2. vertical-slice 队列重建后 P1 四题材不再出现在待补段。
3. quality 队列创新药段清零或给出无法修复的逐条理由。
4. 交接含：各队列剩余量、游标、被 reject 条目的理由清单。

## 5. 红线

- theme-radar 对齐基准：L1 研报判断默认 graph_only/exposure_only，不污染实体正文；broker 材料不进 `## 边际变化`。
- relations 大 JSON 用 `query_relations.py` 查。
- 禁 `git add -A`；不合 main 不推。
