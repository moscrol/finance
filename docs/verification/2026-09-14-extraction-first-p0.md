# 收据 · 工单 #53 提取前置 P0（2026-09-14）

工单 `docs/superpowers/specs/2026-09-14-extraction-first-p0-workorder.md`。
设计依据 `~/foresight/docs/specs/2026-09-13-extraction-first-spec.md` rev.4（金融仓外，未改）。
背景与取舍全文 `docs/handoffs/2026-09-14-extraction-first-p0-review-fixes.md`。

> **工程完成 ≠ 真人有效。** 本页只证明 §6 的 A1–A15 工程验收成立。
> §7 三项阈值（观察周期 / 可接受额外耗时 / 撤回条件）**未填**，真人实验**未开跑**，
> 本页不含任何真人读数。

---

## 0 版本说明：本页第一版的读数已作废

**2026-09-14 质检 N1 判定成立，第一版收据里的两处读数不能采信，现已撤回：**

第一次全量跑基线时，我在它跑到约第 3 分钟就开始创建 `observation_extraction.py`、
第 4 分钟改了 `observation_script.py`。pytest 在收集期导入模块，此后才导入被测模块的
测试拿到的是**改过的代码**——那个 `9554 passed` 不是基线读数，是混合树读数。
最终读数虽然代码稳定，但树上有未提交改动，收据 `dirty=true`、`revision` 指向基线而非
`95f3c5e7`，同样绑不到所宣称的提交上。

**我却把它写成了「干净基线全绿，所以任何失败都不能推给存量红」。那是假证据。**
回填 SHA 不能把脏树读数变成那个 SHA 的收据。仓内 `scripts/check_test_receipt.py
--expect-revision` 本来一句话就能拆穿（exit=1），我没跑。

本页 §1 / §6 的读数是**返修后重取**的：两次都在干净提交上、跑测全程无人触碰那棵树，
并用 `check_test_receipt.py --expect-revision` 绑定。旧读数作为历史观察保留在
`/tmp/xfp0/baseline-pytest.txt` / `final-pytest.txt`，**不作为门禁证据**。

---

## 1 环境与基线

| 项 | 值 |
|---|---|
| 候选工作树 | `.claude/worktrees/feat-extraction-first-p0`（`git worktree add` 新树） |
| 基线工作树 | `.claude/worktrees/xfp0-baseline-d7e5380`（**专为取基线新建的独立树**，detached 于冻结 SHA，跑测期间零改动） |
| 分支 | `feat/extraction-first-p0` |
| 冻结基线 revision | `d7e5380551ba92758935d268fdd0e6fbfdd51ce8`（= 开工时 `gitea/main`，与工单一致） |
| 被测最终 revision | 见 §6.1 收据校验那一段的 `--expect-revision`（**本页是全仓唯一的 SHA 来源**，其余文档指过来、不复制） |
| 最终读数工作树 | `.claude/worktrees/xfp0-final-04c68c54`（**专为取读数新建的 detached 树**，跑测全程零改动、前后 HEAD 一致） |
| 解释器 | `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（AGENTS.md 指定） |
| 平台 | macOS darwin 25.4.0 / `pytest -q -p no:randomly` |
| 原始输出 | `/tmp/xfp0/`：`baseline2-pytest.txt`（基线）、`final2…8-pytest.txt`（历次最终，含 §6.2 那次 1 红的原始输出）、`mutations.txt`、`fe-*.txt`、`registry.txt`、`receipt-*.txt`、`mergetree.txt` |

### 1.1 干净基线读数

```
9554 passed, 77 skipped, 2 xfailed, 17 warnings in 347.24s (0:05:47)   exit 0
```

取法（与第一版的关键差别）：**另建一棵 detached 于 `d7e5380` 的工作树**，
整段跑完期间没有任何人碰它；脚本在跑之前与跑之后各打印一次 `git status --short`，
两次都空。收据校验：

```
$ cd .claude/worktrees/xfp0-baseline-d7e5380
$ .venv-workbench/bin/python scripts/check_test_receipt.py \
      ~/.finance-runtime/test-receipts/20260913T215802Z-d7e53805.json \
      --expect-revision d7e5380551ba92758935d268fdd0e6fbfdd51ce8
  ✓ revision 一致   ✓ 解释器一致   ✓ python 版本一致   ✓ 依赖指纹一致
  ✓ 收据来自干净树   ✓ 依赖门禁未被绕过   ✓ 收据 revision == d7e5380551ba
✅ 可采信 —— 收据成立的条件与当前环境一致，无需重跑。        VALIDATOR_EXIT=0

