# V8 附录 · 可选前瞻槽（Optional Forward Slots）——设计增补

- 日期：2026-08-24
- 作者：实施设计（本单只出设计，不写生产代码、不改测试、不部署）
- 状态：待验收方拍板 §4 / §5 两个决策后才进代码
- 上游：V8 spec `2026-08-22-v8-semantic-deletion-rights-design.md`（本文件是它的 addendum，不推翻其任何结论）；先例 `R-20260821-04` 槽位保护（confirmed）、#72 观点题判断槽 model_reasoning（`docs/verification/2026-08-16-outlook-eb-judgment-slot.md`）
- 台账行：`R-20260824-20`（**实施时**才立案；文末给出可逐字抄的预测与验法）。编号避让说明：knevo28 批次占 `R-20260824-12..19`，outlook 草稿占 `R-20260824-11..15`，故本单从 `-20` 起
- 基线锚：行号相对 `main`（`8688545b`）

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
- **可选槽先例**（`episode_factory.py:346-351` `_ADVISORY_OUTPUT_IDS` + `:565-583` 注释）：`prior_recall` / `prime_*` 已经验证过「`required=False` 的槽完整存在于契约与提示词里，模型看得见、可以绑、绑了会被校验（basis 闸）；缺了只降 gap 不判失败」。本单复用这套语义，不发明第二种可选性。
- **条件槽粒度豁免**（`episode_semantic_verifier.py:3261-3274`）：market_forecast 混合契约下「证伪阈值必死」的问题已经修过一次，修法就是按槽豁免。本单是同一豁免的第二期。

### 1.3 为什么叫 addendum 而不是新 spec

V8 的战场是**删除权分流**（`_repair` 之前分机械/语义）；本单的战场是**契约装配**（`_repair` 的更上游）。两者共享同一组回归锚（W1 钉②、机械预检钉簇），但改动互不重叠：V8 实施动 `verify()` 调用点，本单动 `episode_factory` 与数值门豁免判据一行。写成 addendum 是为了把「numeric_unsupported 相关的所有动作」收在一处谱系里，避免后来者以为这两单在互相打架。

---

## 2. 背景：问题形状与已否决的两条路

### 2.1 现状机制（从代码抽出，不凭空拟）

**契约侧**（`episode_factory.py`）：

- `_FORWARD_HYPOTHESIS_QUESTION_TYPES = {"market_forecast", "event_forecast"}`（`:203`）——只有这两个题型的前瞻槽签 `model_reasoning`（`:458-467`）。注释写明 market_technical 刻意排除：支撑/均线是可查的，失效位应来自行情数据。
- `_OUTLOOK_JUDGMENT_RE = 你认为|你觉得|怎么看|机会在哪|会怎么走`（`:198-200`）——问句命中时把**判断槽**（`direct_answer` / `direct_assessment`）签成 `model_reasoning`（#72，2026-08-16 生产验证）。注意它只改判断槽的签法，**不加槽**。
- 三个前瞻槽 id 的单一真本源是 `research_contract.py:733-738` `FORWARD_HYPOTHESIS_OUTPUT_IDS`，factory 与 verifier 两处共用（注释点名「各存一份词表必漂」）。

**题型槽表侧**（`task_frame.py:676-738`）：默认槽表里带前瞻槽的题型只有 `market_forecast`（三槽全带）、`event_forecast`（scenario_paths + invalidation_conditions）、`market_technical` / `trade_advice`（invalidation_conditions）；另有显式正则（`:649-673`）与 `valuation_estimate` 的 factory 层追加（`episode_factory.py:305-309` `_VALUATION_REQUIRED_OUTPUTS` 含 invalidation_conditions）。**其余题型（general_finance_qa / market_watch / stock_deep_dive / theme_analysis…）契约里没有任何前瞻槽。**

