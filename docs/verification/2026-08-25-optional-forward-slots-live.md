# R-20260824-20 可选前瞻槽 · live 观察（2026-08-25）

港口 8792 @ `468226108fef`；探针用户 `probe-fwd-0825`；五个 run。

> **outcome 仍为 `pending`。** 本文只记观察，不结案：主目标已在生产复现，但另有一条
> 未排除的污染信号（见 §3），n=1 vs n=1，不足以判。执行方不自标 confirmed。

## 1. 读数总表

| # | 问句 | question_type | 挂槽 | 模型绑了 | 真 `basis_mismatch` | 结果 | 用时 |
|---|---|---|---|---|---|---|---|
| A | 中际旭创**怎么看** | `stock_deep_dive` | **3/3** | **3/3** | 0 | completed | 67s |
| B | 光模块**怎么看** | `theme_analysis` | **3/3** | 2/3 | 0 | completed | 88s |
| C | 中际旭创的主营业务和收入结构是什么 | —（未走 episode 路） | 0/3 | — | 0 | completed | 33s |
| D | 光模块产业链的上下游结构**怎么看** | `theme_analysis` | **3/3** | **0/3** | **2**（`counterpoint`） | **degraded** | 59s |
| E | 光模块产业链的上下游结构 | `theme_analysis` | 0/3 | — | 0 | completed | 99s |

run_id：A `run_20260825_001318_148655`／B `…001817_586246`／C `…001945_951998`／
D `…002029_420400`／E `…002247_663989`，均在
`~/.local/share/finance-workbench/users/probe-fwd-0825/runs/`。

## 2. 主目标：达成（样本 A，证据链完整）

契约装配（§8.1 钉 1 的 live 版）：

```
direct_assessment        required=True  model_reasoning   evidence_types=8
supporting_evidence      required=True  evidence          evidence_types=8
counterpoint             required=True  evidence          evidence_types=8
continuation_conditions  required=False model_reasoning   evidence_types=0   ← 本单挂上
invalidation_conditions  required=False model_reasoning   evidence_types=0   ← 本单挂上
scenario_paths           required=False model_reasoning   evidence_types=0   ← 本单挂上
```

公开稿里活下来的条件阈值句：

```
**失效条件**
- 有效跌破 860 元并放量，或公司下修订单/毛利率指引
- 悲观：成本/需求双压 → 跌破 800 元，波动放大
```

**归因三步都验了，不是「看着没删」**：

1. `860` / `800` 在 `detail` / `title` / `observation` 等证据字段中出现 **0 次**
   → 确属模型提出的无据阈值，旧行为下会被数值门整句删；
2. 模型**真的绑了三个可选槽**，`basis` 全为 `model_reasoning` → 槽不是摆设；
3. `numeric_unsupported` 0 次、`basis_mismatch` 0 次、`invalid_model_finish` 0 次。

自保话术（「以盘面为准」这类，2026-08-19 事故的标志）**全稿未出现**。

## 3. 未排除的污染信号（这条决定了不能结案）

样本 D 出现两次真拒收：

```
grounding basis mismatch for counterpoint: expected evidence, got model_reasoning
→ stop_reason=invalid_repair_finish，carried_draft_chars=0，整轮 degraded
```

**出问题的槽是 `counterpoint`，不是本单挂的三个。** 与 2026-08-18 frozen-thirty live
那次（`direct_answer: expected evidence, got model_reasoning`）**同形**，而那次早于本单。

隔离对照 D vs E 是本轮最有信息量的一对——同题型、同主题、契约槽清单只差本单那三个，
**唯一变量是问句尾部的「怎么看」**：

| | D（带信号） | E（无信号） |
|---|---|---|
| 契约槽 | 7 个（4 + 本单 3） | 4 个 |
| basis_mismatch | 2 | 0 |
| 结果 | degraded | completed |

**假说**：挂三个 `model_reasoning` 槽可能把模型带偏，让它对相邻的 evidence 槽也报
`model_reasoning`（priming）。

**反证**：样本 B 同为 `theme_analysis`、同样 3/3 挂槽，`basis_mismatch` 为 0。
所以挂槽**不必然**导致它。

n=1 vs n=1，**判不了**。这正是设计 §8.3 要求误触发腿的原因——它抓到了东西，
但抓到的量不够定性。

## 4. 误触发行为：部分符合预期

样本 D 是刻意选的误触发样本（问上下游结构，语义上不问前瞻，但命中正则）。
**模型一个前瞻槽都没绑**（0/3）——即「不为了填格硬凑情景」这条按预期生效，
设计 §4.2 担心的那种硬凑没有出现。

代价则落在别处：那一轮 degraded 了（§3）。

## 5. 下一步（结案前必须补的）

1. **同形样本再取 3–5 个**，专打「theme_analysis + 误触发信号」这一格，看
   `basis_mismatch` 是随机还是系统性。D/E 那对要能重复才算数。
2. 若确认系统性，收窄方向已在设计 §4.4 写好：给挂槽判据补上
   `output_id in _OUTLOOK_JUDGMENT_OUTPUTS` 这道门（即与 #72 的作用面对齐），
   先砍掉「无判断槽的题也挂槽」那一片。
3. 样本 C 不是合格对照——它压根没走 episode 路（无 `continuous-episode.json`，33s），
   证明不了「同题型无信号则不挂」。**E 才是合格对照**，已补。

## 6. 本轮不涉及

未跑 `--semantic` 严格模式；未测 `market_forecast` / `event_forecast` 回归（离线钉 2 已覆盖
逐字段不变）；8796 / 8802 未动。
