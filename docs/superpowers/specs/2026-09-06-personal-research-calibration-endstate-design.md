# 个人研究校准系统终局设计

> 日期：2026-09-06  
> 状态：设计稿，作为 BP v0.9 的终局与路线依据；实现前仍需按验收项拆分工单。  
> 适用范围：个人投资者研究与学习产品，不构成投资建议、交易策略或自动下单系统。
>
> 关系：本文件承接 `2026-09-05-time-river-endstate-design.md` 的已审终局决策，作为当前面向实现的统一 spec；旧文档保留为原始决策记录，缺口顺序继续参考 `2026-09-05-time-river-gap-roadmap.md`。
>
> 2026-09-06 第二轮审阅（决策记录见 09-05 spec §14；用户拍板：「日内」= 单日切片、推演 = 多步情景树、区间与上下文投影契约入 spec）已并入 §2.3、§3.3、§4.1、§4.2、§4.4、§4.5、§5.4、§7、§8.1、§10、§12、§13。新增缺口 G-02c / G-14 / G-15 / G-16 见 roadmap §2.5。

## 0. 一句话

产品终局是一条可计算、可回溯、可验证的「时间记忆长河」：用户每天用极少操作确认自己的观察，系统把当时可见的信息、依据、判断和后续事实对齐保存；小白获得研究坐标系，高手把个人方法沉淀成可检验的认知复利。

完成标准不是「模型回答更像人」，而是同一段历史可以回答四件事：当时知道什么、用户为什么这样判断、后来发生了什么、这条经验是否值得再次使用。

## 1. 目标与非目标

### 1.1 产品目标

1. 减少副业投资者筛选信息和重复检索的时间，把节省出的时间用于理解、表达和复盘。
2. 让用户留下可回检的判断，而不是只留下聊天文本。
3. 让个人经验先经过时间外验证、同期基准和稳定性检查，再决定是否进入个人方法库。
4. 让同一历史切片在不同模型、不同展示界面下得到相同的事实对象和验证收据。
5. 用个人层与共享层隔离，既允许个人积累，又不把一次反馈或单个用户偏好静默扩散给所有人。

### 1.2 非目标

- 不输出买卖时点、目标价、个股推荐或自动下单。
- 不以命中率、收益率或召回次数作为唯一产品价值指标。
- 不把聊天记录、向量召回或模型上下文当作事实主库。
- 不在没有授权、脱敏和访问隔离前，把私有研报、私有笔记或用户判断开放给其他用户。
- 不承诺通过一次用户反馈自动训练出稳定方法。

## 2. 产品形态

### 2.1 一条河、两个入口、四个工作面

这是一个产品，不是两个彼此独立的应用。

| 工作面 | 用户动作 | 系统职责 | 终局判据 |
|---|---|---|---|
| **今日带读** | 阅读一页摘要，确认或修改观察剧本（或多步情景树，§3.3） | 按授课框架读取当日切片，呈现事实、推断、缺口 | 新用户 10 分钟内能完成一次带读并留下可回检对象 |
| **历史回放** | 回到某个交易日查看当时依据 | 按 `as_of` 和 `knowledge_cutoff` 重建当时可见状态 | 回放不读取未来对象；缺口明确显示 |
| **个人判断台账** | 记录判断、条件、日期，等待回检 | 保存不可静默改写的判断与 verdict | 原判断、修订原因、回检结果都可追溯 |
| **方法检验** | 选择个人框架或候选经验进行检验 | 运行发现、验证、Holdout、滚动回放和失效监测 | 样本不足时不出比率；未过门不进入方法库 |

小白入口默认从「今日带读」开始，重点是建立坐标系；高手入口可以直接从「个人判断台账」和「方法检验」开始，重点是方法复利。两条路径共享时间长河和基础设施。

### 2.2 六条数据轨与两层框架

六条数据轨是事实对象；框架是解释这些对象的横切层，不能混称为第七条数据轨。

| 数据轨 | 内容 | 缺失时的行为 |
|---|---|---|
| **盘面轨** | 指数阶段、量价、成交、涨停热度、流动性指纹 | 返回 `gap`，不从其他轨推算 |
| **题材轨** | 题材事件、叙事版本、生命周期阶段 | 标明词表和模块版本 |
| **舆论轨** | 覆盖事件、覆盖密度、逻辑版本、证伪事件 | 阶段不可派生时标 `unverifiable` |
| **资金轨** | 板块/题材资金流、席位和可授权的资金对象 | 没有可靠来源时返回 `gap`，不填零 |
| **个股轨** | 公告、订单、财报、相对强度等节点 | 只作证据与节点，不生成推荐名单 |
| **判断轨** | 用户判断、Agent 判断、观察剧本、checkpoint、verdict | 判断对象保留原文、版本和回检状态 |

两层框架：

- **授课框架**：创始人提供、可解释、版本化的默认判读坐标；内容由人确认，Agent 负责结构化、执行和验证。骨架（概念 → 标签 → 字段，判读留空）见 `docs/learning/teaching-framework/00-concept-label-skeleton.md`：A 类指数阶段是新标签族 `index_stage`（**不是**供应商的 `market_stage`，两者并存、分开命名与版本），B 类市场风格标量、C 类板块角色（量 / 价 / 锐度 / 主流）、D 类事件锚点回溯（§4.6）。
- **用户私有框架**：仅对该用户生效的规则、偏好和纠偏；只在通过个人层门禁后参与个人回放，不自动进入共享层。

