# 设计：猜你想问选角编排（Knevo 追问契约吸收）

日期：2026-08-17
状态：设计稿，待用户审阅
权威蒸馏：`docs/learning/knevo-distill/q12-猜你想问生成机制.md`；`agent-memory/60_dialogues/knevo/2026-07-08-追问设计-四角度成套.md`；`agent-memory/10_knowledge/knevo-reverse-engineering.md` §5
现有实现：`intelligence/services/followups.py`；连续对话接线 `intelligence/runtime/conversation_orchestrator.py`；legacy ask 接线 `intelligence/api/app.py` s03

## 0. 一句话结论

吸收 Knevo「猜你想问」的**选角表和与结论槽的咬合**，不吸收它的 `suggest_options` 工具，也不把二阶导研究搬进芯片。

现有五类卡片类型保持不变。新增一层确定性编排器 `compose_followups(state)`：用本轮已经结构化的缺口、D3、验证条件，按 A 必选、B/C/D 条件上、2–4 条封顶，编出可点击的下一问。二阶导继续只写在正文 D3。

## 1. 目标与非目标

### 1.1 目标

- 把三条追问生成器收成一个入口，避免连续对话、AnswerSpec、legacy ask 各写一套语义。
- 连续对话在「答完整、无缺口」时也有 2–4 条芯片，不再只在降级时才出现 gap 镜像。
- 芯片是报告弱点和下一步的镜像，不是再问一遍数据块已覆盖的一阶事实。
- D3 二阶导与芯片 B 分账：正文写瓶颈和更优表达，芯片只问下一跳去核什么。
- 生成失败不得拖死主答案。连续对话默认零模型。

### 1.2 非目标

- 不新增模型可见的 `suggest_options` 工具。
- 不把产品类型改成 A/B/C/D 对外名。UI 继续用现有 `type`。`migration` 保留以免旧读取方崩，**compose 第一期不产出**。
- 不把 D3 研究写进芯片，不把 D3 已列出的公司名当成「新发现」再问一遍。
- 不把 71 页手册的 8 种 prompt 骨架做成自由发挥生成器。
- 不合并 foresight（盘面每日主动发问）与 followups（回答驱动）。
- 不改 T、批窗、8792 切包、finance 主库、Wiki/记忆写入。
- 不把 Cordis / 动态 Plugin Loader 引进本仓。追问用 Python Protocol 接缝，见 §13。
- 本 spec 不改 UI 视觉，不接飞书卡片。现有 `{label, full_prompt}` 契约够用。
- 第一期不对 skill registry 做运行时可答性探测（见 §6.4）。

## 2. 术语

| 词 | 含义 |
|---|---|
| 芯片 / followup | 答尾可点击的下一问。字段至少有 `type`、`label`（≤20 字）、`full_prompt`（用户口吻完整问题）。 |
| 角度 A/B/C/D | 编排层内部槽位，不对外改名。 |
| 二阶导 | 正文研究镜头：从目标股反推瓶颈和更优表达。落点是 D3（P0 强势替代 / P1 再升级 / P2 瓶颈补盲）。 |
| 提问二阶 | 芯片不得复读数据块已能直接回答的一阶事实（双红、生命周期阶段、近几日涨停热度）。 |
| 选角 | 根据 `FollowupState` 决定本轮出哪些角度、各几条。 |
| 填充 | 某个角度已经选定后，用哪条结构化材料写成 `full_prompt`。 |

Knevo 原对照：

| Knevo | 本仓类型 | 本仓正文 |
|---|---|---|
| A 纵深（待验证缺口镜像） | `gap` 优先，否则 `evidence` | 结论缺口 / 未满足必需输出 |
| B 横向（同链异标的） | `alternative` | D3 P0/P2；芯片只问下一跳 |
| C 操作（仓位/时机；无空间时给窗口） | 只走 `recheck`（track 改 `counter`）；平替留给 B 和正文 D3 | 不在芯片里重写 D3 名单 |
| D 验证（框架回测/证伪） | `counter` | triggers / 失效条件 |
| 结论⑤ 替代路径 | 不是芯片 | D3 正文 |