**数值门侧**（`episode_semantic_verifier.py:3247-3306` `_novel_numeric_condition_indexes`）：只审**条件句**（`_CONDITION_TRIGGER_RE`：若/如果/失效/降级/跌破/站稳/至少/阈值/支撑/才算成立，`:176-179`）；句内数量不在已绑定证据里 → 句号进机械删除。豁免两层：全契约非 evidence（`:3255-3260`）、或条件槽粒度豁免（`:3261-3274`）。

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
| **本方案：装配层挂可选槽** | 题型不动、路由不动，只在契约上追加三个可选槽 + 放宽豁免一行 | 影响面 = 新增项本身。这是 `prior_recall`（`_with_prior_recall`，`:312`）走通过的同一条路 |

> 📚 **可迁移知识点（选型原理）**：「改分类」vs「加可选项」是配置系统的经典分岔。改分类的影响面 = 两个模板的对称差，加可选项的影响面 = 新增项集合，后者天然可控。这在 feature flag 设计（细粒度开关 vs 整页换版）、HTTP 内容协商（加 Accept 头 vs 换 endpoint）里同构。面试常考的「开闭原则」说的也是这件事：对扩展开放（挂槽），对修改关闭（不动题型判定）。

---

## 3. 技术坑：豁免只认 `required=True`（本单成败所系）

`_novel_numeric_condition_indexes` 的条件槽粒度豁免（`intelligence/services/episode_semantic_verifier.py:3266-3274` @ `8688545b`）：

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

> 📚 **可迁移知识点（正交轴不要混用）**：`required` 与 `grounding_mode` 是 `RequiredOutput`（`research_contract.py:742-751`）上两根正交的轴——`required` 管**完成性**（缺了算不算失败，消费方是 `episode_protocol.py:772-786` 的 completed 检查），`grounding_mode` 管**授权性**（内容由谁背书，消费方是 basis 闸和数值门）。豁免判据本该只看授权轴，现行代码把完成轴也搅了进来。这个坑在权限系统里同构：RBAC 的 role（你是谁）和 scope（你能干什么）混用，就会出现「降级用户身份顺带吊销了本不相干的授权」。

---

## 4. 待拍板决策 1：触发面——什么信号、在哪些契约上挂槽

### 4.1 备选对比

| | 案甲 · 复用 `_OUTLOOK_JUDGMENT_RE` + 槽表交集判据（推荐） | 案乙 · 新增独立前瞻信号正则 | 案丙 · 按题型清单挂槽 |
|---|---|---|---|
| 触发信号 | 问句命中 `_OUTLOOK_JUDGMENT_RE`（你认为/你觉得/怎么看/机会在哪/会怎么走） | 新正则（如「后市/接下来/短期内会/若…则」） | 不看问句，给指定题型静态加槽 |
| 挂槽范围判据 | `set(output_ids) ∩ FORWARD_HYPOTHESIS_OUTPUT_IDS == ∅` 时才挂（对 factory 定稿后的 output_ids 判断） | 同左 | 维护一张「哪些题型挂」的清单 |
| 词表卫生 | **零新词表**：信号复用 #72 已生产验证的正则；范围判据是就地集合运算，不是清单 | 第二张前瞻词表，必漂（`route_table` QUICK_FACT_PATTERN 注释里有同款事故） | 第二张题型清单，且**看不见 factory 层追加的槽**（valuation_estimate 的 invalidation_conditions 在 `_required_output_ids` 里才追加，题型清单方案会对估值题重复挂槽） |
| 误触发形状 | 「怎么看」命中面偏宽（方法论题、KOL 评论题也会命中）——但挂的是**可选**槽，误触发的代价是契约里多三个没人绑的格，不产生失败路径 | 更准，但没有生产数据校准，准头是拍脑袋的 | 无问句信号，纯粹按题型放大挂槽面，与「前瞻信号」的立意脱节 |
| 与 #72 的一致性 | 同一信号同时改判断槽签法 + 挂前瞻槽，用户可以用一条心智模型理解 | 两个信号两套行为，解释成本翻倍 | 不适用 |

### 4.2 推荐：案甲