### 2.3 实体 × 轨覆盖矩阵

六条轨是**数据种类**；实体粒度（指数 / 板块 / 题材 / 个股 / 用户）是**另一条轴**，两者不混。用户口语里的「大盘、板块、个股」是实体粒度，「舆论、资金流、agent 判断」是数据种类——同一句话里两条轴各占一半，spec 把它们拆开放。

「个股轨」保留这个名字（BP v0.7 / deck / 词表 / `river.TRACKS` 均已钉六轨，验证期不改名），但语义钉死为**个股节点轨**：实体为个股的事件节点（公告、订单、财报、相对强度、涨停 / 新高 / 龙虎榜席位），是数据种类不是实体粒度。板块级、指数级的量价与阶段归盘面轨，不归它。

每格四态：✓ 已接（`river.py` v0 [实测]）、○ 有源待接、— 无源（返回 `gap`，不推算）、n/a 不适用；「待核」= 本轮未查表，不猜。

| 实体 \ 轨 | 盘面 | 题材 | 舆论 | 资金 | 个股节点 | 判断 |
|---|---|---|---|---|---|---|
| 指数 / 全市场 | ✓ `fact_market_daily`（切片背景对象 `__market__`） | ○ `fact_mainline_theme_daily` 主线题材 | 待核 | — 北向 / 两融 / ETF 份额无表 | n/a | ○ 待核（`checkpoints.themes` 是自由文本） |
| 板块 | ✓ 量价、双红、涨停热度 | ✓ 涨停成员挂的题材名 | ✓ 研报 tag 覆盖密度 + 产业文档 | ✓ 成分资金流 + 同名 theme_flow | ✓ 成分股行情节点 | ✓ `checkpoints.jsonl` 同名匹配 |
| 题材 | ○ `fact_theme_limit_heat_daily` | ○ 八阶段 / 时间线（G-04 后） | ○ `fact_theme_fundamental_doc.linked_themes`（32 份） | ○ `fact_theme_flow_daily` | ○ 题材成员 | ○ |
| 个股 | ○ `fact_stock_daily` | ○ 所属题材 / 涨停挂名 | 待核 | ○ `fact_sector_stock_daily.fund_flow_1d/5d` | ○ 龙虎榜三表、`fact_limit_advance_daily`、`fact_stock_high_daily`；公告 / 订单 / 财报表待核 | 私有层可挂；观察剧本 / 情景树 `scope` 禁止 |

[实测] `river.resolve_entity` 今天只解析板块（查 `fact_sector_daily`），题材与个股实体入口未开；题材↔板块桥接表 `config_theme_sector_link` 0 行。所以第一、三、四行的 ○ 在实体解析打通之前一律表现为 `gap{reason=entity_unresolved}`——这是如实状态，不是 bug；也不用板块切片去冒充题材切片。

## 3. 最小用户闭环

### 3.1 每日闭环

```text
读取当日切片
  -> 看主矛盾、三维阶段与证据缺口
  -> 系统生成一条观察剧本
  -> 用户确认 / 修改 / 跳过
  -> 系统登记 checkpoint 和回检日期
  -> 到期回检变量是否触发
  -> 生成 verdict 与候选经验
  -> 进入个人方法检验队列，不直接改规则
```

用户的必填动作只有一个：确认、修改或跳过观察剧本。系统自动保存依据、适用范围、来源、回检日期和版本。用户可以一次只登记一个观察剧本，也可以完全跳过；跳过本身是有效行为，不计为失败。

### 3.2 观察剧本对象

观察剧本回答「明天要看什么，以及什么条件会让它升级、降级或放弃」，不回答「明天买什么」。

```text
ObservationScript
  id
  user_id / visibility: private | shared_candidate | shared
  as_of
  knowledge_cutoff
  scope: index | sector | theme
  entity_ids
  variables[]
  upgrade_conditions[]
  downgrade_or_abandon_conditions[]
  evidence_refs[]
  framework_version
  recorded_at
  checkpoint_id
  status: drafted | confirmed | skipped | late | expired
```

硬门：含个股推荐、方向词、买卖时点、目标价或概率承诺的文本不能登记为 `ObservationScript`，必须返回可修正的错误提示；晚于次日开盘登记的对象标记 `late`，不进入方法校准。

### 3.3 情景树对象（多步推演；用户 2026-09-06 拍板）

观察剧本只推一步（T+1 看什么）。**情景树**把它接成多步：每个节点是一条观察剧本，节点之间的边是**六轨注册标签上的确定性条件**——「明天缩量且题材阶段不推进，走分枝 A；放量且涨停热度排名跃迁，走分枝 B；其余走 otherwise」。世界每过一个交易日，河的切片自动判定走了哪条边，树长出一条 `realized_path`。

它回答的是「按这个框架，接下来几步各自该看什么、什么条件算升级 / 降级 / 放弃」，不回答涨跌、时点、目标价——与观察剧本同一道硬门、同一个 `scope`。用户口语里的「推演」在产品语言里就是它。

