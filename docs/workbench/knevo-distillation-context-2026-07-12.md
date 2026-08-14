# Knevo 蒸馏上下文与 Workbench 取长补短边界

> **归档说明（2026-08-06）**：本文写于 2026-07-12，随
> `docs/workbench-runtime-optimization-backlog` 分支归档入 main。所引用的
> `docs/learning/knevo-distill/` 系列在 main 上持续更新过（最新见该目录 E-006），
> 以那边为准；本文的价值在「Knevo 只作机制基准、不照抄」这条边界本身。
>
> 用途：给后续优化 Session 提供背景，不把 Knevo 当作照抄目标。
>
> 本文不包含登录凭证、截图、原始私有对话、隐藏系统提示词或个股投资建议。

## 1. 仓库中已经存在的 Knevo 资料

本分支基于 `main`，因此已经自动包含此前提交的 Knevo 蒸馏资料，不是完全没有上下文。

后续 Session 应先读：

1. `docs/learning/knevo-distill/README.md`
   - 基于历史使用分享整理的核心机制；
   - 作战地图、盘中监控、盘感翻译、问题资产、记忆入库纪律、决策追踪和事实审查。
2. `docs/learning/knevo-distill/q1-异动四分类判据.md`
   - 异动分类、七维数据和组合阈值。
3. `docs/learning/knevo-distill/q2-五维排序量化.md`
   - 确定性、弹性、兑现时间、拥挤度和已定价程度。
4. `docs/learning/knevo-distill/q3-错因归因六分类.md`
   - 判断失败后的归因和修正路径。
5. `docs/learning/knevo-distill/q4-finance-review-check-skill.md`
   - 数值、实体、来源、逻辑、时效、完整性六维事实审查。
6. `docs/learning/knevo-distill/q5-finance-kol-analyze-skill.md`
   - KOL 画像与观点质量审查的边界。
7. `docs/learning/knevo-distill/q7-finance-mode路由表.md`
   - 单入口路由、任务 preset 和下游 Skill 派单。
8. `docs/learning/knevo-distill/q8-finance-industry-track-skill.md`
   - 以上期基线为锚，只报告变化的 delta-only 契约。
9. `docs/learning/knevo-distill/q9-finance-associate历史类比引擎.md`
   - 人工策展的场景案例库与语义检索。
10. `docs/learning/knevo-distill/q10-检索硬触发规则.md`
    - “先检索后开口”、并行检索和空结果改写重试。
11. `docs/learning/knevo-distill/q11-三库矛盾仲裁规则.md`
    - 共享记忆、用户记忆与 provider 事实的冲突处理。
12. `docs/learning/knevo-distill/q12-猜你想问生成机制.md`
    - 下一步问题不是随机推荐，而是当前证据缺口和验证窗口的延伸。
13. `docs/learning/knevo-vs-workbench-技能包对比台账.md`
    - 多轮双盲对比、已补能力、剩余差距和 Workbench 的优势。

上述文件是详细来源；本文只补充 2026-07-12 继续蒸馏后的最新上下文，并把它映射到当前 Workbench P0/P1。

## 2. 2026-07-12 继续蒸馏得到了什么

### 2.1 提示词与工作流

本轮整理出约 40 个可复用用户侧模板，来源分为：

| 来源级别 | 含义 |
|---|---|
| H | 历史用户提示词变量化 |
| S | Knevo 金融 Skill 给出的标准问法 |
| M | 从长期/短期记忆还原的任务骨架 |
| C | 本轮蒸馏对话中形成的新模板 |

高置信、反复出现的约束包括：

1. 时间冻结：只能使用截止某一精确时点可获得的数据；
2. 工具隔离：反事实实验可禁止行情、新闻和记忆；
3. 禁止污染记忆：虚构样本和实验结果不写入长期记忆；
4. 证据分层：事实、历史基线、第三方观点、推断和缺口分开；
5. 信息不足时拒绝补全；
6. 升级、降级和证伪优先使用组合门槛；
7. 强制给反证；
8. 说明完成判断所需的最小数据集；
9. 报告实际调用了哪些工具；
10. 事实审查既指出问题，也保护“不应修改”的正确部分。

