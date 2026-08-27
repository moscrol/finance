# 设计：激活收据（ActivationRecord）

- 日期：2026-08-23
- 状态：Draft v1.1（审架构收口 + 复核钉死 1/2/3/4/5/6）
- 来源：Harness 审架构（静态观察，`5f236d78`，脏树，未 live 注入）
- 相邻：`docs/superpowers/specs/2026-08-19-workbench-production-agent-hardening-design.md` §6 P1（EpisodePhase 投影，**本单不做**）
- 代码树：从 `gitea/main` 开干净树 `feat/activation-receipt`。禁止在主检出 `feat/reading-rules-baseline-batch1` 脏树上改 runtime。

## 0. 一句话

标题、降级提示、trace 只许消费「这轮指导文本是否写入将送给模型的 payload 字段」的收据，不许从「用户选了谁」反推。

人话：小票上的店名必须来自后厨接单回执，不能来自顾客点菜单。

`injected=true` 只证明字段写进去了，**不**证明模型看见了、上下文没挤掉、更不证明按这个写了。

## 1. 证明范围（先钉死）

| 证明 | 本单 | 怎么证 |
|---|---|---|
| 用户请求了某视角 / 基线开关开着 | 记 | `requested` |
| 解析到了具体 profile / 规则集 | 记 | `resolved` |
| 指导文本写入将送给模型的 payload 字段 | **本单要证** | `injected` + `prompt_hash` |
| 模型在窗口里看见了该字段 | **本单不证** | 预算截断 / 上下文挤掉仍可 `injected=true` |
| 模型按该指导组织了答案 | **本单不证** | 输出侧绑定，另开单；禁止做成文风判官 |

把「使用了 / 按 SPT 写了」写进本单验收 = 超范围。收据不是 8 格作文量表。

## 2. 现状（不要重做）

已经成立，本单不重做：

1. 2026-08-14 之后，continuous 主路径会调用 `perspective_lab.active_runtime_prompt`，再经 `project_turn_decision.perspective_context` → `ResearchRunContext` → `episode_protocol` 进入模型输入。单元测试已锁这条注入链。
2. 本脏树上 `episode_protocol` 已拆两层：`reading_baseline`（默认领域方法）与 `perspective_context`（用户显式选中）。`gitea/main` 可能尚无 `reading_baseline` 模块——见 §6.1。
3. `reading_baseline.pending_rules()`（若模块存在）故意不进 prompt。
4. 预算、证据账本、结构 verifier、修复棘轮（空草稿不覆盖旧稿）不动。

当前洞：

```text
用户选择 SPT ──► active_runtime_prompt ──► episode payload
     │                    │ 失败则 ""（与 neutral 同形）
     └──► runtime_answer_header(mode, ids) ──► 交付标题
artifact provenance 只记 cutoff / 日期，不记激活
```

`runtime_answer_header` 只读 mode + ID + `load_profile` 的 display_name，**不读** `active_runtime_prompt` 的返回值。所以可以「指导文本没进模型，小票上仍写 SPT」。这就是 F3 的结构洞。

**F3 不是 2026-08-23 下午 8792 的事故复盘。** 那次 live 的 SPT 头，指导文本其实进了；有色那轮卡在新用户没有画像、422，没走到标题。F3 锁的是「结构上会挂假店名」，不是「今天下午已经挂过」。

`reading_baseline` 是同一失败形状，且默认开、没有标题，更要进同一组收据。否则「开关开着、模型没看到」只能翻 payload 猜。

## 3. 术语

| 术语 | 定义 |
|---|---|
| ActivationRecord | 一条激活的结构化收据。种类见 `kind` |
| requested | 请求态：用户选了什么，或基线开关读到什么 |
| resolved | 解析态：实际落到哪些 id / 规则 id |
| display_names | 与成功写出那份 prompt **同一次**冻结的显示名。仅 `status=injected` 可非空 |
| injected | 注入态：非空指导文本已写入将送给模型的 payload 字段。不是「模型看见了」 |
| prompt_hash | 上述字段字节的 sha256 hex；在 `episode_protocol` **赋值之后**才算。未注入则为 `""` |
| 标题资格 | 交付层可否打印 KOL / SPT 名。结构承诺，不是文风 |

## 4. 字段

一个 run 有一组记录，最少两条槽：`perspective`、`reading_baseline`。neutral / 基线关闭 / 模块未接线时仍写记录，禁止缺席（缺席会被读成「没测」）。