## 3. 现状与缺口

今天有三套生成器，语义重叠但不统一：

| 入口 | 谁调用 | 现在产出 | 洞 |
|---|---|---|---|
| `gap_mirror_followups` | 连续对话终局 | 仅 `open_gaps` → `gap` | 完整答案无芯片 |
| `generate_answer_spec_followups` | 对话里有 AnswerSpec 的路径 | gaps / next_actions / triggers，固定凑 3–4 条 | 无选角，无 D3，常被 conservative 补白 |
| `generate_followups` | legacy ask s03 | 五类模板或 LLM 自由拟，默认 5 条 | 无 A 必选，无 2–4 封顶，LLM 可改类型语义 |

已经吸收、本 spec 不再重做：`{label, full_prompt}`、gap 镜像、跟踪题跳过一阶 `recheck`、追问失败不拖死主答案。

## 4. 架构

```
本轮结构化状态
  -> FollowupState（只读快照）
  -> compose_followups(state)
       1. select_angles(state)      确定性
       2. fill_slots(state, angles) 确定性模板
       3. optional polish(text)     仅润色，可关；失败回退第 2 步原文
  -> FollowupResult（现有 JSON 契约 + 可选 angle）
  -> 消息 followups + followups.json
```

`compose_followups` 是新调用方的唯一入口。三个旧函数降为填充器，测试可以继续直调，生产新接线只走 compose。

层边界：

- **编排器**只读 `FollowupState`，不读 DuckDB，不调检索，不写记忆。
- **D3 构建**仍在 `ask_blocks` / evidence registry。编排器消费已经算好的 P0/P2 条目，不自己算二阶导。
- **主答案**继续独立生成。芯片是答后增强，异常只记 warning。
- **编排器不得进入** `agent_episode` / `episode_protocol` / 工具批次。它是 turn 已结束后的 Projection，见 §13。

## 5. FollowupState

冻结 dataclass，所有字段缺省为空，编排器必须能在空状态下降级，不得抛。

```
subject: str
question: str
question_kind: "stock" | "theme" | "methodology" | "track" | "other"

open_gaps: tuple[str, ...]          # 连续对话：未满足必需输出的公开描述
spec_gaps: tuple[str, ...]          # AnswerSpec.gaps 文本
spec_triggers: tuple[str, ...]      # AnswerSpec.triggers 文本
spec_next_actions: tuple[str, ...]  # AnswerSpec.next_actions

alternatives: tuple[AlternativeItem, ...]
  # name, reason, source ∈ {d3_p0, company_table, none}
bottlenecks: tuple[str, ...]        # D3 P2 词，不是公司名

status: "completed" | "partial" | "degraded"
no_action_room: bool                # 由投影函数按 §6.2 写入，编排器不重算
produced_framework: bool            # 仅 methodology；有 triggers 不自动翻它

listed_names: frozenset[str]        # 正文/D3 已出现的公司或标的名
skip_types: frozenset[str]          # 例如 track → {"recheck"}
parent_followup_prompt: str | None  # 若本问来自父芯片，禁止原样回声
```

投影规则（写死，禁止对整段答案做宽正则）：

| 来源 | 填哪些字段 |
|---|---|
| 连续对话 `ContinuousTurnResult` | `open_gaps`、`status`、`subject`、`question`；`alternatives/bottlenecks` 第一期为空 |
| AnswerSpec | `spec_gaps/triggers/next_actions`；`company_table` 里非 `subject` 的公司名进 `alternatives(source=company_table)`，同时加入 `listed_names` |
| ask compose 的 D3 结构结果 | P0 行进 `alternatives(source=d3_p0)`，P2 词进 `bottlenecks`，两者的公司名进 `listed_names` |
| `parse_track_intent(question)` | `question_kind=track`，`skip_types` 含 `recheck` |
| 投影函数判定 methodology | `question_kind=methodology`，`produced_framework=True`。编排器不猜 kind。 |

D3 不得从 Markdown 反解析。ask 路径必须在构建 D3 时同步给出结构对象（P0 列表、P2 词列表）。第一期连续对话没有 D3 结构对象，B 用 subject 级模板，不假装有替代队列。

