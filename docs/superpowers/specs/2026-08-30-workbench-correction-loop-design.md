# 设计：Workbench 纠偏回路——先接写侧

- 日期：2026-08-30
- 状态：Draft v2（只落本文。未改 `intelligence/`，未切 8792）
- v2 改动（2026-08-30 复核，§3 十条事实**逐条实测全对**，含事实 5 那个身份陷阱）：
  ① §5.3 判据从「主语是 X」（语法角色，确定性实现只能退化成词面命中）改为
  **否定词左邻**——初版与 §8 的 W-corr-1 互相矛盾，实施方会靠放宽门来凑绿；
  ② §5.1 / §9 把环境与身份守卫上提到 runtime，services 只留纯文本门，
  否则 §6 正例夹具在 pytest 下永远走不到写入；
  ③ 补 `previous_turn_message` 与 `status` 字段的实测指针；
  ④ §3 事实 4 补注「A 够得着但不必取」。裁决方向未改。
- 预注册：`R-20260830-04`（`claim_ledger_id.py`，分支名 `feat/workbench-correction-loop`，号不回收）
- 来源：2026-08-30 会话（六张地图 → 记忆卡/纠偏进不进 SP → B 并 A → 「纠偏在工作台是不是没接成环，只有打分 repair 是环」）
- 姊妹单（本单不重做）：
  - `2026-08-30-optimized-orchestration-contract-design.md`——目标态只留包椅与 A（本单不改分流）
  - `2026-08-30-coverage-without-number-ownership-design.md`——**读侧**：有主体的研究题开口必取 `memory_lookup` 块或 gap
  - `2026-08-19-user-framework-perspective-bootstrap-design.md`——慢变量迁出滚动纠偏账（工程纠偏挤出金融原则的病灶仍在）
  - `2026-08-26-dream-loop-repoint-design.md`——夜间挖提案，suggest-only，不直写 corrections
- 代码树纪律：从 `gitea/main` 开干净树再改 runtime。本稿允许落主树 untracked。**禁止**把当回合判官/修复当成「已经接上纠偏环」。**禁止**为了闭合环把经验卡/纠偏拼进引擎 A 的宪法 SP。**禁止**把 `default` 当成测试用户跳过写入（那是生产工作台身份）。

## 0. 一句话

Workbench 里「你纠正系统上一句」今天只是聊天上下文，不是纠偏回路。本单只接**写侧**：用户在工作台对话里纠正上一轮回答时，当场 append 到该用户的 `corrections.jsonl`，留收据，失败不挡回答。读侧（下一轮研究开口必取）归覆盖单。两条都落地，环才闭合。

**判别变量**（P0 只锁写侧，读侧不在本单验收）：

1. **正例**：同一会话里先有一条已完成的 assistant 回答，用户再说「不对，应该先看板块容量再下结论」→ 该用户 `corrections.jsonl` 新增一行，`source=workbench_conversation`，`correction` 含「应为」内容，`original` 指向上一轮回答的截断；本回合研究照常跑。
2. **反例**：用户说「这波不对，应该是情绪退潮」（评盘面，不是纠正上一篇答法）→ **零写入**。精度优先，宁可不记。

人话：编码会话里 `AGENTS.md` 已经强制人落账；工作台研究 agent 不会落。本单把「工作台说不对」接到同一本账上，但只收**纠正上一篇答法**的句子，不收对市场本身的吐槽。

---

## 1. 先分清两张环（听反会把本单做成 repair）

| | 当回合判官 / 修复 | 纠偏回路（本单） |
|---|---|---|
| 谁在转 | 代码 ↔ 模型，一回合内 | 你 ↔ 台账 ↔ **下一轮**研究 |
| Workbench 今天 | **已接上**（`repair_coordinator` + `episode_semantic_verifier`；B compose 还有 `repair_unfulfilled_answer`） | **没接上**：UI / `/api/conversations` 零处调 `record_correction` |
| 写到哪 | 不写 `corrections.jsonl` | 必须写 |
| 跨会话 | 不跨 | 设计上要跨 |
| 本单 | ❌ 不动 | ✅ 只接写侧 |

