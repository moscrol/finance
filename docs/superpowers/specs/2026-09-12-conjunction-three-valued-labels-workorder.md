# 工单 #49：合取式标签的三值逻辑——「确定为假」不该被记成「不知道」

> 日期：2026-09-12
> 上游：OPT-10 最小闭环（走真实跨日闭环时暴露）；`LABEL_VERSION` v4 → v5
> 分支：`feat/method-closed-loop`
> 关联：#42 晋升认证（收据同日三段互相覆盖，一并修）、#48 OPT-05（依赖门）

## 0. 一句话

`dual_red_strict` / `diff_ratio_turn_up` 的 SQL 把「任一输入缺失」一律传播成 NULL，丢掉了合取式
三值逻辑里 `FALSE AND unknown = FALSE` 这半边——**已经能确定为假的行被记成「不知道」**，于是
每个交易日都留下约 8 个 unknown 成员，方法验证按纪律把整个信号日判成数据不足（18 个信号日
作废 16 个），方法永远攒不够样本。判 1 的条件一字未动，这不是放宽口径。

## 1. 根因（实测，2026-09-12）

走 OPT-10 最小闭环时，`method_validation status` 显示双红方法「历史演练 77 个适用阶段日、
18 个信号日、**可配对仅 2 天**」，16 天判 `数据不足`，原因清一色 `unknown_label`、未知成员数
稳定在 8–10。顺着查下去：

1. `history_labels` 里 `dual_red_strict` / `dual_red_streak` 各有 2,534 行 `value_num IS NULL`，涉及 231 个实体。
2. 主库**有行**，是「行在、值为 NULL」的空壳形状（行数审计抓不到）。
3. 缺的是 `diff_ratio`：**8 个 `.TI` 板块**（汽车服务及其他 / 玻璃玻纤 / 长安汽车 / 小米汽车 /
   财税数字化 / 维生素 / 房屋检测 / 华为数字能源）从 2025-01-02 到 2026-02-27 **全程 277/277 天**
   缺该字段，2026-02-27 之后治愈（`.TI` 的 `diff_ratio` 非空率：2025 各季 96.4% → 2026-Q2 起 100%）。
4. 但双红是**三条件合取** `pct_chg>0 AND diff_ratio>10 AND amount>500`。抽 2025-08-06 那天的 8 个成员，
   `amount` 分别是 57.85 / 24.9 / 967.96 / 512.92 / 306.42 / 216.16 / 75.83 / 182.99——**6 个低于阈值 500，
   不必知道 `diff_ratio` 就能确定不是双红**，却全被记成 NULL。

`labels.py` 原写法：

```sql
WHEN is_gap OR pct_chg IS NULL OR diff_ratio IS NULL OR amount IS NULL THEN NULL   -- ← 显式 NULL 传播
WHEN pct_chg > 0 AND diff_ratio > 10 AND amount > 500 THEN 1
ELSE 0
```

## 2. 改法

两个标签都改成「先判确定为假，再判不可知」，`turn_up` 另把**结构前提**与合取项分层：

```sql
-- dual_red
WHEN is_gap THEN NULL                                             -- 该日数据整体不可信（刻意设计，保留）
WHEN pct_chg <= 0 OR diff_ratio <= 10 OR amount <= 500 THEN 0      -- 任一已知条件为假 → 确定为假
WHEN pct_chg IS NULL OR diff_ratio IS NULL OR amount IS NULL THEN NULL
ELSE 1

-- turn_up
WHEN is_gap THEN NULL
WHEN prev_idx IS NULL OR idx - prev_idx <> 1 OR prev_is_gap THEN NULL   -- 结构前提：没有可比的前一交易日
WHEN prev_diff > 0 OR diff_ratio <= 0 THEN 0                            -- 前提成立后才谈合取
WHEN prev_diff IS NULL OR diff_ratio IS NULL THEN NULL
ELSE 1
```

`streak` 不动：它依赖 `dual_red`，后者 NULL 变少它自然跟着变好；`is_break` 对 `NULL` 与 `0`
同样断开，连续段语义不变。`amount_rank_top10` 是单条件，无合取问题。

## 3. 验收

- [x] `test_conjunction_labels_use_three_valued_logic` 六格逐一钉：三种「已知即可判假」→ 0；
  「已知的都为真但有缺失」→ NULL；全已知 → 1 / 0；`streak` 跟随；`turn_up` 两种判假路径；
  结构前提缺失仍 NULL。
- [x] 变异测试：把 SQL 改回 v4 写法 → 该测试红（清 `__pycache__` 后复跑，非缓存假绿）；恢复后绿。
- [x] 方法论三文件 125 passed；ruff 0。
- [x] 真库效果量化（`build-labels` 到 `/tmp/v5lab` 临时库比对，**共享库未动**）：
  - `dual_red_strict` / `dual_red_streak` 的 NULL 从 **2,534 → 568**（−77.6%）；
  - `diff_ratio_turn_up` 几乎不变（3,389 → 3,380）——它的 NULL 主要来自结构前提，那是真不可判，本就不该变；
  - 双红方法的「干净信号日」（全宇宙无 unknown 成员）**2 → 5**（与 `method_validation status` 报的
    「可配对 2 天」逐字对上）；逐日未知成员数从 8–10 降到 0–4。
  - **仍 < `min_n=20`**：修复把本来就该有的样本还回来了，没有、也不该拆掉样本墙。

## 3.1 一个留给用户的口径问题（本单不改）

剩余 13 个信号日各有 1–4 个真不可判成员（占宇宙 221 的 0.5%–1.8%），method_validation 按纪律
把整天判成数据不足。spec OPT-05 的 `gap_policy` 允许规则声明 `skip`（排除该成员并在 coverage
里报）而不是隐式 `break`（整天作废）。两种口径的读数差：**整天作废 5 天可配对 / 排除成员
18 天可配对**（仍 < 20）。这是会改变方法学结论的口径选择，不是正确性问题，**留给用户定**，
本单不动。

## 4. 连带影响

- **`LABEL_VERSION` v4 → v5**：按 #42 认证门，标签语义变化开启新验证轮次，旧收据保留为历史
  观察、不跨轮拼接。这是预期后果不是回归。
- **共享旁路库 `db/history_labels.duckdb` 需重建**（有副作用、写共享库，**等用户点头**）。
  重建后四条种子规则与双红方法的读数都会变——变的是「原先被 NULL 吞掉的样本回来了」。
- **`v5` 号与 PR #673 的关系**：#673（`feat/methodology-backtest-p1-lifecycle-stage`）被 #737 退回时
  预写方案是「rebase 升 v5」，但其分支上仍是 v4、尚无实现。本单先落 v5 并已在 #673 留言；
  #673 重做时改用 v6，或与本单合并重建一次。

## 5. 同单一并修：收据同日三段互相覆盖

`write_receipt` 原本按 `<date>.json` 命名、「同日重跑覆盖」。#42 引入 `declared_stage` 后，
「同一天跑完 discovery / validation / holdout」成了合法且常见的场景（历史回填时三段窗口都在
过去），但三份收据同名互删，只剩最后一份，`lifecycle._stage_ladder` 永远凑不齐三级——三段链
只能靠「跨三天跑」建起来。改成 `<date>[-<stage>].json`；同日**同段**重跑仍覆盖（取最新，
OPT-04「同窗重跑取最新」不变）；无 `declared_stage` 的收据保持旧名，旧目录逐字节不受影响。
回归 `test_same_day_three_stages_do_not_overwrite_each_other`。