```text
ScenarioTree
  id
  user_id / visibility: private | shared_candidate | shared
  as_of                    根节点所在交易日
  knowledge_cutoff
  projection_hash          生成它时 agent 看到的投影（§4.5）
  framework_version
  model_id                 生成它的模型
  scope: index | sector | theme
  entity_ids
  max_depth                ≤ 5 步；每步 = 1 个交易日或一个回检期限（T+1 / T+3 / T+5）
  nodes[]
    node_id, depth
    condition               进入本节点的条件：注册标签谓词（与 methodology_backtest 规则 DSL 同一套白名单）| otherwise
    observation_script_ref  到达本节点后的观察剧本
    analog_ref              可选：从本节点出发的历史相似窗口读数（只报 N 与后续事实；N < 10 写样本不足）
  edges[]                  parent → child；同一父节点的子条件必须互斥且穷尽，`otherwise` 分枝强制存在
  realized_path[]          {node_id, resolved_as_of, evidence_refs}；由河的切片判定，不由人或模型填
  status: drafted | confirmed | resolving | resolved | unresolvable | expired
  recorded_at
```

硬门（在观察剧本的门之上再加三条）：

1. 每条 `condition` 只能引用注册标签（`history_labels` 目录 + `LABEL_VERSION`）；编译不过的条件整棵树拒绝登记。否则 T+k 无法机器判定走了哪条边，树就退化成散文。
2. 节点与边上不得出现概率数字、百分比；`analog_ref` 只带复现次数与后续 5 / 10 / 20 日事实。
3. `realized_path` 只能由 `river.slice(T+k, knowledge_cutoff=T+k)` 的对象写入；任一步所需标签为 `gap` → 该步 `unresolvable`，树停在那里，不猜、不跳。

回检口径：树**不按「走了哪条枝」判对错**——那是世界的选择，不是框架的对错。回检三件事：(a) **覆盖**：世界是否落进某条声明过的分枝而不是 `otherwise`（`otherwise` 占比高说明框架对这个环境没有语言）；(b) **沿路剧本**：每条被到达的观察剧本，变量是否按条件触发（与 G-03 同一口径）；(c) **规则样本**：每条被走过的 `(condition → 下一步事实)` 成为一个样本，进 §5.4 的飞轮。

## 4. 时间与对象契约

### 4.1 两个时钟

每个进入时间长河的对象都要同时记录：

- **有效时间**：世界里什么时候成立，字段为 `valid_from` / `valid_to`。
- **记录时间**：系统什么时候知道或记录，字段为 `recorded_at` / `expired_at`。

回放函数：

```text
river.slice(as_of=T, knowledge_cutoff=C, entity=E, tracks=[...])
```

读取条件：

```text
valid_from <= T < valid_to
recorded_at <= C
expired_at is null OR expired_at > C
```

若历史对象缺少 `recorded_at`，整片标记 `pit_grade=trade_date_only`，与 `pit_grade=strict` 分开统计，不能混成一个平均值。`hindsight=true` 只用于人工复核，不得进入任何校准或方法有效性统计。

**粒度（用户 2026-09-06 拍板）：河的 `as_of` 是单日切片。** `valid_from` 与 `knowledge_cutoff` 都在交易日粒度上比较（[实测] `river._enforce_cutoff` 与 `pit_grade` 取 `recorded_at[:10]`）；盘中时刻（首板时间 `first_limit_time` 等）作为日频对象的 payload 字段保存，不作为切片键。「日内」在本产品里指这个，不指盘中回放。若日后要盘中 cutoff，改的是比较粒度，对象契约不动。

### 4.2 通用对象契约

```text
RiverObject
  track
  entity_id
  object_type
  ref                  # 指向主数据，不在索引层复制正文
  source_hash
  hardness             # L1-L4 或 n/a（L1 叙事线索 … L4 盘面验证）
  validity_kind        # point | state | range
  valid_from / valid_to
  recorded_at / expired_at
  superseded_by
  derivation           # deterministic | frozen_llm
  model_id / prompt_hash   # derivation=frozen_llm 时必填
  label_version
  framework_version
```

索引层只保存 `(as_of, entity, track, ref_hash)` 等定位信息，事实正文留在原轨主库。对象采用 append-only 方式保存，纠正通过新对象、状态和 `superseded_by` 表达，不覆盖旧记录。

**有效期语义按 `validity_kind` 分三种，`valid_to` 才有确定含义**：`point`——只对 `valid_from` 那一天成立（逐日标签、当日事件），`valid_to = valid_from`；`state`——从 `valid_from` 持续到被替代（阶段、叙事版本、判断），`valid_to = null` 表示现行；`range`——由 §4.4 区间派生，`valid_from / valid_to` 是区间首尾。`slice(T)` 取 `point(valid_from = T)` 与 `state(valid_from ≤ T < valid_to)`；`range` 对象只由 `window()` 返回，不混进单点切片。roadmap 09-06 回写说「`valid_to` 全树零命中、纠正没有载体」，缺的正是这个定义。

**两类派生，判据分开写**：终局 §3「换一个模型也能重算」只对 `derivation=deterministic` 成立——它们由确定性代码从事实算出，可进规则谓词、统计门与情景树条件。`derivation=frozen_llm` 是模型写一次的散文（叙事版本、逻辑版本 v1→v3、`fact_theme_fundamental_doc.core_theme`——[实测] 已在河里，`river._fundamental_docs` 自注「可读不可重算，不进任何度量」）：写入时必带 `model_id` 与 `prompt_hash`，只靠存储复现、不靠重算；硬度上限 **L1（叙事线索）**；可进上下文投影（带标记），**不得进**规则条件、统计门、情景树条件与任何度量。没有这条区分，河要么装不下叙事，要么拿叙事去算胜率——两个都错。

