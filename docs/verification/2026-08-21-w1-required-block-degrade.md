# W1 必需输出块降级保留（2026-08-21）

> 规格：`docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md` §W1
> 代码：`fix/ceiling-required-block-degrade` @ `0ed258b5` + 本单未提交实现
> 树：`/Users/a77/fwp-wt-w1-ceiling-degrade`
> 生产 `:8792` **未切**。live 探针本回合不跑（spec：机制证明沿 #298 重放）。

## 问题

判官删的是**一句**，呈现层却把整格换成道歉横幅。r24 已让记账诚实（lost 格 `missing` + 清绑定）；用户看见的正文仍像「这块没了」。个股案 `run_20260821_171744_955225`、R-05 A 臂 `run_20260821_185226_491046` 都是这个形状。

## 改了什么

`_marker_loss_partial_public`：记账收缩不动；有剩余正文 → `CAUSE_VERIFIED` 透传 + harness 前置 `【质检降级】…详见「输出质检」`；sanitize 空 → 空串，**不**走 `_gap_answer`。道歉横幅只留 C3 全灭闸（`repair_wiped_all_outputs` / `_emit_withheld_repair` 空稿）。批评仍走编排器已有通道 `_with_review_appendix`（判官 never-add）。

## 离线

`intelligence/tests/test_ceiling_required_block_degrade.py`：

| 钉 | 锁什么 |
|---|---|
| ① | 块内 N 句、合法删 1 句 → 残块 + missing + 质检附录 + 标注 |
| ② | `numeric_unsupported` 仍删 |
| ③ | 空残块 / sanitize 空 → 无横幅 |
| ④ | C3 全灭闸仍 withhold 修前稿，不套 W1 降级标 |
| ⑤ | `【质检降级】` 可见 |
| 重放 | 皇氏 / 太辰光夹具：before 有横幅，after 残块 + 标注 + 无横幅 |

夹具：`intelligence/tests/fixtures/ceiling-degrade/{huangshi-direct-assessment,taichenguang-counterpoint}.json`。

既有口径已改（不再要求「结构缺口」横幅）：`test_semantic_repair_cannot_remove_a_visible_required_output_marker`、`test_outlook_repair_that_leaves_only_boundary_is_partial_with_gap`、`test_marker_loss_keeps_gap_audit_when_public_remainder_is_sanitized`（现期望空串）、`test_valuation_marker_loss_gap_keeps_task_context`。

## 已知边界

Spec 目标行为 3（语义质量否决对必需块**零删除权**）**未落地**。接到 `_repair` 上会拆掉判官修稿安全网（既有 monotonic rejudge / 调用次数钉红约 40 条）。本单按「句级错误句级删、残块保留降级」收口：非机械 issue 仍删该句，但不再用整格横幅替换。若要收窄删除权，需单独开单，不能混进 marker_loss 邻域。

## 变异 / 全量 / live

变异在未提交树上用文件备份（禁止 `git checkout --`，会冲掉实现）：

| 变异 | 钉红 |
|---|---|
| 1 残块改回空 public + `CAUSE_EVIDENCE_GAP` 横幅 | 5F：①③⑤ + 两案重放 |
| 2 `_with_required_output_degrade_mark` 改恒等 | 4F：①⑤ + 两案重放 |

还原后 9 passed。定向宽集 210 passed，收据 `~/.finance-runtime/test-receipts/20260821T135628Z-0ed258b5.json`。

全量：`5897 passed / 13 skipped / 0 failed`，ruff 绿，收据 `~/.finance-runtime/test-receipts/20260821T140357Z-0ed258b5.json`（相对基线 5888，本单 +9 钉）。live 未跑。台账 `R-20260821-07` pending：机制证明（重放）≠ 部署后自然样本，不得 confirmed。
