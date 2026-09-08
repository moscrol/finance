# 在途交接 · feat/methodology-backtest-p1-lifecycle-stage（工单 #21 剩余 P1 / G-04）

## 这个分支做什么
题材阶段三套词收成一套：七段（`theme_lifecycle_timeline` 状态机）为标签值，八阶段降为读法层别名（`theme_stage_vocab` 映射表，一对多带条件），设计稿五段预留作废。旁路库新标签 `lifecycle_stage`（`LABEL_VERSION` v4），河题材轨新发同口径 `stage` 对象，`daily_agent` 并排给七段钦定词；人工对照集草稿 42 条（`stage_manual` 待创始人填）+ `stage-agreement` 报告。收据 `docs/verification/2026-09-08-theme-lifecycle-stage-vocab.md`。

## 决策与被否方案
- 选能重算的那套（七段）当标签值 / 否 八阶段（要消息面 + 人判，历史上大多数日子算不出）/ 否 五段预留（从未落地、与七段只差两个词）。
- 标签值取「站在当天」的机器状态（`derive_stages(daily=)`）/ 否 按事后段落表取值——起点回溯与短段合并是前视，真库 30 抽只有 28/30 一致，改后 30/30。
- 连板高度不进标签原料 / 否 接 `fact_limit_advance_daily.theme LIKE`——模糊匹配进标签口径就是猜。
- 文档映射表由代码生成并测试比对 / 否 手抄两份。
- UBIQ 小节插在「指数环境周期」前 / 否 与 #36 同插入点（必冲突）。
- 共享旁路库不动，只建临时 v4 库 / 否 现在重建（#36 同理；且两单都升 v4，后合者升 v5）。

## 当前状态
9 新测试 + methodology 100P + daily_agent 续绿；临时库 `/tmp/history_labels.v4-theme.duckdb`（`lifecycle_stage` 95,927 行 / 620 板块）；river vs labels 30/30；对照集草稿 `methodology/reference/theme_stage_reference_set.jsonl` 42 条进 git。**干净树全量门禁见收据（合入前补跑）。**

## 未验证 / 已知边界
- 一致率等创始人填 `stage_manual`（≥ 30 条才出率）。
- 酝酿段恒无（旁路库不读知识库）；「首发」段偏长是机器语义。
- 与 #36 撞 `LABEL_VERSION`；合入后共享库重建 + 四条规则重跑记漂移（预期零漂移：新增列不改旧值）。

## 下一步
- 合入 → 共享库重建 → 路线图 G-04 回写「已落」、INDEX #21「剩余 P1」改为「lifecycle_stage 已落，一致率等标注」。
- #36 的错位标记题材侧双表可以并成一张（`THEME_STAGE_COARSE` 改引 `theme_stage_vocab`）。

## 踩过的坑
- 状态机的 `open_segment(STAGE_EBB, break_start…)` 把段起点回溯到断红首日——按段落表给历史日贴标签会把「当时还是发酵」的日子改成「退潮」，这是隐藏的前视；标签要记循环里的即时状态。
- `resolve_entity("半导体", "2026-09-04")` 解析不出——那天板块宇宙没有 990122.FP 的行（不是周末问题），换 09-07。
