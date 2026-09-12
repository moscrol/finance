# feat/method-closed-loop · 工单 #49（合取式标签三值逻辑 + 收据同日三段）

## 状态：**第五轮修复待复验**（前四轮十三条已收；09-12 独立质检又开三条）

第二轮四条 + 第三轮四条 + 第四轮五条，逐条用复核留下的反例脚本复现 → 修在源头 → 复验。
共享库仍未重建、迁移方案已按实测两次重写但未执行。

**9422P / 0F 是 `29b07912` 那一刻的数，不是放行结论。** 独立质检
（`docs/handoffs/2026-09-12-method-closed-loop-29b07912-review.md`）核实并采信这个数字，但用新探针
又抽出三条：P1 写入发布（原子占名 ≠ 完整发布）、P2 迁移只登记不切换、P2 本文件自相矛盾。
三条已在本分支补修（见「第五轮」），**等对新提交独立复验后再谈合入**。
原以为要另记的条件性遗留（`report --refuted` 按时间戳字符串取最新）**已在 `8bc7252b` 一并修掉**，不另开单。

**这个写入层我连改四轮才收敛**，教训记在 `~/.claude/…/memory/take-latest-is-not-delete-older.md`：
「唯一性」「先后」「兜底」是三件独立的事，指望一个字段兼顾就会反复漏。
第四轮还漏了更底层的一组：**原子占名、完整发布、不可覆盖、崩溃恢复是四个不同的承诺**；
测试必须在承诺之间的交接点暂停或终止进程，否则永远测不到。

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

## 复核修复（09-12 第四轮）

第三轮的修法里，有三处是我自己改出来的新问题：

| # | 缺口 | 实测反例 | 修法 |
|---|---|---|---|
| 1 | Workbench **串规则版本** | 按标题匹配到 v1，`state_for_rule` 却自己挑 version 最大的 v2 → 展示「v1，personal_method」，而 v1 其实是 candidate | 新增 `lifecycle.state_for_file(rule_path, ...)`，身份锁在**匹配到的那一份**文件字节上；note 记住匹配到的 `path` 而不只是 `doc`。**匹配、认证、展示必须是同一份规则** |
| 2 | 写入失败后重试**假成功** | json 落盘、md 写失败 → 原样重试因为 json 在就 `return` 两个路径，md 永远补不回来（故障注入实测） | json 与 md **各自**判幂等 |
| 3 | 防覆盖**不原子** | 「先 `exists()` 再 write」是 check-then-act，并发下两个写手都通过检查、后者覆盖前者（线程池实测）；`write_scan_summary` 完全没接闸 | 三个写入点统一走 `_write_exclusive`：`O_CREAT \| O_EXCL` 原子创建 + 同名比内容 |
| 4 | 迁移方案**不能每步可停** | 固定 `forward_start` = 重建日次日，周五重建、周一登记会被「forward_start must be after registration day」拒 | 改为 `max(重建日, 实际登记日)` 的下一个交易日，并写明**登记时才算**、不在方案里写死日期 |
| 5 | 工单**残留旧迁移指令** | 仍写「在途回检已断」「在 v3 备份库跑完剩余 recheck」，与新版方案相反 | 清掉，只留指向迁移方案的指针（步骤不在两处复述） |

顺带对齐一处复核标为「条件边界」的：`report` 的最近收据也改用 `receipts._parse_ts`——
`12:00:00Z` 与 `12:00:00.500000+00:00` 都是合法 ISO UTC，字符串序与时间序相反，三个读取
口径（`load_steps` / `latest_receipt` / `report`）不能各用各的比法。

新增回归五条：`test_concurrent_writes_cannot_overwrite_each_other`、
`test_scan_summary_also_refuses_overwrite`、`test_retry_repairs_a_half_written_pair`、
`test_mixed_timestamp_forms_order_consistently`、
`test_method_validation_note_does_not_cross_rule_versions`。

## 复核修复（09-12 第五轮 / 独立质检 29b07912 + ef9e61d2）

> P1 与坏收据告警已提交于 `8bc7252b`、`ef9e61d2`；P2（下表 3–7 条）是本次提交的内容。

质检认可 9422P/0F 的全量数字，但用新探针抽出三条。前两条的共同点：**我把「有这个动作」
当成了「这个动作生效」**——占了名不等于发布完，写了标记不等于停用。

