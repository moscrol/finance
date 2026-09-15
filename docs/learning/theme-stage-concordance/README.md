# 题材阶段人工对照集（G-04 验收 b / 工单 #21 P1 剩余项）

目的：给「题材生命周期钦定词表」（`theme_stage_vocab`，tsv-v1）一份人工裁定的金标准——timeline 重放段与创始人判读对不对得上、八阶段诊断映射后与人工是否同名。**标注是创始人的活，agent 只生成模板与算读数，不代填。**

## 用法

```bash
# 生成待标注模板（只读主库；自动抽近 120 交易日双红最活跃的 12 个题材）
python3 scripts/theme_stage_concordance.py build
# 手选题材补样本（例：补发酵 / 分歧段）
python3 scripts/theme_stage_concordance.py build --themes 固态电池,可控核聚变 --force
# 标注后出一致率报告
python3 scripts/theme_stage_concordance.py report --set docs/learning/theme-stage-concordance/concordance-set-<date>.csv
```

## 标注规则

- `human_stage_canonical` 只填钦定七段词之一：**酝酿 / 首发 / 发酵 / 主升 / 分歧 / 退潮 / 回流**；拿不准留空（留空 = 未标注，不计入一致率）。填其它词会被 report 点名剔除。
- 判读依据写 `notes`（看的哪几个证据、为什么不同意 timeline）。
- `sample_kind=boundary` 是阶段切换日（最易错、优先标）；`midpoint` 是长段中点（校验段身）。
- `diagnosis_stage` 列历史样本恒为 `gap:no_recorded_diagnosis`：八阶段诊断的输入是问答会话检索到的证据文本，历史上没有按日落账，**不回填、不猜**；该列随后续每日复盘按日积累后，report 自动纳入「诊断 vs 人工」「timeline vs 诊断」两组读数。

## 已知的样本分布偏斜（2026-09-15 首版模板实测）

131 样本全部落在退潮 / 回流 / 主升——**没有酝酿、首发、发酵、分歧样本**。原因是结构性的：分歧段通常只有 1–2 天，会被 `MIN_PHASE_DAYS=3` 的短段合并吃掉；发酵段短于 7 天时只在边界采一点，且窗口内边界多被后继段覆盖。创始人标注时如认为缺的段重要，用 `--themes` 手选补样本；若裁定「分歧段被合并不可接受」，改的是 timeline 的 `MIN_PHASE_DAYS` 口径，不是词表。

## 裁定之后（两件事按序，不抢跑）

1. 一致率达标（标准由创始人定）后，prompt / 渲染层显示词切到 canonical；
2. canonical 阶段作为 theme 实体标签入旁路库（`methodology_backtest`），`LABEL_VERSION` 升版，已有规则收据重跑并记录漂移（G-04 验收 c）。
