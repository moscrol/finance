# 舆论生命周期阶段词表 + 确定性派生器——工单 #36（G-06）验收收据

> 日期：2026-09-08 · 分支 `feat/opinion-lifecycle-stage` · 基线 `gitea/main@8e452e72`
> 工单：`docs/superpowers/specs/2026-09-08-opinion-lifecycle-stage-workorder.md`（PR #666 分支）；路线图 G-06；§5 第 3 题按推荐执行（v1 不保留「无人问津」，用 `unverifiable`）

## 改了什么

| 文件 | 内容 |
|---|---|
| `intelligence/services/opinion_stage.py`（新） | 词表 `萌芽 / 扩散 / 拥挤 / 退热 / 证伪` + `unverifiable`；`derive_stage(hits, as_of, knowledge_cutoff, falsification_dates)` 纯函数：有效时间 `report_date <= T`、记录时间 `created_at <= C`（记录时刻不可判的行**不计**）；`count_90d`、30 日斜率、近 90 日不同报告日数、自身历史 p80（观测 < 60 日不判拥挤）、近 120 日曾拥挤、连续负斜率天数、回填批次日（同一 `created_at` 日入库 ≥ 10 份）全部进 `inputs`；`derive_stage_series`；错位标记 `dislocation()` 双模块映射表 `THEME_STAGE_COARSE`（`tsc-v0`）。**阈值用 `ast` 只读 `consensus_staging.py` 的三个常量**（它 import 会拉 skill 依赖），缺任一即抛错 |
| `intelligence/services/river.py` | `coverage_metrics` 删掉占位 `stage: unverifiable / stage_reason`；`_opinion_track` 新发 `object_type="stage"` 对象（`payload` 带 stage / coarse / reasons / inputs / derivation_rule；`recorded_at` = 所用研报里最晚的 `created_at`；`source_hash` = 读数哈希） |
| `intelligence/services/methodology_backtest/labels.py` | `THEME_LABELS` 加 `opinion_stage`（16 个标签）；**`LABEL_VERSION` v3 → v4**（`…-opinion_stage_os_v0`）；`LABEL_SPEC` 口径；新 `_build_opinion_stage_labels`：按 `sector_ts_code` 归并全部历史名字、研报按任一名字命中且去重，每 (code, 交易日) 一行文本标签，C = 当日；名字从未命中任何研报的板块**不落行**（NULL 语义） |
| `intelligence/services/methodology_backtest/rules.py` | `LABEL_KINDS["opinion_stage"] = ("theme", "text")`——规则 DSL 可用 `in / not_in / == / !=` |
| `scripts/opinion_stage.py`（新） | `readout --entity --as-of [--cutoff]`；`report --start --end [--entities] [--json] [--no-write]` → `methodology/receipts/opinion_stage/<end>.json`，回填批次 ±30 日单列 |
| `UBIQUITOUS_LANGUAGE.md` | 新小节「舆论生命周期」（插在「指数环境周期」之后、「Flagged ambiguities」之前，避开 #666 在文末追加的「产品终局」表）：六个词 + 进入条件 + 与 `consensus_staging` 阶梯「另一条轴，不互译」的声明 + 回填批次 + 错位标记 |
| 测试 | `intelligence/tests/test_opinion_stage.py` 13 条；`test_methodology_backtest.py` mini 夹具加两份 tag 研报（一份晚入库），标签数 15 → 16，新增 PIT 用例 |

## 验收逐条（工单 §3）

