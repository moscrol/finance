# V8 附录 · 可选前瞻槽（Optional Forward Slots）——设计增补

- 日期：2026-08-24
- 作者：实施设计（本单只出设计，不写生产代码、不改测试、不部署）
- 状态：**§4 / §5 两个决策已由用户批准（2026-08-24）**，可进代码，按 §11 两步实施
- 上游：V8 spec `2026-08-22-v8-semantic-deletion-rights-design.md`（本文件是它的 addendum，不推翻其任何结论）；先例 `R-20260821-04` 槽位保护（confirmed）、#72 观点题判断槽 model_reasoning（`docs/verification/2026-08-16-outlook-eb-judgment-slot.md`）
- 台账行：`R-20260824-20`（**实施时**才立案；文末给出可逐字抄的预测与验法）。编号避让说明：knevo28 批次占 `R-20260824-12..19`，outlook 草稿占 `R-20260824-11..15`，故本单从 `-20` 起
- 基线锚：行号相对 `gitea/main`（**`34fcbaaa`**，2026-08-24 重锚）。初稿锚在 `8688545b`，两天内 main 前进 40 个 commit、三个落点文件全动过（factory +41 行、verifier 79 行、research_contract +180 行），初稿行号已全部失效
- 修订记录：2026-08-24 验收复核；同日二次更正（`harness-architecture-review` 走查）。改动见 §13

> ⚠ **行号会腐烂，符号名不会。** 本文所有 `文件:行号` 都在括号里附了符号名。main 一动行号即失效，**认符号不认数字**；重锚用
> `grep -n '^def _novel_numeric_condition_indexes\|^_ADVISORY_OUTPUT_IDS' <file>` 这类命令现查，不要沿用本文数字。

> 角色分离沿 R2 纪律：本文件是设计合同，不是施工 diff。合并需验收方复算 + 用户确认。

---

## 0. 一句话

问句带前瞻信号（「怎么看 / 会怎么走」这类）但题型不在 `market_forecast` / `event_forecast` 时，装配层把 `scenario_paths` / `continuation_conditions` / `invalidation_conditions` 三槽以 **`required=False` + `grounding_mode=model_reasoning`** 挂上契约，并把数值门的条件槽豁免从「只认必选前瞻槽」放宽到「必选可选都认」——让模型提出的条件阈值**有槽可落、机械门不再整句砍**，同时**不强制情景分析**、不动 `numeric_unsupported` 删除权本身、不碰 V8 回归锚。

人话：现在「你怎么看明天的盘」这类题，模型写「若指数跌破 3870 点则转弱」会被数值门当无据数值整句删掉，因为这道题的契约里根本没有一个授权它提阈值的槽。本单给它补一个**可选的**落点：不写情景分析不算失败，写了阈值有合法身份。

---

## 1. 与 V8 的关系

### 1.1 本单遵守 V8 的哪些结论

| V8 结论 | 本单处置 |
|---|---|
| `numeric_unsupported` 是机械硬违规，**删除权不收窄**（V8 §3.2 白名单第 1 条） | **不违反**。本单不把它移出白名单、不改 `_repair`、不改删句逻辑。动的是**上游契约装配**：一个数是不是「无据」，取决于契约有没有委托模型提出它——这个判定通道（条件槽粒度豁免）V8 之前就已存在，本单只是扩它的适用面 |
| W1 钉②（`test_numeric_unsupported_sentence_is_still_deleted`）保持原断言（V8 §2 目标 3） | **不改这条钉**。它的夹具契约是 `direct_assessment` + `evidence_boundary` 两槽、无任何前瞻槽——本单落地后豁免条件依旧不成立，该钉原样绿。这条钉正是用户此前试图收窄「L5 数值门只标不删」时撞红的那条；本单绕开它的方式不是改断言，而是换了动刀的位置 |
| R-04 槽内数字保护不动（V8 §1.1） | 不动 |
| V8 语义旁路范围锁**必需块**（V8 §6：非必需块语义句维持可删） | 本单挂的可选槽**不获得** V8 的语义免删权。语义判官对可选槽里的句子照常有否决权。本单只管机械数值门这一条通道 |

### 1.2 本单依赖 V8 / 先例的哪些机制

- **R-04 的手法**（V8 §1.3 引为「保下限已证」）：与其在输出端拦（删句），不如在输入端把授权装配好。R-04 是「系统填槽 → 槽内数字免删」；本单是「契约签约 model_reasoning 槽 → 条件阈值免进数值门」。同一根思路的第三次应用（第二次是 #72 判断槽）。
- **可选槽先例**（`episode_factory.py:362-374` `_ADVISORY_OUTPUT_IDS` + `:620` `required=output_id not in _ADVISORY_OUTPUT_IDS`）：`prior_recall` / `prime_*` 已经验证过「`required=False` 的槽完整存在于契约与提示词里，模型看得见、可以绑、绑了会被校验（basis 闸）；缺了只降 gap 不判失败」。本单复用这套语义，不发明第二种可选性。**但注意 prior_recall 的「模型看得见」是靠一条专用动态提示规则换来的，不是白来的——见 §3.2。**
- **条件槽粒度豁免**（`episode_semantic_verifier.py:3258-3271`，`_novel_numeric_condition_indexes` 内第二块）：market_forecast 混合契约下「证伪阈值必死」的问题已经修过一次，修法就是按槽豁免。本单是同一豁免的第二期。

### 1.3 为什么叫 addendum 而不是新 spec

V8 的战场是**删除权分流**（`_repair` 之前分机械/语义）；本单的战场是**契约装配**（`_repair` 的更上游）。两者共享同一组回归锚（W1 钉②、机械预检钉簇），但改动互不重叠：V8 实施动 `verify()` 调用点，本单动 `episode_factory` 与数值门豁免判据一行。写成 addendum 是为了把「numeric_unsupported 相关的所有动作」收在一处谱系里，避免后来者以为这两单在互相打架。

---

## 2. 背景：问题形状与已否决的两条路

### 2.1 现状机制（从代码抽出，不凭空拟）

**契约侧**（`episode_factory.py`）：

- `_FORWARD_HYPOTHESIS_QUESTION_TYPES = {"market_forecast", "event_forecast"}`（`:209`）——只有这两个题型的前瞻槽签 `model_reasoning`（`:495-504`，`_grounding_mode` 的 forward 分支）。注释写明 market_technical 刻意排除：支撑/均线是可查的，失效位应来自行情数据。
- `_OUTLOOK_JUDGMENT_RE = 你认为|你觉得|怎么看|机会在哪|会怎么走`（`:204-206`）——问句命中时把**判断槽**（`direct_answer` / `direct_assessment`）签成 `model_reasoning`（#72，2026-08-16 生产验证）。注意它只改判断槽的签法，**不加槽**；且它与 `output_id in _OUTLOOK_JUDGMENT_OUTPUTS` 是**联合**生效的（`:485-487`），单看正则会高估其现有作用面——本单复用它时的取舍见 §4.4。
- 三个前瞻槽 id 的单一真本源是 `research_contract.py:735-742` `FORWARD_HYPOTHESIS_OUTPUT_IDS`（注释 `:730-734`），factory 与 verifier 两处共用（注释点名「各存一份词表必漂」）。