这批模板的价值不是措辞，而是把研究任务变成可测试的输入契约、工具契约和输出契约。

### 2.2 行业 Know-how

对风远共享知识库的三轮定向检索得到：

- 约 180 条去重共享记忆；
- 10 个行业主题簇；
- 66 条可迁移规则卡；
- 15 条成熟度相对最高的规则；
- 10 条最容易过拟合的规则。

主题明显偏向：

- AI 硬件上游；
- 半导体；
- 光通信；
- 存储；
- 科技主题行为金融。

因此它不是均衡的全行业百科，存在样本选择偏差。

最值得学习的规则结构是：

```yaml
id: R01
name: 按供给弹性而不是需求增速排序
when: 结构性需求上升
then: 优先研究短期无法增加有效供给的环节
mechanism:
  - 有效供应商少
  - 扩产周期长
  - 客户认证慢
  - 良率爬坡慢
indicators:
  - 供应商数量
  - 扩产周期
  - 认证进度
  - 良率
applicable:
  - 供给瓶颈可验证
invalid:
  - 需求转弱
  - 新增有效产能释放
counterexample:
  - 需求高增但供给同步扩张
evidence_grade: candidate
```

即规则不是一段 Markdown 结论，而是包含：

- When/Then；
- 机制；
- 指标；
- 适用条件；
- 失效条件；
- 反例；
- 证据等级；
- 历史案例。

### 2.3 KOL 与机构经验

本轮识别：

- 7 个有两条以上跨时点记录的持续画像；
- 16 个单点 KOL、机构、管理层或数据源卡；
- 7 条第三方报告内化的 Know-how；
- 7 类偏差风险。

重要边界：

- 出现机构名称不等于形成 KOL 画像；
- 至少两条跨时点记录，才允许建立持续画像；
- 第三方观点不能升级为事实；
- 管理层指引、目标价和卖方预测必须保留 speaker、发布时间和验证窗口；
- 当前资料普遍缺少完整命中率、失败样本和利益冲突披露。

Workbench 若实现 KOL 层，应优先做“观点台账”，而不是模拟人物语气：

```yaml
speaker: 某机构或研究者
claim: 某一可验证主张
published_at: 2026-07-01
forecast_window: 30d
source_uri: ...
evidence:
  - ...
counterevidence:
  - ...
status: pending
verified_at: null
outcome: null
bias_tags:
  - selection_bias
```

## 3. 为什么同样是“数据库 + LLM”，答案质量差距很大

“数据库 + LLM”只是零件名，不能说明模型最终看到的上下文和执行流程。

### 3.1 检索载荷不同

LLM 不会读取整个数据库。真正影响答案的是：

- query 是否正确拆解；
- 检索了哪些库；
- 每路取回什么；
- 如何去重和重排；
- 哪些内容因上下文窗口被截断；
- 证据在 prompt 中的顺序。

同一个数据库，最终送给模型的 20 个片段不同，答案就可能完全不同。

### 3.2 数据库内容的“可执行程度”不同

以下内容虽然都能存进数据库，但价值不同：

1. 原始文档；
2. 原子事实；
3. 实体关系；
4. 历史案例；
5. If/Then 规则；
6. 用户偏好；
7. 用户纠偏；
8. 待验证假设；
9. 已回检结果。

Knevo 的优势更像是后五类内容较厚，并且能被任务路由精准调用。

### 3.3 长期用户上下文不同

从用户提供的历史回答可直接观察到：

- 回答引用类似 `fmr-...` 的记忆 ID；
- “双锚”“五类资金”“供给弹性”等私人术语跨回答保持一致；
- 历史判断、次日验证和后续纠偏会被再次调用；
- 用户风格被拆成持有周期、回撤容忍度、确定性/赔率偏好等变量。

这说明高质量个性化不是把最近聊天全文塞进 prompt，而是把可复用框架和纠偏结构化。

### 3.4 工具覆盖和数据时点不同

