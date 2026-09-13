# 收据 · 工单 #53 提取前置 P0（2026-09-14）

工单 `docs/superpowers/specs/2026-09-14-extraction-first-p0-workorder.md`。
设计依据 `~/foresight/docs/specs/2026-09-13-extraction-first-spec.md` rev.4（金融仓外，未改）。

> **工程完成 ≠ 真人有效。** 本页只证明 §6 的 A1–A15 工程验收成立。
> §7 三项阈值（观察周期 / 可接受额外耗时 / 撤回条件）**未填**，真人实验**未开跑**，
> 本页不含任何真人读数。

---

## 0 一句话结论

带读披露之前先收用户自己的观察剧本，这道顺序门被 `read` / `confirm --from-slice` /
`skip` / 日报接缝**共用同一份判定**；门没过时 `guided_reading.build` 一次都不被调用。
新增 76 条验收全绿，五个变异逐条 RED→GREEN，全量 pytest 相对干净基线 **+76 通过、0 新增失败**。

## 1 环境与基线

| 项 | 值 |
|---|---|
| 工作树 | `/Users/a77/finance-workspace-private/.claude/worktrees/feat-extraction-first-p0`（`git worktree add`，干净新树） |
| 分支 | `feat/extraction-first-p0` |
| 基线 revision | `d7e5380551ba92758935d268fdd0e6fbfdd51ce8`（= 开工时 `gitea/main`，与工单冻结号一致，`git fetch gitea` 后核过） |
| 最终 revision | `95f3c5e7`（代码 + 测试 + 文档一并提交；本页回填 SHA 的那一笔是它之后的一个 doc-only 提交——收据自指的经典问题：回填 SHA 必然改变 SHA，被测的是 `95f3c5e7` 的树） |
| 解释器 | `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（AGENTS.md 指定；宿主 `python3` 缺依赖，用错会得到一个看起来完全合理的偏高失败数） |
| 平台 | macOS darwin 25.4.0 / pytest `-q -p no:randomly` |
| 原始输出 | `/tmp/xfp0/`：`baseline-pytest.txt`、`final-pytest.txt`、`mutations.txt`、`fe-{lint,tc,test,build,e2e}.txt`、`registry.txt` |

### 1.1 干净基线读数（改动前，同树同解释器）

```
9554 passed, 77 skipped, 2 xfailed, 17 warnings in 526.44s   exit 0
```

基线是**全绿**，所以下文任何一条失败都不能推给存量红——这次没有存量红可推。

## 2 改了什么

| 文件 | 性质 | 一句话 |
|---|---|---|
| `intelligence/services/observation_extraction.py` | 新增 354 行 | 判定侧：身份解析 / 关联键 / 顺序门 / 字段差异 / 系统骨架引用哈希。**全是纯函数，不写盘** |
| `intelligence/services/observation_script.py` | +595/−? | 台账侧（唯一写入者）：`record_kind` 三分型、草稿版本、提取尝试、五事件、flock + 整行 fsync |
| `intelligence/services/guided_reading.py` | +217 | `gated()` 共用门（门在 `build` 之前）、差异段渲染、`daily_section()` 接缝与入口提示 |
| `intelligence/cli.py` | +455 | `observation draft` / `close` / `list --events` 新命令；`read` / `confirm` / `skip` / daily 接入同一道门 |
| `intelligence/services/personal_export.py` | +5/−1 | 台账描述改成「台账行（三类）」——行数不再等于剧本数，说明必须跟上 |
| `docs/learning/ledger-map.md` | +1 行 | 登记分型格式与唯一写入者 |
| `docs/superpowers/specs/2026-09-01-workorders-INDEX.md` | +1 行 | 登记 #53 |
| `intelligence/tests/test_observation_extraction_first.py` | 新增 1009 行 / 76 条 | A1–A14 验收 |
| `intelligence/tests/test_guided_reading_daily_seam.py` | +16/−4 | 接线断言改指 `daily_section` 并**加强**（见 §5） |

### 2.1 三个值得单独记的设计取舍

1. **成功事件随剧本行一次写入，不追加第二行。** `draft_submitted` / `script_confirmed`
   存在成功剧本行的 `action_event` 里，读取时由 `projected_events` 投影出来。
   两次写会留下「剧本在、事件不在」的窗口，而那种断裂事后无法与「根本没提交」区分。
2. **顺序门在 `build` 之前，且「先记跳过、再生成骨架」这个顺序放进共用门里**（`gated(on_skip=...)`），
   不交给每个调用方自觉。靠约定维持的顺序，总有一个入口会写反，而写反了从输出上看不出来。
3. **关联键里的 `scope` 由身份推导，不取用户 `--scope` 填的那个**（`extraction.scope_for`，
   两侧共用同一个函数）。工单 §2.1 把 scope 写进了键；直接读用户填的值会让
   「填了 index、系统推 theme」把同一个阅读目标劈成两个键，表现是「昨天写的草稿凭空消失」。
   剧本正文里的 `scope` 仍是用户填的那个，受同一道硬门校验，两者互不干扰。
   > ⚠ **如实记一句**：`scope` 由 `canonical_entity_id` 唯一决定，放进键里不增加区分度。
   > 按工单口径实现了，但它是冗余项；将来若要精简键，这是可以去掉的那一位。

## 3 逐条验收（A1–A15）

全部用隔离 `FORESIGHT_USERS_DIR` 临时目录 + 固定本地切片 + 显式写进夹具的开关状态；
**不碰真实用户台账、不碰真库**（`river.slice_river` 与 `resolve_identity` 都打桩）。

| # | 验收 | 观察面 | 结果 |
|---|---|---|---|
| A1 | 草稿 / 身份 | `A1DraftAndIdentity`（9 条）：draft→list 可查；最后成功版生效且旧版保留；改放弃条件也是新版；用户 / 相邻交易日 / 另一实体 / 另一作用域互不放行；名字与代码对齐同一目标；解析不出身份退 2 且零落盘；系统 `drafted` 不冒充用户提交；草稿不登记 checkpoint | ✅ |
| A2 | 原阳性对照 1 | `A2IdenticalBusinessFields`（3 条）：业务字段一致而 ID / 时间 / 顺序 / 空白 / 重复项不同 → `[]`；两边空不崩；无系统骨架**不报成一致** | ✅ |
| A3 | 原阳性对照 2 | `A3ReadIsBlockedWithoutDraft`（3 条）：文本与 JSON 都被拦；`gr.build` 调用次数 **== 0**；无 checkpoint、无剧本行 | ✅ |
| A4 | 原阳性对照 3 | `A4DraftGoesThroughTheSameHardGate`（3 条）：方向词退 2 带 `E_DIRECTION`；结构违规（无放弃条件）同门拒绝；被拒不替换已有有效版 | ✅ |
| A5 | 非空差异 | `A5DiffContent`（5 条）：双向差异项逐条断言；增变量只出现在用户侧且一致字段不进差异；改放弃条件可见；跳过路径不可比；差异段过用词 lint | ✅ |
| A6 | 跳过 | `A6SkipDraft`（5 条）：显式 skip 放行且只记一次；**跳过事件在 `build` 被调用时已落盘**（顺序被钉住）；授权不跨新尝试 / 不跨目标；有草稿时用草稿且**不写虚假跳过** | ✅ |
| A7 | 出口覆盖 | `A7AllExitsShareTheGate`（6 条）：`confirm --from-slice` 与 `skip` 都过门且门没过时 `build` 零调用；`list --json` 遮蔽系统骨架正文、有草稿后解除；完整手填 confirm 保留行为且事件集合恰为 `{script_confirmed}` | ✅ |
| A8 | 日报接线 | `A8DailySeam`（5 条）：无草稿只加入口提示、非带读正文一字不动且过 lint；后台运行**零尝试零事件**；带读关闭时连提示都不出、`merge_into_daily_review` 仍返回同一个对象（`is`）；有草稿则带读 + 差异，且后台写出**不计** `read_completed` | ✅ |
| A9 | 事件续接 | `A9AttemptLifecycle`（7 条）：read→draft→read 同一 attempt、有提交与完成、无 abandoned；read→close 恰一条 abandoned 且重复 close 不叠加；**等待保持 pending**；已作答后 close 不记 abandoned；已关闭尝试不能复活；五事件分列可查；late 确认仍是确认事件（`script_status=late`、`checkpoint_id=None`）；事件不进剧本分母 | ✅ |
| A10 | 重试 / 并发 / 失败 | `A10RetryConcurrencyFailure`（9 条）：同尝试同动作不重复；并发 `open_attempt` ×5 只得一个 pending；成功事件与剧本行同一次写（无第二条独立行）；跨用户 / 跨目标 attempt 拒绝退 2；**收据落盘失败 → 退出码 1 + 无 `read_completed` + 尝试保持 pending**；已完成尝试重放收据不重放正文；原始导出保留三类而 `load()` 只数剧本 | ✅ |
| A11 | 开关矩阵 | `A11SwitchMatrix`（7 条）：显式 `--off` 压过环境 `on` 且**连尝试都不建**；`--skip-draft` 打不开关闭的带读、也不写跳过事件；环境 on/off；新用户默认开、老用户默认关；**只写提取台账不翻转新老用户判据**；及时确认写 checkpoint 后次日默认关而显式 `--on` 仍能 draft/read；带读关闭时独立 draft 照样能存 | ✅ |
| A12 | 旧合同 | `A12LegacyContracts`（7 条）+ 既有回归：无类型旧剧本仍可读且计入状态数；事件不进状态数 / 过期 / 非交易日扫描；未知 `record_kind` 既不是剧本也不是事件但**不丢**；`--from-slice` 确认仍带投影哈希；`--from-draft` 确认是 `user_authored` 且带 `source_draft_id`、**不伪造投影**；draft 永不自动确认；hindsight 标记活过 draft 这一跳 | ✅ |
| A13 | 有牙验收 | 见 §4 | ✅ 5/5 |
| A14 | 不评分 | `A14NoScoring`（6 条）：差异载荷键恰为 `{field,label,user_only,system_only}` 且**全部值都是字符串（一个数都没有）**；读收据键在来源关联白名单内且不含任何数值；差异段无比率 / 分数正则命中；新模块不定义评分型符号（探针先在已知坏样本上验证会红）；profile / derived / answer_scores / experience_cards / interactions / checkpoints 一个字未写 | ✅ |
| A15 | 收据 | 本文件 | ✅ |

> **A14 为什么不是关键词扫描**：工单明写「不以全仓关键词零命中作证」。全文关键词扫描
> 既抓不住 `d = len(a & b) / len(a | b)` 这种没有关键词的评分，又会把
> `## 你写的 vs 系统列的（只列字段差异；不评分、不判谁对）` 这种**声明红线的文案**
> 判成违规。改成结构判据（载荷里没有数 / 收据只有来源关联 / 别的台账零写入）。