# 注：校验器按**自身所在仓**解析「当前 revision」，所以必须在被校验的那棵树里跑；
# 从候选树去校验基线收据会得到 exit=1（比的是候选树的 HEAD），那是处境不符不是收据坏。
```

### 1.2 Closeout（第五轮）环境与基线

第五轮起整条链**重放到最新 `gitea/main` 之上**，分支改名 `fix/extraction-first-closeout`：
`feat/extraction-first-p0` 的提交逐笔重建（SHA 全变、内容不变），merge-base 就是当前 main，
`git merge-tree` 预演 0 冲突（可快进）。§3.4 及之前各轮引用的旧 SHA 指 feat 分支上的历史提交，保留不改。

| 项 | 值 |
|---|---|
| 工作树 | `~/fwp-wt-extraction-first-closeout` |
| 分支 | `fix/extraction-first-closeout` |
| 冻结基线 revision | `1fef3d276d0e251158803fc09d5a81e60d79241b`（= 本轮 `gitea/main`） |
| 被测最终 revision | 见 §6.1「Closeout 读数」的 `--expect-revision`（**唯一来源**，其余位置一律指过来） |
| 门禁工作树 | 第五轮 `…/extraction-closeout-20260915/gate/finance-workspace-private`；第六轮 `…/gate3/finance-workspace-private`（均专建 detached 树） |
| 独立复审树 | `…/extraction-closeout-20260915/qc6/finance-workspace-private`（复审方自建，冻结 `37a4e7b7`，全程未改动） |
| 基线工作树 | `~/.finance-runtime/reviews/extraction-closeout-20260915/baseline/finance-workspace-private`（detached 于冻结基线） |
| 原始输出 | `~/.finance-runtime/reviews/extraction-closeout-20260915/`：`gate/` 各叶 exit+log+junit、`mutations-<§6.1 revision>/`、`pinned-probes-rerun/`、`baseline-pytest.log`、`mergetree.txt` |

## 2 改了什么

| 文件 | 一句话 |
|---|---|
| `intelligence/services/observation_extraction.py` | **新增**。判定侧：身份解析 / 关联键 / 顺序门 / 字段差异 / 骨架引用哈希。全是纯函数，不写盘 |
| `intelligence/services/observation_script.py` | 台账侧（唯一写入者）：`record_kind` 三分型、草稿版本、提取尝试、五事件、flock + 整行 fsync + 残片封口、动作认领与去重 |
| `intelligence/services/guided_reading.py` | `gated()` 共用门（门在 `build` 之前）、差异段渲染、`daily_section()` 接缝与入口提示 |
| `intelligence/cli.py` | `observation draft` / `close` / `list --events`；`read` / `confirm` / `skip` / daily 接入同一道门 |
| `intelligence/services/personal_export.py` | 台账描述改成「台账行（三类）」；逐行解码（残片不再让整份导出失败） |
| `docs/learning/ledger-map.md` | 登记分型格式与唯一写入者 |
| `intelligence/tests/test_observation_extraction_first.py` | **新增** A1–A14，77 条 |
| `intelligence/tests/test_extraction_first_review_fixes.py` | **新增** 三轮返修回归，50 条（S1–S10/N2/N3 + R1–R6 + T1–T4 + Q2/Q3） |
| `intelligence/tests/test_guided_reading_daily_seam.py` | 接线断言改指 `daily_section` 并加强 |

提交链：`95f3c5e7`（实现）→ `b42dc9bf`（收据）→ `08ca525f`（首轮返修 12 项）→
`7a86ce4e`（撤回脏树读数 + 压缩交接）→ `caba87c7`（回填读数）→
`8410e9d3`（复审返修 6 项）→ `b916091e`（诊断拆句 + 交接回填）→ `642c3f5d`（回填读数）→
`b69ac4b4`（复审二返修 4 项 + 文档指针）→ `901c7a87`（Q2 / Q3，复审方所写）→ 本页所在提交。

第五轮（closeout）：上述链在 `fix/extraction-first-closeout` 上逐笔重建（内容同、SHA 变），
其后新增一笔收口提交（即 §6.1 绑定的被测 revision）：
`observation_script.py`（受控确认 record_id 由动作键派生，V1）、
`personal_export.py`（坏行落 `_unparsed_bytes_hex`，V2）、
**新增** `intelligence/tests/test_extraction_closeout.py`（14 条：坏行字节级往返 ×5、
字面量 `\xe7` 与坏字节不塌缩、同秒不同确认动作 ×6、历史确认 id 不被重写、
真 CLI + 临时 DuckDB 全链）、**变异 runner 入仓**
`scripts/review_probes/run_extraction_mutations.py` + 冻结定义 `extraction_mutations.json`（31 条）。

第六轮（独立复审返修）再动两处同样的文件：`observation_script.py` 增 `_legacy_confirm_identity`
（遗留确认行的内容身份，两侧共用一个推导）并接进 `register` 的去重循环；
`personal_export.py` 把四个分支的搬运 dict 归一到 `_carried` 并补两种此前整行丢弃的情形；
`test_extraction_closeout.py` 增 16 条（14 → 30）；冻结定义 31 → **35**（M32–M35），
另重锚 M10 / M23 / M30 / M31。

## 3 逐条验收（A1–A15）

全部用隔离 `FORESIGHT_USERS_DIR` 临时目录 + 固定本地切片 + 显式写进夹具的开关状态；
**不碰真实用户台账、不碰真库**。逐条观察面见
`intelligence/tests/test_observation_extraction_first.py` 的类名（A1→`A1DraftAndIdentity`，依此类推）。

| # | 验收 | 结果 |
|---|---|---|
| A1 | 草稿 / 身份：最后成功版生效且旧版保留、四维关联键互不放行、别名对齐、系统 drafted 不冒充用户提交、草稿不登记 checkpoint | ✅ 11 条 |
| A2 | 业务字段一致而元数据不同 → 差异 `[]`；无骨架**不报成一致** | ✅ 3 条 |
| A3 | 无草稿直接 read 被拦，`gr.build` 调用次数 **== 0**，无 checkpoint / 无剧本行 | ✅ 3 条 |
| A4 | 违规草稿被同一合规门拒绝，不替换已有有效版 | ✅ 3 条 |
| A5 | 双向差异逐条断言；一致字段不进差异；差异段过用词 lint | ✅ 5 条 |
| A6 | 显式跳过只记一次、**跳过事件在 build 之前已落盘**、授权不跨尝试 / 目标、有草稿时不写虚假跳过 | ✅ 5 条 |
| A7 | `confirm --from-slice` / `skip` / `list --json` 都不绕门；手填 confirm 事件集合恰为 `{script_confirmed}` | ✅ 6 条 |
| A8 | 日报无草稿只加入口提示、非带读正文一字不动；后台运行零尝试零事件；关闭时连提示都不出且 `merge` 返回同一对象 | ✅ 5 条 |
| A9 | 五事件续接、等待保持 pending、已关闭不复活、late 仍是确认事件、事件不进剧本分母 | ✅ 7 条 |
| A10 | 重试不重复、并发只一个 pending、成功事件与剧本行同一次写、跨用户 / 跨目标拒绝、**收据落盘失败 → 退 1 + 保持 pending**、已完成尝试返回原收据、原始导出保留三类 | ✅ 10 条 |
| A11 | 开关矩阵七种；**只写提取台账不翻转新老用户判据**；带读关闭时独立 draft 仍能存 | ✅ 7 条 |
| A12 | 无类型旧剧本可读；事件不进状态数 / 过期 / 非交易日扫描；`--from-draft` 是 `user_authored` 且不伪造投影；hindsight 活过 draft 这一跳 | ✅ 7 条 |
| A13 | 有牙验收：见 §4 | ✅ 35/35 |
| A14 | 差异载荷**一个数都没有**；收据键在来源关联白名单内且无数值；新模块不定义评分型符号（探针先在坏样本上验证会红）；profile / 校准台账零写入 | ✅ 6 条 |
| A15 | 本页 | ✅ |

> **A14 为什么不是关键词扫描**：工单明写「不以全仓关键词零命中作证」。全文扫描既抓不住
> `d = len(a & b) / len(a | b)` 这种没有关键词的评分，又会把 `## 你写的 vs 系统列的
> （只列字段差异；不评分、不判谁对）` 这种**声明红线的文案**判成违规。

> **返修顺带删掉一处真问题**：初版把 `diff_field_count` 写进了 read 收据。§2.5 是
> 「只持久化必要来源关联，差异展示时重算」——「差了几项」是派生大小，存进台账下一个人
> 就会拿它做时间序列，那就是收敛指标。已删。

## 3.1 质检返修（2026-09-14，12 项行为缺陷）

质检在 `b42dc9bf` 上实测出 14 项，**逐条复核成立，无误报**。根因表与三条最值得带走的
形状见 `docs/handoffs/2026-09-14-extraction-first-p0-review-fixes.md` §二。

| # | 缺陷 | 修法 | 回归 |
|---|---|---|---|
| S1 | `confirm` 静默清空草稿里的升级 / 机检条件 | 与 variables 同样「从来源继承、命令行覆盖」 | `S1ConfirmFromDraftKeepsUserConditions` |
| S2 | 无骨架也记 `read_completed` 并关尝试 | 不记事件、尝试保持 pending | `S2NoSkeletonIsNotACompletedRead` |
| S3 | 收据分支被 `open_attempt` 的「已结束」挡在前面而不可达 | 收据查询前移并先验归属 | `S3CompletedAttemptReplaysTheReceipt` |
| S4 | `--from-draft` 忽略 `--attempt-id` | 先验归属，按该尝试取版本 | `S4FromDraftHonoursAttemptId` |
| S5 | 确认行冒充「最新草稿」 | 判据加 `action_event.event == draft_submitted` | `S5ConfirmedRowIsNotADraftVersion` |
| S6 | 去重键含时间戳派生位，跨秒重试换键 | 稳定内容键，认领前置于 checkpoint | `S6ConfirmRetryIsDeduped` |
| S7 | repoint 复制动作元数据 → 第二次确认 | 写入侧不复制 + 读取侧按 `action_key` 去重（两道各有断言与变异） | `S7RepointDoesNotForgeASecondConfirmation` |
| S9 | 关闭之后仍可提交（check-then-act） | `ensure_attempt_writable`，判定与追加同锁 | `S9ClosedAttemptRefusesASubmission` |
| S10 | `--attempt-id` 只过滤 events | 两边共用同一谓词 | `S10AttemptFilterCoversPendingToo` |
| N2 | 残片吞掉下一次成功写入 | append 前补换行**封口**（不截断，残片是证据） | `N2TornLineDoesNotSwallowTheNextWrite` |
| N3 | abandoned 追加失败后永久断裂 | 重试据关闭行的 `abandoned` 标记补齐（幂等） | `N3CloseRetryHealsTheAbandonedEvent` |
| S8 | 展示层 `drafted→expired` 换算解除遮蔽 | 遮蔽资格改看「从未成为用户的决定」 | `S8ExpiryDoesNotUnlockTheRedaction` |

A 系两条按真实行为重写（其中 `test_completed_attempt_replays_the_receipt_not_the_body`
正是 S3 点名的名实不符那条，此前断言 `exit=2`），**没有把旧错误断言留作「兼容」**。

## 3.2 复审返修（2026-09-14 第二轮，6 项 P2）

复审在 `caba87c7` 上实测出 6 项，**逐条复核成立**。其中 **R6 是第一轮返修新引入的回归**，
一并认领。修前 11 红 / 2 绿，修后全绿。

| # | 缺陷 | 修法 | 回归 |
|---|---|---|---|
| R1 | 写入断在**汉字中间**时（「算」= `e7 ae 97` 只落了 `e7 ae`），`load_raw` 的 `read_text` 整文件一次解码抛 `UnicodeDecodeError`——不是丢一条，是整本台账读不出来；那个 `except` 只接 `JSONDecodeError`，接不到它。第一轮补的换行救不回来：**读取先炸** | 按字节读、**逐行解码**，损坏限制在它自己那一行；残片仍原样留盘 | `R1TornMultibyteDoesNotBrickTheLedger` |
| R2 | 交付成功但关闭失败 → 完成事件已落、尝试仍 pending；同 ID 重试只返收据就返回，尝试永远挂着 | 重试先补终态（`close_attempt` 幂等；已有完成事件所以只补 closed，不会多一条 abandoned） | `R2CloseFailureIsHealedOnRetry` |
| R3 | 新尝试**复用**旧草稿读完后，按该尝试确认报「没有提交过草稿」——`draft_for_attempt` 只认「在这个尝试里提交的」，而复用是主路径 | 补第二条依据：该尝试自己的 `read_completed` 收据里的 `source_draft_id` | `R3AttemptSelectsTheDraftItActuallyRead` |
| R4 | 完整手填路径**根本没读** `--attempt-id`，传另一目标的 ID 也照样建 checkpoint、关联静默丢弃 | 给了就验归属，验过才用 | `R4ManualConfirmValidatesTheAttempt` |
| R5 | 第一轮只给 `submit_draft` / `record_event` 加了落盘复验，`register` 漏了：并发 close 插在「门过了」与「落盘」之间时，同一尝试上同时出现 `abandoned=true` 与一条确认 + 一个 checkpoint | 新增 `require_open_attempt`，**只对在进行中的尝试里做的动作**复验（`--from-slice` / `skip`）——`--from-draft` 引用已完成的旧尝试是 §2.4.4 明确允许的，不能一刀切 | `R5ConfirmAndSkipRespectAConcurrentClose` |
| R6 | **本轮自伤**：S6 的稳定动作键治好了跨秒重试，却漏了 `due`，于是改回检日期被当成同一个动作，返回成功却沿用旧日期与旧 checkpoint | `due` 进动作键；`_make_id` 也带上 `due`，否则同一秒内两次不同到期日的确认会撞同一个 id | `R6DueIsPartOfTheConfirmActionIdentity` |

另修一处复审点到的措辞残留：`read` 把「收据没落」与「收据已落、仅终态没写」合成一句
「交付结果未知」。两者事实完全不同——后者**确实交付了**且重试能愈合。已拆成两条分支，
各给可执行的下一步，并加断言钉住措辞差异。

> **R6 这条要单独记一笔。** 第一轮我把「动作身份不能掺时间戳」修对了，却把
> 「到期日是动作的一部分」漏了——同一次修改在同一个函数上，一个方向修对、
> 另一个方向修坏。稳定键的字段集合必须**逐个论证「改了它算不算另一个动作」**，
> 不能只反向排除不该进的。

## 3.3 复审二返修（2026-09-14 第三轮，4 处行为缺口 + 1 处文档）

复审在 `642c3f5d` 上实测，逐条成立。修前 4 红，修后全绿。

| # | 缺陷 | 修法 | 回归 |
|---|---|---|---|
| T1 | `--from-draft --attempt-id B` 时 `attempt_id` 从**草稿行**取：A 提交草稿、B 复用读完、指名 B 确认，事件却挂回 A | 「取哪一版」与「算在哪次尝试名下」分开——归属跟显式参数走，没给才回落草稿自己的尝试 | `T1ConfirmIsAttributedToTheAttemptYouNamed` |
| T2 | 收据已落、关闭失败留下一个**仍 pending** 的尝试；**不带** `--attempt-id` 原样重跑会自动复用它，正文重新生成、台账沿用旧收据——重放了正文却声称没重放 | 认领到 `aid` 之后再查一次收据（显式那条仍需前置：已关闭的会被 `open_attempt` 拒） | `T2AutoResumeAlsoHonoursTheReceipt` |
| T3 | 去重比**全历史**，把 A→B→A 的第三次吞掉，有效草稿停在 B，而用户刚把它改回了 A | 从内容分不出「连跑两次」与「想了想改回去」，只能靠位置：**只与紧邻上一版比**，同内容才算重试 | `T3RevertingToAnEarlierDraftIsANewVersion` |
| T4 | R1 只修了观察台账的读取面，**个人导出漏了**——同一份半汉字残片照样让整份导出抛 `UnicodeDecodeError` | 同族第二处补上逐行解码；坏字节也不静默丢，可读部分带走 | `T4PersonalExportSurvivesTheSameTornLine` |
| — | 收据复跑命令与交接复核指针都**写死过 SHA**，返修一轮就指向旧树，复审按它复跑会漏掉最终修复 | SHA 只在收据 §1 留唯一来源，其余文档一律指过去 | —（本条是流程，见 §8） |

> **T3 与 T4 各代表一类反复出现的形状，值得单独记。**
>
> T3：**幂等的边界不能只看内容**。内容相同未必是同一个动作——「重试」与「回滚到旧值」
> 在载荷上完全一样，区别只在它相对于**上一次**的位置。比全历史等于假定用户不会反悔。
>
> T4：**修了一处要先问同族还有谁**。R1 修的是 `observation_script.load_raw`，而
> `personal_export._read_jsonl` 是同一份台账的第二个读者、同一个 `read_text` 写法。
> 一处修好、另一处没修，比两处都没修更难发现——台账读得出来了，导出仍然整份失败。

### 3.3.1 同轮另外两项（Q2 / Q3）与一处范围问题

本轮还有两项由**复审方自己**写实现与用例（提交 `901c7a87`），不是我修的：

| # | 缺陷 | 修法 |
|---|---|---|
| Q2 | 收据落盘、关闭失败的窗口里，同一 pending 尝试又合法提交了 v2；按该尝试确认会选 v2，而那一版**从未出现在那次 read 里** | 完成收据是选版的**最高依据**：有收据就按 `source_draft_id` 取，收据缺来源则返回 `None`，不悄悄回退 |
| Q3 | 手填确认验了归属却把终态校验整体豁免，完全 `abandoned` 的尝试上也能新增确认与 checkpoint | 手填 + 显式尝试是「在进行中的尝试里做动作」，`require_open_attempt=True` |

> **两处要如实记账。**
>
> 1. `b69ac4b4` 那笔是我用 pathspec 提交的，但当时同一棵工作树里有另一个 agent 正在改
>    `observation_script.py` / `cli.py`，他的 Q2/Q3 早期改动被我的提交**一并带走**，
>    而我的提交信息没有描述它们。AGENTS.md 早就写过这个形状（同一棵树两个 agent 共用
>    索引），我照做了 pathspec 却没在提交前重看一遍 diff。
> 2. 复审方标注 **T3 属于范围外变更，待下一轮裁决**。我的依据是：第三轮复审给我的清单
>    里，「草稿 A→B→A，最后修改不生效…全历史内容去重吞掉了新提交」是**需求轴三项之一**，
>    不是我自找的相邻缺口。两边看到的报告版本可能不同，**以复审方的裁决为准**——
>    要退回「只比全历史」，改 `submit_draft` 里那一处 `latest_user_draft` 判据即可，
>    回归 `T3RevertingToAnEarlierDraftIsANewVersion` 与变异 M22 一并撤。

## 3.4 复审三返修（2026-09-14 第四轮，4 项 P2）

复审在 `f43b89c6` 上实测，逐条成立。修前 5 红。**T3 的范围争议由复审方裁决：属范围内、
保留**——原 `642c3f5d` 报告的 S3 明确要求 A→B→A 生效；上一版交接那句「超范围待裁决」作废。

| # | 缺陷 | 修法 | 回归 |
|---|---|---|---|
| U1 | 三版草稿都落盘了，但 **v3 复用了 v1 的事件身份**：动作键 = `draft_submitted｜attempt｜内容哈希`，A→B→A 时 v3 与 v1 同内容同尝试，投影去重后只剩两条提交事件——台账三行、事件两条 | 版本序号进动作身份（`{hash}#{seq}`）；重试判据随之改用**内容哈希**（新落盘字段 `draft_content_hash`）——再拿动作键当判据，每次提交都成「新动作」，重试的幂等就没了 | `U1RevertedDraftGetsItsOwnEventIdentity` |
| U2 | A 确认 → B 确认 → A 确认，当前有效草稿是 v3，第三次却撞上第一次的内容哈希被去重，返回的 `source_draft_id` 指向 v1 | `source_draft_id` 进确认动作键：**同内容不同来源版本是两个动作** | `U2ConfirmIdentityIncludesTheSourceVersion` |
| U3 | 导出用 `errors="replace"`，所有坏字节压成同一个 `�`：「算」断成的 `e7 ae` 与「固」断成的 `e5 9b` 长得一样，残片不再是证据 | 改 `errors="backslashreplace"`——每个坏字节写成 `\xNN`，不同字节仍不同、原字节可还原 | `U3ExportPreservesTornBytesReversibly` |
| — | 交接过期（写着旧读数、把 T3 误述为范围外） | 读数与 SHA 只指 §1 / §6.1，不复制；T3 裁决回写 | —（`c31219a4`） |

