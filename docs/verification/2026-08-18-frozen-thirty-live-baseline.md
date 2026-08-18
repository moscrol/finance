# 冻结 30 题 live 基线（2026-08-18）

- 派单：`docs/handoffs/2026-08-18-frozen-thirty-live-baseline.md`
- 机读基线：`intelligence/eval/measurements/2026-08-18-frozen-thirty-live-3d30b2c5.json`（2.7 MB）
- 被测树：`land/caliber-stack` @ `3d30b2c5`，`source_dirty=false`
- 驱动：`scripts/run_agent_runtime_benchmark.py --backend continuous_glm`（**不是**派单写的 sidecar
  live probe——该题集的 dry-run 契约检查本来就跑在这个驱动上，换 sidecar 等于另写一套）
- **8792 未碰**：artifact 自带 `canonical_runtime_touched=false`、`runtime_switched=false`
- 凭证：`credential_source=environment`（launcher 的 export，**没走 Keychain**——
  旧 BYOK 条目指向已归档的死网关，用它会污染读数）

## 0. 先更正一条我自己说错的话

**这套 30 题不是 holdout。** 我在 `2026-08-18-twelve-failures-root-cause.md` §4.3 写过
「题号与 28 题完全不重叠」——**那是错的，当时只看了前 6 个 id 就下了断言**。

实际逐 id 求交集：

| | 数量 |
|---|---|
| 30 题 ∩ 28 题 | **19 道重叠** |
| 30 题里真正没在 28 题出现过的 | **11 道** |

而且这本来就是设计如此：fixture 自己的 `note` 写着「前九题与 07-25 九题逐字相同；
其余 21 题只搬已有验收/long_tail 题面」，`sample_design` 是 `30×15 / v=0.1375 / ±5pp`
——**它是为方差分辨力设计的回归集，从来不是泛化集**，是我把它当 holdout 了。

**本仓目前唯一与 28 题零重叠的题集是 `uq15_questions.jsonl`（15 题，实测交集 0）。**
真要拿泛化读数，那个才是候选（本单未跑）。

## 1. 主读数

30/30 全部执行完，`execution_status` 无 infra_fail（驱动层无超时/崩溃）。

| 口径 | **没见过的 11 道** | 见过的 19 道 | 全部 30 道 |
|---|---|---|---|
| structural completed | **6**（55%） | 4（21%） | 10（33%） |
| structural partial | 3 | 14 | 17 |
| structural failed | 2 | 1 | 3 |
| semantic passed | 4 | 6 | 10 |
| semantic repaired | 5 | 9 | 14 |
| semantic unavailable | 2 | 4 | 6 |
| **task_alignment 均值** | **0.409** | **0.392** | 0.398 |
| 协议问题数 | 9 | 22 | 31 |
| 中位延迟 | 45.1s | 28.0s | 37.7s |

门禁结论：`passed=false`，`protocol_failure_count=25`。

## 2. 对「是否过拟合到 28 题」的回答

**没有看到过拟合的迹象，但这份证据比想象中弱，两个理由都要说清。**

正面信号：**没见过的 11 道 task_alignment 0.409，见过的 19 道 0.392——没见过的反而略高。**
structural completed 也是没见过的更高（55% vs 21%）。如果前面几轮修复过拟合到了 28 题，
方向应该反过来。

但**这个比较是有 confound 的，不能当结论用**：

1. **两个子集的 `required_outputs` 契约形状不同。** 见过的 19 道来自 A/B/C 验收集，
   输出契约更细更严；没见过的 11 道多来自 frozen-nine，契约项更少。
   **completed 率的差可能来自契约宽严，不是能力差。**
2. **n=11，且单跑。** 本仓方差治理文档（`10_knowledge/eval-harness-variance-governance.md`）
   的结论是单跑不足以定序；今天我在 28 题上也**实测证伪**了「fact 层 0% 翻转」这条校准
   （同尺子下 A4/A6/B6 在两份 run 之间翻了）。**0.409 vs 0.392 这个差远在噪声里。**