同会话追问「不对」时，模型能看见 `ConversationContext`——那是聊天记忆，换会话、隔一周、换一只同类股就没了。本单不取代对话上下文，只补**跨会话台账**。

闭环要三截：

```
你纠正 → 写入 corrections.jsonl → 下一轮研究自动读到 → 行为真的变
         ^^^^^^^^ 本单 P0              ^^^^^^^^ 覆盖单 P0
```

只做本单、不做覆盖单 = 账上有字、A 开口仍不读（今天的形状）。只做覆盖单、不做本单 = 开口去读一本工作台从不写的账。

---

## 2. 术语

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **纠偏** | 用户纠正**系统上一轮回答**的方法/口径/结论，写进 `corrections.jsonl` | 用户对盘面的判断（「这波不对」）；判官拒稿 |
| **写侧** | 工作台收到用户消息时是否 append 台账 | 把卡拼进 SP |
| **读侧** | 下一轮 A 开口是否必取记忆 | 本单不验收 |
| **精度门** | 不确定就不写 | 信号词「不对」一律落账 |
| **收据** | trace 事件 + 结构化报告一行；不打断对话 | 弹窗确认 |

---

## 3. 已核实事实（实施时不要再探一遍）

1. **工作台写入口不存在**。[实测] `intelligence/runtime/`、`intelligence/api/`、`intelligence/webapp/src/` 对 `record_correction` / `record-correction` **零命中**。唯一写入者是 CLI `cmd_record_correction`（`cli.py:1529`）和编码 agent 按 `AGENTS.md` 跑同一条命令。
2. **`AGENTS.md` 纠偏义务管的是编码会话**，不是工作台研究 agent。信号词「不对 / 应该是 / 不是这样」要求当场 `python3 -m intelligence.cli record-correction`。用户在工作台打同样的字，这条义务到不了生产进程。
3. **引擎 A 不自动灌纠偏**。宪法在 `build_episode_instructions`（无卡、无纠偏正文）；`memory_lookup` 要授权 + 身份 + 模型自己点；`prior_recall` 还要求问句像「上次」。开口预取 `asof_prefetch` **不拉**这本账。覆盖单补读，本单不改这条。
4. **引擎 B compose / foresight / framework-daily 会读**，但 Workbench 研究题 A 接住就不走它们。所以「CLI 落了账、foresight 能看见」证明不了工作台研究环闭合。
   - 补注（别读成「A 完全够不着」）：[实测] 全树读 `corrections` 的有 12 个模块，其中 **`episode_tools.py` 是引擎 A 的工具层**。A **够得着**，但要过「capability 授权 → 身份解析 → 模型自己点 `memory_lookup`」三道，任一不成立就读不到。这跟事实 3 不矛盾——**「够得着」不等于「开口必取」**，那一格正是覆盖单 P0 要补的。