> **U1 / U2 是同一个形状的两次。** 动作身份里只放了「内容」，没放「这是第几版 / 确认的是
> 哪一版」。同内容的不同动作于是互相顶替：提交那边表现为事件少了一条，确认那边表现为
> 来源指向旧版本。**幂等键的字段集合要逐个论证「改了它算不算另一个动作」**——这已经是
> 第三次栽在同一句话上（S6 漏 `due`、U1 漏版本序号、U2 漏来源版本），前两次也都写在本页。

## 3.5 收口自查（2026-09-15 第五轮，2 项 P2）

在重放链顶端自查实测，2 项成立；修法与回归都在收口提交里（§6.1「Closeout 读数」绑定的那个 SHA）。

| # | 缺陷 | 修法 | 回归 |
|---|---|---|---|
| V1 | U2 把来源版本放进了**动作键**，事件不再互相顶替；但记录 id `_make_id` 仍只哈希「内容 + 秒级时间 + due」——同一秒内同内容的两次**不同**确认动作（换来源版本 / 换条件 / 换尝试）事件各一条，`script_id` 却指向同一条剧本行：身份在记录层重新撞上 | 受控确认的 record_id 直接由**动作键**派生（`os-<as_of>-<sha256(action_key)[:24]>`）；旧入口 id 合同不变；既有成功行走去重分支**原样返回，不重写历史 id** | `test_distinct_confirmation_actions_have_distinct_record_ids`（换来源版本 / 换条件 / 换尝试 × on-time / late，6 条）+ `test_retry_preserves_preexisting_confirmation_id` |
| V2 | U3 的 `backslashreplace` 只是**预览**：坏字节 `e7` 与原文里的字面量 `\xe7`（四个字符）渲染成同一串，行尾空白也被 strip——展示可分辨 ≠ 字节可还原，JSON 往返后更分不出 | 坏行（`UnicodeDecodeError` 与 `JSONDecodeError` 两类）额外落 `_unparsed_bytes_hex`，`bytes.fromhex` 逐字节还原（含空白与 `\r`）；导出 note 写明恢复方法 | `test_bad_line_round_trips_exact_bytes_through_export`（5 种坏行，**过真实 JSON 序列化**再断言，且台账原字节不动）+ `test_literal_escape_and_torn_byte_do_not_collapse` |

