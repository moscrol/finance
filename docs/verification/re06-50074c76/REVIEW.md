# RE06 · I11 同意门修复复核（第九轮，候选 50074c76）

- 日期：2026-09-16
- 被审 revision：`50074c76`（`Merge branch 'feat/research-validation-03' into fix/re06-i11-consent-measurement`）；修复提交 `9b92eac8`，修复前基线 `3add63d5`（两者均为候选祖先，已用 `git merge-base --is-ancestor` 核实）。
- 审查树：`/Users/a77/fwp-wt-qc-re06-i11`（`git worktree add --detach … 50074c76`，只新增本目录与一份交接）。解释器 `.venv-workbench/bin/python`（3.12.13）。
- 审的范围：`intelligence/services/research_evolution/run_observer.py::ObservingRunStore._measurement_consented` 及其在 `_record` 里的接线。上一轮（`docs/verification/re06-0bd11ece/REVIEW.md` F2 [P2]）指出撤回同意后自用测量事件照写。
- 复核方式：独立反例探针 `test_review_round9.py`（20 条），真 API、真 writer、隔离临时用户目录；每条在修复后（候选）与修复前（把 `3add63d5` 版 `run_observer.py` 临时拷回原位）各跑一次；以 05 读侧 `measure._consent_timeline` / `_scopes_at` 为折叠语义的对照 oracle。

## 结论：放行（I11 服务端同意门）

- 20 条探针在候选上全绿；其中 14 条在修复前为红（都是「不该写却写了」），6 条修复前后都绿（合同守恒）；**修复后仍红 0 条**。
- 写侧门的折叠语义与 05 读侧在被探到的每一条轴上一致：排序键 `(effective_at, action)`、`effective_at > at` 截断、grant/withdraw 集合运算、`REQUIRED_MEASUREMENT_SCOPES` 子集判定、`effective_at` 不可解析时回退 `event_at`、无记录 ≠ 空集。
- 终态家族三条路径（completed / cancelled / executor failure）都汇入同一个门（T10、T16、T17）。
- 上一轮 F2 **不能整体关闭**：修复只交付了「服务端生效 + 关后运行验收」这一半；「前端控制」没有（webapp 里没有任何 consent 引用），I11 验收句里的「05 标缺测范围」对自用路径也没有任何生产者。两项转为跟踪项（见 Spec P2），不阻塞本修复合入。

## 双轴计数

| 轴 | P1 | P2 | P3 |
|---|---|---|---|
| Spec | 0 | 2（均为修复范围之外的 I11 残项，不阻塞） | 0 |
| Standards | 0 | 0 | 4 |

### Spec

**S-P2-1 · I11「关闭测量」今天只能经 API 完成，没有产品入口。**
`intelligence/webapp/src` 中 grep `consent` / `research-evolution/events` 均为 0 命中。上一轮 F2 明确要求「补前后端控制」；本修复只补了后端。用户在 Workbench 里无法表达撤回，I11 的「关闭使用测量后继续研究」对真实用户不可达。建议：前端加同意开关（直接发 `consent_changed`），或在 06 计划里明确把它列为未交付项并留指针，不要把 F2 标成已关闭。

**S-P2-2 · 「05 标缺测范围」对自用路径没有生产者。**
`workbench:` 前缀的自用 pilot 没有任何收据 / 总结构建入口（`grep -rn 'workbench:' intelligence/services intelligence/api` 只命中两处写入点；`pilot_io rebuild` 只服务冻结协议的试点）。撤回→再授权之间的空窗，台账里唯一的标记是 `consent_changed` 行本身——读者可以由此推出缺测窗口，但没有任何输出把它说出来。这是 I11 验收句的读侧一半，与本修复无关，但需要有人认领。

### Standards

**T-P3-1 · 折叠算法在写侧与读侧各写一份。**
`run_observer._measurement_consented` 与 `measure._consent_timeline/_scopes_at` 今天语义相同（13 条探针用读侧 oracle 逐条对过），但这是巧合式一致，不是结构式一致。建议抽一个 `product_value.fold_consent(entries, at)` 供两侧共用，只在身份谓词（owner vs participant）上各自过滤。