**判断轨对象的归因字段**：`agent_judgment` / `observation_script` / `scenario_tree` 必带 `model_id`、`framework_version`、`projection_hash`（§4.5）；缺任一则台账拒收。`user_judgment` 若在产品内做出，记 `projection_hash`（用户当时看到了什么）；产品外补录的标 `projection_hash = null` 并在校准里单列。理由：把「agent 的判断」列为一条轨，却记不下是哪个模型、哪版框架、看着哪片上下文做出的，按 框架 × 模型 分列胜率就无从谈起，「换模型能不能更准」也永远只是感觉。

### 4.3 证据与缺口

每条研究输出都要拆成四类：事实、推断、反证/限制、缺口。缺轨不是空数组，而是：

```text
gap { track, reason, source_checked_at, retryable }
```

缺失来源、授权不明、时间不完整和阶段不可判定都必须成为可见状态。Agent 不得用另一条轨“补齐”缺失事实。

### 4.4 区间契约（用户 2026-09-06 拍板：区间与单点同级）

单点切片回答「这一天是什么」；**区间**回答「这一段怎么走过来的」。两者同级、同一套时钟，联立不降级——区间不是把每条轨压成一个数再求均值，而是**保留对象身份的切片序列**加上**可拆回到天与行的派生对象**。

```text
river.window(start, end, knowledge_cutoff=C, entity=E, tracks=[...])

RiverWindow
  start / end             交易日（按交易日历数，不按自然日）
  knowledge_cutoff        整段一个 C；默认 C = end；C > end → hindsight=true；C < end 拒绝（区间没走完就没有这段区间）
  slices[]                [start, end] 内每个交易日的 RiverSlice，各自带 pit_grade
  derived[]               区间派生对象：RiverObject(validity_kind=range, derivation=deterministic)
  coverage{track: 有对象天数 / 区间天数}
  pit_grade               = min(slices.pit_grade)：任一天降档，整段降档
  hindsight / alias_applied   任一天为真，整段为真
```

区间派生对象的 `object_type` 钦定五类：`streak`（连续 N 日满足某标签）、`transition`（阶段 / 标签从 a 到 b 的跃迁日）、`cumulative`（区间累计：涨幅连乘、资金累计、覆盖新增）、`first_event`（区间内首次出现：首次卖方覆盖、首次涨停）、`signature`（六维 z-score 签名，供相似匹配）。每条带 `derivation_rule{name, version}` 与 `member_refs[]`（指回哪些天的哪些对象），聚类或匹配结果因此能拆回到表和行——`river_window.FeatureSpec` 已经在对 `signature` 这一类做这件事，契约把它推广到五类。

`gap_policy` 必须写在派生规则里，默认 `unverifiable`：区间内任一天所需轨为 `gap`，派生对象标 `unverifiable` 并写明缺哪天——缺一天不是零，也不是「跳过那天继续数」。规则若声明 `break`（缺天中断连续计数）或 `skip`（累计时跳过并在 `coverage` 里报），要写出理由。[实测] `river_query.range_aggregate` 已经这样做（`coverage / codes_seen / caveats`，`require_complete=True` 时只给 gap），它就是 `cumulative` 类的现成实现，纳入而不重写。

**PIT 在区间上不能断。** 派生对象只能从**过了 cutoff 过滤之后**的切片算。[实测] `river_window.build_daily_vectors` 今天读全历史、不接 C、不出 `pit_grade`——单点辛苦守住的无前视纪律，到区间这一层是断的。它必须改走本契约（缺口 G-02c）；`market_regime_analogs` 的窗口读数同理。

**相似匹配挂在区间上，不另起一套特征。** D8 题材类比、D10 市场环境类比、`stock_analogs`、`river_window` 聚类，用的都是「窗口签名 + 加权距离 + 缺维按覆盖率惩罚」这一个形状。契约要求它们的特征维就是 `history_labels` 里的**注册标签**——匹配用的「特征」与规则 DSL 用的「标签」是同一张目录、同一个 `LABEL_VERSION`（缺口 G-16）。这样「找相似窗口 → 看框架在那些窗口上的四态 → 推演 → 回检」才是一个词表上的一条闭环，而不是三套各自命名的特征在互相翻译。匹配读数只报 N、距离、后续 5 / 10 / 20 日事实与失效边界；N < 10 写样本不足；相似是「相对自身历史的相似」，不承诺完全一致。

### 4.5 上下文投影契约（agent 看到什么）

河里存什么（§4.2）、出门说什么（§4.3 四类）之外，还差中间那一步：**从一片切片或一段区间，到塞进模型的那几千 token**。这步今天是写死的截断（[实测] `guided_reading`：每对象 6 个 payload 键、字母序、个股节点 10 条）——确定，但不是高信噪比。

钦定原则：**框架就是信噪比过滤器。** 哪些对象、哪些字段在这次判读里算信号，由生效的授课 / 私有框架的规则决定，不由截断决定。框架对某条轨没有规则时，退到确定性默认序（硬度降序 → `recorded_at` 升序 → `ref` 字典序），并在块上标 `selected_by = default`。

