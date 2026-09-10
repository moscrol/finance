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
- **阻塞项**：当前 per-user 台账的已终态样本量是否够分桶回测，尚未量过。
  量出来不够就**继续留在关闭态**，不许为了「机制看起来在跑」而拍一个数。

### 关闭条件

填数后在此登记：阈值、依据（样本量 + 分桶读数）、确认人、日期；
并把 `intelligence/tests/test_user_memory.py::ReliabilityDownweightTests::
test_threshold_defaults_to_none_until_backtested` 的断言一并更新（它现在故意钉死 `None`）。