**题型槽表侧**（`task_frame.py:~723-790`，`market_forecast` 条目在 `:736`）：默认槽表里带前瞻槽的题型只有 `market_forecast`（三槽全带）、`event_forecast`（scenario_paths + invalidation_conditions）、`market_technical` / `trade_advice`（invalidation_conditions）；另有显式正则（`_REBOUND_HORIZON_RE` 分支，`:648` / `:723`）与 `valuation_estimate` 的 factory 层追加（`episode_factory.py:179-185` `_VALUATION_REQUIRED_OUTPUTS`，已实测含 `invalidation_conditions`）。**其余题型（general_finance_qa / market_watch / stock_deep_dive / theme_analysis…）契约里没有任何前瞻槽。**

**数值门侧**（`episode_semantic_verifier.py:3244-3306` `_novel_numeric_condition_indexes`）：只审**条件句**（`_CONDITION_TRIGGER_RE`：若/如果/失效/降级/跌破/站稳/至少/阈值/支撑/才算成立，`:177-180`）；句内数量不在已绑定证据里 → 句号进机械删除。豁免两层：全契约非 evidence（`:3252-3257`）、或条件槽粒度豁免（`:3258-3271`）。

### 2.2 失败形状

2026-08-19 生产 run 已实锤过一次（`episode_factory.py:462-464` 注释）：前瞻题条件阈值被数值门砍 → 模型学会自保输出「相对变化描述，具体阈值以盘面为准」。那一轮的修法是题型闸门（`_FORWARD_HYPOTHESIS_QUESTION_TYPES`），只覆盖 market_forecast / event_forecast。

但前瞻信号不只出现在这两个题型。「你怎么看明天」「后市会怎么走」经常落在 general_finance_qa / market_watch / stock_deep_dive，这些题的契约没有前瞻槽，于是：

1. 模型写出的条件阈值**没有槽可绑**——绑进判断槽勉强合法（#72 后判断槽是 model_reasoning），但「情景 / 持续 / 证伪」的结构化落点缺失；
2. 数值门照 `_CONDITION_TRIGGER_RE` 命中条件句、阈值不在证据里 → **整句机械删除**；
3. 模型在这些题型上重新学会 2026-08-19 那套自保话术。

### 2.3 已否决的两条路（为什么走本方案）

| 路 | 做法 | 否决理由 |
|---|---|---|
| 收窄 L5「数值门只标不删」 | 把 `numeric_unsupported` 从删句改为标注 | **撞红 `test_numeric_unsupported_sentence_is_still_deleted`**（用户已实测）。且 V8 三筛已把它定性为「保下限、删除权不收窄」（V8 §1.3 表第 1 行）——这条路在结论层面就被封死，不是测试写错 |
| 路由正则放宽 | 把带前瞻信号的题都判成 market_forecast | 太宽：换题型 = 换**整个契约模板**（五槽全换、presentation_profile 换、evidence_plan 换），影响面是两个模板的全部差异。前瞻信号只是问句的一个侧面，不该劫持整题分类 |
| **本方案：装配层挂可选槽** | 题型不动、路由不动，只在契约上追加三个可选槽 + 放宽豁免一行 | 影响面 = 新增项本身。这是 `prior_recall`（`_with_prior_recall`，`:325`）走通过的同一条路 |

> 📚 **可迁移知识点（选型原理）**：「改分类」vs「加可选项」是配置系统的经典分岔。改分类的影响面 = 两个模板的对称差，加可选项的影响面 = 新增项集合，后者天然可控。这在 feature flag 设计（细粒度开关 vs 整页换版）、HTTP 内容协商（加 Accept 头 vs 换 endpoint）里同构。面试常考的「开闭原则」说的也是这件事：对扩展开放（挂槽），对修改关闭（不动题型判定）。

---

## 3. 两个技术坑（本单成败所系）

### 3.1 坑一：豁免只认 `required=True`

`_novel_numeric_condition_indexes` 的条件槽粒度豁免（`intelligence/services/episode_semantic_verifier.py:3263-3271` @ `34fcbaaa`）：

```python
condition_items = tuple(
    item
    for item in contract.required_outputs
    if item.required and item.output_id in FORWARD_HYPOTHESIS_OUTPUT_IDS
)
if condition_items and all(
    item.grounding_mode != "evidence" for item in condition_items
):
    return ()
```

`item.required and` 这个过滤意味着：**`required=False` 的前瞻槽根本进不了 `condition_items`**。如果本单只做装配层挂槽、不动这一行，则挂上的可选槽全部被过滤 → `condition_items` 为空 → 豁免不触发 → 模型按新契约写出的阈值句照样被机械门砍。

**只挂槽不放宽豁免 = 本单等于没做，且比没做更糟**：契约明示「你可以在这格提出条件阈值」，运行时却把按契约写的句子删掉——这是 MOC 已确立原则第 4 条的现场（「授予的额度必须真的传到最下游执行者——只写进 telemetry 不生效，比不做更危险」）。

> 📚 **可迁移知识点（正交轴不要混用）**：`required` 与 `grounding_mode` 是 `RequiredOutput`（`research_contract.py:744-752`）上两根正交的轴——`required` 管**完成性**（缺了算不算失败，消费方是 `episode_protocol.py:784-800` 的 completed 检查），`grounding_mode` 管**授权性**（内容由谁背书，消费方是 basis 闸和数值门）。豁免判据本该只看授权轴，现行代码把完成轴也搅了进来。这个坑在权限系统里同构：RBAC 的 role（你是谁）和 scope（你能干什么）混用，就会出现「降级用户身份顺带吊销了本不相干的授权」。

### 3.2 坑二：`grounding_mode` 主循环不投递、只在恢复路径投递（2026-08-24 复核新增，同日二次更正）

初稿 §7 实施注写着「契约 JSON 里 `required: false` + `grounding_mode: model_reasoning` 已是完整信号，动态提示规则**默认不加**」。**这个前提是错的**——但错的形状比第一版复核写的更精确，两处都实测过：

**两个渲染点，只有一个带 `grounding_mode`：**