```text
project(source: RiverSlice | RiverWindow, framework_version, task, budget) → ContextProjection

ContextProjection
  projection_id / projection_hash    = hash(有序 blocks 的 refs + framework_version + projection_version + budget + source_ref)
  projection_version                 投影算法版本
  framework_version
  source_ref                         {as_of | start,end; entity; knowledge_cutoff; pit_grade; hindsight; alias_applied}
  blocks[]                           有序
    track, object_refs[], hardness, derivation, selected_by（框架规则号 | default）, rendered_text
  omitted{track: count}              每轨没进上下文的对象数——省略要可见，不能静默
  limits[]                           pit_grade 降档 / alias_applied / hindsight：强制块，不可省略
  gaps[]                             源里的 gap 全部带过来：强制块，不可省略
  budget{limit, used}
```

硬规矩：

1. 路径上无 LLM；同一 `(source, framework_version, task, budget)` 两次投影 `projection_hash` 相同。
2. `gaps` 与 `limits` 永远进上下文，且排在事实块之前——缺口是判读的边界条件，不是脚注。
3. `frozen_llm` 对象可进，块上带 `derivation` 标记；默认序里排在同轨 `deterministic` 对象之后。
4. 预算不够时按块整体省略并计入 `omitted`，不得在对象中间截断——半个 payload 比没有更坏。
5. 每条 agent 产物（判断、观察剧本、情景树）记 `projection_hash`；台账拒收没有它的对象。回溯因此是完整的：能重建那天的河，也能重建 agent 那天实际看到的那一小片。
6. 五段出门（结论 / 证据 / 反证 / 观察剧本 / 缺口）是输出侧纪律，投影是输入侧纪律；两头都有门，中间的模型才谈得上被公平回检，「换模型」才是一个可以做实验的问题。

### 4.6 事件锚点回溯（区间的第三种问法）

用户 2026-09-06 原话：「一个最高连板结束后，低位首板或二板后来是谁走出来、是什么形态走出来的、走出来前的量价形态是怎么样的；当时的主流板块是什么阶段、价板块是什么、锐度板块是什么——这些我希望都可以回溯。」这不是一条标签，是一种**查询形状**：一个锚点事件，向后看谁出来、向前看它怎么来的、再看锚点那天的世界。它由 `slice` 与 `window` 组合而成，但必须作为一等契约写下来，否则每次都是手写 SQL，PIT 与缺口纪律在组合处漏掉。

```text
river.anchor_windows(anchor_label, before=m, after=k | until(target_label), knowledge_cutoff=C, context_tracks=[...])

AnchorRecord                              每个锚点日一条
  anchor_as_of                            锚点日 = anchor_label 为真的交易日（锚点标签本身必须是注册的 point 标签，确认日语义）
  context                                 slice(anchor_as_of, C)：锚点那天的 market / sector 轨 + 角色标签
  forward                                 window(anchor_as_of, forward_end, C)：其上的派生对象（谁「走出来」、以什么形态）
                                          forward_end = anchor_as_of + k（定长）或 target_label 首次为真的日子（事件到事件；未发生 → 该记录 open，不进统计）
  lookback[]                              对 forward 里每个命中的实体，window(emerge − m, emerge, C)：走出来之前的量价派生对象
  context_target                          事件到事件模式下，slice(forward_end, C)：目标事件那天的世界（「诞生环境」）
  pit_grade                               各段取最差
  gaps[]                                  任一段所需轨 / 标签缺失 → 该锚点记录整条 unverifiable，不用另两段补
```

两种前瞻窗都是一等：定长 k 适合「锚点后 5 / 10 / 20 日事实」（D8 / D10 已在用）；**事件到事件**适合「上一任断板 → 下一任诞生」这类链式问题（用户 2026-09-06：「观察下次的市场最高标的诞生环境和前一个市场最高标断板的关联」）——此时 `gap_days` 是读数不是参数，链上每一节自带两个上下文切片。母本骨架 §4 的 `LeaderSuccession` 是第一个事件到事件的实例。

硬规矩：

1. **锚点、目标、形态三样都得先是注册标签或派生规则**，没有确定性定义之前这条查询不能跑——定义由创始人填（`docs/learning/teaching-framework/00-concept-label-skeleton.md` §4、§6），agent 不替填。
2. 一条锚点记录的 `knowledge_cutoff` 至少是 `forward_end`：前瞻窗没走完就没有这条记录。回放时显式传入且不得晚于此。事件到事件模式下历史尾部最后一节没有目标事件 → `open`，不进 N。
3. 输出只报事实：锚点出现 N 次、每次走出来的实体与形态、上下文切片、复现次数；不报「下次也会这样」，N < 10 写样本不足。它是 D8 / D10 类比与情景树 `analog_ref` 的直接原料，不是结论。
4. `river_window.windows_around` 是它的前瞻段原型（已按交易日取窗），`river_query.cohort_compare` 是它的统计段原型（纵扫 + 四态）；契约把三段合成一条记录，不另写第三套。

## 5. 方法生命周期与数据飞轮

### 5.1 候选到方法的状态机

```text
feedback
  -> candidate
  -> discovery_passed
  -> validation_passed
  -> holdout_passed
  -> personal_method
  -> shared_candidate
  -> shared_method
```

任何阶段都可以进入：

```text
insufficient | contradicted | invalidated | superseded
```

状态转移必须附带收据：样本范围、对象去重规则、基准、版本、缺口、检验次数、统计结果和失败原因。

### 5.2 反馈不是自动训练

用户反馈只产生候选经验，不能直接：

- 写入共享提示词；
- 改写授课框架；
- 影响其他用户的默认输出；
- 把单次命中记录成“有效规律”。

