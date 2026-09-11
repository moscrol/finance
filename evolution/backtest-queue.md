# 回测队列 —— 待标定的单点阈值（人工登记，非自动流水线）

**这个文件补的是一处悬空引用**：`intelligence/services/reading_baseline.py:21` 写
「数字走 `evolution/` 回测队列，标定后才允许升格为硬判据」，
`docs/learning/reading-rules-inventory-2026-08-19.md`（§1 表、§326）也写「B 类数字进
`evolution/` 回测队列」——但在 2026-09-11 之前，`evolution/` 下**没有这个队列**，
只有策略 1/3/4 的参数（`params.json`）与自动生成的调参建议（`suggestions/`）。
于是「进队列」实际等于「写在文档里没人接」。这里把它落成一张明账。

## 与 `suggestions/` 的区别

| | `suggestions/` | 本文件 |
|---|---|---|
| 谁写 | `scripts/evolve.py suggest` 自动生成 | 人工登记 |
| 内容 | 策略 1/3/4 已有参数的网格回测结果 | **还没有值**的阈值：谁要用、口径是什么、凭什么算过 |
| 出口 | 改 `params.json` + 升 version | 改对应模块常量 + 在此记一行结论 |

## 纪律（三条，与 reading_baseline 同一套）

1. **结构先行**：机制先实现，阈值位留空（`None` / 关闭态），不拿候选值上生产；
2. **口径先固定**：同一批数据在不同口径下会读出不同数字，不写清口径的回测请求不受理；
3. **人工确认才落数**：回测只出建议，填数是人的动作，并在此登记依据。

---

## Q-001 · 召回降权阈值（`user_memory.RELIABILITY_DOWNWEIGHT_THRESHOLD`）

- **登记日**：2026-09-11
- **来源**：`docs/superpowers/specs/2026-09-10-knevo-arch-delta-worklist.md` W3（P2）
- **现状**：机制已实现并有单测（`reliability_downweight` / `judgment_reliability`），
  阈值为 `None` = **功能关闭**。关闭态下召回排序与警告行逐字节不变。
- **要回答的问题**：同类判断的历史计分率低到多少，才值得在召回时压低它的排序并附警告行？

### 口径（已固定，不再讨论）

| 项 | 定 |
|---|---|
| 指标 | **计分率** = `checkpoints.CategoryStat.hit_rate` = `score_sum / n` |
| partial | 计 0.5（`checkpoints.SCORE_MAP`） |
| 分母 n | 已**终态**裁决数（hit/partial/miss）；`unverifiable` 不进分母 |
| 排除项 | `hindsight=True` 的 checkpoint 已在 `calibrate()` 里剔除，不进分母 |
| 生效双闸 | `score_rate < 阈值` **且** `n ≥ PEER_HIT_MIN_N`（KC-11 同一闸） |
| 分类维度 | `by_category`（二阶推演类别）；`resolve_judgment_category` 解析为 None 的记录不降权 |

> **为什么必须先固定**：主干同时存在两种命中率读法——`PEER_HIT_LINE` 按整命中计
> （partial 进分母不进分子），校准器按计分率计。同一组「4 命中 + 6 部分命中」
> 前者读 40%、后者读 70%。不钉死驱动口径，同一个阈值会得出相反的降权结论。
> 本项已定：**降权只看计分率**；`PEER_HIT_LINE` 保持整命中，仅作展示。

### 回测怎么算过

- 样本：`users/<user>/checkpoints.jsonl` × `verdicts.jsonl` 的已终态记录，按 category 分桶；
- 候选值：0.3 / 0.4 / 0.5（0.4 是 `CategoryStat.reliability` 现有的「偏差大」边界，
  但该边界本身也没回测过，**不得直接沿用当默认**）；
- 判据：降权后，被压到后面的判断在后续裁决里确实继续低于均值（否则是噪声）；
  且达到 `min_n` 的类别数足够（类别桶太少时整个问题不成立，应先攒样本）。
- ~~**阻塞项**：当前 per-user 台账的已终态样本量是否够分桶回测，尚未量过。~~
  **已量（2026-09-11），结论：不足 → 继续留在关闭态。** 见下节。