| # | 缺口 | 实测反例 | 修法 |
|---|---|---|---|
| 1 | **P1 原子占名 ≠ 完整发布** | `O_CREAT\|O_EXCL` 先让正式文件名可见、内容随后才写。在 `os._exit(73)`（真实进程终止，`except BaseException` 的清理不执行）处中断 → 正式目录留下 **0 字节 JSON**；读取端静默跳过、派生状态停在旧值，**原内容重试反被当撞名拒绝**，人工不介入恢复不了 | 同目录 `.pending-*` 临时文件写满 → `flush`+`fsync` → `os.link` 无覆盖发布 → fsync 目录。中断只留临时文件（无 `.json` 后缀，`glob("*.json")` 读不到）。**不用 `os.replace`**：它会覆盖已有目标，破掉「失败证据不可覆盖」 |
| 2 | 坏收据**静默跳过** | 读到不可解析的收据直接 `continue`，没有任何告警 | `_warn_corrupt()` 出声；`_write_exclusive` 撞上坏文件时报「疑为旧版写入中断残留」并拒绝，**不自动覆盖也不自动删除**（可能是真证据） |
| 3 | **P2 登记 ≠ 切换** | 夜跑 `METHOD_STUDY_DIR` 写死旧协议 id；`register` 只建目录不改绑定 → 照方案登记完，夜跑仍选旧协议 | 新增 `active` 指针 + `activate` 子命令；夜跑按「显式环境变量 > 指针 > 内置默认」取值，指针缺失时行为与改动前一致 |
| 4 | **P2 封存标记无运行语义** | `write_record(..., "superseded", ...)` 报 `invalid record kind`；手写标记后 `list_studies` 照常枚举、`fingerprint` 不变、standing 仍 `fresh=True` | `supersede()` 写 `superseded.json`，`list_studies()` 默认**不再枚举**已封存协议（审计传 `include_superseded=True`）；`activate` 拒绝切到已封存协议 |
| 5 | **P2 交接自相矛盾** | 本文「下一步」写 ①②③ 不依赖合入，迁移方案写 ①② 不依赖、③④⑤ 依赖；③ 正是重建共享库 | 本文不再复述步骤编号，执行顺序以迁移方案 §4 为唯一来源；撤下「已全部收敛、等合入」的无条件裁决 |
| 6 | **封存只停了枚举，没停执行** | 对已封存协议跑真实 `daily --study-dir <已封存>`：rc=0、新增 capture 1 份。`daily`/`capture` 直接吃 `--study-dir`，根本不过 `list_studies` | `_refuse_if_superseded()` 放在**产生副作用之前**；只读审计与 `recheck` 结算不进此闸（存量待验怎么结算是另一个决定） |
| 7 | **夜跑把「没配过」和「配坏了」一起吞** | 封存活跃协议后，夜跑绑定段静默选回 `475597e2…`，rc=0、stderr 为空——等于悄悄换了实验 | `active` 退出码三态（0 有效 / 1 从未配置 / 3 配置过但失效）；夜跑只对 1 兼容默认，遇 3 **停掉方法日步并告警** |
| 8 | **activate 可返回成功但读不回** | study 在 `users/linxiaoqi5111` 下，不带 `--user` 执行 activate：rc=0，指针却写进 `users/default`，生产用户 `active` rc=1 | `set_active` 发布前校验目录归属（`directory.parent == root`），跨根一律拒绝；`activate` 增加读回核对 |
| 9 | **同意图重复封存报错** | `superseded_at=now` 每次都变，撞上不可覆盖发布 → 第二次 `ValueError` | 同一 successor/reason 幂等返回首次标记（封存时刻不刷新）；不同意图仍报错，不静默改写封存原因 |

迁移方案同步改的：封存改为 `supersede` 命令并**移到 activate 之后**（先封存会留出一段无
活跃协议的空窗）；补上 §3.3 要求却在执行表里漏掉的 **history 重跑**（它与种子规则重跑是
两件事，互不替代）；§3.3 与 §4 的顺序对齐；§4.1 核对表每行标注**最早可查时点**（「旧协议
退出枚举」要到封存后才成立）、库版本改用真正读库的 `methodology_backtest.py report
--labels-db`（`method_validation status` 不读库，§5 自己也承认）、并写明 **`active` 只证明
指针、不等于夜跑最终选择**（还叠加 `METHOD_STUDY_DIR` 覆盖、`FORESIGHT_USER` 身份、
`FINANCE_CODE_ROOT` 代码根）；§4.2 删掉「删除指针不会让夜跑失败」这句过宽的话——它只保证
shell 取到一个目录，旧协议在 v5 库上仍会被版本门拒。所有命令显式带 `--user`。

新增回归七条：`test_interrupted_publish_leaves_no_unreadable_official_file`、
`test_legacy_corrupt_receipt_is_reported_not_silently_skipped`、
`test_supersede_actually_deactivates_not_just_annotates`、
`test_activate_switches_binding_and_refuses_superseded`、
`test_active_binding_distinguishes_unset_from_broken`、
`test_set_active_rejects_study_outside_root`、
`test_supersede_is_idempotent_for_same_intent`。

**第 4 条条件性遗留已在 `8bc7252b` 一并修掉**：`load_refuted` 改用 `_parse_ts` 解析后
排序（与 `load_steps` / `latest_receipt` / `report` 同一口径），并带回归。原以为要另立单，
实际同一提交已覆盖——这里回写为已修，不再重复开单。

## 复核修复（09-12 第五轮 + 跨会话质检）

### 第五轮质检（两条 P2 + 一条 P3，`dd7b6f74`）

