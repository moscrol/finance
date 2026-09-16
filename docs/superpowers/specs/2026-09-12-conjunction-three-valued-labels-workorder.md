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

## 3.1 剩余「真不可判」成员怎么办（本单不改，只记录）

修完之后仍有 13 个信号日各带 1–4 个真不可判成员（`amount` 与 `pct_chg` 已知为真、`diff_ratio`
缺失，确实不知道是不是双红），占宇宙 221 的 0.5%–1.8%；`method_validation` 按纪律把整天判成
数据不足，可配对 5 天。

**更正一处引用**：先前写的「spec OPT-05 的 `gap_policy` 允许声明 `skip`（排除该成员）」不准确。
`river_derive` 的 `gap_policy ∈ {unverifiable, break, skip}` 说的是**天**维度——`skip` 指
「累计时跳过缺天并在 coverage 里报」，对连续量还明确拒绝；它不是「排除成员」的授权。
成员维度的排除在现有契约里**没有**对应条款。

**若将来要做成员排除，按敏感性对照做，不动主结论**：

- 规则**预先固定**（进协议、不可事后调），三个臂使用**同一套**有效成员范围，否则比较总体被改了；
- 覆盖率（排除了几个 / 占比 / 是哪些）随读数一起报；
- 主结论仍用「整天作废」口径，排除口径只作并排的敏感性列；
- **不能用「18 天接近 20 天」当切换理由**——缺失只占 1% 也可能集中在关键成员（这 8 个板块
  里有长安汽车、小米汽车这类高成交额标的，恰恰是双红容易命中的那一类），排除它们可能
  系统性改变结论方向，而不是随机地少几个样本。

## 4. 连带影响

- **`LABEL_VERSION` v4 → v5**：按 #42 认证门，标签语义变化开启新验证轮次，旧收据保留为历史
  观察、不跨轮拼接。这是预期后果不是回归。
- **共享旁路库 `db/history_labels.duckdb` 需重建**（有副作用、写共享库，**等用户点头**）。
  **以迁移方案 `2026-09-12-label-version-migration-plan.md` 为准**（那份是第二版，按实测重写；
  本节只给指针，不复述步骤——初版的步骤已被证明不可执行，留在两处会让接手者照旧走）。
  一句话现状：在跑的前向协议 `475597e2…` 绑定 **v3**、共享库 **v4**、代码 **v5**，
  **待回检对象为 0**（唯一那次观察已结算为 `stage_not_applicable`），所以旧协议直接封存、
  不尝试跨版本结算。**这是 #671 升 v4 时欠下的债，不是本单引入。**
- **`v5` 号与 PR #673 的关系**：#673（`feat/methodology-backtest-p1-lifecycle-stage`）被 #737 退回时
  预写方案是「rebase 升 v5」，但其分支上仍是 v4、尚无实现。本单先落 v5 并已在 #673 留言；
  #673 重做时改用 v6，或与本单合并重建一次。

## 5. 同单一并修：收据写入不再删除任何一次运行

`write_receipt` 原本按 `<date>.json` 命名、「同日重跑覆盖」，两个缺口：

1. #42 引入 `declared_stage` 后，「同一天跑完 discovery / validation / holdout」成了合法且
   常见的场景（历史回填时三段窗口都在过去），但三份收据同名互删，`lifecycle._stage_ladder`
   永远凑不齐三级——三段链只能靠「跨三天跑」建起来。
2. **更要命的是同段重跑会物理删掉上一次结果**（09-12 复核指出，已复现）：留出窗判 refuted
   之后当天换个窗口重跑判 supported，失败那份被覆盖，「同阶段两个不同窗口 = 事后挑窗」
   检测**没有证据可查**，直接晋升 `personal_method`；同窗 `refuted → supported` 也能绕过
   重新验证。**「采用最新结果」≠「删除旧结果」**——取最新是读取层的事（`_stage_ladder`
   已按 `generated_at` 取同窗最新），写入层照做就成了抹掉失败记录。

改法（第三轮复核后的最终形态）：

- **时间戳精度提到微秒**（`_now_iso` 原本 `timespec="seconds"`）。秒级会把「同一秒内两次
  运行」的先后彻底抹掉，读取端排序退化到文件名，而文件名后缀含内容 hash——于是「谁更晚」
  由 hash 随机决定。实测：先 supported、同秒稍后 not_distinguishable，读取端选回 supported，
  生命周期停在 personal_method。
- **排序按解析后的时刻**（`lifecycle._chronological_key`、`latest_receipt`），文件名只作
  同一时刻内的稳定 tiebreak。裸字符串比较也不行：秒级 `…T12:00:00+00:00` 与微秒级
  `…T12:00:00.500000+00:00` 在 `+` 与 `.` 上的字典序先后是巧合不是语义。