个人方法只有在个人层验证通过后才可用于该用户的带读或回放；共享方法还要有跨用户复现、权限和脱敏收据。

### 5.3 飞轮的真实闭环

```text
更少筛选时间
  -> 更多用户愿意记录判断
  -> 更多带有效时间和条件的判断样本
  -> 更好的回检与方法诊断
  -> 更少重复犯错、更清楚的带读
  -> 用户更愿意继续记录
```

飞轮的核心不是“训练数据越多模型越聪明”，而是高质量、可回放、带条件的判断对象变多。无条件的点赞、聊天长度和召回次数不进入方法飞轮。

### 5.4 推演–回检飞轮（情景树接入后的完整一圈）

用户 2026-09-06 原话：「我给 agent 的方法论，他就可以基于历史行情验证胜率，然后再去推演未来，又可以回溯，达到数据飞轮的目的。」这一圈在契约上是这样闭合的：

```text
河：六轨事实 + 注册标签（history_labels，LABEL_VERSION）
  -> 当前单点 / 区间的标签签名                                   §4.2 / §4.4
  -> 历史相似窗口：N、距离、后续 5/10/20 日事实、失效边界          §4.4 相似匹配
  -> 框架在那些窗口上的四态（methodology_backtest）               §6.2
  -> 投影：框架选出的信号 + 缺口 + 相似窗口读数                   §4.5
  -> 情景树：分枝 = 框架条件（注册标签谓词），节点 = 观察剧本       §3.3
  -> 用户确认 / 修改 / 跳过
  -> 逐日回检：河的切片判定走了哪条边，realized_path 自动延长
  -> 每条走过的 (condition -> 下一步事实) = 一个规则样本
  -> 候选规则提议（下文）-> 统计门 -> 个人方法 / 共享候选          §5.1
  -> 框架版本与规则库更新 -> 下一次投影与推演
```

这一圈里模型只做两件事：按框架写出情景树的分枝（候选生成）、向人解释。其余每一步都是确定性代码，同输入同输出，任何一步的读数都能拆回河上的行。

**候选规则提议是这圈的关键一步，之前只有一句话**（§3.1「生成 verdict 与候选经验」）。契约：

- 输入：一批 verdict / `realized_path` 样本，按 `framework_version × market_stage × object_type × horizon` 过滤；
- 输出：**只能是规则 JSON**（`methodology/rules/*.json` 的形状：条件 = 注册标签谓词 + lag，结果 = 已有多窗口收益口径），不能是散文结论；
- `provenance.kind ∈ {user_feedback, agent_discovered, teaching}`；`agent_discovered` 走 G-13 探索 / 验证双窗；
- 提议次数进多重检验分母，与 G-13 同一本账；
- 提议不改任何规则、卡、画像——它只是把一个候选放进队列。

**两条诚实的边界，写进产品原则：**

1. 自进化的是**规则库**（阈值、候选、四态），不是框架的结构——母本由人写、人改、版本化。agent 可以提议，不能改写。
2. 样本墙：按天数 413 个交易日，分桶后 N ≥ 10 是稀缺品。让飞轮转起来靠**横截面**（每天 400 个板块各是一个样本，而不是一天一个）与**结构型规则**（参数少、按阶段条件化）；数字阈值先以 `insufficient` 展示，不阻塞带读与推演。

## 6. 评估体系：两套指标，不能混算

### 6.1 用户价值评估

评估用户是否更省时、更能理解和复盘：

| 维度 | 指标 | 采集方式 |
|---|---|---|
| 省时 | 同一研究任务的中位耗时、完成率 | 前后对照任务，记录任务开始/结束 |
| 解释 | 能否说清依据、条件和缺口 | 冻结题集 + 人工评分/判官评分 |
| 迁移 | 能否把框架用于新案例 | 新实体、新题材或新时间段任务 |
| 修正 | 是否能按结果修正原判断 | 判断与 verdict 的差分记录 |
| 负担 | 每日必填动作数、跳过率、连续中断天数 | 产品事件日志 |

周活、留存和付费转化是经营指标；它们不能替代学习效果，也不能证明某条方法有效。

### 6.2 方法有效性评估

候选规则必须同时报告：

- 发现集、验证集、时间外 Holdout 和滚动回放；
- 同期基准、同一研究宇宙和样本去重；
- 样本量、Wilson 区间、阶段分层和不确定性；
- 多重检验校正、候选尝试次数和探索窗口；
- 失效条件、最近一次失效时间和是否需要重新验证。

`N < 10` 时显示“样本不足”，不出胜率或转化率。即使通过统计门，也只能说明某个定义下的历史可区分性，不能写成未来收益承诺。

### 6.3 失效监测

方法进入个人或共享层后仍需持续监测：

1. 新窗口表现是否跌回基准区间。
2. 适用阶段是否发生漂移。
3. 数据源、标签版本或实体宇宙是否变化。
4. 规则是否被重复使用到超出原始适用范围。
5. 用户是否只在成功后登记、造成选择性记录偏差。

出现失效时，方法标记 `invalidated` 或 `needs_revalidation`，保留历史收据，不静默删除。

## 7. 防过拟合门禁