| 渲染点 | 何时用 | 发不发 `grounding_mode` |
|---|---|---|
| `generic_research_owner.py:419-429`（主循环） | 正常研究回合 | ❌ 只发 `id / description / evidence_types / required` |
| `intelligence/runtime/episode_finalizer.py:169-178`（恢复器） | 主循环没交出合法 finish 之后的**终局恢复**（`_FAILURE_REASON_CODES` 含 `invalid_model_finish`） | ✅ `:175` 明确带上 |

- `episode_protocol.py:302` 的通用提示写的是「每个 binding 的 `basis` 必须与对应 required output 的 `grounding_mode` 一致」——**在主循环里，这是在要求模型对齐一个它看不见的字段**。
- 解析侧 `basis` 的默认值是 `"evidence"`（`basis=str(raw.get("basis") or "evidence")`），basis 闸在 `:738` 硬拒，拒的是**整份 FINAL_JSON**。
- `basis_mismatch` 归类 `RejectionKind.FORMAT` → `reinject=True, allow_recovery=True`，于是落到恢复器，而恢复器的提示词里**恰好带着这个字段**。

**所以系统的真实工作方式是「先让你摔一跤，摔完再告诉你答案」，每次白烧一个来回。**

**[实测]** 不是推断。`intelligence/eval/measurements/2026-08-18-frozen-thirty-live-3d30b2c5.json` 里有两次：

```
grounding basis mismatch for direct_answer: expected evidence, got model_reasoning
stop_reason=invalid_model_finish
```

注意**猜错方向与设计预期相反**（模型报了 `model_reasoning`，契约签的是 `evidence`）。方向随机恰恰是最强的证据：病因是「没告诉它」，不是「它偏好某一侧」。

**为什么 `prior_recall` 没踩到**：因为它有一条**专用动态提示规则**（`episode_protocol.py:150-170`）。§1.2 说的「prior_recall 已验证过模型看得见」，看得见靠的正是这条规则，不是主循环的契约 JSON。

**因此 §7 那条实施注反转**：动态提示规则**默认加**，且是 §8.1 钉 10 的前置条件，不再是「实施方裁量」。

> ⚠ **但这条规则是补丁，不是修复**——见 §10 第 10 条与 §13「本单留下的技术债」。结构修法是给主循环渲染补上 `grounding_mode`（照抄恢复器 `:175` 的写法），让约束**由构造即满足**。按 `harness-architecture-review` C2 约束三筛：这条约束本身是**真下限**（谁给这格背书是事实来源问题），烂的是它被实现成**拦输出**（审已产出的稿、且拒整份）——判「**可改写成拦输入**」，正确动作是**减契约管辖权**，不是像本单这样再加一条逐槽手写规则。修完之后，`_question_type_rules` 里凡是只为传达 `grounding_mode` 的规则（prior_recall 那条、本单这条）都可以删。

> 📚 **可迁移知识点（承诺值 vs 执行值）**：这是「字段设了但没送到消费者」的典型——契约里 `grounding_mode` 有值、闸门按它判、唯独**该按它行事的执行者在主路径上收不到**。查法很机械：对每个约束字段，从**产生点**一路 grep 到**每一个**执行点，中间任何一次序列化没带上它，这个字段在那条路径上就是装饰。**注意「每一个」**——本单第一版复核只查到主循环就下了「压根不进提示词」的结论，漏掉恢复器那条，把形状说重了；多路径系统里，字段可能只在某几条路上丢。这和「预算字段填了但执行处没读」是同一个体检项，也是分布式系统里 header 只在重试链路上带全、feature flag 没下发到部分客户端的同款形状。

---

## 4. 决策 1（已批准）：触发面——什么信号、在哪些契约上挂槽

### 4.1 备选对比

| | 案甲 · 复用 `_OUTLOOK_JUDGMENT_RE` + 槽表交集判据（**已批准**） | 案乙 · 新增独立前瞻信号正则 | 案丙 · 按题型清单挂槽 |
|---|---|---|---|
| 触发信号 | 问句命中 `_OUTLOOK_JUDGMENT_RE`（你认为/你觉得/怎么看/机会在哪/会怎么走） | 新正则（如「后市/接下来/短期内会/若…则」） | 不看问句，给指定题型静态加槽 |
| 挂槽范围判据 | `set(output_ids) ∩ FORWARD_HYPOTHESIS_OUTPUT_IDS == ∅` 时才挂（对 factory 定稿后的 output_ids 判断） | 同左 | 维护一张「哪些题型挂」的清单 |
| 词表卫生 | **零新词表**：信号复用 #72 已生产验证的正则；范围判据是就地集合运算，不是清单 | 第二张前瞻词表，必漂（`route_table` QUICK_FACT_PATTERN 注释里有同款事故） | 第二张题型清单，且**看不见 factory 层追加的槽**（valuation_estimate 的 invalidation_conditions 在 `_required_output_ids` 里才追加，题型清单方案会对估值题重复挂槽） |
| 误触发形状 | 「怎么看」命中面偏宽（方法论题、KOL 评论题也会命中）——但挂的是**可选**槽，误触发的代价是契约里多三个没人绑的格，不产生失败路径 | 更准，但没有生产数据校准，准头是拍脑袋的 | 无问句信号，纯粹按题型放大挂槽面，与「前瞻信号」的立意脱节 |
| 与 #72 的一致性 | 同一信号同时改判断槽签法 + 挂前瞻槽，用户可以用一条心智模型理解 | 两个信号两套行为，解释成本翻倍 | 不适用 |

### 4.2 结论：案甲（已批准）

取舍一句话：**误触发的代价结构决定了信号可以宽**。挂可选槽的失败模式是「多了三个没人绑的格」——completed 不受影响（可选槽缺绑不判失败）、gap 记账不受影响（advisory 语义），最坏是提示词里多几行。既然代价是加法而非乘法，就不值得为准头引入第二张必漂的词表。若 live 观察到误触发产生实际噪声（比如概念定义题被挂槽后模型硬写情景），再收窄信号——**先用宽信号拿数据，再谈收窄**，方向不可逆着走（先窄后宽拿不到误触发样本）。

**但「代价是纯加法」这句要打折（2026-08-24 复核）**：LLM 有**给了格就填**的倾向。误触发时模型可能在「这个概念怎么看」这类题上硬写情景分析；而这三槽是 model_reasoning，其条件句此时已被数值门豁免——**误触发不只是多三个空格子，它同时小幅扩大了无据阈值能存活的面**，方向是「变错」而不是「变笨」（正是 §5.2 那把尺子指向的贵的一侧）。结论不变（仍走案甲），但**验收判据必须能看见这件事**：§8.3 因此增加一条误触发样本腿，不是可选项。