```python
kind: Literal["perspective", "reading_baseline"]
requested: str
# perspective: "neutral" | "single:<id>" | "compare:<id>,<id>"
# reading_baseline: "on" | "off" | "not_wired"
resolved: tuple[str, ...]
# perspective: 校验后的 perspective_id；neutral 为空
# reading_baseline: 实际注入的规则 id；关闭或无规则为空
display_names: tuple[str, ...]
# 仅 status=injected 时非空；来自写出 prompt 的同一次 RuntimePerspectiveContext
# degraded / inactive 必须是 ()
renderer: str
# 写出注入文本的函数名，例如 activate_runtime_perspective / activate_reading_baseline
# 只作溯源，不作分支条件
prompt_hash: str
# sha256 hex；perspective_lab / 纯函数产出时必须是 ""
# 只允许 seal_prompt_hash(record, field_bytes) 在协议赋值后写入
injected: bool
status: Literal["inactive", "injected", "degraded"]
reason: str
# injected 时为空；其余写机器可读原因码，见下
```

`status` 真值表（实现按表，不许另发明状态）：

| 条件 | status | injected | display_names | 标题资格（仅 perspective） |
|---|---|---|---|---|
| 未请求（neutral / 基线 off / 未接线） | `inactive` | false | `()` | 无 KOL 标题 |
| 请求了且 payload 字段非空 | `injected` | true | 同一次 build 冻结 | 可印这些 display_names |
| 请求了但 payload 字段为空 | `degraded` | false | `()` | **禁止**印 KOL / SPT 名 |

原因码（`degraded` / `inactive` 用，可加不可删）：

- `not_requested`
- `switch_off`
- `not_wired`   # 本 revision 没有 reading_baseline 模块
- `profile_missing`
- `build_failed`
- `empty_prompt`
- `no_rules`

## 5. 不变量

实现与测试共同验收。违反任一条 = 本单未完成。

**I1 标题只消费收据；店名跟成功的那次 build 冻结。** `runtime_answer_header` 的唯一输入是 perspective 的 `ActivationRecord`。禁止再接收裸 `mode` + `perspective_ids`。禁止在交付时再 `load_profile`。`status != injected` 时返回空串。`status == injected` 时只用 `record.display_names`——这组名字必须来自写出那份 prompt 的同一次 `build_runtime_context` / `RuntimePerspectiveContext`，不得另开一次 load。一轮 turn 只 `activate` 一次；continuous 注入文本与标题、legacy `AskOptions` 覆盖值，都用这一次的 `(text, record)`。

legacy research 在 `inactive` 时仍可印 `runtime_neutral_banner()`（「当前视角：数据中立」）。这不是店名，是旧交付契约。continuous 的 inactive **不得**印这张横幅，以保持 Episode 正文逐字节等于引擎输出。

**I2 请求失败必须 `degraded`，禁止静默空串冒充未请求。** `active_runtime_prompt` 今日 `except: return ""` 与 neutral 的 `return ""` 撞车。本单后：neutral → `inactive` + `not_requested`；选了但构建失败 → `degraded` + 原因码。调用方仍可把注入文本当成空串（不让整轮崩溃），但收据不得写成 inactive。

**I3 `prompt_hash` 对的是 `episode_protocol` 落字段的那份字节，后哈希。** `activate_*` 产出的 `prompt_hash` 必须是 `""`。`seal_prompt_hash(record, field_bytes)` 只在协议把字符串写入 `payload["perspective_context"]` / `payload["reading_baseline"]` **之后**调用，`field_bytes` 就是刚赋进去的那个 Python 字符串。禁止在 `perspective_lab` 里先哈希。未注入则密封后仍为 `""`。`injected=true` 但 `field_bytes==""` 是实现错误，必须抛。

**I4 单一真本源。** 标题、`runtime_fallback_notice`、`_episode_context_provenance`、continuous / legacy 两条引擎，只读这组记录。禁止第二份「是否激活」布尔值。

**I5 收据不声称遵从，也不声称「模型看见了」。** 字段、文档、trace 名禁止出现 `used` / `followed` / `applied_by_model` / `seen_by_model`。`injected` 的注释必须写明：预算截断或上下文挤掉后仍可以是 true。

**I6 两条引擎共用记录类型，不新做双渲染 IR。** 现有注入原语已经共用 `active_runtime_prompt`。本单不引入 ContextFacet、不分别实现 continuous JSON / legacy Markdown 渲染器。