- **文件名 `<date>[-<stage>]-<HHMMSSffffff>-<sha256 前 32 位>`**：时刻定先后，摘要定身份。
  4 位摘要那版**实测撞了**（两份结论相反的收据同得 `120000-c62b`，四次写入只剩三份，
  状态从 contradicted 变回 personal_method）——16 bit 撑不起「内容不同必不同名」。
- **原子创建 + 同名比内容，禁止静默覆盖**（`_write_exclusive`）：用 `O_CREAT | O_EXCL` 让
  「不存在才创建」由内核一次完成，同名且内容相同 → 幂等跳过，内容不同 → 抛
  `ReceiptCollision`。唯一性不靠摘要长度赌，这道闸才是兜底。
  第四轮复核补齐三处：① 原本是「先 `exists()` 再 write」的 check-then-act，并发下两个
  写手可以都通过检查、后者覆盖前者（线程池实测）；② `write_scan_summary` 完全没接闸；
  ③ json 与 md **各自**判幂等——只有 json 落盘、md 写失败时，原样重试必须补上 md，
  不能因为 json 在就整体当成功返回（文件写入故障注入实测）。

证伪库 `write_refuted` 与扫描汇总 `write_scan_summary` 同规矩——证伪是资产，同日再跑一次
不该把上一条从库里抹掉。

另有一处一并对齐：`report` 的「最近收据」也改用 `receipts._parse_ts`。`12:00:00Z` 与
`12:00:00.500000+00:00` 都是合法 ISO UTC，字符串序与时间序相反，三个读取口径
（`load_steps` / `latest_receipt` / `report`）不能各用各的比法。

回归十条：`test_same_day_three_stages_do_not_overwrite_each_other`、
`test_same_window_rerun_keeps_both_runs_and_takes_the_latest`、
`test_same_second_runs_keep_their_order`、`test_write_receipt_refuses_silent_overwrite`、
`test_receipt_stem_never_collides_across_distinct_contents`（3000 份不同内容零碰撞）、
`test_concurrent_writes_cannot_overwrite_each_other`、`test_scan_summary_also_refuses_overwrite`、
`test_retry_repairs_a_half_written_pair`、`test_mixed_timestamp_forms_order_consistently`、
`test_method_validation_note_does_not_cross_rule_versions`，
以及证伪库「scan 不覆盖 run」的端到端断言。

## 6. 同单一并修：认证要比对**当前生效**的标签口径

`derive_state` 原本只比较收据**彼此之间**的 `(rule_version, rule_sha256, label_version)` 变化。
于是「升级后旧收据自动成为历史观察」这句话并不成立：三份同为 v4 的成功收据在 v5 代码下
彼此一致，照样成链、照样 `personal_method`，要等到有人跑出第一份 v5 收据才切轮次；**重建
旁路库本身不触发失效**（09-12 复核指出，已复现）。

加 `current_label_version` 参数（`queue` 传 `labels.LABEL_VERSION`，`state_for_rule` 默认取它），
口径不符的收据一律降历史观察并在 `blocked_by` 里写明旧口径与当前口径。

**产品入口要一起接**：Workbench 的 `episode_factory.method_validation_note` 原本直接调
`derive_state` 且两个身份参数都不传，于是同一组旧收据 `state_for_rule` 说 candidate、
Workbench 说 personal_method（第三轮复核）。但改走 `state_for_rule` 还不够——它会自己挑
「version 最大那份」，于是「按标题匹配到 v1、却拿 v2 的状态去展示 v1」（第四轮复核实测）。
最终改为新增 `lifecycle.state_for_file(rule_path, ...)`：身份锁在**匹配到的那一份**规则文件
的字节上。**匹配、认证、展示必须是同一份规则。**

回归：`test_stale_label_version_receipts_are_history_not_evidence`（不传 → 旧行为成链；
传 → 全降历史观察）、`StateForRule::test_default_current_label_version_blocks_stale_receipts`、
`test_method_validation_note_honours_label_version_gate`（两个入口给同一答案）。

## 7. 同单一并修：另两处消费端

- **`river_derive._bind_dual_red_strict` 同步三值逻辑**：同名同版本的标签走两条路径（标签层
  SQL 供规则编译器、River 绑定供情景树分枝与区间派生），口径不一致时两边给出不同真值且
  没有任何地方会报错。新增 `test_label_binding_parity.py` 把同一组输入喂两条路径逐格比对
  （7 格覆盖三值逻辑每一种结局），变异测试确认能抓到不一致。
- **`report` 的「最近收据」按 `generated_at` 取**，不按文件名字典序：新文件名下同日的
  `holdout` 字典序在 `validation` 之前，字典序会永远选中 validation，即使稍后跑的 holdout
  已经把它证伪了。
