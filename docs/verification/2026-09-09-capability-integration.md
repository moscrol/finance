# 能力整包集成 · 验收记录（滚动）

> Spec：`docs/superpowers/specs/2026-09-09-capability-integration-and-live-research-design.md`
> 进度台账：`docs/superpowers/plans/2026-09-09-capability-integration/PROGRESS.md`
> 本文件只记「跑过的命令 + 返回码 + 原件路径」，不复述计划。

## I1 · 00 污染归因（2026-09-09 22:15，工程+真实重审完成）

**提交**：`feat/i1-availability-attribution` @ 01de7e94（基于 `baseline/capability-benchmark-00` b044b61c；已推 gitea）。改动面：`intelligence/eval/capability_benchmark.py`、`intelligence/tests/test_capability_benchmark.py`。题面、密封判分点、评分权重、通过阈值未动（题库指纹不变：questions `d987df999f866873`、sealed-manifest `4ef1fd08f5db09cf`）。

**判据**（spec §I1 四行表的实现）：episode 事件链上游失败证据（`model_error` / `repair_model_retry` / `model_turn` 带 `error`）+ 最终有效回答（`outcome.draft` 非空）联合分类 → `clean` / `recovered`（接受，保留失败与耗时记录）/ `unavailable_final`（隔离，允许按原条件续跑，不因 stop_reason 改名漏掉）/ `product_failure`（接受并判败，不许重跑洗分）。判官不可用/降级逐轮明示（`judge_status`、`exc_class`、实际 `served_models`；`exc_class=None` 照样列出）。resume 与 review-pack 共用 `case_service_isolated`（有 run 目录现读 episode 权威面，读不到退回旧 `quota_tainted` 标记）。所有尝试计入 `summary.availability_class` 与 `attempts` 分母。

**红→绿**：

```
# 旧实现（git stash 后）：6 failed, 17 passed
# 新实现：
cd /Users/a77/fwp-wt-i1-attribution
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_capability_benchmark.py -q      # → 23 passed, rc=0
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check \
  intelligence/eval/capability_benchmark.py intelligence/tests/test_capability_benchmark.py  # → 0
```

**真实原件重审**（reclassify 派生新报告，旧件只读保留；派生件目录 `~/.finance-runtime/capability-integration/i1/`）：

```
python -m intelligence.eval.capability_benchmark reclassify --artifact <旧件> --output <派生件>   # rc=0 ×3
```

| 旧件（`~/.finance-runtime/capability-benchmark-00/runs/`） | 存档口径 | 重审四类 | 变化 |
|---|---|---|---|
| `20260909T125222Z-cb00-baseline-372d047c0b0f.json`（20:53） | completed 6（含 tainted 1）+ skipped 24 | recovered 2 + unavailable_final 4 + skipped 24 | **calc-01 / material-01 / material-02 由「干净」翻隔离**（同为 `model_turn_error=LLM 调用 HTTP 502`、draft=0、终态 `invalid_repair_finish` 类改名）；feel-01/02 为真实恢复样本（中途 502、终稿 900+ 字），保留失败记录照常评审 |
| `20260909T103255Z-…​.json`（18:33） | tainted 1（feel-01） | unavailable_final 1（一致，无翻转） | 判官不可用 1 轮明示 |
| `20260909T080447Z-…a6a7c10e.quota-tainted.json`（16:04 废件） | tainted 25 + engine_missing 4 | unavailable_final 22 + unclassified_no_episode 4（run 目录已被移走，退回旧标）+ engine_missing 4 | **calc-01 在废件里同形漏标**（changed=[cb00-calc-01]）；判官不可用 27 轮明示 |

**spec 四类反例逐条对账**：calc-01 漏判（真实 `run_20260909_205227_971715`）→ 单测 `test_renamed_terminal_failure_…` + 上表两件实锤；恢复成功 feel 样本 → `test_recovered_case_…` + 20:53 件 feel-01/02；真实产品失败对照 → `test_product_failure_without_service_excuse_…`（空稿无服务借口→照常判败）；判官不可用 → `test_reclassify_…` 的 judge_flags（exc_class=None 也列）+ 真件 27 轮明示。

**移交（→00 车道）**：当前在跑的 cb00-baseline 批次链上带着上述 3 题假干净；批次停下后下一次 `--resume` 用 01de7e94 代码跑（新判据不搬假干净题、按原条件重跑），最终基线件再 reclassify 归档。见 BLOCKED W5。