> V1 是「幂等键的字段集合要逐个论证」的**第四次**，但形状推进了一层：这回键本身是对的，
> 错在**以键去重的记录身份没跟着键走**。动作键修对之后，还要挨个检查以它为输入的派生身份
> （record id、事件 `script_id` 指向）是否同步——键与 id 是两层，各要有自己的牙。
>
> 顺带补上 §7 此前明记的一条缺口：`test_real_cli_draft_read_and_receipt_with_local_database`
> 用**真实 CLI + 真实身份解析 + 真实 River 切片**跑通 draft→read→重试收据全链
> （数据面是临时 DuckDB 固定夹具 `fact_sector_daily_generation`，legacy 快照），
> 打桩不再是唯一证据；但仍不是生产库证据。

## 3.6 独立复审六与返修（2026-09-15，3 项）

第五轮的 V1 / V2 是**自查**所得、无人独立复核，M29–M31 也从未由非提交者重放过。
第六轮请独立复审在冻结 `37a4e7b7` 上实测：变异重放 31/31 零偏差、文档抽查四组全对上，
**另实测出 3 项缺陷，逐条复核成立、无误报**。报告与可复现证据
`~/.finance-runtime/reviews/extraction-closeout-20260915/qc6/REPORT.md`。

| # | 缺陷 | 修法 | 回归 |
|---|---|---|---|
| F1 · P1 | **V1 的修复自己留的洞**：`action_event` 的唯一写点就是 `register`，所以本次升级**之前**落盘的确认行根本没有动作键；而去重分支只认动作键 → 对这些行完全不去重。实测同内容重试后台账出现两条 confirmed、同一个可证伪点被重复登记进回检队列（checkpoints 两行同 id），而 `load_events` 只投影出 1 个事件且只指新行——「2 条确认、1 个事件」自相矛盾地落了盘 | 补「内容身份」判据：维度与动作键的内容部分逐一对齐（user / as_of / scope / due / 实体 / `DIFF_FIELDS`），两侧共用 `_legacy_confirm_identity` 推导。遗留行没记来源版本与尝试，**不拿它们当判据**（永不命中），能比的维度全比上 | `test_legacy_confirmed_row_without_action_event_is_not_duplicated` + `test_legacy_match_requires_full_content_identity`（8 个维度逐个证明「改了它就是另一个动作」） |
| F2 · P2 | 导出对「合法 JSON 但不是记录」的行（`[1,2]` / `"str"` / `42` / `null` / `true`）整行丢弃：`isinstance(rec, dict)` 没有 else。实测 7 行台账导出只剩 2 行、`counts=2`，五行既不在导出也不在计数里 | 归一到唯一构造点 `_carried`，四个分支共用 | `test_non_record_line_is_carried_not_dropped`（7 种 × 字节级往返 + 计数 + 台账原字节不动） |
| F3 · P3 | 全空白行（`"   "` / `" \t\r"`）同样静默跳过且不计数，与同一函数「计数是台账行数」的口径相反 | 有字节就有行：照搬并计数；**行分隔符切出的空段仍然跳过**，不凭空多出一行 | 同上（`spaces` / `blank-cr` 两个参数化变体） |