> **A14 顺带修掉一处真问题**：初版把 `diff_field_count` / `comparable` 写进了 read 收据。
> 工单 §2.5 是「只持久化必要来源关联，差异展示时重算」——「差了几项」是派生的大小，
> 存进台账下一个人就会拿它做时间序列，而那就是收敛指标。已删，收据只留
> `system_script_ref` / `projection_hash` / `source_draft_id` / `granted_by`。

## 4 变异测试（A13 有牙验收）

harness `/tmp/xfp0/mutate.py`：每次运行前清 `__pycache__` 且 `PYTHONDONTWRITEBYTECODE=1`
（防「同长度改动 + 秒内还原」被 `.pyc` 缓存伪造成回归），变异后跑对应用例、还原后再跑一次。

| # | 变异（唯一锚点，改一处） | 期望红 | 实测 |
|---|---|---|---|
| M1 | `observation_extraction.diff_scripts`：`if mine == theirs:` → `if True:`（差异恒空） | A5 | 变异 3 failed / 还原 5 passed ✅ |
| M2 | `guided_reading.gated`：`if not decision.allowed:` → `if False:`（绕过共用门） | A3 / A7 / A8 | 变异 5 failed / 还原 14 passed ✅ |
| M3 | `observation_script.user_drafts`：作者判据 `author_origin == AUTHOR_USER` → `status == "drafted"`（系统骨架冒充用户草稿） | A1 | 变异 1 failed / 还原 8 passed ✅ |
| M4 | `cli.cmd_observation_read`：门没过时先记一条 `abandoned` 再返回（命令返回即离开） | A9 | 变异 2 failed / 还原 8 passed ✅ |
| M5 | `observation_script.user_drafts`：`_key_of(rec) == target` → `_key_of(rec)[1:] == target[1:]`（关联键去掉用户） | A1 隔离用例 | 变异 1 failed / 还原 8 passed ✅ |

