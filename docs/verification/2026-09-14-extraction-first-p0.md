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
| 被测最终 revision | `b916091e`（第二轮复审返修后；`7a86ce4e` 是第一轮的被测树，读数保留在 §6.1 对照里） |
| 解释器 | `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（AGENTS.md 指定） |
| 平台 | macOS darwin 25.4.0 / `pytest -q -p no:randomly` |
| 原始输出 | `/tmp/xfp0/`：`baseline2-pytest.txt`（基线）、`final2/3/4/5-pytest.txt`（历次最终，含 §6.2 那次 1 红的原始输出）、`mutations.txt`、`fe-*.txt`、`registry.txt`、`receipt-*.txt`、`mergetree.txt` |

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

## 2 改了什么

| 文件 | 一句话 |
|---|---|
| `intelligence/services/observation_extraction.py` | **新增**。判定侧：身份解析 / 关联键 / 顺序门 / 字段差异 / 骨架引用哈希。全是纯函数，不写盘 |
| `intelligence/services/observation_script.py` | 台账侧（唯一写入者）：`record_kind` 三分型、草稿版本、提取尝试、五事件、flock + 整行 fsync + 残片封口、动作认领与去重 |
| `intelligence/services/guided_reading.py` | `gated()` 共用门（门在 `build` 之前）、差异段渲染、`daily_section()` 接缝与入口提示 |
| `intelligence/cli.py` | `observation draft` / `close` / `list --events`；`read` / `confirm` / `skip` / daily 接入同一道门 |
| `intelligence/services/personal_export.py` | 台账描述改成「台账行（三类）」——行数不再等于剧本数 |
| `docs/learning/ledger-map.md` | 登记分型格式与唯一写入者 |
| `intelligence/tests/test_observation_extraction_first.py` | **新增** A1–A14，77 条 |
| `intelligence/tests/test_extraction_first_review_fixes.py` | **新增** 两轮返修回归，39 条（首轮 S1–S10/N2/N3 + 复审 R1–R6） |
| `intelligence/tests/test_guided_reading_daily_seam.py` | 接线断言改指 `daily_section` 并加强 |

提交链：`95f3c5e7`（实现）→ `b42dc9bf`（收据）→ `08ca525f`（首轮返修 12 项）→
`7a86ce4e`（撤回脏树读数 + 压缩交接）→ `caba87c7`（回填读数）→
`8410e9d3`（复审返修 6 项）→ `b916091e`（诊断拆句 + 交接回填）→ 本页所在提交。

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
| A13 | 有牙验收：见 §4 | ✅ 19/19 |
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

## 4 变异测试（A13 有牙验收，19 条）

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

全部还原后 `115 passed`，工作树无残留。原始输出 `/tmp/xfp0/mutations.txt`。
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
| e2e | `PATH=.venv-workbench/bin:$PATH pnpm test:e2e` | ✅ **15 passed (48.0s)** |
| registry-check | `market_feature_store.cli registry-check` | ✅ exit 0，「registry 校验通过（档位/表名/计划步骤归属）」 |

> 新树跑前端叶子前要先 `pnpm --dir intelligence/webapp install --frozen-lockfile`：
> 不装 `node_modules` 时 `eslint: command not found` 的退出码与「真红」一模一样，
> 那是**无结论**不是红。e2e 还要把 `.venv-workbench/bin` 放进 `PATH`，否则
> playwright 的 webServer 回落宿主 `python3`（无 uvicorn），在任何测试跑起来前就死。

### 6.1 全量 pytest 读数

```
9671 passed, 77 skipped, 2 xfailed, 17 warnings in 397.58s (0:06:37)   exit 0
```

收据校验（把「收据树 == 被测树」从规程文字变成 exit code）：

```
$ .venv-workbench/bin/python scripts/check_test_receipt.py \
      ~/.finance-runtime/test-receipts/20260914T022225Z-b916091e.json \
      --expect-revision b916091e
  读数     passed=9671 failed=0 error=0 skipped=77
  ✓ revision 一致   ✓ 解释器一致   ✓ python 版本一致   ✓ 依赖指纹一致
  ✓ 收据来自干净树   ✓ 依赖门禁未被绕过   ✓ 收据 revision == b916091e1f43
✅ 可采信 —— 收据成立的条件与当前环境一致，无需重跑。        VALIDATOR_EXIT=0
```

差量对账：

| | 基线 `d7e5380` | 最终 `b916091e` | 差量 |
|---|---|---|---|
| passed | 9554 | 9671 | **+117** |
| failed | 0 | 0 | **0** |
| skipped | 77 | 77 | 0 |
| xfailed | 2 | 2 | 0 |

**+117 逐条点得出名字**，不是「总数不增所以没回归」这种含糊口径：

| 来源 | 条数 |
|---|---|
| `test_observation_extraction_first.py`（A1–A14） | 77 |
| `test_extraction_first_review_fixes.py`（首轮 S1–S10/N2/N3 25 条 + 复审 R1–R6 14 条） | 39 |
| `test_guided_reading_daily_seam.py`（2 元组视图不是死代码） | 1 |
| 合计 | **117** |

> 中途对照：`7a86ce4e`（第一轮返修后）是 9657P，与本行的 9671P 差 14，
> 正是复审返修新增的那 14 条。

> 耗时 347s → 357s：两次都在安静机器上、同一解释器、同一依赖指纹下取得，
> 这 10s 属于噪声量级，**不作为耗时结论**。

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

## 7 未验证 / 明确不在本次范围

- **真人效果完全未验证。** §7 三项阈值未填，实验未开跑。`read_completed` 只证明
  **系统成功交付**，不证明人读完或学会；`pending` 不等于离开。
- **P1–P5 未做**：知识分类、预埋提问、勾稽 / 试教台、§4.5 方案 C 均未实现。
- **未推、未合 main、未部署、未改生产运行时。** 合并需用户明确确认。
- **真库路径上的身份解析未在本单跑过**：全部用例对 `river.slice_river` 与
  `resolve_identity` 打桩。复用既有 `river.resolve_entity`，但没有本单的真库证据。
  （质检独立补测过 16 个临时库场景 + 少量只读生产解析，与 River 现有结果一致；
  那是质检方的证据，不是本单的。）
- **`--from-draft` 与 `--from-slice` 同传时后者胜**，未做互斥拒绝，无测试。
- **提取门未过时退出码是 0**（与既有「带读未开启 → 0」同档；机器判定看 JSON 的
  `blocked` / `code`）。这是一个选择而不是必然。
- **关联键里的 `scope` 是冗余项**（由 `canonical_entity_id` 唯一决定），按工单口径保留。

## 8 最终提交与复跑

- 分支 `feat/extraction-first-p0`；被测 revision **`b916091e`**
- 交接 `docs/handoffs/inflight/feat-extraction-first-p0.md`（状态）+
  `docs/handoffs/2026-09-14-extraction-first-p0-review-fixes.md`（背景全文）
- 复跑：`git worktree add <新树> `7a86ce4e`` → §6 那八条命令 → 变异按 §4 手改复现
  （每次改前清 `__pycache__`）。**跑全量期间不要碰那棵树**——本页 §0 就是这么栽的。
- **未推、未合 main。** `gitea/main` 现为 `1fef3d27`；
  `git merge-tree --write-tree gitea/main HEAD` 预演 **0 冲突**（`/tmp/xfp0/mergetree.txt`）。合并前按
  「比较基准是目标分支不是快照」重新 diff，并对工单 INDEX 这个热文件跑
  `git merge-tree` 列新造冲突。