> **F1 是这条链上最值得记的一次。** 前四轮的教训是「幂等键的字段集合要逐个论证」，
> 第五轮我照做了，把键修对了；F1 说明还差一层：**键修对之后，要问「这个键在历史数据上
> 存不存在」**。我的新判据对**将来**写入的行成立，对**已经落盘**的行永不命中——而去重分支
> 存在的全部意义就是拦住重试，历史行恰恰是最可能被重试的那批。
> 可迁移的一句话：**给已有数据加判别字段时，先问没有这个字段的旧数据走哪条路**；
> 「新数据都对」不等于修好了，往往等于把洞挪到了你不看的那一半。
>
> F2 / F3 则是「修了一处先问同族还有谁」的第三次（R1 台账读取面 → T4 导出面 → 本轮
> 导出的其余分支）。同一个函数里，两个分支带了 hex、另两种情形整行丢——
> 各分支各拼一份 dict 就必然漂。现在只有 `_carried` 一个构造点。

**一处如实记账**：`c64e0ff2` 的提交信息把新增回归写成「22 条」，实测是 **16 条**
（7 + 1 + 8，`--collect-only` 实测该文件 14 → 30）。提交信息已落盘不改写，在此更正；
本页与 §6.1 的差量表以实测为准。

## 4 变异测试（A13 有牙验收，35 条）

harness `/tmp/xfp0/mutate.py`：每次运行前清 `__pycache__` 且 `PYTHONDONTWRITEBYTECODE=1`
（防「同长度改动 + 秒内还原」被 `.pyc` 缓存伪造成回归），锚点唯一性由 harness 自检
（M4 第一版命中两处被拒，M3 在重构后命中零处被拒——两次都是 harness 先发现的）。

| # | 变异 | 期望红 | 实测 |
|---|---|---|---|
| M1 | 差异恒空 | A5 | ✅ |
| M2 | 绕过共用门 | A3 / A7 / A8 | ✅ |
| M3 | 系统 drafted 冒充用户草稿 | A1 | ✅ |
| M4 | 命令返回即 abandoned | A9 | ✅ |
| M5 | 关联键去掉用户 | A1 隔离用例 | ✅ |
| M6 | 确认行冒充最新草稿（回退 S5） | S5 | ✅ |
| M7 | 过期解除遮蔽（回退 S8） | S8 | ✅ |
| M8 | 残片吃掉下一次写入（回退 N2） | N2 | ✅ |
| M9 | 关闭后仍可提交（回退 S9） | S9 | ✅ |
| M10 | 确认重试不去重（回退 S6） | S6 | ✅ |
| M11 | 确认丢掉用户机检条件（回退 S1） | S1 | ✅ |
| M12 | 改点伪造第二次确认（**写入侧**） | S7 | ✅ |
| M13 | 读取面不去重（**读取侧**） | S7 | ✅ |
| M14 | 整文件解码（回退 R1） | R1 | ✅ |
| M15 | 关闭失败不补终态（回退 R2） | R2 | ✅ |
| M16 | 复用草稿找不回来（回退 R3） | R3 | ✅ |
| M17 | 手填确认不验尝试（回退 R4） | R4 | ✅ |
| M18 | 落盘不复验尝试（回退 R5） | R5 | ✅ |
| M19 | 去重键漏 due（回退 R6） | R6 | ✅ |
| M20 | 归属跟草稿行走（回退 T1） | T1 | ✅ |
| M21 | 自动续接不查收据（回退 T2） | T2 | ✅ |
| M22 | 全历史内容去重（回退 T3） | T3 | ✅ |
| M23 | 导出仍整文件解码（回退 T4） | T4 | ✅ |
| M24 | 同尝试新版顶掉收据（回退 Q2） | Q2 | ✅ |
| M25 | 手填豁免终态校验（回退 Q3） | Q3 | ✅ |
| M26 | 提交身份不含版本序号（回退 U1） | U1 | ✅ |
| M27 | 确认身份不含来源版本（回退 U2） | U2 | ✅ |
| M28 | 导出残片不可逆（回退 U3） | U3 | ✅ |
| M29 | 确认动作唯一但 script_id 沿用同秒内容哈希（回退 V1） | V1 | ✅ |
| M30 | 坏 UTF-8 行只留预览、丢原始字节（回退 V2） | V2 | ✅ |
| M31 | 坏 JSON 行丢 `_unparsed_bytes_hex`（回退 V2） | V2 | ✅ |
| M32 | 拆掉遗留确认行的内容身份去重，只按动作键认（回退 F1） | F1 | ✅ |
| M33 | 遗留行身份漏掉 `due`：改回检日期被旧行吞掉 | F1 边界 | ✅（只红 `[due]` 一个变体） |
| M34 | 导出丢弃合法 JSON 非记录行（回退 F2） | F2 | ✅（红在 5 个非记录变体） |
| M35 | 导出静默跳过全空白行（回退 F3） | F3 | ✅（红在 2 个空白变体） |