1. **时间切分**：验证数据的时间必须晚于发现数据；Holdout 不得被探索过程读取。
2. **对象去重**：同一实体、同一交易日、重叠窗口和同源事件不能重复计数。
3. **基准对照**：候选经验必须与同期、同宇宙基准比较，不能只报绝对命中。
4. **分层稳定性**：至少按市场阶段、题材阶段或对象类型分层，报告哪一层失效。
5. **尝试记账**：所有候选尝试进入多重检验分母；失败的候选不能从历史上抹掉。
6. **用户选择偏差**：区分“用户主动登记”与“系统自动生成”，不能用登记样本代表全部研究任务。
7. **框架隔离**：授课框架、个人框架和共享方法使用不同版本号与命名空间。
8. **收据门禁**：没有完整 `source_hash`、时间语义、样本范围和数据缺口说明的结果不得进入方法库。
9. **回放门禁**：回放必须在同一 `(as_of, knowledge_cutoff, label_version, framework_version)` 下幂等。
10. **人工升级**：从个人层升到共享层必须经过人工审阅、脱敏检查和跨用户复现，不能由 Agent 自动批准。
11. **投影门禁**：agent 产物没有 `projection_hash` 不得入台账；同一投影输入两次 hash 不同视为投影层 bug，阻塞发布。
12. **区间 PIT**：任何区间派生、相似匹配、聚类读数都必须从 `window(start, end, C)` 出，`pit_grade` 随段；绕过 `window()` 直读全历史的路径视为前视泄漏。
13. **情景树条件可编译**：分枝条件必须能被规则编译器接受（注册标签白名单）；编译不过的树不得登记，也不得渲染给用户。

## 8. 基础设施与模块边界

### 8.1 模块

| 模块 | 责任 | 禁止承担 |
|---|---|---|
| `track providers` | 从已有主库读取六条轨对象 | 互相补事实、修改主数据 |
| `river index` | 按时间、实体、轨索引对象引用 | 复制正文、写入模型结论 |
| `river window` | 区间切片序列与五类派生对象，PIT 随段 | 读未过 cutoff 的天；缺天补零或跳过不报 |
| `context projection` | 按框架把切片 / 区间投影成有序上下文块，出 `projection_hash` | 调 LLM 选内容；静默截断；丢 gap |
| `analog matcher` | 在注册标签上做窗口签名相似匹配 | 自建第二套特征目录；出概率 |
| `framework runtime` | 用授课/私有框架读取切片 | 直接升级方法状态 |
| `observation scripts` | 生成、登记、回检观察剧本 | 输出买卖指令 |
| `scenario trees` | 生成、登记、逐日解析情景树 | 写方向 / 概率；人工填 `realized_path` |
| `candidate proposer` | 从 verdict / `realized_path` 提议规则 JSON | 输出散文；改规则或画像 |
| `checkpoint/verdict` | 保存可证伪点和到期结果 | 用事后信息改写原判断 |
| `methodology backtest` | 运行分窗、基准和统计门 | 把样本不足显示成胜率 |
| `candidate queue` | 管理候选经验和状态转移 | 静默写共享层 |
| `replay/eval` | 生成回放和评估收据 | 读取未来或绕过 PIT |
| `access/provenance` | 用户隔离、脱敏、授权和来源追踪 | 以免责声明代替权限控制 |

### 8.2 确定性原则

- LLM 负责解释、归纳和生成候选表达；事实标签、时间切片、统计和状态转移由确定性代码完成。
- 任一对象都能回溯到主数据、来源哈希和版本。
- 任何展示层都只能调用统一读取面，不能自行拼接事实轨。
- 同一输入在相同版本下重复运行，核心结构化结果必须一致。

## 9. 权限、隐私与授权

用户层级至少分为：`private`、`shared_candidate`、`shared`。默认是 `private`。

- 用户判断、私有笔记和个人框架默认只对本人可见。
- 进入共享候选前必须脱敏、去除私有原文和可识别信息。
- 数据源的可读不等于可商业分发；收费前逐项核对取用、加工、引用和展示权限。
- 用户退出后可导出个人判断记录；删除、保留和备份规则要可解释。
- 权限、来源和删除操作都写入审计日志。

## 10. 路线与验收

### V1：0–3 个月，先把闭环跑通

- 授课框架 v0 母本和版本号。
- `river.slice` 三轨版本：盘面、题材、判断。
- 今日带读 + 观察剧本的确认/修改/跳过流程。
- 两时钟与 `pit_grade` 收据。
- 判断、checkpoint、verdict、候选经验队列。
- 上下文投影契约 v0（G-14）：框架规则未成前全部 `selected_by=default`，但 `projection_hash` 已入台账——带读接进每日复盘之前必须先有它。
- 新用户 10 分钟完成一次带读；同一切片两次读取结构化结果一致。

### V2：3–6 个月，把对照面补齐

- 区间契约 `river.window` 与区间 PIT（G-02c）——相似匹配与环境剧本的前置。
- 六轨读取面补齐舆论、资金、个股。
- 舆论生命周期阶段词表和三维并置。
- 情景树 v0（G-15）：深度 ≤ 3、分枝条件限于已归一的 `market_stage` 与双红系标签，先跑通逐日解析。
- 用户价值评估题集、任务耗时和解释评分。
- 方法面板按 `framework × market_stage × object_type × horizon` 分列。
- 权限隔离、脱敏和完整成本记录通过 Alpha/Beta 硬门。

### V3：6–12 个月，形成个人方法复利

