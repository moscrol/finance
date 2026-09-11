# feat/method-closed-loop · 工单 #49（合取式标签三值逻辑 + 收据同日三段）

## 这个分支做什么
走 OPT-10「用一条现有方法跑完真实跨日闭环」时抓到的两个真缺陷，都修在源头：

1. **合取式标签丢了三值逻辑**（`labels.py`，`LABEL_VERSION` v4→v5）：`dual_red_strict` /
   `diff_ratio_turn_up` 把「任一输入缺失」一律传播成 NULL，丢掉 `FALSE AND unknown = FALSE`
   那半边——已经能确定为假的行被记成「不知道」。改成「先判确定为假、再判不可知」；
   `turn_up` 另把**结构前提**（无相邻前一交易日 / 前一日 gap）与合取项分层。判 1 的条件
   一字未动，不是放宽口径。`data_gap` 日仍整日 NULL。
2. **收据同日三段互相覆盖**（`receipts.py`）：#42 引入 `declared_stage` 后「同一天跑完
   discovery / validation / holdout」是合法且常见的场景（历史回填时三段窗口都在过去），但
   文件名只有日期粒度，三份同名互删只剩最后一份，`lifecycle._stage_ladder` 永远凑不齐三级。
   改 `<date>[-<stage>].json`；同日**同段**重跑仍覆盖；无 stage 的收据保持旧名。

## 怎么找到的（可复现路径）
`method_validation status` 报双红方法「77 个适用阶段日、18 个信号日、**可配对仅 2 天**」，
16 天判数据不足、原因清一色 `unknown_label`、未知成员稳定 8–10 → 查 `history_labels` 有
2,534 行 `value_num IS NULL` → 主库**有行、值为 NULL**（行数审计抓不到的空壳）→ 缺的是
`diff_ratio`，**8 个 `.TI` 板块 2025-01-02→2026-02-27 全程 277/277 天**缺该字段（2026-Q2 起治愈）
→ 但双红是三条件合取，抽 2025-08-06 那 8 个成员，`amount` 有 6 个低于阈值 500，**不必知道
`diff_ratio` 就能确定不是双红**。

## 决策与被否方案
- 只把「确定为假」从 NULL 改回 0；否了「放宽判 1 的条件」——那是改口径不是修 bug。
- `turn_up` 的结构前提保留 NULL；否了「一律套三值逻辑」——没有可比的前一日时，「由负转正」
  这个概念本身不成立，那是真不可判。
- `streak` / `amount_rank_top10` 不动：前者依赖 `dual_red`（NULL 变少自然跟着好，且 `is_break`
  对 NULL 与 0 同样断开，连续段语义不变），后者是单条件无合取。
- 用 `v5`；否了让给 #673——#673 被退回后分支上仍是 v4、尚无实现，已在其 PR 留言请改 v6 或合并重建。
- **不动共享旁路库**：量化在 `/tmp/v5lab` 临时库做。重建 `db/history_labels.duckdb` 是写共享库的
  副作用操作，等用户点头。

## 已验证
- 全量等价 CI：ruff 全过 + **9408 passed / 0 failed / 77 skipped / 1 xfailed**（基线 gitea/main@6382c13b）。
- 新回归两条：`test_conjunction_labels_use_three_valued_logic`（六格逐一钉三值逻辑 + 两类仍须 NULL）、
  `test_same_day_three_stages_do_not_overwrite_each_other`（三份共存 → 链到 personal_method；同段重跑
  覆盖取最新 → contradicted；无 stage 保持旧名）。
- **变异测试**：把 SQL 改回 v4 写法 → 三值逻辑测试红（清 `__pycache__` + sleep 后复跑，非缓存假绿）；恢复后绿。
- 临时库实测（共享库未动）：`dual_red_strict` NULL **2,534 → 568**（−77.6%）；`turn_up` 3,389 → 3,380
  （几乎不变，它的 NULL 主要来自结构前提，本就不该变）；双红方法干净信号日 **2 → 5**，逐日未知成员
  8–10 → 0–4。**仍 < min_n=20**。

## 本轮闭环实跑读数（历史验证半边，v4 共享库上）
四条种子规则切三段不重叠窗口（discovery 2024-12-20→2025-09-30 / validation 2025-10-01→2026-04-30 /
holdout 2026-05-01→2026-09-10），`scan` 带 BH，四条**每段都未过门**。其中一个值得记的实例：
`limit_heat_rank_jump_3d` 在 holdout 段 Wilson [50.8%, 54.0%] 判 supported、BH adjusted_p=5.9e-17
（看起来铁证），**但块 bootstrap 区间 [40.5%, 64.1%] 包含基准 45.4%** → 合成后 not_distinguishable。
3,688 个事件只发生在 77 个交易日（25 个块），两种区间宽度差 7 倍。这是 OPT-05 在真实数据上抓到的
第一个「BH 拦不住的伪显著」——BH 管多重检验，管不了样本相关性。
（#737 记的「v4 上 limit_heat 全窗翻 supported」也由此得到解释：那是窗口选择 + 相关样本共同撑起来的。）

## 未验证 / 已知边界
- 共享旁路库未重建，所以线上读数仍是 v4 口径。
- 闭环的**前瞻半边**（预登记 → 到期回检）已由 `method_validation` 在真实运行（协议 475597e2，
  前向自 2026-09-10），本单未改它；剩余 13 个信号日各有 1–4 个真不可判成员，按纪律整天作废。
- **留给用户的口径问题**（工单 §3.1）：spec OPT-05 的 `gap_policy` 允许 `skip`（排除成员 + 报覆盖率）
  而非隐式 `break`（整天作废）。两种口径：**5 天可配对 / 18 天可配对**（都 < 20）。会改变方法学结论，
  不是正确性问题，本单不动。

## 下一步
1. 用户确认合 PR；合后按需重建共享旁路库（`build-labels` → `outcomes` → 四规则重跑），
   重建后所有 v4 收据按 #42 认证门变历史观察，需按阶段重跑。
2. `gap_policy` 口径拍板。
3. #673 重做时改 v6 或与本单合并重建一次。