5. **生产工作台身份是 `default`**。[实测] `2026-08-19-user-framework-perspective-bootstrap-design.md` §3.2：launcher 设 `FORESIGHT_USERS_DIR`、不设 `FORESIGHT_USER`，UI 身份 = `default`。`TurnOrchestrator._ingest_track_next_watch`（`conversation_orchestrator.py:5207`）把 `default` 和 `golden-test` / `tester` 一起跳过——**那是跟踪题写 checkpoint 的名单，不能抄到本单**。抄了 = 生产零写入、夹具还绿。
6. **大脑根**：`userspace.users_dir()` = `FORESIGHT_USERS_DIR` > 仓内回落。本机工作台 = `~/.local/share/finance-workbench/users/<id>/corrections.jsonl`。写死仓内 `intelligence/users/` 会再造孤儿账（`R-20260827-16`）。
7. **`record_correction` 已够用**：必填 `correction`，可选 `original` / `principle` / `themes`，append-only，带稳定 `id`。本单只加**旁路字段**（`source` / `conversation_id` / `corrected_message_id` / `plane`），不改必填合同。旧行无这些键，加载必须容缺。
8. **慢变量已被工程纠偏挤出窗口**。[实测] 08-19 spec：常驻只取带 `principle` 的最近 5 条，当时进 prompt 的全是工程/架构类，用户 06-29 金融原则出局。本单若把工作台句子无差别写入且带 `principle`，会再挤一次。因此 P0 **只写 `plane=user_method`**；工程词表命中则不写（编码会话继续走 CLI，不走工作台自动落）。
9. **接线点已有上下文**。`_run_turn_ledgered`（`:1830`）在跑研究前已 `load_conversation` + `build_conversation_context`；`recent_messages` 里能取到上一轮 completed assistant。纠偏摄入必须挂在**研究之前或并行**，且**零占** `research_policy.max_llm_calls` / 工具刀。
10. **梦矿不写这本账**。`dream/miner.py` 自述绝不写 `corrections`。本单不把夜间提案自动转正。

---

## 4. 目标形态

```
工作台用户消息进 TurnOrchestrator
  ├─ 装配 ConversationContext（已有）
  ├─ 本单：精度门 ingest
  │    ├─ 无上一轮 assistant → 跳过
  │    ├─ 评盘面 / 纯情绪 / 工程词表 → 跳过
  │    ├─ 纠正上一篇答法 → record_correction（fail-open）
  │    └─ 收据：trace user_correction_recorded（有则记，无则不挡）
  ├─ 控制器 / 包 / 引擎 A（不动）
  └─ 下一轮研究的读：覆盖单开口必取 memory_lookup
```

写入字段（新行；旧加载容缺）：

| 字段 | P0 |
|---|---|
| `correction` | 用户的「应为」（必填，现有） |
| `original` | 上一轮 assistant 正文截断（上限 240 字，现有可选） |
| `principle` | P0 **不自动编**。用户原文里自己写出「原则：…」才抄；否则留空，避免假原则挤常驻 5 条 |
| `themes` | 能从上一轮 `turn_intent` / task_frame.subject 拿到就写，拿不到空 |
| `source` | 固定 `workbench_conversation` |
| `conversation_id` | 本会话 |
| `corrected_message_id` | 被纠正的 assistant `message_id` |
| `plane` | `user_method`（本路径唯一合法值） |

去重：同一 `user` + 同一 `correction` 正文归一后，24h 内已有一行 → 不追加。号不回收的同一思想：不改历史行。

---

## 5. 精度门（P0 核心，宁可不记）

用确定性抽取，**P0 不上 LLM 分类**（会烧研究预算、方差进写入）。

### 5.1 先过硬前置（缺一条就不写）

**分两层放，别都塞进 services 那个函数**——否则 §6 那三条正例夹具永远跑不通
（守卫会在 pytest 下先早退）。仓里已有正确形状，就是事实 5 引的那对：

| 层 | 放什么 | 先例 |
|---|---|---|
| `runtime`（orchestrator） | 环境守卫（`PYTEST_CURRENT_TEST`）+ 身份名单 + 探针前缀 | `_ingest_track_next_watch`：守卫在这里，测试只 monkeypatch 断言「该调时调了」（`test_conversation_orchestrator.py:903`） |
| `services`（本单新模块） | **纯文本精度门 + 显式 path 写入，不带任何环境守卫** | `ingest_next_watch`：无守卫、吃显式路径，所以真实写入测得动（`test_track_contract.py:395`） |

前置条件（层归属标在括号里）：