| # | 判据 | 结果 |
|---|---|---|
| 1 | 每段确定性派生；同 `(events, as_of)` 幂等；无 LLM | ✅ `test_deterministic_and_stateless`（事件顺序无关、`source_hash` 相同） |
| 2 | 五种走法 | ✅ `test_walk_sprout_spread_crowded_cooling`（萌芽 → 扩散[历史 < 60 不判拥挤] → 拥挤 → 退热[连续 10 日负斜率] → 覆盖归零仍退热）、`test_sprout_then_unverifiable_when_coverage_vanishes`、`test_falsification_is_terminal`（含证伪日在 as_of 之后不算）、`test_backfill_batch_is_named` |
| 3 | `recorded_at > C` 不参与 | ✅ `test_recorded_after_cutoff_is_invisible`：同一天 C 不同，`hits_used` 2 vs 3、阶段 萌芽 vs 扩散；`C < T` 拒绝；记录时刻不可判的行不计并写 reason |
| 4 | 真库覆盖率报告 | ✅ `2026-06-01 → 2026-09-05`：69 个交易日，**355 / 683** 个板块名曾被研报 tag 命中，24,495 个单元格；分布 **unverifiable 15,938（65.1%）/ 萌芽 4,113 / 扩散 2,040 / 退热 2,293 / 拥挤 111 / 证伪 0**（河里没有证伪事件对象，恒 0 是实话）；回填批次 ±30 日内 0 格（2026-01 那次批次离窗口远）。4.8s |
| 5 | 错位四值各一例；题材侧缺 → unverifiable | ✅ `test_four_values_and_module_tables`（含 证伪 / unverifiable 不在序上、未知模块拒绝） |
| 6 | 词表进 `UBIQUITOUS_LANGUAGE.md`；与题材八阶段 / 七段不重名 | ✅ 新小节；`test_vocabulary_does_not_collide_with_theme_stages` |
| 7 | 阈值 import 不写死 | ✅ `test_thresholds_come_from_consensus_staging_not_literals`（`ast` 解析 + 源码里无 `TH_* = 数字`）；`test_missing_threshold_in_source_raises` |
| 8 | `river.py` 占位字符串消失；舆论轨出 `stage` 对象且哈希稳定 | ✅ `rg stage_reason intelligence/` 0 命中；`test_opinion_track_emits_stage_object_and_no_placeholder`（`recorded_at` 取最晚研报 `created_at`） |
| 9 | `LABEL_VERSION` 升版、旁路库重建、收据重跑 | ⚠️ **只建到临时库** `/tmp/history_labels.v4-opinion.duckdb`（1:57，16 标签，`opinion_stage` 143,104 行 / 344 实体，总 1,608,178 行；分布 unverifiable 113,303 / 萌芽 13,096 / 扩散 11,969 / 退热 3,359 / 拥挤 1,377）。**共享库 `db/history_labels.duckdb` 仍是 v3**——本分支未合入前不动共享产物（#663 等在途树读它）；合入后按 #661 的做法：备份 → `build-labels` → `outcomes` → 现有四条规则重跑记漂移，由验收 session 做 |
| 10 | 干净树全量门禁 | 见下 |

### DSL 接得上的探针（不是结论）

临时规则 `/tmp/opinion_crowded_probe.v1.json`（`opinion_stage in ["拥挤"]` → 后 5 日 `fwd_return > 0`，`heat_final` 宇宙）在临时 v4 库上 `run --no-write`：n=550、k=391、p=0.711、p0=0.451、p=1e-34、四态 `supported`。**只证明 `opinion_stage` 能进规则 DSL 与统计门**；样本是同一批题材连续多日的自相关格、单一时期（2026-06~08 那段），不满足前后半段 / 多时期复现要求，**不进 `methodology/rules`、不进任何对外物料、不得当结论引用**。

## 门禁

干净树 `~/fwp-wt-opinion-stage` @ `97ea28fb`、`.venv-workbench`、`env -u MARKET_FEATURE_STORE_DB`：ruff 0；pytest **8177P / 0F / 76S / 1xfail**（848s，与另两条门禁并跑）；`check_test_receipt --expect-revision HEAD` 可采信。红集为空是判据（基线树与本分支基线不同，不作横向减法）。

## 已知边界

- **扩散不要求斜率为正**（工单表里写了「30 日斜率 > 0」）：≥ 3 份但持平 / 下滑且从未拥挤的日子否则无段可去；斜率进 `inputs.slope_30` 供读者判。
- **回填批次抬高自身 p80**：`半导体` 的 p80=35 来自 2026-01 那次 14 份入库，之后 `count_90d=10` 永远到不了拥挤——今天读数「扩散」是对的口径但偏保守；历史 p80 要不要剔掉批次窗，留下一版（`os-v1`）。
- 自身历史短（60~90 观测日）时 p80 偏低，拥挤判得早（合成走法里 61 日即拥挤）。
- 证伪段依赖 `kind=falsification` 事件对象，河里今天没有；`_opinion_track` 传的是空列表。
- 错位标记的题材侧双表在 G-04（#21 剩余）落地后并成一张（`THEME_STAGE_MAPPING_VERSION` 升版）。
- 与 #21 剩余同样升 `LABEL_VERSION`：后合入者 rebase 再升一版（v5）。