### 测量记录 · 2026-09-11（样本量：**不足**）

口径同上，直接复用 `checkpoints.load_calibration()` 出数，**不另写一套统计**——
本项的全部意义就是口径唯一，自己再实现一遍聚合等于给漂移开口子。

本机 `FORESIGHT_USERS_DIR=~/.local/share/finance-workbench/users`。全部 user 目录里
只有两个有 `checkpoints.jsonl`，其余均为探针/实验 user（`probe-*` / `tracediff-*` / `fsr*` 等）：

| user | checkpoints | verdict 行 | 已终态 n | 待回检 | unverifiable | hindsight 剔除 | category 桶 | 达 min_n(=10) 的桶 |
|---|---|---|---|---|---|---|---|---|
| `linxiaoqi5111` | 84 | 210 | 80 | 4 | 130 | 0 | 2 | **1** |
| `default` | 21 | 0 | 0 | 8 | 0 | 0 | 0 | 0 |

`linxiaoqi5111` 的分桶读数（唯一有终态样本的台账）：

| category | n | hit | partial | miss | 计分率 | ≥min_n |
|---|---|---|---|---|---|---|
| 生命周期推演 | 78 | 7 | 0 | 71 | **0.090** | ✓ |
| duckdb_flow/市场路径 | 2 | 0 | 0 | 2 | 0.000 | — |

**结论：不足，`RELIABILITY_DOWNWEIGHT_THRESHOLD` 继续留 `None`。** 三条理由，任一条单独成立即否决：

1. **只有 1 个桶达 min_n**。判据写的「达到 `min_n` 的类别数足够」不成立——
   分桶回测的前提是桶之间可比，1 个桶没有「之间」。
2. **三个候选值在这份数据上无法区分**。0.3 / 0.4 / 0.5 触发的都是同一个桶
   （0.090 < 0.3），降权行为逐字节相同。此时填任何一个数都不是「回测选出来的」，
   是「随便挑的」——正是本文件纪律 3 要挡的那个动作。
3. **召回侧影响面为 0**。`linxiaoqi5111` 的召回池 `judgments.jsonl` 只有 1 条，
   `resolve_judgment_category` 解析为「前瞻判断」，而校准里没有这个桶，
   走 `stat is None` 分支 → 不降权。**今天把阈值填上，召回结果一个字都不会变。**

另有一条**不构成否决、但必须记下**的观察：那 78 条终态样本全部是
`object_type=agent_judgment` 且 `source=logic_lifecycle`，即**单一机器来源批量产出**。
就算将来攒够桶数，也要先回答「这是不是同一个模块在自己跟自己比」——
相关样本不能当独立样本用（与 `feat/methodology-correlated-samples` 是同一个坑）。

> 顺带记一笔、但**不要在这条线上顺手处理**：0.090 本身是个信号（`logic_lifecycle`
> 产的 78 条只命中 7 条）。那属于 `by_source` 维度的模块降级——「命中率长期不达标的
> 模块应降为资料工具」，是另一条闸，别混进召回降权。

**复现（只读，不写任何文件）**：

```bash
cd <repo> && PYTHONPATH=. .venv-workbench/bin/python -c "
from intelligence.services import checkpoints as C
from intelligence.services import user_memory as UM
from intelligence import userspace
us = userspace.user_space('linxiaoqi5111')
cal, _ = C.load_calibration(us.checkpoints_path, us.verdicts_path)
print('scored', cal.scored, '/ min_n', UM.PEER_HIT_MIN_N)
for s in cal.by_category:
    print(f'{s.category}  n={s.n}  rate={s.hit_rate:.3f}  ok={s.n >= UM.PEER_HIT_MIN_N}')
"
```

**下次什么时候再量**：等 **≥2 个 category 桶各自达 min_n**，且召回池里有能解析到这些桶的
记录（否则测得再准也没有作用对象）。在此之前重量一次仍是同样结论，不必反复跑。

### 关闭条件

填数后在此登记：阈值、依据（样本量 + 分桶读数）、确认人、日期；
并把 `intelligence/tests/test_user_memory.py::ReliabilityDownweightTests::
test_threshold_defaults_to_none_until_backtested` 的断言一并更新（它现在故意钉死 `None`）。
