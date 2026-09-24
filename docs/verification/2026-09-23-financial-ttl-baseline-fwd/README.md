# 财务链前向（#855 两道门 + 混比补检）· 阳性对照读数（2026-09-23）

工单 #66 验收项：「把 `comparison_baseline_gaps()` 的主体回退关掉，R3 positive-persistence 封存答卷
干跑必须从『基线缺口』变为无命中；还原后回命中。」本目录是这一项的可复现入口与三次读数。

分支 `fix/financial-ttl-baseline-fwd-0923`：把 #855 自己的两格（`1068b42fe`、`132afc0b1`）与
`fix/financial-comparison-0922` 自己的两格（`5d50cd864`、`63f8a3859`）cherry-pick 到 main `626d8a508` 之上。
不再合 #835（已关闭，财务线 `d82cb16b5` 已随 #863 squash 进 main）。

## 干跑入口

`dry_run_sealed.py`（本目录）。原件 `~/.finance-runtime/reviews/8792-ttl-baseline-20260922/dry-run-sealed*.log`
只有输出没有命令，作者的脚本没有留下；本脚本按 `scripts/review_probes/replay_financial_r6.py` 的方式
解码封存 episode（`ResearchTaskContract.from_dict` / `AgentEvidence` / `OutputEvidenceBinding`），只调
adapter 真正接线的两道门：

- `track_contract.conclusion_ttl_conflicts(public)`：`_track_public_delivery` 披露的那份（公开稿）。
- `financial_claim_checks.comparison_baseline_gaps(_numbered_sentences(text), evidence, bound, subject=contract.subject)`：
  `_issue_backfill_plan` 走补数的那道；生产在 draft 上算，这里 draft 与公开稿各算一列互证。

不调模型、不联网（socket connect 被拒）、不写封存目录；每个输入的 sha256 落进报告并在结束时复核。
R3 `f2-dated-citation-plan` 封存时没有 episode（原作者干跑里就是主体 null / 绑定 0），脚本按无契约无证据处理。

```
PY=.venv-workbench/bin/python   # 主树解释器
S=docs/verification/2026-09-23-financial-ttl-baseline-fwd/dry_run_sealed.py
R=~/.finance-runtime/reviews/8792-ttl-baseline-fwd-20260923
$PY $S --cases ~/.finance-runtime/reviews/8792-boundary-retest-20260918 \
       --cases ~/.finance-runtime/reviews/8792-financial-live-r6-20260918 \
       --output $R/dry-run-A-clean.json
```

## 三次读数（revision `755077674`，同一解释器，同 8 份封存答卷）

| 轮次 | 题 | 主体 | 绑定 | TTL 冲突 | 基线缺口 (draft) | 基线缺口 (public) |
|---|---|---|---|---|---|---|
| R3 `8792-boundary-retest-20260918` | f1-opt-out | 中际旭创 | 19 | 命中 | — | — |
| R3 | f2-dated-citation-plan | None（无 episode） | 0 | — | — | — |
| R3 | f3-formatted-financial | 中际旭创 | 25 | — | — | — |
| R3 | positive-persistence | 中际旭创 | 13 | — | **命中** | **命中** |
| R6 `8792-financial-live-r6-20260918` | f1-opt-out | 中际旭创 | 13 | — | — | — |
| R6 | f2-dated-citation-plan | 中际旭创 | 14 | — | — | — |
| R6 | f3-calculated-financial | 中际旭创 | 13 | — | — | — |
| R6 | positive-persistence | 中际旭创 | 13 | — | — | — |

命中原文（R3 positive-persistence）：`触发条件「不低于两期中较低值」依赖净现比的历史比较基准，但已绑定证据只够算 0 期、需要 2 期`。
与 #855 作者 `dry-run-sealed-after.log` 的 1/8 TTL、1/8 基线缺口逐题一致。

| 读数 | 树 | `financial_claim_checks.py` sha256 | TTL | 基线缺口 draft / public | 报告 |
|---|---|---|---|---|---|
| A 干净 | dirty=false | `8eace1625e4adc8acd10372332c7db69d01df5bbedfa6a37d9a46f1d00bed318` | 1/8 | 1/8 · 1/8 | `$R/dry-run-A-clean.json` |
| B 关掉主体回退 | dirty=true | `a651e9e3166f2bf9bc8c456dcb7d27d95944e4a674a2ab565079c04e0a8b4126` | 1/8 | **0/8 · 0/8** | `$R/dry-run-B-fallback-disabled.json` |
| C 还原 | dirty=false | `8eace1625e4adc8acd10372332c7db69d01df5bbedfa6a37d9a46f1d00bed318` | 1/8 | 1/8 · 1/8 | `$R/dry-run-C-restored.json` |

B 的临时改动只有一行：在 `comparison_baseline_gaps()` 里 `values = _observations(evidence, bound, subject)` /
`if not values:` 之后插入 `return ()`，让「已绑定读数只指向一个主体时按该主体解析」的回退成为死代码——
这正是 `132afc0b1` 修的那个 0 命中：契约主体写中文名「中际旭创」，带 36 条读数的证据标题只有代码
`300308.SZ`，标题反查落空。关掉回退，R3 positive-persistence 的缺口消失（0/8）；`git checkout` 还原后
sha256 回到 A 的值，缺口回到 1/8。TTL 冲突一列三次不变（它不经过这段代码），可作对照。

```
# B：python 一行替换后 git diff --stat 为 1 file changed, 1 insertion(+)
# 还原：git checkout -- intelligence/services/financial_claim_checks.py && git diff --exit-code -- 同文件
```

## 不主张什么

- 不是自然验收：R3 固定 `c481272e`、R6 固定 `dfd7b4ff` 的四题仍各 0/4，不据此改判。
- 只覆盖这两道门；`_observations` 按契约主体反查只匹配到表头的既有洞（`calculation_ratio_gaps` /
  `financial_claim_mismatches` 在这份回合里返回空是「判不了」）本轮未修，单独立单。
- 四叶（python / frontend / e2e / registry）由主会话在预览树串行跑，本目录不含全量读数。
