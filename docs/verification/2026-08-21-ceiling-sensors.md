# W5 封上限传感器聚合：金标 + 近 7 日窗读数（2026-08-21）

> spec：`docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md` W5
> 脚本：`scripts/audit_ceiling_sensors.py`（只读 `continuous-episode.json`，零配额）
> 树：`/Users/a77/fwp-wt-ceiling-sensors` @ `feat/ceiling-sensors`（基线 `gitea/main=0ed258b5`）
> 不立预测行（工具单）。

## 金标（历史 run 实跑）

```
python3 scripts/audit_ceiling_sensors.py \
  --runs-dir ~/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260821_171744_929436 \
  --runs-dir ~/.local/share/finance-workbench/users/probe-ab-0821-post/runs/run_20260821_164659_624916 \
  --since 2026-08-21 --until 2026-08-21
```

| run | A | B | C | D |
|---|---|---|---|---|
| E4 `run_20260821_171744_929436` | **不可判**（无 `projection_cited_unbound_count`） | 命中：`unreachable_without_tools` 四格名单（落盘是名单不是布尔） | **命中**：`marker_loss=chain_mapping` | 未命中 |
| B 臂 `run_20260821_164659_624916` | 不可判（同缺字段） | 干净 | 干净（`repaired` 但 `rejected_claim_indexes=[]`） | 干净（预取 `CXO概念` = 问句精确名） |

退出码 1（E4 的 B/C 非零）。与 spec 金标一致：E4 报 C + A 不可判；B 臂干净。

E4 的 C 不是靠 `rejected_claim_indexes`（repair 后该字段是 `[]`，见 `docs/trace-profile.md`），而是表里的另一支：`marker_loss` 落账。OR 不能退化成只看 indexes。

E4 同时报 B，是表的诚实读数，不是金标漂移——`repair_goal` 事件里 `unreachable_without_tools` 非空。

## 近 7 日窗（2026-08-15..2026-08-21）

默认扫 `~/.local/share/finance-workbench/users/*/runs`。

| | 读数 |
|---|---|
| scanned | **356** |
| A 命中 / 不可判 | **0 / 354**（有字段的 2 条都是 #298 后探针且 =0：`run_20260821_202251_705778` / `run_20260821_202439_961598`） |
| B 命中 | **110**（mandatory 106、unreachable 6、两路同时 2） |
| C 命中 | **14**（全部 `marker_loss`，无 `repair_wiped_all_outputs`、无 repaired+非空 indexes） |
| D 命中 | **1**：`run_20260821_152044_472523` 预取 `CXO` ≠ 问句 `CXO概念`（#288 修前的 tracediff 原案） |
| 退出码 | **1**（B/C 非零，夜检会红——这是计量，不是回归失败） |

机器可读落 `/tmp/ceiling-sensors-7d.json`（本机本次实跑，不入库）。

A 的 354 不可判是量纲诚实：#298（`59ec4294`）才开始写 `projection_cited_unbound_count`。把缺字段当成 0，夜检会假绿。

D 那 1 条是传感器在扫历史窗时抓到的已知漏网，不是新故障。#288 之后的 B 臂金标同题已干净。

## 变异

先提交 `08671566` 再改（`git checkout --` 只能回到已提交态）。两次都已亲手复现后还原：

1. 缺字段当 0（`semantic.get(..., 0)`）→ 3 红：`test_missing_projection_field_is_unjudgeable_not_zero`、`test_gold_e4_shape_via_fixture`、`test_live_gold_e4_reports_c_and_unjudgeable_a`
2. C 只留 `rejected_claim_indexes`、关掉 `marker_loss` / `repair_wiped_all_outputs` → 4 红：上列金标两条 + `test_shape_c_from_marker_loss` + `test_shape_c_from_repair_wiped_all_outputs`

还原后本文件 19 passed。全量门禁：ruff 绿，pytest **5907 passed / 0 failed / 13 skipped**（基线 5888 + 本单 19）。本文件收据 `~/.finance-runtime/test-receipts/20260821T135443Z-08671566.json`；全量在同树 `08671566` 上跑完。

## 落点

- 审计件：本仓 `scripts/audit_ceiling_sensors.py`
- TOOLKIT E 档：harness-reference 分支 `docs/ceiling-sensors`（干净树 `/Users/a77/hr-wt-ceiling-sensors`）。主检出树 `docs/constraint-three-sieves` 有他人未提交 TOOLKIT 改动，未就地改。vault `50_agents/TOOLKIT.md` 等该 PR 合入后再对 pin。