`question_kind` 只由投影函数写，冻结规则：

1. `parse_track_intent(question)` 为真 → `track`（优先）。
2. 否则 `subject` 非空且问句不像方法论 → 有个股代码或公司名则 `stock`，否则 `theme`。
3. 否则问句命中冻结词表 `{错因, 归因分类, 检索规则, 五维排序, 四分类判据, 框架怎么回测}` 且 `subject` 空 → `methodology`。
4. 否则 `other`。

P0 连续对话只用 1、2、4，不启用第 3 条（避免误伤）。methodology 套在 P1 随 ask/AnswerSpec 一起开。

## 6. 选角与填充

### 6.1 选角表

`select_angles` 只返回有序角度列表，长度为 2–4，目标 3。不生成文案。

| 条件 | 动作 |
|---|---|
| `open_gaps` 或 `spec_gaps` 非空 | A 必选，条数 = `min(2, 缺口数)` |
| 无缺口且 `question_kind != methodology` | A 仍占 1 条，类型走 `evidence`（Knevo：完整结论也要打最薄的一层） |
| `question_kind == methodology` 且无缺口 | 跳过 A，D 占 2–3 条（Knevo 方法论轮 D×3） |
| `alternatives` 或 `bottlenecks` 非空，或 `question_kind ∈ {stock, theme}` | +B 一条 |
| `no_action_room` 为真 | +C 一条，类型按 §6.3，不占用 B |
| `spec_triggers` 非空，或 `question_kind ∈ {stock, theme, other}` 且无缺口 | +D 一条（无 trigger 时用 conservative `counter`）。这是完整答案的默认第三件，不依赖 `produced_framework` |
| `produced_framework` 且无缺口 | D 改为 2–3 条，且跳过 A（与上行 methodology 规则合并，不叠第四条 A） |
| 以上凑不满 2 条 | 按 B → D → C 用 conservative 模板补到 2 |
| 超过 4 条 | 截断，保留顺序 A、B、C、D |

完整无缺口的个股/题材默认三件套：**A `evidence` + B `alternative` + D `counter`**。若同时 `no_action_room`，用 C 替换 D（仍是 3 条，不扩成 4）。这就是连续对话今天空芯片的补法。

### 6.2 `no_action_room`

只看结构化标志，不扫正文：

```
no_action_room =
    bool(open_gaps or spec_gaps)
    or status in {"partial", "degraded"}
    or any(action 以「等待」「需等」「待验证」开头 for action in spec_next_actions)
```

`status == completed` 且无缺口且没有等待型 next_action → 假。用户「现在就能核公告」时不应被当成无操作空间。

投影函数必须按上式写入 `no_action_room`，编排器读字段、不再算一遍，避免两处公式漂移。

### 6.3 填充公式

每条必须带具体 `subject` 或缺口原文，禁止「还想了解更多吗」。

| 角度 | type | `full_prompt` 公式 | `label` |
|---|---|---|---|
| A 有缺口 | `gap` | 沿用 `gap_mirror_followups`：只补这一项，给来源与数据日期 | `补齐：{缺口}` 截断到 20 |
| A 无缺口 | `evidence` | `{subject}目前最硬的一条公司级证据是什么，出自哪份公告或研报？` | `核对最硬证据` |
| B 有 D3/公司表 | `alternative` | `除了{subject}，下一跳应先核{name}的哪条订单/认证/产能证据？不要重复列出已有替代名单。` | `下一跳：{name}` |
| B 仅有瓶颈词 | `alternative` | `{subject}若不是最优表达，{bottleneck}这一环谁更接近订单或产能约束？` | `瓶颈：{词}` |
| B 无结构（连续对话第一期） | `alternative` | 现有模板：同链暴露度相近的替代标的，但**不得点名** `listed_names` 里的公司 | `同链下一跳` |
| C 无操作空间 | `recheck`（track 则改 `counter`） | `若{subject}现在不能动手，哪个可观察信号出现后才进入可执行窗口？` | `等到什么信号` |
| C 有可执行 next_action | `recheck` | `下一步如何执行并核验：{action}？` | 截断 action |
| D | `counter` | 有 trigger 用 trigger 原文；否则「出现哪些反证应下调对{subject}的判断」 | `证伪条件` |