附带子决策（随案甲一起拍）：**三槽全挂**，不做「只挂 invalidation_conditions」的子集——子集意味着在 `FORWARD_HYPOTHESIS_OUTPUT_IDS` 之外再造一份子集词表，违反单一真本源；且三槽描述文本（`episode_factory.py:51/52/75`，实测未漂）与 `task_fulfillment.py:195-218` 的措辞标记词表都已齐备，挂三槽零增量成本。

### 4.3 额外排除条件（不在交集判据里、需显式写）

- `_is_evidence_free_task(frame)` 为真（方法论题 / 反事实题）不挂：这些题全契约非 evidence，数值门整体豁免（`:3252-3257`）已覆盖，挂槽纯属污染契约。
- `market_forecast` 反弹变体（`_REBOUND_HORIZON_RE` 分支，`task_frame.py:648` / `:723`）无需排除：其槽表已含 continuation/invalidation，交集判据自然拦下。

### 4.4 子决策：要不要连 `_OUTLOOK_JUDGMENT_OUTPUTS` 门一起复用（2026-08-24 复核新增）

`_OUTLOOK_JUDGMENT_RE` 今天**从不单独生效**——它与 `output_id in _OUTLOOK_JUDGMENT_OUTPUTS`（`direct_answer` / `direct_assessment`）是 `and` 在一起的（`episode_factory.py:485-487`）。本单若只复用正则、不带这个 output 门，触发面就比 #72 今天的实际作用面**更宽**：契约里连判断槽都没有的题也会被挂三槽。

**定为：不带 output 门**（即挂槽只看正则 + 交集判据 + evidence-free 排除）。理由与 §4.2 同——宽信号先拿数据；且「有没有 direct_answer 槽」与「这题是不是问前瞻」没有因果关系，用它当门是借来的判据。**但实施时必须在挂槽函数上写一行注释点明这处与 #72 的作用面差异**，否则下一个人比对两处会以为漏了条件。若 §8.3 误触发腿显示噪声集中在无判断槽的题上，收窄时第一个该加的就是这个门。

---

## 5. 决策 2（已批准）：数值门豁免怎么放宽

### 5.1 备选对比

| | 案甲 · 去掉 `item.required and`（**已批准**） | 案乙 · `all()` 改 `any()` | 案丙 · 可选前瞻槽走「标注不删」 |
|---|---|---|---|
| 做法 | `:3266` 一行：`if item.output_id in FORWARD_HYPOTHESIS_OUTPUT_IDS`。豁免判据变成「契约里存在前瞻槽（无论必选可选）且它们**全部**非 evidence」 | 「存在**至少一个** model_reasoning 前瞻槽」即豁免 | 豁免不动；对可选前瞻槽契约里的条件句，数值门从删句改为 W1 式标注 |
| 语义 | 豁免依据回归纯授权轴（grounding_mode），完成轴（required）退出判定 | 混合签约契约（一个 evidence 前瞻槽 + 一个 model_reasoning 前瞻槽）也豁免 | 给数值门开第二种处置分支 |
| 保守性 | 保持 `all()`：契约里只要有**一个** evidence 签约的前瞻槽，整个条件句豁免就不触发（fail-closed 于证据侧） | **打穿下限**：market_technical 若被挂槽（或未来有人改触发面），其 evidence 签约的失效位阈值也被豁免——「技术位必须可查」失守 | — |
| 与 V8 的关系 | 白名单成员资格不动，删除路径不动 | 同左 | **这就是用户已撞红放弃的「L5 只标不删」换皮**——数值门的删除权被部分收窄，违反 V8 §3.2 结论 |
| 改动量 | 一行 + 钉 | 一行 + 钉 | 新分支 + 新呈现 + 新钉簇 |

### 5.2 结论：案甲（已批准）

取舍一句话：required 本来就不该是豁免判据——它回答「缺了算不算失败」，不回答「谁授权这个阈值」（§3.1 的正交轴论证）。去掉它之后豁免判据在两根轴上各自干净：授权轴用 grounding_mode（`all(!= "evidence")`），存在轴用「契约里有没有前瞻槽」。

**对现存契约零行为变化的论证**（2026-08-24 已逐条实测于 `34fcbaaa`；实施时仍须用参数化夹具复核，不得只信本推导）：

命题：今天不存在「output_id ∈ `FORWARD_HYPOTHESIS_OUTPUT_IDS` **且** `required=False` **且** `grounding_mode != "evidence"`」的槽。只要它成立，去掉 `item.required and` 就不改变任何现存契约的判定。逐个枚举 `required=False` 的产生点：

1. **factory 装配**（`episode_factory.py:620`）：`required=output_id not in _ADVISORY_OUTPUT_IDS`——`required=False` **只**可能来自 advisory 集合。该集合实测为 `{prior_recall, prime_memory, prime_quote, prime_news, dual_red_snapshot, aggregate_count, detail_rows, cross_table_intersection, catalog_preflight, contradiction_audit}`（`:362-374`），与三个前瞻槽**交集为空**。
   > 初稿此处写「`_ADVISORY_OUTPUT_IDS` 只含 prior_recall/prime_*」，**是错的**（漏了后六个 operator 槽）。结论不受影响（漏掉的那些也都不是前瞻槽），但论据已按实测更正——照抄初稿那句去推别的结论会翻车。
2. **W2 不可达降级**（`mandatory_satisfiability.py:115-147` `apply_unreachable_downgrade`）：入口只圈 `evidence_required_output_ids(contract)`（`required=True` **且** `grounding=evidence`），而 `_downgrade_output`（`:181-186`）实测只 `replace(item, required=False, preplaced_gap=…)`——**不碰 `grounding_mode`**。所以唯一理论路径（market_technical / trade_advice 的 invalidation_conditions 被降级）产出的是 `required=False` + **仍为 evidence** 的槽：去掉 `item.required` 后它会进 `condition_items`，但 `all(!= evidence)` 失败 → 不豁免——**与现行为一致**（现行为下它被过滤出去、condition_items 为空、同样不豁免）。
3. **W2 静态链路预检**（`apply_static_chain_mapping_precheck`，`:60-85`）：只作用于 `chain_mapping`，不涉前瞻槽。
4. **market_forecast / event_forecast 的必选前瞻槽**：`required=True`，改前改后都进 `condition_items`、都豁免——不变。
5. 全树另一处 `required=False` 字面量（`intelligence/runtime/codex_headless_runtime.py:511`）实测是 `_load_headless_provider_projection(..., required=False)` 的无关 kwarg，不是 `RequiredOutput`。

命题成立 → 第 1 步（§11）确实零行为变化，可独立合入、独立回滚。