第四轮（M1–M28，旧 harness `/tmp/xfp0/mutate.py`）：全部还原后 `135 passed`，工作树无残留。
原始输出 `/tmp/xfp0/mutations.txt`。

**第五轮起 runner 入仓**：`scripts/review_probes/run_extraction_mutations.py` + 冻结定义
`scripts/review_probes/extraction_mutations.json`（M1–M31，每轮全量重放，不再依赖 /tmp）。
与旧 harness 的差异全部 fail-closed：

- **锚点必须恰好命中一次**——旧版失配是「跳过继续跑」（本页 §4 曾专门写「跳过的锚点等于
  没有牙」当纪律），新版直接断言中止，纪律变成 exit code；
- **collection error ≠ 红**——红要求 `exit=1` 且 `failures>0` 且 `errors=0`，收集错误冒充不了牙；
- **只测已提交 revision**——runner 自建 detached 临时树，定义与被执行的 runner 都从**那棵树**里读
  （两者与调用方逐字节相等才开跑），未提交改动混不进证据；
- 每条变异留 diff、红 / 绿完整日志（含 command/cwd/revision 头）、JUnit、改前 / 改后 / 还原三个
  sha256；还原按原字节写回并断言相等，逐条重跑绿 + 收尾全量绿 + 树 porcelain 干净才写
  `complete=true`；失败保留树用于诊断。
- 跑在 `-B` + `PYTHONDONTWRITEBYTECODE=1` 下（.pyc 缓存教训照旧），`FORESIGHT_USERS_DIR`
  指向隔离目录、`FWP_TEST_RECEIPT=0`（局部变异不产全量收据，不污染收据流）。

第五轮读数：基线 `149 passed` → **M1–M31 逐条 RED**（failures>0、errors=0）→ **逐条还原 GREEN**
→ 收尾 `restored-full` `149 passed`；`complete=true`，`definitions_sha256=200aa1f2…`
与仓内冻结文件 shasum 一致。**该轮已由独立复审在冻结 `37a4e7b7` 上重放，31/31 零偏差**
（§6.4），两次 `definitions_sha256` 相同。

第六轮读数（在 §6.1「最终读数」绑定的 revision 上，35 条）：基线 `165 passed` →
**M1–M35 逐条 RED** → 逐条还原 GREEN → `restored-full` `165 passed`；`complete=true`、
`final_status` 空（树 porcelain 干净）、35 条 `before_sha256 == restored_sha256`。
证据目录 `~/.finance-runtime/reviews/extraction-closeout-20260915/mutations-<该 revision>/`。

> **这一轮 runner 自己派上了用场：它在 M10 上 fail-closed 中止了整次运行。**
> F1 的修复改写了去重循环、F2/F3 的修复把四个分支的搬运 dict 归一到 `_carried`，
> 于是 M10 / M23 / M30 / M31 四条旧锚点命中 0 次。第四轮遇到同样的事时，旧 harness
> 是「跳过继续跑」，靠人记得「跳过的锚点等于没有牙」并逐条重锚；这次是 exit code 直接
> 把话说死——**纪律写进文档会漂，写进退出码不会**。四条已逐条重新锚定到**同一语义**
> （不是换个更好咬的地方）：M10 关掉整条去重含新旧两支、M23 退回整文件一次解码、
> M30/M31 让两支各自绕过 `_carried` 只留预览（归一之后仍要逐支证明有牙）。
> 重锚后全量 35 条自检：锚点恰好命中一次 + 改后可编译 + 红来自各自声明的 targets。

> **第四轮的改动打失效了四个旧锚点**（M16 / M19 / M22 / M23——它们的代码区域被 U1–U3
> 与 Q2 重写过），harness 报「锚点命中 0 次，跳过」。已逐条重新锚定：
> **「跳过」的锚点等于没有牙，不能留在数字里充数。** 28/28 全部 RED→GREEN。
（M10 / M3 / M4 的锚点在历次重构后失配过，每次都是 harness 的唯一性自检先发现的。）

> M12 第一版是「没有牙」：写入侧回退后，读取侧的去重把它兜住了，测试照样绿。
> 说明**同一个不变量的两道防线必须分别钉**，只断言最终结果会漏掉其中一道。
> 补了一条直接断言「改点行里没有 `action_event`」的用例之后，两道各有独立的牙。

## 5 既有测试的改动（只加不减）

- `test_guided_reading_daily_seam.py::ProductionSeamIsWired`：接缝函数换成 `daily_section`
  后断言改指新名字，并**加两条**（`hint=` 真的接到 merge 上；`build_for_daily_review`
  仍是 2 元组视图、不是死代码）。
- `test_observation_extraction_first.py` 两条按真实行为重写（见 §3.1 末）。
- 复审返修未改写任何既有断言，只新增 14 条（R1–R6）。

**没有删除或放松任何既有语义断言**；checkpoint / 投影 / hindsight / late 的测试一行未动。

## 6 最终门禁

| 叶子 | 命令 | 结果 |
|---|---|---|
| python-lint | `ruff check .` | ✅ |
| python | `pytest -q -p no:randomly` | 见 §6.1 |
| frontend-lint / typecheck / test / build | `pnpm --dir intelligence/webapp …` | ✅ 四条均 exit 0 |
| e2e | `PATH=.venv-workbench/bin:$PATH pnpm test:e2e` | ✅ **15 passed (1.1m)** |
| registry-check | `market_feature_store.cli registry-check` | ✅ exit 0，「registry 校验通过（档位/表名/计划步骤归属）」 |

> 新树跑前端叶子前要先 `pnpm --dir intelligence/webapp install --frozen-lockfile`：
> 不装 `node_modules` 时 `eslint: command not found` 的退出码与「真红」一模一样，
> 那是**无结论**不是红。e2e 还要把 `.venv-workbench/bin` 放进 `PATH`，否则
> playwright 的 webServer 回落宿主 `python3`（无 uvicorn），在任何测试跑起来前就死。

### 6.1 全量 pytest 读数

```
9690 passed, 77 skipped, 2 xfailed, 17 warnings in 745.36s (0:12:25)   exit 0
```

收据校验（把「收据树 == 被测树」从规程文字变成 exit code）：

```
$ .venv-workbench/bin/python scripts/check_test_receipt.py \
$ cd .claude/worktrees/xfp0-final-04c68c54          # ← 专为取读数新建的独立树
$ .venv-workbench/bin/python scripts/check_test_receipt.py \
      ~/.finance-runtime/test-receipts/20260914T043310Z-04c68c54.json \
      --expect-revision 04c68c54
  读数     passed=9690 failed=0 error=0 skipped=77
  ✓ revision 一致   ✓ 解释器一致   ✓ python 版本一致   ✓ 依赖指纹一致
  ✓ 收据来自干净树   ✓ 依赖门禁未被绕过   ✓ 收据 revision == 04c68c54a49b
✅ 可采信 —— 收据成立的条件与当前环境一致，无需重跑。        VALIDATOR_EXIT=0
```

差量对账：

