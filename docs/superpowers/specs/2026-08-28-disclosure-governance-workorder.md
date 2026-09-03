# 工单：disclosure 归档治理——178 个未跟踪公告 md + evidence-gap 队列（P1-P2）

- 状态：**已执行（树 `/Users/a77/kb-wt-disclosure-archive-0813-0828`，分支 `disclosure/archive-0813-0828` @ `6b14d2c8`；活库 disclosures 工作区已清；未合 main）**
- 目标仓：`/Users/a77/knowledge-base-private`
- 来源：2026-08-28 欠账盘点。
- 优先级：**P1（治理未跟踪文件）→ P2（gap 补证）**

## 0. 一句话

知识库仓 `wiki/raw/disclosures/` 里堆了 178 个未进 git 的公告 md（2026-08-13 ~ 08-28），先治理入库；evidence-gap 队列还有 20 条 pending（含 P0 3 条）和 review-queue 3 条待处理。跨仓 kb-ingest 工单转出的 disclosure 类任务也归本单收口。

## 1. 证据

- 未跟踪文件：`git -C <kb> status --short -- wiki/raw/disclosures/` 共 188 行，其中 md 178 个。日期分布：08-13:1、08-14:14、08-15:14、08-20:18、08-21:19、08-22:22、08-24:7、08-25:19、08-26:21、08-27:21、08-28:28。
- inflight 提示：「活库 disclosures 未跟踪，勿随脏分支提交」——即抓取侧一直在落盘，只是没人做干净的归档提交。
- gap 队列：`wiki/raw/disclosures/evidence-gap-queue.json`，summary 20 条 pending（P0:3 / P1:1 / P2:16）。
- review-queue：`wiki/raw/disclosures/review-queue/review-queue_all_20260815.json`，`review_items` 3 条；工具 `skills/disclosure-archive/scripts/review_queue.py`。
- apply 侧约束：`docs/handoffs/inflight/disclosure-rss-l3-nightly-report.md` 记明近 3 天可升 L3 = 0，**勿 `auto_apply --apply`**。
- 题材定向补证的现成工具：`wiki/raw/theme-radar/theme-evidence-readiness-*.json`（光模块 48 行 / 超级电容 32 行）→ `python3 scripts/build_disclosure_archive_prompt_from_readiness.py --theme <题材>` 生成归档 prompt（只归档不入库）。

## 2. 范围

**做**：① 178 个 md 做一次干净的归档提交（专用分支）；② evidence-gap P0 三条补证归档；③ review-queue 3 条出结论；④ 接收 kb-ingest 工单转来的 disclosure 任务清单并归档。

**不做**：不做实体正文 apply（升 L3 由夜巡链路单独判定，当前读数为 0）；P1/P2 gap 只做到留游标；不改抓取侧脚本。

## 3. 步骤

1. 开工自查：`git status --short && git branch --show-current && git worktree list`。开分支 `disclosure/archive-0813-0828`。
2. 归档提交前置检查：
   - `python3 scripts/check_tracked_file_sizes.py`（或等价手段）确认没有超限大文件混入。
   - 确认全部是 md（无 pdf/zip 混入——红线文件类型禁提交）。
   - 抽查 3-5 个文件确认是正常公告抓取产物（非半截写入）。
3. 归档提交：按日期分组、pathspec 提交（例：`git add wiki/raw/disclosures/2026-08-14/ && git commit -- wiki/raw/disclosures/2026-08-14/`，或整批一个 commit，但 add 必须限定 `wiki/raw/disclosures/` 路径）。
   完成判据：`git status -- wiki/raw/disclosures/` 干净；分支推送（不合 main）。
4. evidence-gap P0 三条：读 gap 描述 → 用 disclosure-archive skill 抓取对应公告落盘 → 更新 gap 状态。找不到官方披露的，gap 标注「查无」及检索路径，不硬凑。
5. review-queue 3 条：`python3 skills/disclosure-archive/scripts/review_queue.py` 走一遍，逐条给终态。
6. 接收 kb-ingest 工单转来的 disclosure 任务（08-26/27/28 批里 `leave` 到本管线的约 19 条）：能归档的归档，题材级的用 readiness → prompt 工具批量生成归档指引；处理不完的留游标。

## 4. 验收

1. disclosures 目录 git 状态干净，归档 commit 可追溯（分支上，未合 main）。
2. evidence-gap 队列 P0 清零（或带「查无」标注）。
3. review-queue 3 条有终态。
4. 交接含：归档文件数按日分布、gap 余量（P1/P2 游标）、kb-ingest 转入任务的处理清单。

## 5. 红线

- 只归档不 apply：实体正文 L3 升级走夜巡判定，本单禁 `auto_apply --apply`。
- 禁提交 pdf/zip/db 类文件。
- 禁 `git add -A`（本单尤其危险——活库同时有别的 agent 在落盘新公告，add 必须限定路径 + 日期目录）。
- 不合 main 不推（合并等用户确认）。