- 环境剧本：指数阶段、流动性指纹、历史窗口、失效边界。
- 私有框架容器和差分声明。
- 个人方法失效监测、重新验证和跨用户共享门。
- 探索模式只输出候选规则 JSON，探索次数进入多重检验分母；相似匹配与规则 DSL 共用注册标签目录，候选规则提议契约落地（G-16）。
- 情景树接相似窗口读数（`analog_ref`）与私有框架；深度放开到 5。
- 历史回放接入授课框架和私有框架。

### 最小验收集

1. 随机抽取 30 个 `(as_of, entity)` 切片，每条对象都能回溯到 `source_hash`。
2. 缺少任一轨时返回 `gap`，不返回伪造的零值或补全段落。
3. 同一 `(as_of, knowledge_cutoff, framework_version)` 重放结果幂等。
4. 含推荐、买卖时点、目标价或概率承诺的观察剧本被拒绝并给出错误码。
5. `N < 10` 的方法格显示样本不足，不能显示百分比。
6. 一次用户反馈不会改变共享提示词、授课框架或其他用户输出。
7. `hindsight=true` 的对象无法进入校准和方法统计。
8. 用户退出后可以导出自己的判断台账，且私有对象不会出现在其他用户查询中。
9. `window(start, end, C)` 对同一输入幂等；任一天 `trade_date_only` 则整段 `trade_date_only`；`C < end` 被拒绝。
10. 随机抽 30 个区间派生对象，每条 `member_refs` 都能解析回对应切片里的对象；所需轨缺天的派生对象为 `unverifiable`，不是数字。
11. 同一 `(source, framework_version, task, budget)` 两次投影 `projection_hash` 相同；源里每个 gap 都出现在投影里。
12. 缺 `projection_hash` / `model_id` 的 agent 判断被台账拒收并给出错误码。
13. 含未注册标签、概率数字、缺 `otherwise` 分枝、或子条件不互斥的情景树被拒绝并给出错误码。
14. 情景树 T+k 所需标签为 `gap` 时状态为 `unresolvable`，`realized_path` 不延长。
15. `anchor_windows` 的锚点、目标、形态任一未注册为标签或派生规则时拒绝执行并给出错误码；每条锚点记录 `knowledge_cutoff ≥ anchor + k`，三段任一缺失则整条 `unverifiable`。
16. `index_stage`（授课框架）与 `market_stage`（供应商）在旁路库分开成两个标签、两个版本号；任一读取方不得把一个当另一个用（测试：两者在同一天可以不同且都被保留）。

## 11. 壁垒假设与验证

当前没有已验证的护城河。可积累的壁垒假设有四层：

1. **结构化时间资产**：多轨、双时钟、来源和缺口形成可重放的研究历史。
2. **领域框架资产**：授课框架和个人框架被编码成可解释、可检验的规则，而不是散文提示词。
3. **判断与结果资产**：用户留下带条件的判断和回检，形成其他通用 Agent 不容易直接复制的个人数据。
4. **验证收据资产**：候选经验的失败、失效、重新验证和跨用户复现都被保留，形成方法筛选记录。

只有当用户持续记录、回检和复用，且数据授权、时间语义和评估收据长期稳定，这些资产才可能构成切换成本和产品壁垒。模型能力、提示词和单次研报不作为壁垒叙事。

## 12. 关键决策

- 时间长河是索引和契约，不另建第二套事实库或向量记忆中台。
- 六条数据轨与两层框架分开表达；框架决定“怎么读”，不伪装成事实轨。
- 观察剧本替代“第二天的方向”，方法检验替代“模型自我训练”的模糊叙事。
- 用户价值与方法有效性分开评估；任何一边的好结果都不能代替另一边。
- 个人层先于共享层；一次反馈永远不能静默改变共享输出。
- 缺口、样本不足和失效是产品状态，不是需要隐藏的异常。
- 单点与区间同级：`slice` 与 `window` 同一套时钟，区间派生对象带 `member_refs`，PIT 不在区间上断。
- 框架是信噪比过滤器：agent 看到的上下文由框架规则选出、带 hash 入账，不由截断决定。
- 推演是多步情景树：分枝是注册标签上的条件，路径由河判定，不写方向与概率。
- 河里两类对象：确定性派生可进统计与条件，模型散文只进上下文、硬度封顶 L1。
- 「日内」= 单日切片：as-of 交易日粒度，盘中时刻只是字段。

## 13. 待实现工单映射

本 spec 与现有路线的对应关系：

- `G-01`：授课框架 artifact v0；骨架已落（`teaching-framework/00-concept-label-skeleton.md`），A 类 `index_stage` 标签族、B / C 类标签、D 类锚点定义等创始人填 §6 清单。
- `G-02a/G-02`：三轨读取面与双时钟对象契约。
- `G-02c`：区间契约 `river.window` 与区间 PIT（`river_window` / `market_regime_analogs` 改走契约）；含 §4.6 `anchor_windows` 事件锚点回溯。
- `G-03`：观察剧本对象和带读模式。
- `G-04/G-05/G-06/G-07`：题材、盘面、舆论阶段统一与三维并置。
- `G-08/G-09`：环境剧本与分层方法面板。
- `G-10/G-11/G-13`：私有框架、历史回放和探索模式。
- `G-14`：上下文投影契约与 `projection_hash` 门禁。
- `G-15`：情景树对象、编译门、逐日解析与三项回检。
- `G-16`：相似匹配与规则 DSL 共用注册标签目录；候选规则提议契约。

实施时优先完成 V1 的最小闭环，再按 V2/V3 扩展数据轨和方法复利，不把未实现的终局能力写成当前产品事实。