回声禁令：`full_prompt` 去空白后不得等于 `parent_followup_prompt`；不得把 `listed_names` 写成「新发现的替代」。B 可以点名 `alternatives` 里的 `name`，因为那是「去核已经选出的下一跳」，不是发现新票。

### 6.4 可答性闸门（第一期静态）

第一期不做 skill 探测，只做类型级闸门：

- `question_kind == methodology`：禁止 `alternative`（没有标的可跳）。
- `track`：禁止 `recheck`（已有下期关注清单）。
- `gap`：无缺口不得造。
- 子 run：仍生成芯片（用户点进来是新问题）；只禁回声，不禁深度。Knevo「不对 suggest_options 返回再 suggest」对应我们「不对芯片生成结果再套一层生成」，已经满足。

第二期若要做「答得动才放」，白名单是：`alternative` → 个股深挖或题材研究；`gap/evidence` → 现有检索/核验；`counter/recheck` → 跟踪契约或 AnswerSpec triggers。本 spec 不实施。

### 6.5 LLM 润色

- 连续对话：默认 `polish=False`。
- legacy ask：可 `polish=True`，但必须先选角再填槽；LLM 只改 `label/full_prompt` 措辞，不得改 `type`、不得增删条数、不得改 `angle`。
- JSON 非法、超时、类型被改：丢润色，用确定性原文，warning 记 `followup_polish_dropped`。
- 禁止把整份答案再丢给模型「自由生成 5 条」。现有 `_llm_followups` 在 P1 接线后删除或降为 polish 实现。

## 7. 对外契约

`Followup` 增加可选字段 `angle: "A" | "B" | "C" | "D"`。旧读取方忽略即可。

`followups.json` 保持：

```
{
  "followups": [Followup, ...],
  "llm_used": bool,
  "llm_provider": str | null,
  "warnings": [str, ...]
}
```

条数合同：成功时 **2–4**，通常 3。不再保证 5 条。现有 `test_no_llm_yields_five_typed_templates` 必须改合同，不得为了绿测保留 5 条。

寒暄 / 单条事实无延伸：`question_kind=other` 且无缺口、无 D3、无 spec → 仍出 2 条 conservative（A evidence + D counter），不静默空列表。连续对话的「纯寒暄」若任务框架判定不研究，可以 0 条；判定权在现有 task frame，编排器不自作主张。

## 8. 接线顺序

### P0 — 编排器 + 连续对话（本 spec 的第一实施切片）

1. 在 `followups.py` 增加 `FollowupState`、`select_angles`、`compose_followups`。
2. `gap_mirror_followups` 改为 A 槽填充器，行为与现单测兼容。
3. `conversation_orchestrator` 连续终局：用 `ContinuousTurnResult` 投影 state，再 `compose_followups`。有缺口时 A 仍是 gap 镜像；无缺口时走 §6.1 完整套。
4. 落盘仍写 `followups.json`，消息 `followups` 字段仍是 asdict 列表。
5. 不切 8792。

### P1 — 收口另外两条路径

1. AnswerSpec 路径改投影 + compose，删除「conservative 凑满 4 条」里与选角冲突的补白。
2. ask s03 改投影 + compose；D3 构建函数同时返回结构对象。
3. `_llm_followups` 改为 polish 或删除。

### P2 — 连续对话补 B 的结构来源（可选，另开 spec）

若连续 episode 日后产出等价于 D3 的替代队列，再投影进 `alternatives`。本 spec 不发明连续对话的 D3。

## 9. 失败与降级

| 情况 | 行为 |
|---|---|
| state 全空 | 2 条 conservative，不抛 |
| 选角后填充文本为空 | 丢掉该槽，用下一 conservative |
| polish 失败 | 确定性原文 |
| compose 抛错 | 调用方 catch，主答案照发，degrade `followup_compose_failed`；连续对话可回退到现有 `gap_mirror` |
| 主答案超时/取消 | 不生成芯片 |