用户提供的历史回答中可直接看到：

- 具体盘中时间；
- 行情、新闻和财务来源；
- 跨市场信息；
- 事件日历；
- 产业链关系；
- 历史记忆。

因此答案是“历史框架 + 当前数据”的组合，不是单纯依靠记忆写作。

### 3.5 编排不同

高质量链路更接近：

```text
任务识别
-> query expansion
-> 用户记忆 / 共享知识 / 历史案例 / 当前会话并行检索
-> 行情 / 新闻 / 财务 / 图谱工具
-> 冲突仲裁
-> 证据标准化
-> 任务模板
-> 反证与质量门禁
-> 回答
-> checkpoint
-> 到期回检
-> 规则或记忆版本更新
```

低质量链路通常是：

```text
检索几个片段
-> 把片段和问题一起交给 LLM
-> 生成一篇长文
```

### 3.6 输出契约不同

Knevo 高密度回答常使用稳定结构：

- 当前结论；
- 事实与来源；
- 框架解释；
- 排序表；
- 反证；
- 条件分支；
- 翻转条件；
- 时间窗口；
- 下一步问题。

稳定的结构主要来自工作流，不是模型临场发挥。

### 3.7 反馈闭环不同

质量会随使用增长，依赖：

```text
判断
-> 冻结当时证据
-> 等待验证
-> 记录结果
-> 归因命中或失败
-> 更新规则版本和权重
```

如果系统只保存“最终回答”，不保存当时证据、验证窗口和后验结果，就无法形成认知复利。

## 4. 直接观察与工程推断必须分开

### 4.1 直接观察到的事实

- 回答会引用长期记忆 ID；
- 私人框架跨多轮保持一致；
- 盘中回答带时间和数据来源；
- 输出结构稳定；
- 会给条件和翻转点，而不只是重复用户结论；
- 存在按任务区分的金融 Skill；
- 共享知识、用户记忆和外部 provider 在回答中承担不同角色。

### 4.2 高概率工程推断

以下是根据输出和工具行为反推，不是获得了 Knevo 私有源码：

- 问题会被拆成 task、entity、time scope、framework 和 required evidence；
- 多路检索可能并行；
- 记忆可能包含 type、event_time、confidence、version、supersedes 等元数据；
- workflow 可能使用显式状态机、DAG 或子 agent；
- 规则、观点和假设可能是不同对象。

后续开发不能把这些推断写成“已证实的 Knevo 内部实现”。

## 5. Workbench 应学习什么

### 5.1 把 Skill 任务契约放在通用 Ask 之上

手动 Daily Agent 的原始产物正确，但最终回答被通用 Ask 覆盖，说明当前缺少明确的主任务所有权。

应学习：

```text
入口路由确定任务
-> 专项 Skill 拥有主回答
-> 通用检索只补证据
-> 质量门禁统一收口
```

对应当前 Backlog：`P0-1`。

### 5.2 建立唯一 Evidence Registry

事实、引用、statement 和 UI 数字必须来自同一 Registry。

建议最小类型：

```text
fact_source
bound_evidence
context_only
weak_candidate
counterevidence
```

对应当前 Backlog：`P0-2`、`P0-4`。

### 5.3 让规则成为一等对象

把高价值行业 Know-how 存成 RuleCard，不要直接把 66 条文本作为 system prompt。

原因：

- 可检索；
- 可版本化；
- 可记录适用范围；
- 可挂反例；
- 可回检命中率；
- 失效后可 supersede，而不是覆盖历史。

### 5.4 打通对话记忆闭环

推荐流程：

```text
对话
-> 抽取 facts / rules / hypotheses / preferences / corrections
-> 人工确认高风险项
-> 版本写回
-> 下轮按实体和任务召回
```

用户纠偏应链接原判断，不能只保存最新一句话。

### 5.5 把研究编排升级为显式 DAG

可并行节点：

- 用户记忆；
- 共享规则；
- 当前盘面；
- 财务；
- 新闻；
- 图谱；
- 历史案例；
- KOL 观点；
- 反证检索。

统一收口节点：