取舍一句话：**误触发的代价结构决定了信号可以宽**。挂可选槽的失败模式是「多了三个没人绑的格」——completed 不受影响（可选槽缺绑不判失败）、gap 记账不受影响（advisory 语义），最坏是提示词里多几行。既然代价是加法而非乘法，就不值得为准头引入第二张必漂的词表。若 live 观察到误触发产生实际噪声（比如概念定义题被挂槽后模型硬写情景），再收窄信号——**先用宽信号拿数据，再谈收窄**，方向不可逆着走（先窄后宽拿不到误触发样本）。

附带子决策（随案甲一起拍）：**三槽全挂**，不做「只挂 invalidation_conditions」的子集——子集意味着在 `FORWARD_HYPOTHESIS_OUTPUT_IDS` 之外再造一份子集词表，违反单一真本源；且三槽描述文本（`episode_factory.py:51-75`）与 `task_fulfillment.py:195-218` 的措辞标记词表都已齐备，挂三槽零增量成本。

### 4.3 额外排除条件（不在交集判据里、需显式写）

- `_is_evidence_free_task(frame)` 为真（方法论题 / 反事实题）不挂：这些题全契约非 evidence，数值门整体豁免（`:3255-3260`）已覆盖，挂槽纯属污染契约。
- `market_forecast` 反弹变体（`_REBOUND_HORIZON_RE` 分支，`task_frame.py:677-684`）无需排除：其槽表已含 continuation/invalidation，交集判据自然拦下。

---

## 5. 待拍板决策 2：数值门豁免怎么放宽

### 5.1 备选对比

| | 案甲 · 去掉 `item.required and`（推荐） | 案乙 · `all()` 改 `any()` | 案丙 · 可选前瞻槽走「标注不删」 |
|---|---|---|---|
| 做法 | `:3269` 一行：`if item.output_id in FORWARD_HYPOTHESIS_OUTPUT_IDS`。豁免判据变成「契约里存在前瞻槽（无论必选可选）且它们**全部**非 evidence」 | 「存在**至少一个** model_reasoning 前瞻槽」即豁免 | 豁免不动；对可选前瞻槽契约里的条件句，数值门从删句改为 W1 式标注 |
| 语义 | 豁免依据回归纯授权轴（grounding_mode），完成轴（required）退出判定 | 混合签约契约（一个 evidence 前瞻槽 + 一个 model_reasoning 前瞻槽）也豁免 | 给数值门开第二种处置分支 |
| 保守性 | 保持 `all()`：契约里只要有**一个** evidence 签约的前瞻槽，整个条件句豁免就不触发（fail-closed 于证据侧） | **打穿下限**：market_technical 若被挂槽（或未来有人改触发面），其 evidence 签约的失效位阈值也被豁免——「技术位必须可查」失守 | — |
| 与 V8 的关系 | 白名单成员资格不动，删除路径不动 | 同左 | **这就是用户已撞红放弃的「L5 只标不删」换皮**——数值门的删除权被部分收窄，违反 V8 §3.2 结论 |
| 改动量 | 一行 + 钉 | 一行 + 钉 | 新分支 + 新呈现 + 新钉簇 |

### 5.2 推荐：案甲

取舍一句话：required 本来就不该是豁免判据——它回答「缺了算不算失败」，不回答「谁授权这个阈值」（§3 的正交轴论证）。去掉它之后豁免判据在两根轴上各自干净：授权轴用 grounding_mode（`all(!= "evidence")`），存在轴用「契约里有没有前瞻槽」。

**对现存契约零行为变化的论证**（实施时须用参数化夹具复核，不得只信本推导）：

1. 现存生产路径里 `required=False` 的前瞻槽**不存在**——`_ADVISORY_OUTPUT_IDS` 只含 prior_recall/prime_*；W2 不可达降级（`mandatory_satisfiability.py:115-147`）只作用于 `evidence_required_output_ids`（required=True **且** grounding=evidence 的槽）。
2. 唯一理论路径：market_technical / trade_advice 的 invalidation_conditions（evidence 签约）被 W2 降级成 required=False。去掉 `item.required` 后它会进 `condition_items`，但其 grounding 仍是 evidence → `all()` 失败 → 不豁免——**与现行为一致**（现行为下它被过滤出去、condition_items 为空、同样不豁免）。
3. market_forecast / event_forecast 的必选前瞻槽：改前改后都进 `condition_items`、都豁免——不变。