全部变异还原后 `76 passed`，工作树无变异残留（`grep` 过 `if True:` / `if False:` / 注入的事件行，clean）。
原始输出 `/tmp/xfp0/mutations.txt`。

## 5 既有测试的改动（只加不减）

`intelligence/tests/test_guided_reading_daily_seam.py::ProductionSeamIsWired` 的源码断言
原本钉 `build_for_daily_review` 这个名字。接缝函数换成 `daily_section`（多带「入口提示」
与「字段差异」两个出口）后，断言改指新名字，并**加了两条**：

- `assertIn("hint=", src)`——只改名不把提示接到 merge 上，日报那一段会静默消失；
- 新增 `test_two_tuple_view_still_exists_for_existing_callers`——`build_for_daily_review`
  仍是 `daily_section` 的 2 元组视图，不是无人调用的死代码。

**没有删除或放松任何既有语义断言**；checkpoint / 投影 / hindsight / late 的测试一行未动。

## 6 最终门禁

| 叶子 | 命令 | 结果 |
|---|---|---|
| python-lint | `.venv-workbench/bin/python -m ruff check .` | ✅ All checks passed |
| python | `.venv-workbench/bin/python -m pytest -q -p no:randomly` | 见下 |
| frontend-lint | `pnpm --dir intelligence/webapp lint` | ✅ exit 0 |
| frontend-typecheck | `pnpm --dir intelligence/webapp typecheck` | ✅ exit 0 |
| frontend-test | `pnpm --dir intelligence/webapp test` | ✅ exit 0 |
| frontend-build | `pnpm --dir intelligence/webapp build` | ✅ exit 0 |
| e2e | `PATH=.venv-workbench/bin:$PATH pnpm test:e2e` | ✅ **15 passed (1.1m)** |
| registry-check | `.venv-workbench/bin/python -m market_feature_store.cli registry-check` | ✅ exit 0，「registry 校验通过（档位/表名/计划步骤归属）」 |