| 缺口 | 实测 | 修法 |
|---|---|---|
| 同内容重试漏补目录同步 | 首次发布在 `link` 成功、`fsync` 目录失败之间中断，重试走「已存在」分支直接判成功，目录项永远落不了盘 | 抽出 `_fsync_dir`，**所有**成功路径（首次 / 幂等 / 竞态输家）都做。探针读数 `["first-failed"]` → `["first-failed", "retry-succeeded"]` |
| 证伪库坏文件被当成「没有证伪」 | 0 字节反证在场，`report --refuted` 照常打印「目前没有任何规则被证伪」——**证据损坏伪装成证据不存在** | `load_refuted` 返回 `(条目, 读不出的路径)` 并走 `_warn_corrupt`；CLI 逐条打印、声明「汇总不完整」、退出码 2（空库仍 0） |
| 非 UTF-8 漏出 `UnicodeDecodeError` | 它不是 `OSError` 子类，异常里没有文件路径 | 补进捕获、包成带路径的 `ReceiptCollision` |

### 跨会话质检（另一 Claude 会话 `finance-workspace-private-00`）

| 缺口 | 实测 | 修法 |
|---|---|---|
| **`LOG_DIR` 在赋值前被使用**（`22c60030`） | 夜跑 `set -uo pipefail`，绑定解析把 stderr 重定向到 `$LOG_DIR/…`，而 `LOG_DIR` 20 行后才赋值 → 整条命令在**重定向阶段**失败（rc=1、输出空）→ 落进「1 = 从未配置」→ 静默回退旧 v3 协议。**整条指针链一次都没跑过** | `LOG_DIR` 赋值 + `mkdir -p` 提到绑定解析之前。判据用**日志文件是否被创建**区分「shell 层 rc=1」与「命令自身 rc=1」——两者退出码相同、语义相反 |
| **守卫只查存在不查能力**（`607f53a6`） | 运行快照的 `scripts/` 不随部署更新，「新 wrapper + 旧 CLI」是链切前的常态；旧 CLI 遇 `active` 是 argparse `invalid choice` → **exit 2** → 落进 `*)` → 每夜 skip，理由写「指针已配置但失效；请 activate」，而那份 CLI 连 `activate` 都没有 | 先用**顶层** `--help` 的子命令列表探能力。`active --help` 不能当探针（argparse 优先处理 `--help`，不校验子命令合法性，两边都返回 0）。探不到按「从未配置」走默认 + 日志写真原因；case 里 3 单列，`*)` 改中性措辞 |

两条都做了变异确认（挪回 `LOG_DIR` / 把探针换成 `if true`，对应回归各自变红）。

**干净树全量**（源树有在途续修，混合树读数不作数）：`22c60030` **9435P/0F**；
`607f53a6` 9436P/1F，那 1 红是已知的 10 秒墙钟超时型 flaky
（`test_real_conversation_round_trip…`，本次全量跑了 12:34，机器负载高），隔离复跑 **3/3 绿**，
与本分支改动面无交集。

## 迁移欠账（本单只写方案，未执行）

`docs/superpowers/specs/2026-09-12-label-version-migration-plan.md`（**第二版**）。协议 `475597e2…`
绑定 **v3**、共享库 **v4**、代码 **v5**。**这是 #671 升 v4 时欠下的债，不是本单引入。**

真实待办清点（初版漏了这步）：history 1 份、capture **1 份**、recheck 1 份且已判
`stage_not_applicable`、**待回检 0**。所以真实状况是「新的 capture 跑不了」，不是
「有对象卡在半路」——初版那句「在途回检已断」是夸大，已订正。

方案要点（**步骤编号、顺序、依赖关系一律以迁移方案 §4 为准**，本文不给第二套）：
备份 v4 只读留档、重建共享库到 v5、`register` 新协议、`activate` 切绑定、
`supersede` 封存旧协议、种子规则按阶段重跑。两个容易踩的坑：

- `forward_start` 取 **max(重建日, 实际登记日) 的次个交易日**；写死成「重建日次日」
  会在重建与登记之间停过周末时被 `register` 拒。
- **`register` 不切绑定**，`activate` 才切；不做这一步，夜跑仍跑旧协议。

上一版本文就是自己另编了一套号，把「重建共享库」——最需要点头的那一步——误写成
「不依赖合入」，接手者照做会在实现未合入时先改共享数据口径。
另立两单：`status` 打印口径对照；协议改记库的**身份**（label_version + 内容指纹）而非
绝对路径，否则库一搬家就永久失配。

## 下一步
1. 对第五轮新提交做独立复验（新增边界 + 原回归），再由用户确认合 PR。
2. 共享库重建**按迁移方案 §4 分步走**，每步可停；**哪几步依赖合入以该节为准**。
   除备份留档外均依赖合入，且修文档不等于获准写共享库，仍需用户逐步点头。
3. 成员排除若要做，按敏感性对照另立单，主结论不动。
4. #673 重做时改 v6 或与本单合并重建一次。
5. 另立单：`method_validation status` 打印口径对照，避免下次升版再悄悄断掉在途实验。