1. （runtime）本进程不是 pytest（`PYTEST_CURRENT_TEST`）。
2. （runtime）`user_id` 非空，且 **不是** `golden-test` / `tester`；**是** `default` 也写（事实 5）。
3. （runtime）`user_id` 不匹配探针前缀：`probe-` / `fsr2-` / `ablation-` / `golden-`（自用摩擦台账那条纪律：探针不进用户账）。
4. （runtime 取、services 收）本会话存在一条 `role=assistant` 且 `status=completed` 的上一轮（按时间倒序第一条）。没有上一轮 = 用户在开新题，不是纠偏。
   - ⚠️ **不要复用 `previous_turn_message`**（`conversation_orchestrator.py:1670`）。[实测] 它的实现是
     「倒序找**第一条带 `turn_intent` 的消息**」——`for message in reversed(recent_messages): if TurnIntent.from_dict(...) is not None: return message`，
     **不看 role、不看 status**。照抄会把带 intent 的**用户**消息、或**未完成**的 assistant 稿
     当成「被纠正的上一篇」，于是 `original` 指错、`corrected_message_id` 指错，
     而写入照样成功、夹具照样绿。
     （本条初版写的是「先确认它是不是这个语义」——那是把核对甩给实施方；答案是**不是**，
     现在直接写死。）
   - P0 自己滤：`role == "assistant" and status == "completed"`，倒序取第一条。要么新写一个
     helper，要么给 `previous_turn_message` 加可选谓词参数——**别原地改它的语义**，
     `_run_turn_ledgered:1843` 还在用它取继承 intent，改了会动到别的路。
   - `status` 字段实测在盘（`messages.jsonl` 里有 `"status": "pending"`），本条可判，不是纸面约束。
5. （services）用户正文去空白后长度 ≥ 8，且含「应为」载荷（见 5.2），不是光一个「不对」。

### 5.2 「应为」载荷（有纠正内容才写）

命中下列之一，并抽出 `correction` 片段：

- `不对，应该是…` / `不对，应该…` / `不是这样，应该…` / `你理解错了…应为…`
- `应该是` / `应为` / `不是 A 是 B`（A/B 都要抽到）

只说「不对」「错了」「不行」没有后半句 → 不写。

### 5.3 排除（过了 5.2 仍可能是评盘面）

**判据是否定词的左邻，不是全句词面。** 初版写「主语是盘面/行情/这波/今天/板块/大盘」——
那是**语法角色**，而 §5 已经定死「确定性抽取、不上 LLM」，确定性实现只能退化成**词面命中**，
两者会在本单自己的正例上分叉：W-corr-1「不对，应该先看**板块**容量再下结论」含「板块」、
不含指代，按词面命中该排除，按 §8 却必须写入。同一份稿子两条相反判决，
实施方会先写门再写夹具、拿到红、然后**放宽门**去凑绿——精度目标当场作废。

可判的替代（按标点切小句，只看否定词所在小句与其前一小句）：

1. **定位否定词**：`不对` / `错了` / `不是这样` 的首次出现。
2. **看它的左邻**：
   - 左邻小句含**指代**（`你` / `刚才` / `上一条` / `这个回答` / `上一篇` / `你说`）
     → 被纠正的是**回答**，继续判载荷。
   - 否定词**在句首**（左邻为空）→ 缺省视为纠正回答，继续判载荷。
   - 左邻紧贴**市场指示词**（`这波` / `这轮` / `今天` / `大盘` / `行情` / `这只` / `它`）
     且无指代 → 被纠正的是**市场**，整句不写。
3. **工程词表**（整句命中即不写，与位置无关）：PR、分支、commit、pytest、8792、
   harness、worktree、合入、强推。工作台自动路径不收编码纠偏，编码会话继续走 CLI。

对表（三条都要在夹具里）：

| 句子 | 否定词左邻 | 判 |
|---|---|---|
| 你刚才说双红就能上，**不对**，应该先看容量 | 含指代「你刚才」 | 写 |
| **不对**，应该先看板块容量再下结论（= W-corr-1） | 句首，左邻为空 | **写**（「板块」在后半句，不参与判定） |
| 这波**不对**，应该是情绪退潮（= W-corr-3） | 紧贴「这波」 | **不写** |