**实施必须补的一条注释**：放宽后，第一块豁免（`:3252-3257` 全契约非 evidence）**仍然保留** `if item.required` 过滤，与第二块不再对称。这个不对称是**对的**——第一块问「整个契约是不是 evidence-free」，advisory 可选槽（prior_recall 等）不该左右这个判断；第二块问「模型有没有被授权提条件阈值」，可选与否无关。**必须把这个理由写进注释**，否则下一个人来「统一一下风格」就会顺手把第一块也放宽，那才是真的打穿下限。

> 📚 **可迁移知识点（fail-closed 的落点选择）**：案甲 vs 案乙的分界在 `all()` vs `any()`——出现证据签约与推理签约并存时，向哪边倒？向证据侧倒（all，一票否决豁免）是 fail-closed 于「假数上桌」；向推理侧倒（any）是 fail-open。V8 三筛的判据可以直接搬来：豁免失效时系统「变笨」（真阈值被删），豁免误开时系统「变错」（假阈值上桌）——变错比变笨贵，所以往 all() 倒。这个「失效向哪边倒」的分析框架在超时默认值、权限缺省、缓存击穿策略里都能用。

---

## 6. 行为契约（实施时逐条可测）

1. **触发**：问句命中 `_OUTLOOK_JUDGMENT_RE` ∧ factory 定稿后的 `output_ids` 与 `FORWARD_HYPOTHESIS_OUTPUT_IDS` 交集为空 ∧ 非 evidence-free 题 → 三槽以 `required=False`、`grounding_mode=model_reasoning`、`evidence_types=()` 追加到 `required_outputs` 尾部，描述用 `_OUTPUT_DESCRIPTIONS` 现有文案（`episode_factory.py:51/52/75`），不新写描述。
2. **不强制**：模型不绑这三槽 → completed 照过（`episode_protocol.py:787-788` `if not required.required: continue`，在 `:784` 起的 completed 检查块内）；不进 `missing_outputs`；不触发 gap 公开声明（`continuous_turn_adapter.py:1726` 等处均按 `item.required` 过滤，自动生效）。
3. **有槽可落**：模型绑这三槽必须 `basis=model_reasoning`（`episode_protocol.py:696-701` basis_mismatch 闸）。**闸门是既有的，但「模型知道该报 model_reasoning」不是既有的**——`grounding_mode` 不进提示词（§3.2），所以本条依赖新增的动态提示规则，不能标成「自动生效」。
4. **数值门贯通**：挂槽后的契约里，条件句（`_CONDITION_TRIGGER_RE` 命中）的新阈值不再进 `numeric_unsupported` 机械删除（§5 案甲放宽后豁免触发）。**非条件句**不受影响——数值门本来只审条件句，事实句的无据数字仍由语义判官按 `verified_quantities` 逐句审。
5. **现状保持**：
   - market_forecast / event_forecast 契约字节级不变（不重复挂、必选性不变、签法不变）；
   - market_technical / trade_advice / valuation_estimate / 显式正则命中的契约不挂（交集判据拦下），market_technical 的 invalidation_conditions 保持 evidence 签约；
   - 无前瞻信号的题（同题型）契约不变；
   - 无前瞻槽契约上的条件句阈值**照删**（V8 回归锚原样绿）。
6. **不扩语义豁免**：可选槽内句子被 LLM 语义否决时，处置沿 V8 结论（非必需块可删）。本单不给它们免删权。
7. **可选性不外溢**：`_ADVISORY_OUTPUT_IDS` **不**加这三个 id（全局加会把 market_forecast 的必选前瞻槽也降成可选）。可选性只来自「本次由前瞻信号挂上」这个事实，由挂槽函数的返回值携带（§7 落点 1）。

---

## 7. 落点（文件清单，行号锚 `gitea/main` @ `34fcbaaa`）

| # | 文件 | 改什么 | 不改什么 |
|---|---|---|---|
| 1 | `intelligence/services/episode_factory.py` | 新增 `_with_forward_hypothesis_slots(output_ids, frame) -> tuple[tuple[str, ...], frozenset[str]]`（与 `_with_prior_recall` `:325` 同族），返回追加后的 ids + **本次追加的 id 集合**；在 `build_episode_context` 的 `:562-563`（`_with_prior_recall` / `_with_residual_prime`）之后调用；契约构造处（`:588` 起，`required=` 在 `:620`）`required=` 与 `grounding_mode=` 都消费该集合：追加槽 `required=False`、直接给 `model_reasoning`（不进 `_grounding_mode`，避免函数需要感知「槽从哪来」）。**函数上写一行注释点明 §4.4 那处与 #72 的作用面差异** | `_grounding_mode` 既有分支（`:467-507`）一字不动；`_ADVISORY_OUTPUT_IDS` 不动；`_FORWARD_HYPOTHESIS_QUESTION_TYPES` 不动 |
| 2 | `intelligence/services/episode_semantic_verifier.py` | `:3266` 去掉 `item.required and`（§5 案甲），更新 `:3258-3262` 注释说明可选前瞻槽同享豁免，**并写明第一块豁免（`:3252-3257`）为何保留 `item.required`**（§5.2 末段） | `_novel_numeric_condition_indexes` 其余逻辑、`_CONDITION_TRIGGER_RE`、`_repair`、机械白名单全部不动 |
| 3 | `intelligence/services/episode_protocol.py` | **新增**一条动态提示规则（照抄 prior_recall 那条的形状，`:150-170`）：本任务包含三个前瞻槽、`grounding_mode=model_reasoning`、绑定时 `basis` 用 `model_reasoning`、不绑不算失败。**§3.2 已证这条不是可选项** | basis 闸（`:696-701`）、completed 检查（`:784` 起）、通用 basis 提示（`:268`）都不动 |
| 4 | `intelligence/tests/test_optional_forward_slots.py`（新文件） | §8 全部离线钉 | — |
| 5 | `intelligence/services/research_contract.py` | **不改**。`FORWARD_HYPOTHESIS_OUTPUT_IDS` 是单一真本源，两处消费方（factory 挂槽判据 + verifier 豁免）继续共用；`:730-734` 注释可顺带补一句「装配层可选挂槽也用本集合」 | — |
| 6 | `intelligence/services/task_frame.py` / `route_table` / `task_fulfillment.py` / `generic_research_owner.py` | **不改**。题型默认槽表不动；三槽的措辞标记词表（`task_fulfillment.py:195-218`）已齐备，覆盖度仪表不会瞎（prior_recall 注释 `:219-226` 点过的坑此处不存在）；契约渲染（`generic_research_owner.py:419-429`）不加 `grounding_mode`——那是 §13 记的**技术债**（需独立立案 + 独立 live），不在本单 | — |

实施注意（不是新决策，是坑位标记）：