芯片生成不得增加 episode 工具步数，不得重跑检索。

## 10. 测试合同

新单测放 `intelligence/tests/test_followups.py`，四条 state fixture 钉死选角，不走网络、不走模型。

| fixture | 输入要点 | 必须 |
|---|---|---|
| gaps_only | 两条 open_gaps，completed | 至少 1 条 `gap` 且 angle=A；总数 2–4；`full_prompt` 含缺口原文 |
| d3_present | 无缺口，P0 含「星网锐捷」，listed_names 含它 | 恰好 1 条 angle=B；该条可点名星网锐捷；不得再把星网锐捷写成「新发现」 |
| no_action_room | partial + 一条 gap | 有 A；有 C 且问信号/窗口，不问「现在该买吗」 |
| methodology | question_kind=methodology，无缺口 | 无 A、无 `alternative`；D 至少 2 条；总数 2–4 |

横切断言：

- 每条 `len(label) ≤ 20`，`full_prompt` 非空且为用户口吻（含「请」或问号，或沿用现有 gap 句式）。
- `parent_followup_prompt` 原样不得出现。
- track 题无 `recheck`。
- 芯片正文不含「双红」「近几日涨停热度」这类一阶复读。
- `compose` 在 `polish=True` 但 LLM 改 type 时，落盘 type 仍是选角结果。

接线测：

- 连续对话完整答案（`open_gaps=()`）消息里 followups 长度 ∈ [2,4]。
- 连续对话有缺口时，现有 gap 镜像测继续绿，且可多出 B/C/D，但 A 仍在。
- ask 的 followups 端点仍 200；条数合同改为 2–4。

## 11. 与二阶导的分账（验收用语）

评测或人工看芯片时，用这两句判断有没有吸歪：

- 正文没有 D3 或没有「谁更接近订单/瓶颈」，算二阶导缺失，不能用芯片 B 顶替。
- 芯片 B 把 D3 名单再念一遍，或问「还有哪些替代标的」且答案已在 D3，算芯片越权。

正确形态：正文已经写出「真正卡在 PI 膜 / 更优表达是 XX」；芯片写「请核 XX 的订单或认证，不要重复名单」。

## 12. 落地时不讨论的问题

下列问题本 spec 已选定，实施时不得重新展开：

- 对外类型不改名。
- 连续对话第一期没有 D3 结构就不用假 D3。
- 条数 2–4，不再 5。
- 编排确定性，模型只润色。
- 先连续对话，再 ask / AnswerSpec。
- 追问是 turn-stopping 投影，不进 episode loop，不做成模型可见工具，不引入 Cordis。
- 组件先问「能挂上 dsh 哪条接缝」；挂得上则按该接缝反推形状，见 §14。

实施计划在本 spec 审阅通过后另写，不在本文展开文件级改动清单。

## 13. 与 dsh「万物皆插件」的对齐

对照权威：dsh `docs/architecture.md`（本地 pinned `tmp/dsh-source-index` @ `47f943859bef60e4160492346772ded9b24f765a`）；本仓已确认稿 `docs/superpowers/specs/2026-08-15-agent-base-dsh-absorption-design.md` §7.7。

### 13.1 先回答：算不算独立插件、影不影响主进程

**对研究主循环：独立。对交付层：同进程、同步、可卸载。**

| 问 | 答 |
|---|---|
| 会不会多走一步模型、多调工具、改 bindings / Evidence / 答案正文 / run status？ | 不会。compose 只读 `FollowupState`，写芯片列表。 |
| 是不是 Cordis 插件包、独立进程、可热插拔 npm 行？ | 不是。吸收稿已否决「把 Cordis 全量引入 Python」和「第一期上完整 Plugin Loader」。 |
| 卸掉追问，主研究还能不能跑完？ | 能。调用方 `try/except`，失败 degrade，主答案照发。 |
| 会不会拖住「run=completed 但消息还没写完」？ | 会，如果把重 IO / LLM 塞进 claim 和 `revise_message` 之间。P0 必须保持零模型、纯 CPU 模板，耗时与现有 `gap_mirror` 同级。 |

