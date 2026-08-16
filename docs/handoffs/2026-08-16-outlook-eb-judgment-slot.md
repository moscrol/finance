# handoff: R-20260816-11 十题窗判断槽 0-hash → eb 下跌

- 日期：2026-08-16
- 状态：**M2 已交**。报告 `docs/verification/2026-08-16-outlook-eb-judgment-slot.md`（validate RC=0）。R-11 Closed confirmed。量具修复另开 `R-20260816-15`。不切 8792。
- 接收方：分诊 agent（`agent-run-triage`）→ 已完成；下一接收方=量具修复（R-15）
- 基线：当时 `gitea/main` @ `cfac6ce6`。本 M2 从后来的 `gitea/main`（含 #98）拉分支。
- 决策背景：十题窗预注册「eb 修后不降」失败（−17.5pp）。检阅交叉验证：掉分格子是判断槽 hashes=0、旁槽仍 bound。**不复用 R-06**。

## 失败标准（先冻这个，再归因）

修后 `evidence_bound_rate` 相对修前下降，且下降由判断槽（`direct_answer` / `direct_assessment`）`evidence_hashes=0` 贡献。否命题是：判断槽在修后仍有哈希，或下降来自旁槽被剥 / 无 episode。

## 冻结样本（对齐键 `slot`+`run_id`）

用户 `outlook-ab-0816`。优先这三对（两边都是 completed/repaired）：

| slot | pre | post | pre eb | post eb |
|---|---|---|---|---|
| L01:r3 | `run_20260816_184616_575486` | `run_20260816_184718_305950` | 1.00 (2/2) | 0.50（判断槽 0-hash） |
| L03:r2 | `run_20260816_185728_883724` | `run_20260816_185901_871285` | 1.00 (2/2) | 0.50（判断槽 0-hash） |
| L05:r2 | `run_20260816_190515_806994` | `run_20260816_190657_142513` | 1.00 (2/2) | 0.50（判断槽 0-hash + gap 文案） |

`post:L01:r2` 兼有 judge transient，只作旁证。O06/O07/O08 同形可扩样本，不作唯一锚。

收据：`docs/verification/2026-08-16-outlook-ten-question-ab.md`。
计分：`~/.finance-runtime/outlook-ab-20260816/score.json`（20:19，只读）。

## 任务

1. 读账本 Open，回填 pending（R-11 保持 pending，直到 PRIMARY 立住或该形状被 REJECT）。
2. **M2** 对照上表三对：定位第一次让判断槽失去哈希、且能预测该槽 eb 下跌的 step。对齐失败再退回 M1。
3. 至少 3 条可证伪假设。其中一条必须是「判断槽 0-hash 与 R-06/judge 窗地板同因」——预期 **REJECT** 或给出独立机制。
4. 报告 `docs/verification/2026-08-16-outlook-eb-judgment-slot.md`。`validate-report.sh` RC=0。
5. 若有修复建议：新开 `R-20260816-12`（或下一号），不要改写 R-11 的预测原文。

## 完成定义

- 报告首字符 `# Agent Run Triage Report`，PRIMARY 有 step/span + 原始摘录 + Evidence ID。
- R-11 回填：PRIMARY 点名该形状 → `confirmed`；并进 R-06 或只怪窗地板 → `refuted`。
- PR 到 main。不切 8792。

## 边界

- 8795 侧车可只读已有 run；新 live 须另开树，不停泊 `21dbf6c1d83f`。
- 不动 T / `_REPAIR_SECONDS_CAP` / 生产档位 / `_BALANCED_SYNTHESIS_RESERVE`。
- 不翻 `ASK_LONGTAIL_BASELINE` / `ASK_JUDGE_RECHECK` / `ASK_DEGRADED_FALLBACK`。
- 不放宽 5pp。不动 `_CLAIM_POLICY`、`ANALYTICAL_MARKERS`。
- 不结 R-10。不把核心集 0pp 诚实闸并进本案。
- 薄账写入者=检阅方。本文件不在 `docs/dsh-absorption-spec` 提交。