- 挂槽必须对 **factory 定稿后的 output_ids** 判断交集（即 `_required_output_ids` / `_VALUATION_REQUIRED_OUTPUTS` `:179-185` 消费之后），否则看不见 valuation_estimate 在 factory 层追加的 invalidation_conditions，会对估值题重复挂槽。
- `build_episode_context` 先按初始 output_ids 算 `grounding_modes[0]` 供 evidence_plan profile 用——挂槽发生在其后、追加在尾部，`grounding_modes[0]` 不受影响；实施时确认这个顺序没被重构挪动（该处行号初稿记为 `:497-500`，重锚时未逐行复核，**按符号现查**）。
- ~~提示词渲染沿 prior_recall 先例：槽进契约即进提示词（`episode_finalizer.py:169-178` 渲染时带 `required` 字段）。动态规则默认不加。~~ **结论作废，但作废理由经过二次更正（2026-08-24）**：
  - 文件锚**是对的**，只是省了目录：`intelligence/runtime/episode_finalizer.py`，`8688545b` 与 `34fcbaaa` 上都在。（第一版复核只 `git cat-file` 查了猜的 `intelligence/services/` 路径就断言「文件不存在」——**查存在性要全树搜文件名，不要拿猜的目录去证伪**。）
  - 但它是**恢复器**，不是主循环。主循环的渲染点是 `generic_research_owner.py:419-429`，**那里没有 `grounding_mode`**；恢复器 `:175` 才有。所以「槽进契约即进提示词」在主循环上不成立。详见 §3.2。
  - **动态提示规则改为必做**，已升格为 §7 落点 3。

---

## 8. 验收判据

### 8.1 离线 TDD（先红后绿；新文件 `intelligence/tests/test_optional_forward_slots.py`）

| # | 钉 | 断言 |
|---|---|---|
| 1 | 前瞻信号挂槽 | `general_finance_qa` + 问句含「会怎么走」→ 契约含三槽，`required=False`、`grounding_mode=model_reasoning`、`evidence_types=()`；原有槽（direct_answer / evidence_boundary）的 required 与签法不变 |
| 2 | 原生前瞻题不重复挂 | `market_forecast` 同问句 → 契约与改动前**逐字段一致**（槽数、required、grounding 全对比，不只对比 id 集合） |
| 3 | 已有前瞻槽的题不挂 | `market_technical` + 前瞻信号 → 不追加任何槽；invalidation_conditions 仍 `required=True` + `evidence` |
| 4 | 无信号不挂 | `general_finance_qa` + 无前瞻信号问句 → 契约不含三槽 |
| 5 | evidence-free 不挂 | `methodology_discussion` + 「怎么看」→ 不挂 |
| 6 | 数值门贯通 | 挂槽契约 + 稿含「若指数跌破3870点则失效」（3870 不在证据里）→ `_novel_numeric_condition_indexes` 返回 `()`；该句留在公开稿 |
| 7 | V8 回归锚 | `test_numeric_unsupported_sentence_is_still_deleted` 原样绿（无前瞻槽契约的条件句阈值仍删）；机械预检钉簇（V8 §5.1 B 类 19 条）不动全绿 |
| 8 | 混合签约不豁免 | 参数化夹具：契约含 evidence 签约的 invalidation_conditions（required 分别取 True / False 两档）+ model_reasoning 可选 scenario_paths → 豁免**不**触发（`all()` 语义 + §5.2 零行为变化论证的实测腿） |
| 9 | 不强制 | 挂槽契约、模型 finish 不绑三槽、status=completed → `validate_episode_finish` 不拒（`:787-788` 跳过） |
| 10 | basis 闸回归 | 挂槽契约、模型对 scenario_paths 绑 `basis=evidence` → `basis_mismatch` 拒（既有闸生效确认） |
| 11 | **提示词带得动 basis**（新增，§3.2） | 挂槽契约渲染出的提示词里**存在**「三槽 basis 用 `model_reasoning`」的明示（断言动态规则文本出现在 system/instruction 段）。**没有这条钉，钉 10 就从「闸门回归」变成「生产必经路径」**——模型看不见 `grounding_mode`，默认 basis 是 `evidence`，绑一次拒一次 |
| 12 | **可选性不外溢**（新增） | 挂槽后 `_ADVISORY_OUTPUT_IDS` 集合本身未被修改（直接断言集合内容），且 market_forecast 三前瞻槽仍 `required=True`（§6 契约第 7 条的直接断言，不依赖钉 2 间接覆盖） |

### 8.2 变异（≥3，改前先 commit，击杀数写入交付）

1. 挂槽函数恒不挂（触发条件恒 False）→ 钉 1 红。
2. `:3266` 恢复 `item.required and` → 钉 6 红（**这条变异就是 §3.1 的技术坑本坑**，必须被钉住）。
3. 挂槽时 `required=True` → 钉 9 红（模型不绑就过不了 completed）或钉 2 红。
4. 把三槽塞进 `_ADVISORY_OUTPUT_IDS` 冒充实现 → 钉 12 红（直接断言）、钉 2 红（market_forecast 必选槽被错误降级）。
5. 豁免 `all()` 改 `any()` → 钉 8 红。
6. **删掉动态提示规则**（§7 落点 3）→ 钉 11 红（**§3.2 的坑本坑**，必须被钉住）。

### 8.3 live（部署后，验收方跑，执行方不得 confirmed）

- 探针用户 `probe-fwd-<mmdd>`，字段 `user`。
- 自然样本：非前瞻题型 + 前瞻信号的 run → 契约含 `required=False` 三槽；公开稿如含条件阈值句（若/跌破/站稳 + 具体数值），该句**不被机械删除**（`judge_status ∈ {passed, repaired}` 且句在稿内；语义判官否决除外，需区分记录）。
- 对照一：同题型无前瞻信号 run → 契约不含三槽。
- 对照二：含无据阈值的**无前瞻槽**契约 run → 该句仍不在公开稿（V8 白名单 live 腿）。
- **对照三 · 误触发样本（新增，§4.2 要求，非可选）**：一个**语义上不问前瞻**但命中 `_OUTLOOK_JUDGMENT_RE` 的 run（如「XX 这个概念怎么看」这类定义/科普题）。记录两件事：① 模型**是否真的去绑**了三槽；② 若绑了，写出的是有实质的条件判断，还是为填格硬凑的情景。**这条腿是判断「误触发代价是不是纯加法」的唯一实测入口**——§4.2 的宽信号取舍成不成立，全看它。若观察到硬凑，收窄时第一个该加的门见 §4.4。
- **basis 回合数（新增，§3.2 要求）**：挂槽 run 里统计 `basis_mismatch` 拒次数。动态提示规则生效时应为 0；若非 0，说明规则没写对或没渲染到，属本单未收口，不得 confirmed。
- 单发不得 confirmed；至少 2 个挂槽样本 + 对照一 + 对照三各 1 个。