dsh 原文把「插件」定义成：往共享 context 上挂服务和可逆 effect，**包括 loop 自己**；扩展靠旁挂，不靠改特权核心。我们要的是这条**接缝纪律**，不是把 TypeScript 插件树搬过来。

### 13.2 dsh 里这种功能该挂哪

dsh 新行为必须挂已有扩展点，改 loop 本身要先改架构图。追问对应的是：

| dsh 机制 | 为什么是它 | 我们的落点 |
|---|---|---|
| `agent/turn-stopping`（serial，无 `next()`） | 轮次将停，只能观察/附带，不能再开 step | 答案已定后的 `compose_followups` |
| Session Event vs Live Event | 模型看见的必须能从 durable log 重建 | 芯片**默认不是**模型可见输入；进 `followups.json` 和消息字段，不进下一轮 prompt，除非另开 durable 事件（本 spec 不开） |
| Capability seam = Definition + Provider + Consumer | 换提供方不改 loop | 见下表 |
| ConversationNode / 从 `session/event` 渲染 UI | 产品壳消费投影，不回调 loop | Workbench 读消息 `followups` |

禁止的挂法（那才是影响主进程）：

- 做成 Knevo 那种模型可见 `suggest_options` 工具（会进 step、烧预算、污染轨迹）。
- 挂 `agent/pre-step` 或 `tools/pre-execute`（能改模型看见的东西或拦截工具）。
- 写进 `episode_protocol` 的终局 JSON，让模型自己编 A/B/C/D。

### 13.3 我们怎么用这条原理（不引入 Cordis）

吸收稿 §7.7 已选定：先用 **Python Protocol + Profile + 调用点**，等跨领域复用真出现再评估插件包。追问的三角色如下。

```
FollowupComposer(Protocol)          # Definition：compose(state) -> FollowupResult
AngleComposer / NullComposer       # Provider：选角实现，或恒返回空
conversation / ask s03             # Consumer：把结果投影进消息和 artifact
```

纪律（实施时当门禁）：

1. **Provider 只依赖 services。** `followups.py` 继续留在 `intelligence/services/`。`runtime/` 只投影 state、调用 Protocol、catch。`layer_audit` 方向不变：services 不得 import runtime。
2. **NullComposer 必须可替换。** Profile 或入口能关掉追问；关掉后连续对话与 ask 的主路径测试仍绿。这就是 dsh「卸载则 effect 回卷」的 Python 版，不需要插件加载器。
3. **同一 turn 内芯片对模型不可见。** 用户点击芯片等于**新 turn 的用户消息**，不是给当前 episode 补一条 tool result。
4. **Durable 事实仍是答案、gaps、bindings。** 芯片是 Live/交付投影。重放研究不重跑 compose 也能重建主答案；芯片可从同一份 `FollowupState` 重算。
5. **不在 P0 做独立进程或队列。** 同进程同步调用。独立进程会引入「run 已完成、芯片后到」的竞态，现有测试已经在防这个窗口。

### 13.4 和吸收稿六条边界的关系

追问只兑现其中两条，其余不动：

- **Projection（第 6 条）**：芯片从终局状态派生，UI/评测读投影，不读 episode 内存。
- **Scoped 能力（第 3 条，弱）**：`NullComposer` vs `AngleComposer` 是交付层开关，不是工具授权。
- 不碰工具流水线、Session Event 分类落地、RuntimeHandle、ResearchProfile 全文。那些仍归 2026-08-15 吸收稿。

## 14. 反推法：先问能不能挂上 dsh 接缝

dsh 说的是**万物皆插件**，整机才是 harness。本仓已有另一刀：通用 harness（不管对错，只保证不夹带）vs 领域 harness（必须懂 A 股）。两刀一起用，不要混成「万物都是 harness」。

对任意组件只问一句：**明天若必须做成 dsh 插件，它挂哪条已文档化的接缝？**