> **e2e 的坑记一句**：新 worktree 里必须把 `.venv-workbench/bin` 放进 `PATH`，否则
> playwright 的 webServer 回落到宿主 `python3`（没有 uvicorn），在任何测试跑起来之前就死掉。
> 前端四叶子还需要先在**新树里**跑一次 `pnpm --dir intelligence/webapp install --frozen-lockfile`：
> 新树没有 `node_modules`，不装就是「无结论」而不是「绿」，而两者在 `exit != 0` 上长得一样。

### 6.1 全量 pytest 读数

```
9631 passed, 77 skipped, 2 xfailed, 17 warnings in 984.91s (0:16:24)   exit 0
```

相对干净基线 `9554 passed, 77 skipped, 2 xfailed / 0 failed`：

| | 基线 | 最终 | 差量 |
|---|---|---|---|
| passed | 9554 | 9631 | **+77** |
| failed | 0 | 0 | **0** |
| skipped | 77 | 77 | 0 |
| xfailed | 2 | 2 | 0 |

**+77 逐条对得上**：`test_observation_extraction_first.py` 76 条 +
`test_guided_reading_daily_seam.py::test_two_tuple_view_still_exists_for_existing_callers` 1 条。
没有「总数不增所以没回归」这种含糊口径——差量是可点名的。

> 耗时 984s vs 基线 526s：这次跑的时候机器上同时有前端 `install` / e2e 在占 CPU，
> 不是代码变慢。两次读数**不构成耗时对照**，要比耗时得在安静机器上重跑一对。

**中途作废过一次读数**：第一次全量跑到 30% 时我改了 `cli.py`（把一处字面量换成常量），
那次读数的条件不自洽（部分模块按旧版收集、部分按新版导入），已杀掉、代码定稿后重跑。
上表是重跑的结果。

## 7 未验证 / 明确不在本次范围

- **真人效果完全未验证。** §7 三项阈值未填，实验未开跑；本页任何数字都不是真人读数。
  `read_completed` 只证明**系统成功交付**，不证明人读完或学会；`pending` 不等于离开。
- **P1–P5 未做**：知识分类、预埋提问、勾稽 / 试教台、§4.5 方案 C 均未实现，无 `object_type` 新增。
- **未合 main、未推、未部署、未改生产运行时。** 合并需用户明确确认。
- **`--from-draft` 与 `--from-slice` 同时给时后者胜**（按代码顺序），未做互斥拒绝——
  边缘用法，未写测试。
- **`observation draft` 的身份解析要开一次真库**（read-only）。本次全部用例都打桩，
  真库路径上的身份解析**未在本次跑过**；它复用的是 `river.resolve_entity` 现有实现，
  但「本单没有真库证据」这一点如实记在这里。
- **提取门未过时退出码是 0**（与既有「带读未开启 → 0」同档，机器判定看 JSON 的
  `blocked` / `code`）。这是一个选择而不是必然，写在这里以便复核。

## 8 最终提交

- 分支：`feat/extraction-first-p0`
- 被测 revision：**`95f3c5e7`**（`feat(observation): 工单 #53 提取前置 P0……`，12 files changed,
  3061 insertions, 51 deletions；11 道 pre-commit 全过）
- 交接：`docs/handoffs/inflight/feat-extraction-first-p0.md`
- 复跑本页：`git checkout 95f3c5e7` → `git worktree add` 新树 → §6 那八条命令
  （前端先 `pnpm --dir intelligence/webapp install --frozen-lockfile`；e2e 要把
  `.venv-workbench/bin` 放进 `PATH`）→ 变异按 §4 表里的五组 old→new 字符串手改复现，
  每次改前清 `__pycache__`。
- **未推、未合 main。** 合并需用户明确确认；合并前若 `gitea/main` 已前移，按「送审的
  比较基准是目标分支，不是快照」重新 diff，并对工单 INDEX 这个热文件跑一遍
  `git merge-tree` 列新造冲突。