- entity resolution；
- freshness；
- conflict resolution；
- evidence binding；
- quality gate。

### 5.6 增加 Narrative Composer，但不让它修改事实

Workbench 的结构化证据更可审计，但表达偏模块拼装。

正确做法：

```text
Evidence Registry
-> deterministic report
-> Narrative Composer
-> citation validator
```

Narrative Composer 只能组织已绑定事实，不能新增数字、来源或证据等级。

### 5.7 自动建立 checkpoint 和回检

任何预测性结论都应包含：

- 冻结时点；
- 判断；
- 支持证据；
- 反证；
- 验证窗口；
- 升级/降级门槛；
- 到期状态；
- 错因分类。

## 6. Workbench 不应照搬什么

### 6.1 不照搬无来源的精确数字

既往双盲对比发现 Knevo 也会出现：

- 无溯源数值概率；
- 无法复核的历史案例数字；
- 不完整时间窗口上的精确估计；
- 目标价或仓位式结论。

这些不能因为表达流畅而进入 Workbench。

### 6.2 不把共享规则当作事实

66 条规则是研究假设和经验卡，不是客观定律。

使用前必须检查：

- 来源；
- 样本数；
- 行业适用性；
- 时间跨度；
- 失败案例；
- 是否存在 AI 硬件样本偏置。

### 6.3 不模拟 KOL 语气替代观点审查

优先做：

- 观点原文；
- 证据链；
- 激励和利益冲突；
- 历史一致性；
- 可证伪指标；
- 到期验证。

不要为了“像某人”而补写其未表达的结论。

### 6.4 不牺牲 Workbench 已有优势

Workbench 在既往对比中更强的部分：

- 引用可复核；
- 缺数诚实；
- 时间冻结；
- 结构化证据；
- 双盲回检；
- 本地私有执行；
- 确定性数据链。

优化目标是补记忆连续性、研究编排和叙事综合，不是削弱证据纪律。

## 7. 对当前优化 Backlog 的影响

### 第一阶段：先修现有 P0

1. Skill 主回答链；
2. 弱证据硬写门禁；
3. service/research readiness；
4. Evidence Registry 一致性。

这些是 Knevo 式高级能力的地基。P0 不修，不应先导入 66 条规则或大规模提示词。

### 第二阶段：最小记忆闭环

建议对象：

```text
RuleCard
UserCorrection
Hypothesis
Checkpoint
Claim
HistoricalCase
```

每个对象必须可版本化并带来源。

### 第三阶段：研究 DAG 和 Narrative Composer

将当前串行模块拼装改为：

```text
QuestionPlan
-> parallel retrieval/tools
-> normalized evidence
-> conflict arbitration
-> domain Skill projection
-> narrative
-> validation
```

### 第四阶段：KOL 与行业经验

只将经过来源审计、具备适用/失效条件的规则卡加入召回。

不要把整份蒸馏 Markdown 全量塞进 prompt。

## 8. 新 Session 的执行说明

新 Session 应使用以下顺序：

1. checkout `docs/workbench-runtime-optimization-backlog`；
2. 读本文；
3. 读 `docs/workbench/runtime-optimization-backlog-2026-07-12.md`；
4. 按需读取 `docs/learning/knevo-distill/` 中对应专题，不要一次通读全部正文；
5. 从 P0-1 开始复现；
6. 每个 P0 独立 PR；
7. 每个实现都回答：
   - 学的是 Knevo 哪个机制；
   - 保留了 Workbench 哪个优势；
   - 有什么替代方案；
   - 如何用测试证明不是只改善文案。

推荐给新 Session 的指令：

```text
checkout docs/workbench-runtime-optimization-backlog。
先读 docs/workbench/knevo-distillation-context-2026-07-12.md 和
docs/workbench/runtime-optimization-backlog-2026-07-12.md。
Knevo 只作为机制基准，不照搬答案；保留 Workbench 的证据可审计、
缺数诚实、时间冻结和双盲回检。从 P0-1 开始，先复现，再做最小修复，
补契约测试，独立 PR，不合并 main。
```