| | 基线 `d7e5380` | 最终 `04c68c54` | 差量 |
|---|---|---|---|
| passed | 9554 | 9690 | **+136** |
| failed | 0 | 0 | **0** |
| skipped | 77 | 77 | 0 |
| xfailed | 2 | 2 | 0 |

**+117 逐条点得出名字**，不是「总数不增所以没回归」这种含糊口径：

| 来源 | 条数 |
|---|---|
| `test_observation_extraction_first.py`（A1–A14） | 77 |
| `test_extraction_first_review_fixes.py`（S1–S10/N2/N3 25 + R1–R6 14 + T1–T4 7 + Q2/Q3 4 + U1–U3 8） | 58 |
| `test_guided_reading_daily_seam.py`（2 元组视图不是死代码） | 1 |
| 合计 | **136** |

> 逐跳对照：`7a86ce4e` 9657P → `b916091e` 9671P（+14 = R1–R6）→ `b69ac4b4` 9678P
> （+7 = T1–T4）→ `c9ebab07` 9682P（+4 = Q2/Q3）→ `04c68c54` 9690P（+8 = U1–U3）。
> 每一跳的增量都点得出名字。

> **取法这次终于对了，前两次不是。** 本次全量跑在**专为取读数新建的 detached 树**
> （`xfp0-final-04c68c54`）上：脚本在跑前跑后各打一次 `git status --short` 与
> `rev-parse HEAD`，前后都是空 + `04c68c54`。
>
> 此前两次（`c9ebab07` 与更早那次）都取在共享工作树上，而并驻 agent 在跑测期间提交过，
> 收据记的 revision 因此不是起跑时那个——正是本页 §0 的形状。那两次结论仍可采信
> （`git diff` 证明中途那笔是 docs-only），但**理由是事后补的，不是取法本身保证的**。
> 基线那次一开始就用的独立树，四轮之后终于把最终读数也改回同一做法。

> 耗时 347s → 357s：两次都在安静机器上、同一解释器、同一依赖指纹下取得，
> 这 10s 属于噪声量级，**不作为耗时结论**。

#### Closeout 读数（第五 / 六轮；取法同上：专建 detached 树、跑期零改动、收据绑定）

```
基线 1fef3d27（= 本轮 gitea/main）：9617 passed, 77 skipped, 2 xfailed   exit 0
第五轮 e20302a6                  ：9767 passed, 77 skipped, 2 xfailed   exit 0
最终   3b0531b9（本页唯一 SHA 来源）：9783 passed, 77 skipped, 2 xfailed   exit 0
```

**最终读数**取在 `~/.finance-runtime/reviews/extraction-closeout-20260915/gate3/finance-workspace-private`
（专为取读数新建、detached 于顶端）：脚本跑前跑后各打一次 `git status --porcelain` 与
`rev-parse HEAD`，前后都是空 + `3b0531b9`（`gate3/status-{before,after}.txt`、
`revision{,-after}.txt`）。收据校验：

```
$ cd ~/.finance-runtime/reviews/extraction-closeout-20260915/gate3/finance-workspace-private
$ .venv-workbench/bin/python scripts/check_test_receipt.py \
      ~/.finance-runtime/test-receipts/20260915T122059Z-3b0531b9.json \
      --expect-revision 3b0531b9832df571897c6a5e75c305b63f9623f2
  读数     passed=9783 failed=0 error=0 skipped=77
  ✓ revision 一致   ✓ 解释器一致   ✓ python 版本一致   ✓ 依赖指纹一致
  ✓ 收据来自干净树   ✓ 依赖门禁未被绕过   ✓ 收据 revision == 3b0531b9832d
✅ 可采信 —— 收据成立的条件与当前环境一致，无需重跑。        VALIDATOR_EXIT=0

# 基线收据 20260915T104747Z-1fef3d27.json（在基线树内同法校验，passed=9617、干净树、exit 0）；
# 第五轮收据 20260915T095136Z-e20302a6.json（gate 树，passed=9767、干净树、exit 0）。三份都留档。
```

> **一次取法上的自我纠正**：最终全量一度在落后一提交的 `c64e0ff2` 上开跑（那时顶端已是
> `3b0531b9`）。发现后直接停掉、另建 gate3 于顶端重取——**落后一提交的收据冒充顶端读数，
> 正是本页 §0 记的那个错**；「差的那一提交只改了 JSON」是事后辩解，不是取法保证的。

差量对账（对 closeout 冻结基线）：

| | 基线 `1fef3d27` | 最终 `3b0531b9` | 差量 |
|---|---|---|---|
| passed | 9617 | 9783 | **+166** |
| failed | 0 | 0 | 0 |
| skipped | 77 | 77 | 0 |
| xfailed | 2 | 2 | 0 |

+166 逐条点得出名字（`--collect-only` 两边核过：三个提取测试文件在最终 revision 共收
**165** 条 = 变异 runner 的 baseline `executed`，接缝文件基线 14 / 最终 15）：

| 来源 | 条数 |
|---|---|
| `test_observation_extraction_first.py`（A1–A14） | 77 |
| `test_extraction_first_review_fixes.py`（S / R / T / Q / U 各轮回归） | 58 |
| `test_extraction_closeout.py`（V1 / V2 §3.5 的 14 + F1 / F2 / F3 §3.6 的 16） | 30 |
| `test_guided_reading_daily_seam.py`（15 − 14） | +1 |
| 合计 | **166** |

### 6.2 一次 1 红与它的归因

第二轮返修后的首跑（`/tmp/xfp0/final3-pytest.txt`）出现 **1 红**：
`test_workbench_conversation_integration.py::test_real_conversation_round_trip_persists_skills_sse_and_three_turns`
（断言第三轮助手消息仍是 `pending` 而非 `completed`）。

判**负载敏感抖动、非本单回归**，三条依据缺一不可：

1. **零路径交集**——该测试文件全文不含 `observation` / `guided_reading`；本单改动全部
   落在 observation 服务与 `observation` CLI 子命令内。
2. **隔离复跑**——单文件连跑两次，6 passed / 6 passed。
3. **本仓成文前例**——`docs/verification/2026-09-07-forward-call-gate-live.md` 记过
   **同一条测试**在高负载下转红、降 load 后同文件 109/109 绿，处置同为「负载敏感、非回归」。

随后两次全量（`final4` 9670P、`final5` 9671P）均 exit 0。**两次读数都留档**，
不按「已知红」掩过去——首跑那份原始输出也在 `/tmp/xfp0/` 里。

### 6.3 Closeout 门禁全叶与审查探针重放（第五 / 六轮）

全部叶子在 gate 树（第五轮，`gate/`）与 gate3 树（第六轮，detached 于顶端）各跑一遍，
exit 码与日志逐叶留档（`gate{,3}/*.exit` / `*.log` / `*.xml`）。**第六轮 gate3 全绿**：
ruff ✅ / 全量 pytest ✅（读数见 §6.1）/ frontend install+lint+typecheck+test(**76**)+build ✅ /
e2e **15 passed** ✅ / registry 四步 ✅ / `audit_ledger_spec_crosswalk` ✅ / dataset `registry-check` ✅。