**I7 pending 基线规则不得出现在 `resolved` 或注入文本。** 已有纪律，本单加一条收据断言锁住（模块存在时）。

**I8 `status != injected` 的用户可见文本禁止店名。** header、`runtime_fallback_notice`、以及拼进 answer 的任何前缀，都不得出现 `display_name`、`sptfei`、`spt-`（大小写不敏感）。今日「该视角未知」这句可以留；谁写「SPT 映射失败」就是把店名挂回去。实现用固定句，再用一条扫描断言锁死。

## 6. 接线（改谁、不改谁）

只改激活的**生产与消费点**。

**可以改：**

- `perspective_lab` 激活原语与 header / fallback
- `conversation_orchestrator` 的注入处和标题处（只换收据消费点，不改路由 / lane 决策）
- `ask_synthesis._active_perspective_prompt`（委托同一次 activate，或吃 orchestrator 传入的覆盖值）
- `AskOptions` 增加「已激活文本」覆盖字段，避免 legacy 再 build 一次
- `TurnControlResult` / `ResearchRunContext` 增加 record 字段（不把 record 序列化进模型 prompt）
- `episode_protocol.build_episode_input` 赋值后 `seal_prompt_hash`
- `continuous_turn_adapter._episode_context_provenance` 增加 `activations`
- 新模块 `intelligence/services/activation_receipt.py`（类型 + 密封 + 店名扫描）

**不可以改（§9 按此名单，不要写成「loop diff 为空」）：**

- `agent_episode` 状态机
- structural / semantic verifier
- `episode_tool_batch`
- `research_tool_registry` 的 ToolSpec / 授权表

| 点 | 今日 | 本单 |
|---|---|---|
| 新 `activate_runtime_perspective` | 无 | 一轮一次，返回 `(text, ActivationRecord)`；`prompt_hash=""`；成功则冻结 `display_names` |
| `active_runtime_prompt` | 返回 `str`，失败 `""` | 委托上面，只回 `text`；禁止第二份逻辑 |
| `runtime_answer_header` | `(us, mode, ids)` + 再 `load_profile` | 只收 `record`；`status != injected` → `""`；印 `record.display_names` |
| `runtime_fallback_notice` | 只收 `mode` | 改收 `record`；固定句，无店名 |
| orchestrator 注入处 | 只取 prompt 字符串 | 持有同一次 `(text, record)` |
| orchestrator 标题处 | 独立 `runtime_answer_header(mode, ids)` | `runtime_answer_header(record)`；`degraded` 时 `runtime_fallback_notice(record)` |
| ask_synthesis | 自己再 build 一次 | 有覆盖值就用覆盖值，否则委托 `activate_runtime_perspective` |
| episode_protocol | 有文本才写入字段 | 赋值后密封 `prompt_hash`；写 baseline 槽（见 §6.1） |
| provenance | cutoff / 日期 | 增加 `activations` |

模型输入仍是字符串。record 是控制面对象，不进 prompt 正文。

### 6.1 `reading_baseline` 与主干

`gitea/main` 可能没有 `intelligence/services/reading_baseline.py`。本单仍要锁同一类型：

- `activation_receipt.activate_reading_baseline(guidance, rule_ids, *, enabled, pending_ids=())` 是纯函数，F6–F9 直接喂它，不依赖该模块。
- `episode_protocol` 能 `import reading_baseline` 就接线真实 guidance / 规则 id。
- 不能 import 时，baseline 槽写 `inactive` + `not_wired`，禁止缺席。

## 7. 故障注入矩阵

先静态单测。不要求 live SPT。

### F3 布置（唯一合法缝，写死）

现码里 `validate_runtime_selection` / `load_profile` 与 `build_runtime_context` 共用 profile。**删 profile 文件会让两路一起挂，测不到「有名无文」。**

唯一合法布置：

1. 真实 `init_perspective`，profile 在盘上。选用一个带店名的 display_name（测试用 `SPT-Molmansk` 或内置「风远框架视角」），保证未 patch 时 `load_profile` 能读到这个名字。
2. `unittest.mock.patch.object(perspective_lab, "build_runtime_context", side_effect=FileNotFoundError("articles gone"))`
3. 调用 `activate_runtime_perspective(...)`（不要调用已删 profile 的路径）。

禁止：