夹具必须同时有正例和后两行。缺 W-corr-3 = 门是松的，会把吐槽写成方法论；
缺句首那行 = 门是紧的，而**现实中用户很少写指代**，紧门等于这条路白接。

> 若要改成「必须带指代才写」（更严、误写更少、漏写更多），把 W-corr-1 的冻结原文
> 一并改成带指代的版本——**两处必须同时改**，这正是初版分叉的地方。

---

## 6. 阶段

### P0 — 工作台写侧接通（本单交付）

- 新模块 `intelligence/services/workbench_correction_ingest.py`：`maybe_record_workbench_correction(...)` 纯函数，返回 `recorded | skipped | failed` + 原因码。原因码封闭枚举（`no_prior_answer` / `no_payload` / `market_commentary` / `engineering` / `identity_skipped` / `dedup` / `recorded` / `write_failed`）。
  - ⚠️ 枚举跨了两层：`identity_skipped`（以及 pytest 早退那档）由 **orchestrator** 判，
    services 那个纯函数**永远不会返回它**。夹具直接调 services 时这条码不出现，别据此判「枚举没实现」。
    要么在枚举定义处标明「仅 orchestrator 收据可见」，要么把它挪出 services 的返回域、
    只留在 trace payload 的 `reason` 里。**二选一写死**，不要两处各写一半。
- 接线：`conversation_orchestrator._run_turn_ledgered` 在 `build_conversation_context` 之后、`turn_controller` 之前调一次。`try/except` 吞写入异常，**fail-open**，警告进 `warnings`，不改 lane、不改包、不改 A。
- 仍走现有 `corrections.record_correction`；旁路字段用现有 dict 多写几键，加载方容缺。
- 收据：`_trace(..., "user_correction_recorded", ...)`，payload 只含 `id` / `reason` / `plane` / `corrected_message_id`，不含用户全文（台账进 gitignore，trace 不二次扩散）。
- 夹具（TDD，先红后绿）：
  - 正例：有上一轮 assistant + 「不对，应该先看板块容量」→ 文件多一行，`source=workbench_conversation`。
  - 反例：无上一轮 → 零写入。
  - 反例：「这波不对，应该是情绪退潮」→ 零写入。
  - 反例：`user_id=tester` / `probe-x` → 零写入。
  - 正例：`user_id=default` → **写入**（钉死不抄 5207 名单）。
  - 写入抛 OSError → 研究函数仍被调用（fail-open）。
  - 24h 去重。
- 验收：本机工作台身份 `default` 走一遍正例，读 `FORESIGHT_USERS_DIR` 下该用户文件尾行，不读仓内回落。

### P1 — 和读侧对缝（覆盖单落地后才做）

- 覆盖单开口 `memory_lookup` 必须能召回 P0 新行（靠现有 `select_relevant` 的 `correction` / `original` / `principle` 文本键即可，不强制新索引）。
- 夹具：P0 正例落账后，无「上次」的「瑞华泰怎么看」开口观察含该原则或 gap 声明——**这条的记忆预取属于覆盖单**；本单只保证行在、字段在。
- 若覆盖单未合：本单 P1 不开工，避免「写了没人读」被验收成闭环。

### P2 — 人看得见（可选）

- 结构化报告 / UI 一行「已记纠偏」，不弹窗、不打断输入。
- 显式按钮「记为纠偏」作为精度门的**补充**，不是替代：点了就绕过 5.3 排除里「缺指代」那条，仍排除工程词表与探针身份。

### P3 — 只登记不施工

- 常驻 5 条窗口被工程纠偏挤占：归 08-19 `user_framework` / `promoted_to_code`，本单不扩大 `DEFAULT_RESIDENT_LIMIT`。
- 多根大脑合并（`R-20260827-16`）：本单只写当前 `userspace.user_space(run_store.user_id)`。
- 经验卡自动 `answer-score --save-card`：另一条学习环，不在本单。

