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

## 0.5 第二处更正：本报告初版的主结论被自己的数据推翻了

初版写「没见过的 11 道 align 0.409 > 见过的 19 道 0.392，**没看到过拟合迹象**」。
用户追问「DuckDB 数据不是已经到 8-18 了吗，怎么还在用那个快照」，顺这条线查下去，
**那个信号是两道假满分撑起来的**。逐层剔除后：

| 口径 | 没见过 | 见过 |
|---|---|---|
| 初版（全 30 道） | 0.409 (n=11) | 0.392 (n=19) |
| 剔 3 道 `infra_fail`（派单要求，见 §3.2） | 0.500 (n=9) | 0.414 (n=18) |
| **再剔 2 道 fast-path 串题（见 §3.1）** | **0.357 (n=7)** | **0.424 (n=17)** |

**方向翻转：摘掉假满分后，没见过的题反而更差。**

**所以初版那句「没看到过拟合迹象」撤回。** 现在的诚实表述是：
**这份数据既不能证明过拟合、也不能证明没有**——n=7 vs 17 单跑，噪声压过任何差值。
留着初版那句不撤，等于拿两条 bug 的满分去背书一个产品结论。

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

**答不了。这份数据既不能证明过拟合、也不能证明没有。**（初版给的「没看到过拟合迹象」
已在 §0.5 撤回——那个信号是 §3.1 两道假满分撑起来的，剔掉后方向就翻了。）

剔除 infra_fail 与假满分后：没见过的 **0.357 (n=7)** vs 见过的 **0.424 (n=17)**。
表面看是「没见过的更差 = 有过拟合」，**但同样不能这么读**，理由如下：

1. **两个子集的 `required_outputs` 契约形状不同。** 见过的 19 道来自 A/B/C 验收集，
   输出契约更细更严；没见过的 11 道多来自 frozen-nine，契约项更少。
   **completed 率的差可能来自契约宽严，不是能力差。**
2. **n=7 vs 17，且单跑。** 本仓方差治理文档（`10_knowledge/eval-harness-variance-governance.md`）
   的结论是单跑不足以定序；今天我在 28 题上也**实测证伪**了「fact 层 0% 翻转」这条校准
   （同尺子下 A4/A6/B6 在两份 run 之间翻了）。**0.357 vs 0.424 这个差远在噪声里。**
3. **本次剔除动作本身就是证据不稳的证明。** 同一份数据，剔 5 道（占六分之一）就让
   主结论翻向。**任何靠这个量级样本得出的方向性结论都不该被采信。**

**结论：要真回答过拟合，得跑与 28 题零重叠的 uq15（15 题，实测交集 0），并且多跑取分布。
在那之前，本仓没有任何一份读数能回答这个问题——包括本报告。**

## 3. 两个实测查出的 bug（都比初版写的严重）

先回答「为什么锚在 07-24 而库里已经有 08-18」：**锚点是对的，而且大部分题真的生效了。**
冻结基准必须钉死 as_of，否则答案随行情天天变，跑两次就没法比。实测验证：
`rebound-duration` 的答案是「下跌阶段（第1天）/ 缩量观望 / 上涨534家 / 涨停40家 /
跌停24家 / 强势5.52%」，而库里 `fact_market_daily` 07-24 那行是
`(下跌阶段, 1, 缩量观望, 534, 40, 24, 5.52)`——**逐字段完全一致**。
（08-18 那行是 `底部横盘阶段, 15, 主线抱团, 2121, 79, 7, 8.61`，完全不同，没被误用。）

30 题的 `data_cutoff`：对齐锚点 **21** / 漂到跑的当天 **2** / 无 cutoff **7**。
问题出在那 2 道和另外 3 道上。

### 3.1 `deterministic_fast_path` 串题，且判分器给了满分

| | `index-rebound-space` | `sci-tech-support` |
|---|---|---|
| 问题 | 科创50你认为**反弹空间**有多少 | 科创50的**支撑点位**在哪 |
| `stop_reason` | `deterministic_fast_path` | `deterministic_fast_path` |
| 答案 sha256 | `572e7f30fd12` | **`572e7f30fd12`（相同）** |
| 长度 / 延迟 / llm_calls | 194 / 2.2s / **0** | 194 / 0.8s / **0** |
| `data_cutoff` | 2026-08-18 | 2026-08-18 |
| **判分** | **completed / passed / align 1.0** | **completed / passed / align 1.0** |

两个不同的问题拿到**逐字节相同**的 194 字答案，正文是
「截至 2026-08-18，科创50收盘 1790.87。按近期日线结构，**反弹空间**先看上方压力区…」
——**它答的是「反弹空间」那题**，`sci-tech-support`（问支撑位）拿到的是别人的答案，
**方向都反了**（问支撑位，答压力位）。

三处同时失效：① 一条确定性快路径按标的而非按问题意图返回答案；
② 该路径**不吃题目的 `as_of`**，用跑的当天数据；③ **判分器给了 1.0 满分**——
0 次模型调用、0.8 秒、答非所问，三个轴全绿。

**这是本轮最贵的一条**：它不是「答得不好」，是**假绿**，而且假在结构、语义、对齐三个轴上同时假。

> 顺带：第三道 fast-path 是 `C2-non-trading-day`，答案是「该确定性旁路尚未接入本次
> A/B runner。」（align 0.25）。它至少**如实说了自己没接**，没有假装答对。

### 3.2 3 道 `runner_exception`：日期格式让运行时直接崩

`ruihuatai-valuation` / `B8-valuation-band` / `open-event-fed`：

- `status=failed`、答案长度 **0**、`llm_calls=0`、`tool_calls=0`、`provider_attempts=0`
- 但延迟 73.6s / 89.5s / 136.7s ——**烧掉五分钟墙钟，一次模型都没调到**
- 全部同一个异常：`ValueError:runtime source_date must be ISO date`

**按派单纪律重跑了一次**（`--case` 三道，artifact
`intelligence/eval/measurements/2026-08-18-frozen-thirty-infra-rerun-3d30b2c5.json`）：
**三道全部挂在同一个异常，逐条复现。** 不是偶发，是确定性缺陷。

按派单定义这三道是 **`infra_fail`，不计入质量分布**——初版报告把它们算进了
structural failed，**那是错的，已在 §0.5 重算**。

### 3.3 两条 bug 指向同一处

`source_date must be ISO date`（崩）与 `data_cutoff` 漂到当天（串题那条路径不吃锚点），
**都是日期在运行时边界上没被正确传递**。这与 28 题里 A3 的病同族——
Phase 2 当时只修了 28 题那侧的题面，**没修这条通路本身**，所以换一套题它照样犯。

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