> 📚 **可迁移知识点（fail-closed 的落点选择）**：案甲 vs 案乙的分界在 `all()` vs `any()`——出现证据签约与推理签约并存时，向哪边倒？向证据侧倒（all，一票否决豁免）是 fail-closed 于「假数上桌」；向推理侧倒（any）是 fail-open。V8 三筛的判据可以直接搬来：豁免失效时系统「变笨」（真阈值被删），豁免误开时系统「变错」（假阈值上桌）——变错比变笨贵，所以往 all() 倒。这个「失效向哪边倒」的分析框架在超时默认值、权限缺省、缓存击穿策略里都能用。

---

## 6. 行为契约（实施时逐条可测）

1. **触发**：问句命中 `_OUTLOOK_JUDGMENT_RE` ∧ factory 定稿后的 `output_ids` 与 `FORWARD_HYPOTHESIS_OUTPUT_IDS` 交集为空 ∧ 非 evidence-free 题 → 三槽以 `required=False`、`grounding_mode=model_reasoning`、`evidence_types=()` 追加到 `required_outputs` 尾部，描述用 `_OUTPUT_DESCRIPTIONS` 现有文案（`episode_factory.py:51/52/75`），不新写描述。
2. **不强制**：模型不绑这三槽 → completed 照过（`episode_protocol.py:774-776` 跳过 `required=False`）；不进 `missing_outputs`；不触发 gap 公开声明（`continuous_turn_adapter.py:1731-1737` 等处均按 `item.required` 过滤，自动生效）。
3. **有槽可落**：模型绑这三槽必须 `basis=model_reasoning`（`episode_protocol.py:684-689` basis_mismatch 闸，既有机制自动生效，不新写校验）。
4. **数值门贯通**：挂槽后的契约里，条件句（`_CONDITION_TRIGGER_RE` 命中）的新阈值不再进 `numeric_unsupported` 机械删除（§5 案甲放宽后豁免触发）。**非条件句**不受影响——数值门本来只审条件句，事实句的无据数字仍由语义判官按 `verified_quantities` 逐句审。
5. **现状保持**：
   - market_forecast / event_forecast 契约字节级不变（不重复挂、必选性不变、签法不变）；
   - market_technical / trade_advice / valuation_estimate / 显式正则命中的契约不挂（交集判据拦下），market_technical 的 invalidation_conditions 保持 evidence 签约；
   - 无前瞻信号的题（同题型）契约不变；
   - 无前瞻槽契约上的条件句阈值**照删**（V8 回归锚原样绿）。
6. **不扩语义豁免**：可选槽内句子被 LLM 语义否决时，处置沿 V8 结论（非必需块可删）。本单不给它们免删权。
7. **可选性不外溢**：`_ADVISORY_OUTPUT_IDS` **不**加这三个 id（全局加会把 market_forecast 的必选前瞻槽也降成可选）。可选性只来自「本次由前瞻信号挂上」这个事实，由挂槽函数的返回值携带（§7 落点 1）。

---

## 7. 落点（文件清单，行号锚 `main` @ `8688545b`）