---

## 7. 非目标

- ❌ 改判官、修复轮、`repair_unfulfilled_answer`。
- ❌ 把纠偏/经验卡拼进 `build_episode_instructions`。
- ❌ P0 用 LLM 判断「这是不是纠偏」（预算 + 方差）。
- ❌ 信号词「不对」一律落账。
- ❌ 跳过 `default` 用户。
- ❌ 探针 / pytest / `tester` 写入生产账。
- ❌ 工作台自动写工程纠偏（编码会话继续 CLI）。
- ❌ 自动编 `principle` 挤常驻窗。
- ❌ 梦矿提案转正。
- ❌ 当覆盖单的验收（开口必取记忆）。

---

## 8. 冻结对话草案（P0 实施时钉死原文）

| ID | 会话 | P0 必须看见 |
|---|---|---|
| W-corr-1 | 用户「瑞华泰怎么看」→ assistant 任意完成稿 → 用户「不对，应该先看板块容量再下结论」 | 新行；`source=workbench_conversation`；`correction` 含板块容量；研究仍跑 |
| W-corr-2 | 无历史，首句就是「不对，应该先看板块容量」 | **零写入**（无上一轮回答） |
| W-corr-3 | 上一轮是盘面回答 → 用户「这波不对，应该是情绪退潮」 | **零写入** |
| W-corr-4 | 与 W-corr-1 同文，`user_id=default` | **写入**（身份反例） |
| W-corr-5 | 与 W-corr-1 同文，`user_id=tester` | **零写入** |

W-corr-3 和 W-corr-2 缺一不可：一个钉「不是评市场」，一个钉「不是没上文的口头禅」。

---

## 9. 实施落点（给领单方，不在本稿改代码）

| 文件 | 职责 |
|---|---|
| `intelligence/services/workbench_correction_ingest.py` | **纯文本精度门 + 显式 path 写入**；无环境守卫、无身份名单（那两样在 runtime，见 §5.1）；可单测、不 import `runtime` |
| `intelligence/runtime/conversation_orchestrator.py` | `_run_turn_ledgered` 装配后调一次；环境/身份守卫在此；fail-open；trace |
| `intelligence/tests/test_workbench_correction_ingest.py` | §8 五条 + fail-open + 去重，**全部直接调 services 函数、传 tmp_path**（照 `test_track_contract.py:395` 的手法） |
| `intelligence/tests/test_conversation_orchestrator.py` | 只加一条：该调时调了 + 身份/pytest 守卫拦住时没调（照 `:903` monkeypatch 手法） |
| `intelligence/services/corrections.py` | **尽量不改**；若要旁路字段，只扩展写入 dict，加载容缺 |

分层：摄入逻辑放 `services/`，orchestrator 只接线。不要在 `webapp` 里写账——UI 可以后挂收据，真源在 turn。

**守卫别下沉**：把 `PYTEST_CURRENT_TEST` 写进 services 那个函数，正例夹具就永远走不到写入，
只能靠"显式传 fixture 路径"绕——那是旁注不是设计，落地时会先变成一条红、再变成一次放宽。
`_ingest_track_next_watch` / `ingest_next_watch` 这一对只示范**分层**（守卫留在 runtime、写入函数本身不看环境）。**不要照抄跳过名单**——那份名单把 `default` 和探针身份一起跳过，抄过来生产零写入（见 §5.1）。

---

## 10. 成立条件

- 本稿是设计裁决，不是已交付。P0 未合 main、未切 8792 之前，工作台研究环仍是「只有 repair 是环」。
- 读侧闭环以覆盖单 P0 的 opening 观察为准；本单绿只证明「工作台会写」。
- 身份以 `run_store.user_id` + `userspace.user_space` 为准，不以仓内 `intelligence/users/` 抽样。
- 精度门用冻结对话，不用线上「感觉记少了」回溯放宽——放宽另立单并带新的反例。