- 删 profile 文件当 F3
- 把 F3 写成 2026-08-23 下午 8792 live 复盘
- 在 header 测试里再 `load_profile` 取名去拼标题

断言：

- `status=degraded`，`reason=build_failed`，`injected=false`，`display_names=()`，`prompt_hash=""`
- `runtime_answer_header(record)==""`
- `runtime_fallback_notice(record)` 与任何拼进 answer 的前缀：不含该 display_name、不含 `sptfei`、不含 `spt-`
- 即使用户空间里 `load_profile` 仍能读到店名，用户可见文本也不得出现它

### 全表

| # | 布置 | 期望 | 期望 header / 可见文本 |
|---|---|---|---|
| F1 | `mode=neutral`，无 id | `inactive` / `not_requested` | 不前置 KOL 头（neutral 正文逐字节等于引擎输出） |
| F2 | `mode=single`，profile 在，build 成功 | `injected`，`display_names` 来自同一次 context | 印这些冻结名；不得另 load |
| F3 | 见上：patch `build_runtime_context` 抛 `FileNotFoundError` | `degraded` / `build_failed` | 空头 + 无店名降级声明 |
| F4 | `mode=single`，build 成功但 `context.prompt==""`（patch 返回空 prompt 的 context） | `degraded` / `empty_prompt`，`display_names=()` | 空 |
| F5 | `mode=compare`，只解析到部分 id | `resolved` 仅含成功的；最终 prompt 非空才 `injected` | 仅 `injected` 才印冻结名 |
| F6 | 纯函数：`enabled=True`，guidance 非空，rule_ids 给定 | reading_baseline=`injected`，`resolved=rule_ids` | （无标题） |
| F7 | 纯函数：`enabled=False` | `inactive` / `switch_off`，`resolved=()` | （无标题） |
| F8 | 纯函数：`enabled=True`，guidance 为空 | `degraded` / `no_rules` | （无标题） |
| F9 | 纯函数：`pending_ids` 非空 | pending id 不得出现在 `resolved` | — |
| F3b | 密封：`activate` 后 `prompt_hash==""`；协议赋值后再 `seal_prompt_hash` | 哈希等于 `sha256(字段字节)` | — |

F3 是本单的主红用例：结构上今日会挂 SPT 标题。落地后必须红→绿。

## 8. 非目标

- 重写 episode 状态机 / 改成 reducer
- EpisodePhase 状态投影（相邻稿 P1）
- 子研究继承卫生、episode 聚合预算
- `ToolSpec` 只读 / 并发属性
- 语义 verifier 句级删除改 claim-level；`correlated_judge` 交付策略
- 输出侧证明「按 SPT 写了」或「模型看见了」
- ContextFacet / 双引擎 renderer IR
- 在本脏树实现或把本文件混进 reading-rules 的合入
- 只加 `if not prompt: 不印标题`（空串仍和 neutral 撞车；基线无标题，洞还在）
- 去掉标题（F2 真注入时用户也看不见选了谁）

## 9. 验收

完成 = 下列全部为真，缺一条不算完：

1. F1–F9 与 F3b 各有定向测试，F3 为必红必绿。
2. `rg "runtime_answer_header\\(" intelligence` 的生产调用点只传入 `ActivationRecord`，不再传入裸 mode/ids，也不再 `load_profile`。
3. 一次 continuous 成功（或 degraded）run 的 private artifact `research_context.activations` 含 perspective 与 reading_baseline 两条记录，字段齐全。
4. 全仓无 `used_by_model` / `perspective_applied` / `seen_by_model` 这类遵从或「看见了」字段。
5. `agent_episode` / structural+semantic verifier / `episode_tool_batch` / `research_tool_registry` 的 diff 为空。`conversation_orchestrator` 只允许注入处与标题处的收据消费点变化。
6. `status != injected` 的用户可见前缀扫描：无 display_name / `sptfei` / `spt-`。

## 10. 实现顺序

1. `activation_receipt.py` + F1/F3/F6 测试（先红）。
2. `activate_runtime_perspective` / header / fallback；`active_runtime_prompt` 委托。
3. orchestrator 一轮一次 activate；标题与 fallback 只消费 record；AskOptions 覆盖值。
4. `episode_protocol` 赋值后密封；provenance 落 `activations`。
5. 跑 F1–F9、F3b 与既有视角注入测试。

一次只做本单。下一张才是 EpisodePhase 投影。