**T-P3-2 · docstring 说「读台账失败按未知处理（继续写）」，实际什么都写不进去。**
`append_once` 会重读同一份台账，坏行同样触发 `StoreCorrupt`，`_record` 兜底后只剩 stderr（T12、T13）。净行为是「意外 fail-closed」：无害（研究照常），但 docstring 的承诺与事实不符，且掩盖了一个设计问题——若将来 append 不再重读，这个 fail-open 就会真的把「同意未知」的事件写进去。建议把门的读失败也改成不写（与 append 一致），或至少把文案改成「读失败时不会有事件落账」。

**T-P3-3 · 门的读取在 `try_transaction` 之外（TOCTOU）。**
读台账 → 构造事件 → 拿锁追加，中间落进来的撤回会被漏判。语义上可辩护：事件的 `event_at` 在读之前就取好了，插入的撤回其 `effective_at` 通常 ≥ 该 `event_at`，读侧会把该事件判为撤回前发生。不算缺陷，记录在此供修复方选择是否把读移进事务。

**T-P3-4 · 第一条部分授权就把「自用默认」翻掉（T07、T08）。**
只授 `["logging"]` 或只授 `["blind_review"]` 都会让此前照写的自用测量停掉。与 05 读侧一致（有记录但不覆盖必需范围 = 不进有效测量），也符合模块 docstring 的规则，但对用户是意外。将来做 UI 时文案要说清「开启任一同意项 = 开始按范围管理测量」。

### 观察（不计入）

- T11：05 `measure_pair` 对「有 `run_started`、无 `run_finished`」的 attempt——计入 attempt 分母、不判失败、`effective_status` 由证据读取器读真实 RunStore 得到（不是从测量事件），缺口以 `timing_missing:<task>` / `cost_unknown:attempt:<id>` 落入 `limitations` → `incomplete`；撤回前写下的 `run_started` 不被追溯排除。即「关闭前后的分母与缺口都可解释」在读侧成立。要留意的是：撤回后读取器仍会去读该 run 的终态——按 05「退出计数保留、明细依同意处理」这属于「计数」而非「明细」，但应由 05 的评审确认。
- 客户端给的未来 `effective_at` 会被如实尊重（预约撤回，T03/T04）。生产时钟是 `datetime.now()`，客户端与服务端有钟差时「立刻撤回」会晚生效钟差那么久；是部署问题，不是代码问题。
- 每次 `_record` 全量读一遍台账（一个 run 三次）；自用台账体量下可忽略。

## 逐条探针判定

三类：**A** = 修复前应红、修复后转绿；**B** = 修复前后都绿（合同守恒）；**C** = 修复后仍红（新发现）。

| # | 探针 | 类 | 修复前失败原因 / 守恒说明 |
|---|---|---|---|
| T01 | `withdraw_research_stops_measurement` | A | 修复前撤 research 后仍写三类事件；读侧 oracle 同判 False |
| T02 | `regrant_after_withdraw_restores_measurement` | B | 再授权后三类事件齐；oracle True |
| T03 | `future_withdraw_is_not_applied_before_its_effective_at` | B | 预约撤回未到期不提前生效 |
| T04 | `future_withdraw_applies_once_clock_passes_effective_at` | A | 修复前到期后仍写 |
| T05 | `other_participants_withdraw_does_not_gate_owner` | B | 别人的撤回不影响 owner |
| T06 | `other_participants_grant_does_not_reopen_owner_gate` | A | 修复前照写；修复后别人的授权不能替 owner 开门 |
| T07 | `grant_logging_only_closes_gate_in_step_with_read_side` | A | 修复前照写；{logging} ⊉ {research, logging}，读侧同判 |
| T08 | `first_grant_of_unrelated_scope_closes_gate` | A | 修复前照写；与读侧一致，产品后果见 T-P3-4 |
| T09 | `same_instant_grant_and_withdraw_withdraw_wins` | A | 修复前照写；排序键 'grant' < 'withdraw' 与读侧一致 |
| T10 | `midrun_withdraw_writes_run_started_but_not_finish_or_cost` | A | 修复前终态与成本照写；修复后只剩 create 点写下的 `run_started` |
| T11 | `read_side_counts_start_only_attempt_as_gap_not_failure` | B | 读侧不在修复范围；钉住归类口径（见观察） |
| T12 | `corrupt_ledger_line_keeps_research_usable_and_appends_nothing` | B | 前后都：run completed、台账逐字节不变（append_once 同样 StoreCorrupt） |
| T13 | `corrupt_ledger_gate_leaves_stderr_trace` | A | 修复前只有「落盘失败」一行，没有「读同意记录失败」 |
| T14 | `consent_row_with_unparseable_times_is_ignored_fail_open` | B | 两个时间都解析不出的撤回行被跳过 → 照写；只有绕过校验器才能造出此行，读侧 `prepare_events` 会整条拒收，两侧都「看不见」 |
| T15 | `naive_effective_at_falls_back_to_event_at` | A | 修复前照写；无时区 `effective_at` 回退 `event_at`，与读侧同一回退 |
| T16 | `cancel_path_is_gated_too` | A | 修复前 cancel 终态写 `run_started` + `run_finished(cancelled)` |
| T17 | `executor_failure_path_is_gated_too` | A | 修复前失败终态写 `run_started` + `run_finished(failed)` |
| T18 | `consent_tagged_with_owner_participant_id_counts_as_owner` | A | 修复前照写；`participant_id == owner` 与空同等对待 |
| T19 | `withdraw_posted_in_another_conversation_gates_this_run` | A | 修复前照写；同意是 owner 级，门不看 pilot_id |
| T20 | `backdated_late_grant_cannot_reopen_a_later_withdraw` | A | 修复前照写；按 `effective_at` 折叠而非台账顺序 |