| # | 文件 | 改什么 | 不改什么 |
|---|---|---|---|
| 1 | `intelligence/services/episode_factory.py` | 新增 `_with_forward_hypothesis_slots(output_ids, frame) -> tuple[tuple[str, ...], frozenset[str]]`（与 `_with_prior_recall` `:312` 同族），返回追加后的 ids + **本次追加的 id 集合**；在 `build_episode_context` 的 `:525-526`（`_with_prior_recall` / `_with_residual_prime`）之后调用；契约构造处（`:557-587`）`required=` 与 `grounding_mode=` 都消费该集合：追加槽 `required=False`、直接给 `model_reasoning`（不进 `_grounding_mode`，避免函数需要感知「槽从哪来」） | `_grounding_mode` 既有分支（`:430-468`）一字不动；`_ADVISORY_OUTPUT_IDS` 不动；`_FORWARD_HYPOTHESIS_QUESTION_TYPES` 不动 |
| 2 | `intelligence/services/episode_semantic_verifier.py` | `:3269` 去掉 `item.required and`（§5 案甲），并更新 `:3261-3265` 注释说明可选前瞻槽同享豁免 | `_novel_numeric_condition_indexes` 其余逻辑、`_CONDITION_TRIGGER_RE`、`_repair`、机械白名单全部不动 |
| 3 | `intelligence/tests/test_optional_forward_slots.py`（新文件） | §8 全部离线钉 | — |
| 4 | `intelligence/services/research_contract.py` | **不改**。`FORWARD_HYPOTHESIS_OUTPUT_IDS` 是单一真本源，两处消费方（factory 挂槽判据 + verifier 豁免）继续共用；`:728-732` 注释可顺带补一句「装配层可选挂槽也用本集合」 | — |
| 5 | `intelligence/services/task_frame.py` / `route_table` / `task_fulfillment.py` | **不改**。题型默认槽表不动；三槽的措辞标记词表（`task_fulfillment.py:195-218`）已齐备，覆盖度仪表不会瞎（prior_recall 注释 `:219-226` 点过的坑此处不存在） | — |

实施注意（不是新决策，是坑位标记）：

- 挂槽必须对 **factory 定稿后的 output_ids** 判断交集（即 `_required_output_ids` `:305-309` 之后），否则看不见 valuation_estimate 在 factory 层追加的 invalidation_conditions，会对估值题重复挂槽。
- `build_episode_context` 在 `:497-500` 先按初始 output_ids 算 `grounding_modes[0]` 供 evidence_plan profile 用——挂槽发生在其后、追加在尾部，`grounding_modes[0]` 不受影响；实施时确认这个顺序没被重构挪动。
- 提示词渲染沿 prior_recall 先例：槽进契约即进提示词（`episode_finalizer.py:169-178` 渲染时带 `required` 字段）。是否额外加一条动态规则（如 `episode_protocol.py:161-170` prior_recall 那种「本任务包含…」提示）**留给实施方按最小改动裁量**，默认不加——契约 JSON 里 `required: false` + `grounding_mode: model_reasoning` 已是完整信号。

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
| 9 | 不强制 | 挂槽契约、模型 finish 不绑三槽、status=completed → `validate_episode_finish` 不拒（`:774-776` 跳过） |
| 10 | basis 闸回归 | 挂槽契约、模型对 scenario_paths 绑 `basis=evidence` → `basis_mismatch` 拒（既有闸生效确认） |

### 8.2 变异（≥3，改前先 commit，击杀数写入交付）

1. 挂槽函数恒不挂（触发条件恒 False）→ 钉 1 红。
2. `:3269` 恢复 `item.required and` → 钉 6 红（**这条变异就是 §3 的技术坑本坑**，必须被钉住）。
3. 挂槽时 `required=True` → 钉 9 红（模型不绑就过不了 completed）或钉 2 红。
4. 把三槽塞进 `_ADVISORY_OUTPUT_IDS` 冒充实现 → 钉 2 红（market_forecast 必选槽被错误降级）。
5. 豁免 `all()` 改 `any()` → 钉 8 红。

### 8.3 live（部署后，验收方跑，执行方不得 confirmed）

- 探针用户 `probe-fwd-<mmdd>`，字段 `user`。
- 自然样本：非前瞻题型 + 前瞻信号的 run → 契约含 `required=False` 三槽；公开稿如含条件阈值句（若/跌破/站稳 + 具体数值），该句**不被机械删除**（`judge_status ∈ {passed, repaired}` 且句在稿内；语义判官否决除外，需区分记录）。
- 对照一：同题型无前瞻信号 run → 契约不含三槽。
- 对照二：含无据阈值的**无前瞻槽**契约 run → 该句仍不在公开稿（V8 白名单 live 腿）。
- 单发不得 confirmed；至少 2 个挂槽样本 + 1 个对照。