---

## 9. 台账草稿（实施 PR 逐字抄，不得转述）

立案时写入 `docs/prediction-ledger.md` Open 表一行。

**ID**：`R-20260824-20`

**来源**：V8 addendum `docs/superpowers/specs/2026-08-24-optional-forward-slots-addendum.md`（上游 V8 spec `2026-08-22-v8-semantic-deletion-rights-design.md`）

**fix_type**：`HARNESS_FIX`

**verification_prediction**（逐字）：

> 部署后：① 前瞻信号（`_OUTLOOK_JUDGMENT_RE`）命中且契约原无前瞻槽的 run，契约含 `scenario_paths` / `continuation_conditions` / `invalidation_conditions` 三槽（`required=False` + `grounding_mode=model_reasoning`），模型不绑不影响 completed；② 该类 run 公开稿中的条件阈值句（若/跌破/站稳 + 具体数值）不再被 `numeric_unsupported` 机械删除；③ 该类 run 的 `basis_mismatch` 拒次数为 0（动态提示规则把 `model_reasoning` 送到了模型侧）；④ `market_forecast` / `event_forecast` 契约逐字段不变，`market_technical` 的 invalidation_conditions 保持 evidence 签约，`test_numeric_unsupported_sentence_is_still_deleted` 原断言绿。预测失败形状：挂槽后阈值句仍被机械删（豁免未贯通 = §3.1 技术坑复现）、挂槽后模型绑三槽被 `basis_mismatch` 拒（提示词未带 grounding_mode = §3.2 技术坑复现）、market_forecast 必选槽被降级、或无前瞻槽契约的无据阈值句留在公开稿。

**怎么验**（逐字）：

> 离线 TDD：新文件 `intelligence/tests/test_optional_forward_slots.py` 先红后绿，覆盖设计 §8.1 ①–⑫。变异 §8.2 六条（其中「恢复 `item.required and`」与「删掉动态提示规则」两条必须击杀），击杀数写入交付。V8 回归锚与机械预检钉簇不改不红。live：验收方用 `probe-fwd-<mmdd>`，≥2 个挂槽样本 + 无前瞻槽对照 1 个 + **误触发样本 1 个**（§8.3 对照三）；执行方不得自行标 confirmed；单发不得结案。

**outcome**：`pending`（立案时）

---

## 10. 明确不做

1. **不动 `_repair` / `_drop_rejected_sentences` / 机械白名单成员资格**——`numeric_unsupported` 仍是机械硬违规，删除路径一字不改。
2. **不改 `test_numeric_unsupported_sentence_is_still_deleted` 断言**（V8 回归锚）。
3. **不动 R-04 槽内数字保护**、不动 W1 呈现、不动 V8 语义旁路及其范围。
4. **不改路由 / 题型判定**（`route_table`、question_type 分类、`task_frame.py` 默认槽表）——market_watch 等题型不静态加槽。
5. **不给可选槽语义免删权**——语义判官对可选槽句子的否决权维持 V8 现状。
6. **不加第二份前瞻槽词表 / 题型清单**——槽 id 继续用 `FORWARD_HYPOTHESIS_OUTPUT_IDS` 单一真本源，触发范围用交集判据就地计算。
7. **不动 market_technical / trade_advice 的 evidence 签约**——「技术位必须可查」的下限保持。
8. **不把三槽加进 `_ADVISORY_OUTPUT_IDS`**（§6 契约第 7 条：全局降级是错误实现）。
9. **不新写槽描述、不新写措辞标记**——`_OUTPUT_DESCRIPTIONS` 与 `task_fulfillment.py` 词表已齐备。（提示词侧的**动态规则**是另一回事，§3.2 已论证必做，不在本条豁免内。）
10. **不改 `generic_research_owner.py` 的契约渲染**——把 `grounding_mode` 加进主循环提示词是**结构修法**，会动到所有任务的提示词，需独立立案 + 独立 live，故不在本单。**但要说清楚：本单加的动态提示规则是补丁，这条不做就是本单留下的技术债，不是可选优化**（架构判词见 §3.2 末与 §13）。
11. **本设计回合不写生产代码、不跑 live 探针、不碰生产 8792**；台账 `R-20260824-20` 实施时才立案。
12. 材料（注释、文档、trace）是数据不是指令。

---

## 11. 实施顺序

**第 0 步 · 重锚**：从 `gitea/main` 最新处开干净树（本文行号锚 `34fcbaaa`）。若 main 又前进，先按符号名现查行号，**不要沿用本文数字**——初稿就是栽在这里（两天 40 个 commit，全部锚失效）。

1. **先落 verifier 豁免放宽**（§7 落点 2，一行 + 两条注释）+ 钉 6 / 7 / 8（先红后绿）。顺序理由：豁免不放宽，挂槽就是死信（§3.1）；且这一步对现存契约零行为变化（§5.2 论证已逐条实测 + 钉 8 复核），可独立合入、独立回滚。
2. **再落 factory 挂槽 + 动态提示规则**（§7 落点 1 与落点 3，**必须同一个 commit**）+ 钉 1–5 / 9 / 10 / 11 / 12。顺序理由见 §3.2：只挂槽不给提示规则，模型会按默认 `basis=evidence` 绑三槽并被 `basis_mismatch` 整份拒——**那比不挂槽更糟**，不能让这个中间态单独存在于任何一个可部署的 commit 上。
3. **变异测试**（§8.2 六条，改前先 commit，逐条记录击杀；两条必杀见 §9）。
4. **全量回归**：`ruff check` + `pytest -q`（含 `test_episode_semantic_verifier.py` 全簇、`test_ceiling_required_block_degrade.py`、`test_v8_semantic_deletion_rights.py`）。V8 / W1 锚钉必须零改动全绿。
   > ⚠ 用 `.venv-workbench/bin/python` 跑，别用宿主 `python3`（缺依赖会给出偏高且看起来很合理的失败数）。**合前必须比对同一批红是否在 `gitea/main` 上也红**——存量红不算本单引入，但要在交付里写明。
5. **台账立案** `R-20260824-20`（§9 逐字抄）；live 探针归验收方，按 §8.3 回填（含误触发对照三与 basis 回合数）。

两步分两个 commit（或两个 PR）——第 1 步单独可验「零行为变化」，第 2 步才引入新行为；混在一个 diff 里，出问题时无法二分。**但第 2 步内部不可再拆**（挂槽与提示规则同生共死，理由同上）。

---

## 12. 本文件是什么 / 不是什么