计数：A 14 / B 6 / C 0。

## 验证与收据

收据目录 `~/.finance-runtime/test-receipts/`，`revision` 均为 `50074c76`，`tree` 均为审查树。`worktree_dirty_total=1` 是本目录（未跟踪），不计入 `dirty`。

| 运行 | 收据 | dirty | 读数 |
|---|---|---|---|
| 修复方 4 条 + 原 I11 探针（候选） | `20260916T030751Z-50074c76.json` | false | 5 passed |
| round9 首版 18 条（候选） | `20260916T031444Z-50074c76.json` | false | 18 passed |
| round9 首版 18 条（**修复前**，`run_observer.py` 换成 3add63d5 版） | `20260916T031517Z-50074c76.json` | **true**，`dirty_paths=[run_observer.py]` | 6 passed / 12 failed |
| round9 全 20 条（候选） | `20260916T031657Z-50074c76.json` | false | 20 passed |
| round9 全 20 条（**修复前**） | `20260916T031724Z-50074c76.json` | **true**，同上 | 6 passed / 14 failed |
| 回归：`test_research_evolution_{api,rework,i11_consent}` + 3–8 轮全部探针 + round8_merge + 原 I11 探针 + round9（候选） | `20260916T031829Z-50074c76.json` | false | 130 passed，44.7s |

修复前对照的两张收据 `dirty=true` 是刻意的（那正是被换掉的文件），只作对照用，不可当候选读数引用。每次换文件前后都清了 `__pycache__` 并用 `PYTHONDONTWRITEBYTECODE=1`；还原后 `git diff --quiet` 为真、`_measurement_consented` 出现次数回到 2。

重放（在审查树根目录）：

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
env -i PATH="$PATH" HOME="$HOME" PYTHONPATH="$PWD" "$PY" -m pytest -q -p no:cacheprovider docs/verification/re06-50074c76/test_review_round9.py
# 修复前对照
git show 3add63d5:intelligence/services/research_evolution/run_observer.py > /tmp/run_observer_before.py
cp /tmp/run_observer_before.py intelligence/services/research_evolution/run_observer.py
env -i PATH="$PATH" HOME="$HOME" PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 "$PY" -m pytest -q -p no:cacheprovider -rf docs/verification/re06-50074c76/test_review_round9.py
git checkout -- intelligence/services/research_evolution/run_observer.py
```

## 没验的边界

- 生产时钟（`datetime.now().astimezone()`）与客户端钟差下的撤回时序；探针全部用 FakeClock。
- 撤回与终态 claim 的真并发（T-P3-3 的 TOCTOU 只做了代码推断，没有用 barrier 复现）。
- `pilot_io import-events` 路径写入的 M 渠道同意行（T14/T15 用 `EvolutionStore` 真 writer 直写绕过校验器，没有走那条 CLI）。
- 前端：没有 UI，无从测。
- 全仓 pytest / 前端四叶 / E2E 本轮未跑；只跑了 research_evolution 相关 130 条。合并前仍需按 AGENTS.md 跑等价 CI。
- 05 `summarize` 对自用事件的处理：没有生产者，未触发。

本轮未修改任何业务代码、未 push、未合并、未触碰生产用户数据。
