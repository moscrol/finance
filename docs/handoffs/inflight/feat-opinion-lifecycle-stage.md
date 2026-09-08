# 在途交接 · feat/opinion-lifecycle-stage（工单 #36 / G-06）

## 这个分支做什么
钦定舆论生命周期词表（萌芽 / 扩散 / 拥挤 / 退热 / 证伪 + unverifiable），`opinion_stage.derive_stage` 从研报事件按 `recorded_at <= C` 确定性派生，无状态；河舆论轨新发 `stage` 对象；旁路库新标签 `opinion_stage`（`LABEL_VERSION` v4）进规则 DSL；覆盖率报告 + 错位标记。收据 `docs/verification/2026-09-08-opinion-lifecycle-stage.md`。

## 决策与被否方案
- 阈值用 `ast` 只读 `consensus_staging.py` 的三个常量 / 否 直接 import（会拉 opinion_store / pan_realize 等 skill 依赖进 services）/ 否 复制数字（两处写必漂）。
- 扩散不设「斜率 > 0」门，斜率进 inputs / 否 照工单表——≥3 份但持平的日子会无段可去。
- 名字从未被研报命中的板块不落 `opinion_stage` 行（NULL）/ 否 落 unverifiable——两者语义不同：前者连负证据缺失都谈不上。
- 共享旁路库不动、只建临时 v4 库验证 / 否 现在就重建共享库——#663 等在途树读 v3，本分支未合就换版会让它们的收据「不可比」。
- UBIQ 新小节插在文中（「指数环境周期」后）而不是文末 / 否 追加到文末——#666 在文末追加「产品终局」表，两边同位置必冲突。

## 当前状态
13 新测试 + methodology 87P；真库覆盖率报告 2026-06-01→09-05：355/683 板块名有覆盖，24,495 格，unverifiable 65.1%，拥挤 111，证伪 0。临时 v4 库 `/tmp/history_labels.v4-opinion.duckdb`（`opinion_stage` 143,104 行）；DSL 探针 `opinion_stage in ["拥挤"]` 跑通（读数不是结论，见收据）。**干净树全量门禁见收据（合入前补跑）。**

## 未验证 / 已知边界
- 回填批次抬高自身 p80（半导体 p80=35 来自 2026-01 批次），拥挤偏保守；历史短时偏激进。`os-v1` 候选：历史剔批次窗。
- 证伪事件对象河里没有，段恒 0。
- 共享库仍 v3；合入后由验收 session 重建并重跑四条规则记漂移（#661 做法）。
- 与 #21 剩余（G-04）撞 `LABEL_VERSION`：后合入者 rebase 升 v5，错位标记双表并一张。

## 下一步
- 合入 → 重建共享旁路库 v4 → 四条规则重跑 → 路线图 G-06 回写「已落（#36）」、§5 第 3 题写入拍板。
- G-07 三维并置可以开工：题材侧（G-04 后）× 本词表 × 盘面 `market_stage`。

## 踩过的坑
- `fact_sector_daily` 同一 `sector_ts_code` 有两个 `sector_name`（990380.FP）——按 (code, name) 迭代会撞旁路库主键；按 code 归并名字。
- 后台 `( … ) > log &` 跑长任务会被回收（交接里早写过），`build-labels` 要前台跑（2 分钟）。