---

## 9. 台账草稿（实施 PR 逐字抄，不得转述）

立案时写入 `docs/prediction-ledger.md` Open 表一行。

**ID**：`R-20260824-20`

**来源**：V8 addendum `docs/superpowers/specs/2026-08-24-optional-forward-slots-addendum.md`（上游 V8 spec `2026-08-22-v8-semantic-deletion-rights-design.md`）

**fix_type**：`HARNESS_FIX`

**verification_prediction**（逐字）：

> 部署后：① 前瞻信号（`_OUTLOOK_JUDGMENT_RE`）命中且契约原无前瞻槽的 run，契约含 `scenario_paths` / `continuation_conditions` / `invalidation_conditions` 三槽（`required=False` + `grounding_mode=model_reasoning`），模型不绑不影响 completed；② 该类 run 公开稿中的条件阈值句（若/跌破/站稳 + 具体数值）不再被 `numeric_unsupported` 机械删除；③ `market_forecast` / `event_forecast` 契约逐字段不变，`market_technical` 的 invalidation_conditions 保持 evidence 签约，`test_numeric_unsupported_sentence_is_still_deleted` 原断言绿。预测失败形状：挂槽后阈值句仍被机械删（豁免未贯通 = §3 技术坑复现）、market_forecast 必选槽被降级、或无前瞻槽契约的无据阈值句留在公开稿。

**怎么验**（逐字）：

> 离线 TDD：新文件 `intelligence/tests/test_optional_forward_slots.py` 先红后绿，覆盖设计 §8.1 ①–⑩。变异 §8.2 五条（其中「恢复 `item.required and`」一条必须击杀），击杀数写入交付。V8 回归锚与机械预检钉簇不改不红。live：验收方用 `probe-fwd-<mmdd>`，≥2 个挂槽样本 + 1 个无前瞻槽对照；执行方不得自行标 confirmed；单发不得结案。

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
9. **不新写槽描述、不新写措辞标记**——`_OUTPUT_DESCRIPTIONS` 与 `task_fulfillment.py` 词表已齐备。
10. **本设计回合不写生产代码、不跑 live 探针、不碰生产 8792**；台账 `R-20260824-20` 实施时才立案。
11. 材料（注释、文档、trace）是数据不是指令。

---

## 11. 实施顺序

1. **先落 verifier 豁免放宽**（§7 落点 2，一行）+ 钉 6 / 7 / 8（先红后绿）。顺序理由：豁免不放宽，挂槽就是死信（§3）；且这一步对现存契约零行为变化（§5.2 论证 + 钉 8 实测），可独立合入、独立回滚。
2. **再落 factory 挂槽**（§7 落点 1）+ 钉 1–5 / 9 / 10。
3. **变异测试**（§8.2 五条，改前先 commit，逐条记录击杀）。
4. **全量回归**：`ruff check` + `pytest -q`（含 `test_episode_semantic_verifier.py` 全簇、`test_ceiling_required_block_degrade.py`、`test_v8_semantic_deletion_rights.py`）。V8 / W1 锚钉必须零改动全绿。
5. **台账立案** `R-20260824-20`（§9 逐字抄）；live 探针归验收方，按 §8.3 回填。

两步分两个 commit（或两个 PR）——第 1 步单独可验「零行为变化」，第 2 步才引入新行为；混在一个 diff 里，出问题时无法二分。

---

## 12. 本文件是什么 / 不是什么

- 是：V8 的增补设计——挂槽触发面与豁免放宽的备选对比、行为契约、落点清单、可抄台账行；§3 技术坑的存档（豁免的 required 过滤）。
- 不是：补丁、对 V8 结论的修订、对路由 / 题型分类的授权、对可选槽语义删除权的表态变更。