**所以诚实的结论是：这份数据不支持「过拟合了」，也不足以支持「没过拟合」。**
要真回答，得跑与 28 题零重叠的 uq15，并且多跑取分布。

## 3. 一处影响 validity 的实测缺陷

**题目锚点没有全部下达到数据层。** 30 题的 `as_of` 全是 `2026-07-24`，但 arm 记录的
`data_cutoff`：

| | 题数 |
|---|---|
| 对齐题目锚点（`2026-07-24`） | 21 |
| **漂到 `2026-08-18`（跑的当天）** | **2** |
| 无 cutoff | 7 |

漂掉的两道：`index-rebound-space`、`sci-tech-support`，**两道都在「没见过」那 11 道里**。
它们拿今天的盘面回答一个锚在 07-24 的问题，答案本身失去意义。

这与 28 题里 A3 的病是**同一族**（日期锚到不了产品），Phase 2 只修了 28 题那侧的题面，
**没修这条通路本身**。7 道无 cutoff 的暂时判不了是「不需要」还是「丢了」。

## 4. 协议问题分布（31 条）

| 次数 | 问题 |
|---|---|
| 3 | `ValueError:runtime source_date must be ISO date` |
| 3 | `runtime_invalid_actions:1` |
| 2 | `missing mandatory capability evidence: market_data` |
| 2+2+1+1 | `numeric_lineage_gap:...`（数值血缘断链，多题多点位） |
| 1 | `semantic repair removed required output: current_baseline` |

最后一条值得单独看：**语义修复把一个必需输出删掉了**——修复动作本身造成了契约缺口。
与今天在 28 题上发现的「修尺子过程中造出新的尺子缺陷」是同一形状。

## 5. 成本与延迟（供「一轮评估多少钱多少分钟」决策）

| 项 | 值 |
|---|---|
| 墙钟总时长 | 约 23 分钟（30 题串行） |
| 延迟 min / p50 / p90 / max | 0.0s / 37.7s / 130.8s / 173.8s |
| LLM 调用 | 72 次 |
| provider 尝试 | 112 次（比 LLM 调用多 40 次 → 存在重试） |
| 工具调用 | 75 次 |
| token | 输入 763,499 / 输出 22,062 |

**输入输出比 35:1**——上下文占了绝大部分成本，值得单独看一眼是不是有重复投喂。

## 6. 本报告不做的事（派单红线，逐条自陈）

- **不做绝对质量宣称**：题集非独立出题（08-10 章审自陈「题目我出、判分我判」，
  用户独立出题复测只有 8/10）。本基线只作**回归对比锚**。
- **判分同源 confound 记录在案**：本次判分走驱动内置的 structural / semantic 判据，
  与答案同属一条运行时链路，**没有做到派单要求的异源判分**。后续对比必须同参跑，
  不可与异源判分的读数混序。
- **单跑，不做多跑统计**：方差局限见 §2。
- **不 cherry-pick**：30 题一次跑完全部入账，无重跑、无挑选。`passed=false` 原样记。

## 7. 复现

```bash
# launcher 的 export 就是唯一凭证源，别维护第二份
set -a; . <(grep '^export ' /Users/a77/.local/bin/start-finance-workbench); set +a
export WORKBENCH_REPO_ROOT=<被测树>; export PYTHONPATH=<被测树>; cd <被测树>
.venv-workbench/bin/python scripts/run_agent_runtime_benchmark.py \
  --backend continuous_glm \
  --finance-root "$FINANCE_WS" --knowledge-wiki "$KNOWLEDGE_WIKI" \
  --questions-file intelligence/eval/fixtures/frozen-thirty-2026-08-16.questions.json \
  --output intelligence/eval/measurements/<日期>-frozen-thirty-live-<rev>.json
```

驱动**要求显式传两个根，不传就 exit 2**——这是它的 fail closed，别绕。
