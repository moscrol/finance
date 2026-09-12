# feat/method-closed-loop · 工单 #49（合取式标签三值逻辑 + 收据同日三段）

## 状态：**等用户确认合入**（复核两轮共八条缺口已全部修完并复验，全量 9417P/0F）

第二轮四条 + 第三轮四条，逐条用复核留下的反例脚本复现 → 修在源头 → 复验。
共享库仍未重建、迁移方案已按实测重写但未执行。

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
   （**第二轮复核后改法更进一步**：任何一次运行都不再被覆盖，见下文 P1-1。）

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
- 全量等价 CI：ruff 全过 + **9413 passed / 0 failed / 77 skipped / 1 xfailed**（基线 gitea/main@6382c13b，含复核修复）。
- 新回归：`test_conjunction_labels_use_three_valued_logic`（六格逐一钉三值逻辑 + 两类仍须 NULL），
  收据相关的三条见下文复核段。
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
- 剩余「真不可判」成员的处置见下文复核段（`skip` 那处引用已更正）。

## 复核修复（09-12 第二轮）

| # | 缺口 | 修法 | 回归 |
|---|---|---|---|
| P1-1 | 写入层**删除**运行记录 → 留出窗 refuted 后同日换窗重跑 supported 直接晋升；同窗 refuted→supported 也绕过重验 | 文件名 `<date>[-<stage>]-<HHMMSS>-<hash4>`：时刻求唯一，内容 hash 解「同一秒内 run 紧接 scan」的撞名，同内容原样重写仍幂等。证伪库 / scan 汇总同规矩 | `test_same_day_three_stages…`、`test_same_window_rerun_keeps_both_runs…`、证伪库「scan 不覆盖 run」端到端 |
| P1-2 | 「升级后旧收据自动成历史观察」未实现：`derive_state` 只比收据**彼此**的 `label_version`，三份 v4 在 v5 代码下照样成链；重建库不触发失效 | 加 `current_label_version` 绝对检查，`queue` / `state_for_rule` 传 `labels.LABEL_VERSION` | `test_stale_label_version_receipts…`、`StateForRule::test_default_current_label_version_blocks_stale_receipts` |
| P2-3 | `river_derive` 双红绑定仍是旧 NULL 传播，与标签层同名同版本给出两种真值、无人报错 | 同步三值逻辑 | 新增 `test_label_binding_parity.py` 7 格逐格比对两条路径；变异（改回 NULL 传播）确认能抓到 |
| P2-4 | `report` 按文件名字典序取「最近收据」，`holdout` < `validation` 导致永远选 validation | 改按 `generated_at` 取 | 手工验证：同日 validation(11h,supported) + holdout(12h,refuted) → 取到 holdout |

复现脚本对修复后代码重跑：三条 P1 场景全部从 `personal_method` 变 `candidate`，且四份收据
全部留档。全量 **9413 passed / 0 failed**（基线 gitea/main@6382c13b）。

**工单 §3.1 更正一处引用**：`gap_policy` 的 `skip` 是**天**维度（累计时跳过缺天，对连续量
还明确拒绝），不是成员维度的排除授权；成员排除在现有契约里没有条款。若将来要做，按
敏感性对照做：规则预先固定、三臂同一套有效成员范围、覆盖率随读数报、主结论不动——
且不能用「18 天接近 20 天」当理由（缺失集中在长安汽车 / 小米汽车这类高成交额标的，
恰是双红容易命中的一类，排除可能系统性改变方向）。

## 复核修复（09-12 第三轮）

第二轮的修法被证明还不够——四位 hash 会撞、秒级时间戳丢顺序：

| # | 缺口 | 实测反例 | 修法 |
|---|---|---|---|
| 1 | 同秒重跑仍误晋升 | `generated_at` 截到秒 → 同秒两份逐字相同 → 排序退化到文件名 → 后缀是内容 hash → 谁更晚由 hash 随机决定。先 supported、同秒稍后 not_distinguishable，读取端选回 supported | 时间戳提到**微秒**；`lifecycle._chronological_key` 与 `latest_receipt` 改按**解析后的时刻**排序（裸字符串在秒级/微秒级混排时 `+` 与 `.` 的字典序是巧合），文件名只作同刻 tiebreak |
| 2 | 迁移方案第二步执行不通 | 三道门各自独立拒绝：`validate_protocol` 对 v3 协议直接拒（与库无关）、`_check_sources` 要求库**绝对路径**与冻结值一致（换备份即拒）、备份水位停在 9/10 算不出 D+5。且清点后**待回检 = 0** | 方案重写：旧协议直接封存不跨版本结算，新协议在 v5 库另起。订正初版「在途回检已断」的夸大 |
| 3 | 四位 hash 仍覆盖失败记录 | 两份结论相反的收据同得 `120000-c62b`，四写只剩三份，`contradicted` → `personal_method` | 摘要用 sha256 前 **32 位**（128 bit）；并加 `_guard_no_silent_overwrite`：同名比内容，相同则幂等跳过、不同则抛 `ReceiptCollision`。**唯一性不靠长度赌，闸才是兜底** |
| 4 | Workbench 入口漏接版本门 | `method_validation_note` 直接调 `derive_state` 不传身份参数：同一组旧收据 `state_for_rule` 说 candidate、它说 personal_method | 统一走 `state_for_rule`（同时锁规则文件字节 sha256 与当前标签口径） |

新增回归：`test_same_second_runs_keep_their_order`、`test_write_receipt_refuses_silent_overwrite`、
`test_receipt_stem_never_collides_across_distinct_contents`（3000 份不同内容零碰撞）、
`test_method_validation_note_honours_label_version_gate`（两入口同答案）。
复核的 `reproduce.py` 对修复后代码重跑：碰撞段 2000 次找不到碰撞、同秒段取到时间上更晚的
那份、产品入口两边都是 candidate。全量 **9417 passed / 0 failed**。

## 迁移欠账（本单只写方案，未执行）

`docs/superpowers/specs/2026-09-12-label-version-migration-plan.md`（**第二版**）。协议 `475597e2…`
绑定 **v3**、共享库 **v4**、代码 **v5**。**这是 #671 升 v4 时欠下的债，不是本单引入。**

真实待办清点（初版漏了这步）：history 1 份、capture **1 份**、recheck 1 份且已判
`stage_not_applicable`、**待回检 0**。所以真实状况是「新的 capture 跑不了」，不是
「有对象卡在半路」——初版那句「在途回检已断」是夸大，已订正。

方案：① 备份 v4 库只读留档 → ② 旧协议写 `superseded`（含「待回检 = 0」）→ ③ 重建到 v5
→ ④ 新协议 `forward_start` = **max(重建日, 实际登记日) 的次个交易日**（固定成「重建日次日」会在③④之间停过周末时被 register 拒）→ ⑤ 种子规则按阶段重跑。①② 不依赖本单合入。
另立两单：`status` 打印口径对照；协议改记库的**身份**（label_version + 内容指纹）而非
绝对路径，否则库一搬家就永久失配。

## 下一步
1. 用户确认合 PR。
2. 共享库重建**按迁移方案分步走**，每步可停；①②③ 不依赖本单合入。
3. 成员排除若要做，按敏感性对照另立单，主结论不动。
4. #673 重做时改 v6 或与本单合并重建一次。
5. 另立单：`method_validation status` 打印口径对照，避免下次升版再悄悄断掉在途实验。