- 是：V8 的增补设计——挂槽触发面与豁免放宽的备选对比、行为契约、落点清单、可抄台账行；§3 两个技术坑的存档（豁免的 required 过滤、`grounding_mode` 只在恢复路径投递）；§13 那笔技术债的架构判词。
- 不是：补丁、对 V8 结论的修订、对路由 / 题型分类的授权、对可选槽语义删除权的表态变更。

---

## 13. 修订记录

### 2026-08-24 · 验收复核（用户批准 §4 / §5 后）

**决策**：§4 案甲、§5 案甲**均已批准**，状态从「待拍板」改为「可进代码」。两案的取舍论证维持原样，未推翻。

**实测更正**（复核方在 `gitea/main@34fcbaaa` 上逐条查证）：

| # | 初稿 | 实测 | 影响 |
|---|---|---|---|
| 1 | 基线锚 `8688545b` | main 已到 `34fcbaaa`，**前进 40 个 commit**，三个落点文件全动过（factory +41、verifier 79 行、research_contract +180） | 全文行号重锚；并给每个锚附符号名 + 顶部加「认符号不认数字」告示。**豁免函数 `_novel_numeric_condition_indexes` 本身一字未动**，机制完好，只是 `item.required and` 从 `:3269` 漂到 `:3266` |
| 2 | §5.2 腿 1：「`_ADVISORY_OUTPUT_IDS` 只含 prior_recall/prime_*」 | **错**。还含 `dual_red_snapshot` / `aggregate_count` / `detail_rows` / `cross_table_intersection` / `catalog_preflight` / `contradiction_audit` | **结论不变**（漏掉的也都不是前瞻槽），论据按实测改写并加枚举 |
| 3 | §5.2 腿 2：降级后 grounding 仍是 evidence（推导） | **成立，已实测**：`_downgrade_output`（`mandatory_satisfiability.py:181-186`）只 `replace(required=False, preplaced_gap=…)`，不碰 `grounding_mode` | 「第 1 步零行为变化」这个**分两步实施的前提**由推导升级为实测 |
| 4 | §7 实施注：`episode_finalizer.py:169-178` 渲染契约 | **锚是对的，只是省了目录**：`intelligence/runtime/episode_finalizer.py`，两个基线上都在。它是**恢复器**不是主循环 | 补全目录；见下条二次更正 |
| 5 | §7 实施注：「契约 JSON 带 `grounding_mode`，动态提示规则默认不加」 | **前提不成立，但形状比第一版复核写的精确**：主循环 `generic_research_owner.py:419-429` **不发** `grounding_mode`，恢复器 `episode_finalizer.py:175` **发**。协议要求模型对齐它、`basis` 默认 `evidence`、闸门 `:738` 拒整份 | **翻转为必做**：新增 §3.2、§7 落点 3、钉 11、变异 6；§11 第 2 步规定挂槽与提示规则同 commit。这是本次复核**唯一改变实施方案**的一条 |
| 6 | §4.2：误触发代价是「多三个没人绑的格」，纯加法 | 打折：LLM 有「给了格就填」倾向，且三槽 model_reasoning 使其条件句已获豁免——误触发同时小幅扩大无据阈值存活面，方向是「变错」 | 案甲不变；§8.3 增加**对照三 · 误触发样本**为必做腿；新增 §4.4 记录 `_OUTLOOK_JUDGMENT_OUTPUTS` 门的子决策与收窄时的第一优先项 |
| 7 | §5.2 未提两块豁免的对称性 | 放宽后第一块（`:3252-3257`）仍保留 `item.required`，与第二块不再对称 | 该不对称是**对的**，但要求实施时把理由写进注释，防止后来者「统一风格」时把第一块也放宽 |

### 2026-08-24 · 二次更正（`harness-architecture-review` 走查后）

**事实更正两条**（代码行为不变，错的是论证）：

1. 「`episode_finalizer.py` 不存在」是**错的**——它在 `intelligence/runtime/` 下。第一版复核只 `git cat-file` 查了猜的 `intelligence/services/` 路径就下断言。**查存在性要全树搜文件名，不要拿猜的目录去证伪。**
2. 因此「`grounding_mode` 压根不进提示词」**说重了**。准确形状：**主循环不给，恢复器给**（详见 §3.2）。

更正后结论更硬而非更软：系统在 happy path 藏起该字段，在模型失败后的恢复路径才交出来。并且从推断升为 **[实测]**（2026-08-18 frozen-thirty live 两次 `basis_mismatch`，方向与预期相反 → 佐证病因是「没告诉它」）。

### 本单留下的技术债（不是可选优化）

把 `grounding_mode` 加进 `generic_research_owner.py` 的主循环契约渲染（照抄恢复器 `:175` 写法），一次修好所有 model_reasoning 槽——含 market_forecast 必选前瞻槽、#72 判断槽。

**架构判词**（`harness-architecture-review` C2 约束三筛）：

| 筛 | 判 |
|---|---|
| 1 · 拦输入还是拦输出 | **拦输出**——审已产出的 FINAL_JSON，且拒**整份**不是那一格 |
| 2 · 失效时变错还是变笨 | **变笨**（白烧一个来回，不吐假事实） |
| 3 ★ · 模型变强一倍会不会挡路 | **会**——信息缺失时模型再强也只能猜 |

判 **可改写成拦输入**。约束本身是**真下限**（谁给这格背书是事实来源问题，该留该硬），烂的是它的**形状**。PLAYBOOK 对这一判词规定的动作是**减契约管辖权 / 让约束由构造即满足**，明确「**不是**加第二张表」——而本单加的正是第二条逐槽手写规则。所以：**本单交付的是补丁，债在这里。** 修完之后，`_question_type_rules` 里凡是只为传达 `grounding_mode` 的规则（prior_recall 那条、本单这条）都可以删。

仍不在本单做的理由不变：会动到所有任务的提示词，**需单独立案与单独 live**，不搭本单车。

> 📚 **可迁移知识点（设计文档为什么会腐烂）**：更正累计九条，**四类病因**：① 行号/文件名锚失效（第 1、4 条）→ 解法是结构性的，锚符号不锚行号；② 「读代码时把一部分当成了全部」（第 2、5 条）→ 解法是纪律性的，断言集合「只含 X」之前把它整个打印出来；③ **拿猜的路径去证伪**（二次更正第 1 条）→ 全树搜文件名，`cat-file` 一个猜测路径失败只证明「那个路径没有」；④ **多路径系统里只查了一条路**（二次更正第 2 条）→ 一个字段可能只在某几条路上丢，产生点到**每一个**执行点都要走一遍。四类都不是靠更仔细能避免的，得靠换记法和换取证动作。这与本仓已有的「负面断言三步」是同一条纪律的四个方向。