> 前端与 e2e 叶子本轮的 diff 是**纯 Python**，照样在 gate3 重跑了一遍：
> 「改动不涉及它所以它还是绿」是推理，exit code 才是证据。新树跑前端叶子前仍需
> `pnpm install --frozen-lockfile`，e2e 仍需把 `.venv-workbench/bin` 放进 `PATH`。

三、四轮复审的 **20 条原始探针**（`test_original_four_contracts.py` / `test_version_contracts.py` /
`test_export_bytes.py` / `check_extraction_attempt_contract.py`）在被测树上重放 **20/20 绿**：
把探针文件复制到中立目录、从 gate 树根运行，import 就解析到被测代码
（`pinned-probes-rerun/rerun.xml`；跑前后 gate 树 porcelain 干净）。

> **一条会误导的红，先归因再入档。** 同一批探针若按 QC 快照里的原路径跑
> （`/private/tmp/extraction-qc-<被审 sha>/…`），得 **10 红**——QC 目录是整棵冻结在被审
> revision 的仓快照，自带根 `conftest.py`，pytest 在快照内收集时 import 的是**旧代码**
> （JUnit classname `docs.verification.extraction-f43b89c6.…` 实锤）。那 10 红是已修缺陷在
> 旧代码上的红，不是被测树的红。两种跑法都留档（`gate/original-probes.*` = 快照内、红；
> `gate/original-probes-pinned.*` 与 `pinned-probes-rerun/` = 被测树、绿），
> 探针目录跑前后指纹一致（`gate/probes-tree-{before,after}.txt`，仅头部时间戳行不同）。

### 6.4 独立复审六（2026-09-15）

第五轮之后补的一轮**独立复审**（另一个 agent、独立上下文、自建 detached 复审树，
固定冻结 `37a4e7b7`，全程未改仓内任何文件、未 commit）。它做了三件事，结论各自留档：

| 任务 | 结论 |
|---|---|
| 独立重放当时冻结的 31 条变异（M29–M31 首次由**非提交者**重放） | **零偏差**：`exit 0`、`complete=true`、baseline/收尾均 149、31 条红形状全部合规、31 条还原逐字节相等、`definitions_sha256` 与仓内冻结文件及提交者归档**三方一致** |
| 30 条对抗探针（自己写，不抄仓内测试） | **27 面守住、3 条 CONFIRMED 缺陷**（即 §3.6 的 F1/F2/F3，已返修） |
| 文档抽查四组（§3.5 / §4 / §6.1 / §6.3 对归档证据） | **四组全部对上**：两份收据的 passed/failed/skipped/revision/dirty 与差量 +150、归档变异 run 的 `complete`/sha/149、pinned 探针 20/20 与各叶 exit 0、逐文件收集数 77+58+14=149 与 seam 15 |

守住的 27 面逐条列在 `qc6/REPORT.md` §D（每条都有探针名与运行记录），其中值得单独点出的：
非受控入口的 id 合同与**从 `e20302a6^` 提取并 exec 的旧版 `_make_id` oracle** 逐字符相等
（证明「只改受控确认、旧合同不变」不是自述）；`check_result` 对 10 种伪造读数逐一拒绝
（证明 runner 的 fail-closed 不是注释）；31 条 targets 恰等命中、`-k` 零卷入。

复审方还自己记了**一条勘误**：其第一版 definitions 分析脚本按函数名比对 targets，把类名
targets 全部误报成 stray，v2 修正后为零，两版输出都留档。这条值得抄进纪律——
**报告里的「发现」也要先证伪一次**，否则误报会和真发现一起被下一个人当事实用。

返修后我方重放复审方那 30 条探针：**28 绿 2 红**，两条红都是探针自带的
`test_probe_targets_reviewed_tree`（断言 import 解析到**复审方那棵树**），我在自己的树上跑，
处境不符、非缺陷；已另行打印 `observation_script.__file__` / `personal_export.__file__`
证明绑在被测树上。F1/F2/F3 三条原本红的探针**在返修后全绿**。

## 7 未验证 / 明确不在本次范围

- **真人效果完全未验证。** §7 三项阈值未填，实验未开跑。`read_completed` 只证明
  **系统成功交付**，不证明人读完或学会；`pending` 不等于离开。
- **P1–P5 未做**：知识分类、预埋提问、勾稽 / 试教台、§4.5 方案 C 均未实现。
- **未推、未合 main、未部署、未改生产运行时。** 合并需用户明确确认。
- **生产库上的身份解析未在本单跑过**：closeout 补了一条真 CLI + 真实身份解析 + 真实
  River 切片的全链用例（临时 DuckDB 固定夹具，§3.5），A1–A15 主体用例仍对
  `river.slice_river` / `resolve_identity` 打桩——打桩不再是唯一证据，但**生产库**上仍只有
  质检方的旁证（16 个临时库场景 + 少量只读生产解析），不是本单的。
- **`--from-draft` 与 `--from-slice` 同传时后者胜**，未做互斥拒绝，无测试。
- **提取门未过时退出码是 0**（与既有「带读未开启 → 0」同档；机器判定看 JSON 的
  `blocked` / `code`）。这是一个选择而不是必然。
- **关联键里的 `scope` 是冗余项**（由 `canonical_entity_id` 唯一决定），按工单口径保留。

## 8 最终提交与复跑

- 分支 `fix/extraction-first-closeout`（第五轮起，见 §1.2；`feat/extraction-first-p0` 与各 QC
  分支为历史，合并后清理）；被测 revision 见 §6.1「Closeout 读数」那一段（**唯一来源**）
- 交接 `docs/handoffs/inflight/fix-extraction-first-closeout.md`（状态；
  `feat-extraction-first-p0.md` 已冻结为历史并加转向）+
  `docs/handoffs/2026-09-14-extraction-first-p0-review-fixes.md`（背景全文）
- 复跑：`git worktree add <新树> <§6.1「Closeout 读数」那个 SHA>` → §6 那八条命令
  → 变异一条命令复现：`python scripts/review_probes/run_extraction_mutations.py --output <新目录>`
  （runner 自建 detached 树；锚点唯一 / 可编译 / 执行非空 / 还原逐字节相等全 fail-closed）。
  独立复审可直接复用 `qc6/probe_v1_identity.py` / `probe_v2_export.py` / `probe_runner.py`——
  它们各带一条「我 import 的是哪棵树」的自检，**改那条常量指向你自己的树再跑**。
  **跑全量期间不要碰那棵树**——本页 §0 就是这么栽的。
  > 这里刻意**不写死 SHA**：写死过一次（`7a86ce4e`），下一轮返修后它就指向了旧树，
  > 而复审方按它复跑会漏掉最终修复（复审二实测）。指针只留一处，就是 §6.1 那一段。
- **未推、未合 main。** closeout 分支的 merge-base 就是当前 `gitea/main`（§1.2 冻结基线），
  `git merge-tree --write-tree gitea/main fix/extraction-first-closeout` 预演 **0 冲突**
  （`~/.finance-runtime/reviews/extraction-closeout-20260915/mergetree.txt`）。合并前按
  「比较基准是目标分支不是快照」对**当时**的 `gitea/main` 重新预演，并对工单 INDEX
  这个热文件跑 `git merge-tree` 列新造冲突。