| 判定 | 含义 | 反推我们怎么长 |
|---|---|---|
| 挂得上，且不改 loop 图 | 「能在 dsh 上跑」= 形状可移植 | 做成 Definition + Provider + Consumer；领域计算留在 Provider；卸掉不影响主循环 |
| 只能进某个 tool 的 `execute` | dsh 只宿主流水线 | 保持 ToolSpec；对错仍由 Evidence / Verifier 判；不要把算法写进 loop |
| 找不到接缝、或必须改 `agent-loop` | 焊死了，或它根本是领域真源 | 先拆焊点；真源（Evidence Ledger、语义核验、截止日）留在 Python 网关，dsh 只能当对照臂调用，不能当账本 |

「能在 dsh 上跑」**不等于**生产研究改走 dsh。DuckDB、截止日、绑定仍在本仓。这句话只检验边界。

### 14.1 追问套进去的结果

dsh 现成接缝（`docs/subsystems/session-projection.md`）：

> 框架负责驱动，领域负责计算……它是一项可选能力，**不属于 agent-loop 主干**。三个函数必须同步。领域插件卸载后，其 key 从快照消失，客户端读作能力缺失。

再加一条 UI：`ConversationNodeDefinition` 从事件渲染一行，点击经 `agent.followup()` 变成**下一轮用户消息**。

所以追问若要在 dsh 上跑，做法是：

1. 注册一个 projection unit `followups`：`init / apply / view` 都是纯函数、同步。
2. `apply` 只吃已提交的终局事实（subject、status、open_gaps、D3 结构引用），不调模型、不调工具。
3. `view` 输出芯片列表（即我们的 `compose`）。
4. Chat Node 画按钮；点击 = 新 turn，不是本 turn 的 tool result。
5. 不注册 `suggest_options` 工具。
6. 卸载该插件 = `NullComposer`：loop 与核验不变。

这与 §13 一致，并多锁一条：**P0 的 compose 必须能当 `view()` 用**——输入是冻结 state，输出是整份芯片值，无 IO、无订阅。LLM 润色若要做，只能在投影之外的可选 carrier，不能进 `apply/view`，否则在 dsh 上会撕掉「同步一致性切面」。

### 14.2 第一刀组件对照（只定形状，不在本 spec 改建）

| 本仓组件 | 能挂的 dsh 接缝 | 反推 |
|---|---|---|
| `agent_episode` / Runtime Protocol | `ctx.agentLoop` | 通用循环；金融规则不准再渗进去 |
| `llm_refine` / provider 链 | `ctx.llm` | 换模型是 adapter，不是改 loop |
| `research_tool_registry` + `finance_query` 等 | `ctx.tools`，语义在 `execute` | 宿主流水线 + 领域执行体 |
| `honesty_gates` / 截止日 | `tools/pre-execute` guard | hook 可挂；判据仍是领域 |
| `episode_semantic_verifier` | 无通用「对错」接缝 | **不能**做成 dsh 插件顶替；loop 只能调用，不能拥有 |
| `evidence_ledger` | 不是 session log；近 `storageDomain` | 金融真源留本仓；session 只存引用 |
| D3 / `ask_blocks` | 领域计算，经 tool result 或 storage 露出 | 出结构对象给投影，禁止 Markdown 反解析 |
| **追问 `followups`** | **`ctx.sessionProjections` + ConversationNode** | 本 spec 的目标形状 |
| `foresight` | `ctx.jobs` / `ctx.commands`（可不经模型 turn） | 不要焊进 ask s03 |
| skills | `ctx.skills` | 渐进披露，不是工具爆炸 |
| 子研究 / Task | `ctx.subagents` | 隔离上下文，回摘要 |
| Workbench 芯片 UI | ConversationNode | 只读投影，不回调 loop |
| `keychain_credentials` | `ctx.credentials` | 已是 seam |
| 压缩 | `agent/pre-step` + `ctx.tokenMeter` | 先接口后策略（吸收稿 §7.6） |

判定口令仍用 7 月 31 日那句：规则要懂 A 股才能写 → 领域 Provider / 网关；否则 → 通用接缝。
