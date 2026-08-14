# FinHot 与金融 Agent 营销链路设计

- 日期：2026-07-05
- 状态：设计稿，待用户审阅
- 目标版本：P0 证据驱动内容生成闭环，P1 接入检索增强，P2 接入发布效果复盘

## 1. 背景与目标

用户希望为 FinHot 和金融 Agent 搭建一条营销内容自动生成链路，覆盖文案、短视频脚本、投放素材和千人千面策略。

本设计不把营销理解成“批量套模板写广告词”，而是把现有四个资产串成一个可复盘的内容生产系统：

- FinHot：金融信息流阅读器，负责信息发现、多源聚合、质量打分、AI 摘要和官方披露查新。
- 金融 repo：市场数据、每日复盘、Theme Radar、Perspective Lab、策略矩阵和研究工作流。
- 知识库 repo：Evidence Graph、实体/概念/来源/关系层、RAG 索引和证据分层。
- video-use：对话式视频剪辑流水线，负责口播素材转写、剪辑、字幕、动画 overlay 和渲染自检。

一句话目标：

> 建立一个证据驱动的营销内容 Agent，以介绍产品为主线，把真实产品能力、使用场景、截图、案例和发布反馈串起来，持续生成、发布、复盘 FinHot 与金融 Agent 的内容素材。

定位澄清：内容主线是**产品介绍**（产品是什么、能做什么、解决什么问题、怎么用），不以教学/边做边学为主。教学向内容（build-in-public、技术选型分享）只作为辅线，用于吸引 AI 工具爱好者人群，不占主要产能。

## 2. 关键原则

### 2.1 证据先于文案

每个营销卖点都必须能追溯到产品功能、代码文档、截图、案例产物或使用日志。营销 Agent 不应凭空发明能力，也不应把仍在验证中的研究假设包装成确定结果。

对外表达分三层：

- 产品事实：已经存在的功能和能力，例如 FinHot 多源聚合、金融 Agent 每日复盘、知识库证据图谱。
- 使用场景：用户如何用这套系统完成任务，例如从信息流发现线索，再用 Theme Radar 查证据。
- 价值主张：这套系统带来的效率和认知收益，例如减少信息噪音、让研究结论可追溯。

### 2.2 研究员定位，不承诺收益

金融 Agent 的长期定位是研究员和分析顾问，不是操盘手。营销内容必须明确边界：

- 可以说“帮助整理线索、复盘、验证证据、生成研究内容”。
- 不说“保证抓涨停、自动赚钱、替你买卖、直接提升收益率”。
- 不把回测、案例、单次判断包装成确定性投资建议。

### 2.3 先半自动，再闭环自动化

P0 阶段采用“Agent 生成，多版本输出，人工发布，人工确认复盘”。等发布效果台账有足够数据后，再进入 P1/P2 的自动变体生成和效果归因。

这样做的取舍：

- 优点：低风险，能快速产出内容，也能沉淀真实反馈。
- 缺点：短期不会做到无人投放和自动调预算。

### 2.4 产品介绍为主线，教学为辅线

内容产能优先分配给产品介绍类内容：功能 demo、使用场景、案例展示、价值主张。教学/建设日志类内容仅作为辅线补充，每批占比不超过 20%，且必须落脚回产品能力本身。

### 2.5 从素材事实库开始，而不是先接平台 API

营销系统最先缺的不是发布 API，而是稳定的“可讲素材”。先把产品定义、功能、截图、案例、禁用表达、目标人群整理成结构化文件，再让 Agent 基于这些材料生成内容。

可迁移知识点：

> 这和 RAG 的工程思想一致：先构建高质量检索语料和数据契约，再谈生成效果。没有可信语料，模型生成越强，越容易放大幻觉。

## 3. 方案比较

### 3.1 推荐方案：证据驱动的半自动营销链路

做法：

```text
产品事实库
  -> 检索相关功能/案例/截图/边界
  -> 生成多平台内容变体
  -> 人工审核与发布
  -> 记录发布效果
  -> 复盘 winning patterns
  -> 反向更新素材事实库和生成策略
```

优点：

- 符合现有 repo 的证据分层和审计习惯。
- 能复用知识库和金融 repo 的 RAG、Theme Radar、台账机制。
- 适合从 7 天 MVP 起步，后续平滑升级。
- 能让用户学习主流 Agent 产品化方法：结构化语料、Hybrid 检索、rerank、效果闭环。

缺点：

- 需要先写素材事实库和台账 schema。
- 第一阶段仍要人工发布和复盘。

### 3.2 替代方案 A：模板化内容工厂

做法：预设几十个模板，只替换产品名、功能名和价格/CTA。

优点：

- 最快，当天能产出大量文案。
- 工程复杂度最低。

缺点：

- 内容同质化严重。
- 不能利用知识库和案例证据。
- 很难做千人千面，只是模板换皮。

结论：可作为 fallback，不作为主线。

### 3.3 替代方案 B：全自动投放 Agent

做法：直接接入广告平台或社媒 API，自动生成素材、投放、关停低效素材、加预算。

优点：

- 最接近“全链路 Agent”愿景。
- 成熟后能减少运营手工动作。

缺点：

- 需要稳定转化数据、预算控制、合规审查和平台 API。
- 当前没有足够历史样本支撑自动决策。
- 金融产品内容容易触发合规风险，不能过早无人干预。

结论：P3 之后再评估，不进入 P0/P1。

## 4. 产品定位与内容主线

### 4.1 FinHot

一句话定位：

> 本地优先的金融信息流阅读器，把 RSS、微博、雪球、微信、X 和官方披露源聚合成可打分、可摘要、可追踪的高信号阅读流。

核心卖点：

- 多源聚合：财经 RSS、微博、雪球、微信、X、自定义 watchlist。
- AI 增强：摘要、中译、质量打分。
- 主题阅读：Topic Reading、聚类、时间线整理。
- 官方证据：disclosure_lookup 按公司/关键词查公告、互动易、问询函，并做 P0-P3 分级。
- 本地优先：本地 SQLite、桌面应用、BYOK AI。

主要内容角度：

- “我如何不被金融信息流淹没”。
- “同一个题材，为什么我先看源头证据再看热闹”。
- “一个财经 RSS 阅读器为什么要做官方披露查新”。

### 4.2 金融 Agent

一句话定位：

> 面向 A 股主题研究的个人市场情报工作台，把盘面数据、研报/公告证据、题材图谱和个人认知框架对齐，输出带出处、可复盘、可证伪的研究结论。

核心卖点：

- 每日复盘：市场强弱、板块信号、涨停、连板、新高、策略矩阵。
- Theme Radar：题材定义、产业链、公司分层、证据强度、市场信号、缺口。
- Evidence Graph：实体、概念、来源、证据、关系层。
- Perspective Lab：把用户自己的市场框架结构化，并用外部角色做 challenger。
- 双盲与 checkpoint：把判断登记、盘后验证、经验回灌。

主要内容角度：

- “不是问 AI 明天买什么，而是让 AI 帮我把判断拆成证据和反证”。
- “一个题材从研报、公告到盘面的完整发酵链路”。
- “金融 Agent 能帮你做什么：复盘、题材证据、判断验证的完整工作台”。

### 4.3 video-use

一句话定位：

> 对话式视频剪辑流水线，把原始口播素材转成带字幕、节奏、动画 overlay 和自检的短视频。

在营销链路中的角色：

- 把用户录制的产品讲解剪成发布视频。
- 把金融 Agent 的研究产物改写为口播脚本和分镜。
- 把功能 demo、截图和数据故事做成短视频素材。

## 5. 目标人群

P0 以产品目标用户为主，核心是让他们理解产品能做什么、值不值得用。

| 人群 | 优先级 | 痛点 | 主推产品 | 主要钩子 |
|---|---|---|---|---|
| 主观交易者 | 主线 | 盘面、研报、消息太散，复盘靠感觉 | 金融 Agent | 可追溯复盘、题材证据、反证条件 |
| 财经内容创作者 | 主线 | 选题多但消化慢，内容生产压力大 | FinHot + 金融 Agent | 信息发现到长文/视频脚本的一条链 |
| AI 工具爱好者 | 辅线 | 想看真实 Agent 项目，不想看玩具 demo | 全套系统 | 本地优先、多 repo 协作、真实产品能力 |

P0 不面向“想要确定性荐股”的用户，也不把产品包装成投顾服务。

## 6. 系统架构

```text
Repo docs / screenshots / usage manuals
  -> marketing source inventory
  -> claim registry
  -> content brief
  -> retrieval context
  -> content generator
  -> review package
  -> publish log
  -> performance ledger
  -> learning summary
  -> next batch briefs
```

模块分工：

1. Marketing Source Inventory：登记可用于营销的素材源，包括 README、产品手册、截图、案例报告、视频素材。
2. Claim Registry：登记可对外表达的卖点、对应证据、禁用表达和风险等级。
3. Persona Matrix：登记目标人群、痛点、渠道偏好、CTA。
4. Content Brief Builder：把产品、渠道、人群、目标组合成生成任务。
5. Retrieval Layer：从素材事实库和必要 repo 文档召回上下文。
6. Content Generator：生成多版本文案、长文大纲、短视频脚本、分镜、封面标题。
7. Review Gate：检查事实可追溯、禁用表达、金融合规边界。
8. Performance Ledger：记录发布效果和人工复盘。
9. Learning Loop：总结高表现钩子、低表现表达、下一轮生成策略。

## 7. 数据落点

P0 先在金融 repo 内新增 `docs/marketing/`，因为营销链路首先围绕金融 Agent 的产品化表达，并需要读取现有 specs、manual、ledger。

目标结构：

```text
docs/marketing/
├── README.md
├── products.yaml
├── features.yaml
├── claims.yaml
├── personas.yaml
├── content-briefs/
│   └── 2026-07-05-launch-batch.yaml
├── generated/
│   └── 2026-07-05-launch-batch.md
└── performance/
    └── marketing-performance.jsonl
```

P0 只写文档和 JSONL/YAML，不写数据库。等数据量超过几十批后，再考虑 DuckDB。

## 8. 核心数据契约

### 8.1 产品定义 `products.yaml`

```yaml
products:
  - id: finhot
    name: FinHot
    positioning: 本地优先的金融信息流阅读器
    primary_audience: [主观交易者, 财经内容创作者, AI 工具爱好者]
    repo_path: /Users/a77/finhot
    public_boundary:
      can_say:
        - 多源聚合财经信息
        - AI 摘要、中译、质量打分
        - 本地优先和 BYOK AI
      cannot_say:
        - 保证提前发现牛股
        - 替代专业投顾
  - id: finance_agent
    name: 金融 Agent
    positioning: A 股主题研究与复盘工作台
    primary_audience: [主观交易者]
    repo_path: /Users/a77/finance-workspace-private
    public_boundary:
      can_say:
        - 帮助整理盘面、题材和证据
        - 输出带出处、可复盘、可证伪的研究结论
      cannot_say:
        - 自动下单
        - 保证收益
```

### 8.2 功能事实 `features.yaml`

```yaml
features:
  - id: finhot-ai-summary
    product_id: finhot
    name: AI 摘要与中译
    evidence_refs:
      - repo: /Users/a77/finhot
        path: README.md
        section: 它是什么
    assets:
      - /Users/a77/finhot/docs/screenshots/entry-detail.png
    audience_value:
      主观交易者: 快速判断一条信息是否值得深读
      财经内容创作者: 快速消化外文和长文章
    risk_level: low
  - id: finance-theme-radar
    product_id: finance_agent
    name: Theme Radar
    evidence_refs:
      - repo: /Users/a77/finance-workspace-private
        path: docs/productization-roadmap.md
        section: 第二条产品闭环：Theme Radar
    audience_value:
      主观交易者: 把题材定义、产业链、证据和盘面信号放在一起看
    risk_level: medium
```

### 8.3 卖点声明 `claims.yaml`

```yaml
claims:
  - id: claim-evidence-first-research
    text: 金融 Agent 不只总结观点，而是把每个判断拆成证据、反证和验证路径。
    product_ids: [finance_agent, knowledge_base]
    support_feature_ids: [finance-theme-radar]
    allowed_channels: [longform, short_video, social_post]
    prohibited_rewrites:
      - AI 会告诉你明天买什么
      - 自动提高收益率
    review_required: true
```

### 8.4 内容 brief `content-briefs/*.yaml`

```yaml
brief_id: 2026-07-05-launch-batch
objective: 为 FinHot 和金融 Agent 生成第一批产品介绍内容
channels: [x_thread, zhihu_article, short_video]
personas: [主观交易者, 财经内容创作者, AI 工具爱好者]
products: [finhot, finance_agent]
content_types:
  - pain_point_post
  - demo_script
  - feature_showcase
  - use_case_story
required_claim_ids:
  - claim-evidence-first-research
constraints:
  - 不承诺收益
  - 不写明文密钥、内部路径可在内部草稿出现但对外发布需替换
  - 对外内容避免泄露私有仓库细节
```

### 8.5 效果台账 `marketing-performance.jsonl`

```json
{
  "content_id": "2026-07-05-finance-agent-short-video-001",
  "brief_id": "2026-07-05-launch-batch",
  "product_ids": ["finance_agent"],
  "persona": "主观交易者",
  "channel": "short_video",
  "hook_type": "pain_point",
  "claim_ids": ["claim-evidence-first-research"],
  "published_at": "2026-07-05T20:00:00+08:00",
  "metrics": {
    "views": 0,
    "likes": 0,
    "comments": 0,
    "clicks": 0,
    "follows": 0
  },
  "human_notes": "",
  "next_action": "observe"
}
```

## 9. 检索与生成策略

### 9.1 P0：显式引用上下文

P0 不急着建索引。Content Generator 直接读取 `docs/marketing/*.yaml` 和少量明确登记的源文档。

优点：

- 简单、可控、容易审查。
- 不会误读大知识库或私有材料。

缺点：

- 召回能力有限。
- 需要人工维护 features 和 claims。

### 9.2 P1：Hybrid 检索

P1 引入 Hybrid 检索。Hybrid 检索是“关键词检索 + 向量检索”的混合方案：

- BM25：适合精确命中产品名、功能名、文件名、术语。
- 向量检索：适合理解语义相近的表达，例如“信息太多看不过来”召回“金融信息流阅读器”。
- rerank：先粗召回一批，再用更精细的模型或规则重排，减少噪音。

推荐策略：

```text
brief
  -> BM25 top 20
  -> vector top 20
  -> merge + dedupe
  -> rerank top 8
  -> generation context
```

面试可讲点：

> 只用向量检索容易漏掉专有名词和精确字段，只用 BM25 又处理不好同义表达。Hybrid + rerank 是生产 RAG 里很常见的组合。

### 9.3 P2：基于效果的生成策略选择

P2 根据 `marketing-performance.jsonl` 聚合不同 hook、persona、channel、claim 的表现：

- 哪些人群更吃 demo 型内容。
- 哪些渠道更适合建设日志。
- 哪些卖点容易被误解或低互动。
- 哪些标题带来点击但评论质量差。

P2 只生成下一轮建议，不自动投放。

## 10. 内容输出格式

每次生成批次至少输出四类内容。

### 10.1 短帖

适用渠道：X、即刻、朋友圈、微信群预热。

输出字段：

- 标题或第一句话 hook。
- 正文。
- CTA。
- 使用的 claim_ids。
- 发布风险提示。

### 10.2 长文大纲

适用渠道：知乎、公众号、博客、研究网站。

输出字段：

- 标题候选 5 个。
- 文章结构。
- 每节核心论点。
- 需要截图或 demo 的位置。
- 引用素材来源。

### 10.3 短视频脚本

适用渠道：抖音、B 站、小红书、视频号。

输出字段：

- 目标时长。
- 口播稿。
- 分镜表。
- 屏幕录制清单。
- 字幕风格建议。
- video-use 剪辑 brief。

### 10.4 投放素材变体

P0 先只生成素材，不自动投放。

输出字段：

- 目标人群。
- 痛点版本。
- 功能版本。
- 案例版本。
- CTA 版本。
- 禁用表达检查结果。

## 11. video-use 接入方式

P0 不让 Marketing Agent 直接剪视频，而是生成 video-use 可消费的剪辑 brief。

流程：

```text
content generator
  -> short video script
  -> shot list
  -> recording checklist
  -> user records raw footage
  -> video-use inventories and transcribes footage
  -> user confirms editing strategy
  -> video-use renders preview/final
  -> final video registered in marketing ledger
```

video-use brief 示例：

```text
目标：把 FinHot 和金融 Agent 的组合讲成 60 秒产品 demo。
结构：Hook -> 信息噪音问题 -> FinHot 发现线索 -> 金融 Agent 验证题材 -> CTA。
素材：屏幕录制 FinHot timeline、金融 Agent Theme Radar 产物、用户口播。
风格：快节奏产品 demo，中文字幕，保留真实操作界面。
风险边界：不承诺收益，不出现具体买卖建议。
```

## 12. Review Gate

每条内容发布前经过四类检查。

### 12.1 事实检查

- 每个核心卖点必须绑定 `claim_id` 或 `feature_id`。
- 如果生成内容出现未登记能力，标记为 `unsupported_claim`。
- 如果引用私有路径或内部数据，对外发布前必须替换为泛化描述或截图。

### 12.2 金融合规边界

禁止表达：

- 保证收益、稳赚、自动赚钱。
- 明确买卖指令。
- 把研究案例包装为投资建议。
- 暗示 AI 可以替代投顾资质。

### 12.3 隐私与安全

禁止发布：

- `.env*`、token、配置凭证。
- 私有数据库路径和敏感文件内容。
- 未脱敏的用户私有数据。
- 未授权的研报正文长摘录。

### 12.4 内容质量

检查项：

- 是否能被目标人群听懂。
- 是否有具体场景，而不是抽象堆功能。
- 是否有明确 CTA。
- 是否避免模板化重复。

## 13. 错误处理

- 缺少产品事实库：生成任务失败，并提示先补 `products.yaml` / `features.yaml`。
- claim 无证据：内容生成继续，但该段标记 `review_required`，不能直接发布。
- 出现禁用表达：Review Gate 失败，并给出替换建议。
- 检索结果不足：降级到 P0 显式上下文，不进行自由发挥。
- 效果台账字段缺失：复盘命令跳过该条，并输出缺字段报告。
- video-use 缺少素材：只生成录制清单，不进入剪辑。

## 14. 测试计划

P0 以文档和数据契约为主，测试应轻量但可自动化。

### 14.1 Schema 校验

- `products.yaml` 必须有 `id`、`name`、`positioning`、`public_boundary`。
- `features.yaml` 的 `product_id` 必须存在于 products。
- `claims.yaml` 的 `support_feature_ids` 必须存在于 features。
- `content-briefs/*.yaml` 的 required_claim_ids 必须存在于 claims。

### 14.2 Review Gate 回归样例

准备正反例：

- 合规表达：帮助复盘题材证据。
- 违规表达：保证抓到主线龙头。
- 隐私风险：包含 `.env` 或 token 字样。
- 无证据卖点：声称已有自动投放 API。

### 14.3 生成质量抽查

每批人工抽查：

- 是否命中目标 persona。
- 是否使用正确产品定位。
- 是否含有可追溯 claim。
- 是否至少有 3 个不同 hook 类型。

## 15. Rollout 计划

### P0：7 天 MVP

目标：不用新建复杂服务，先跑通第一批内容。

任务：

1. 新建 `docs/marketing/`。
2. 写 `products.yaml`、`features.yaml`、`claims.yaml`、`personas.yaml`。
3. 写第一批 `content-briefs/2026-07-05-launch-batch.yaml`。
4. 生成第一批内容：20 条短帖、5 篇长文大纲、3 条短视频脚本。
5. 手工发布其中 3-5 条。
6. 建 `marketing-performance.jsonl` 登记效果。
7. 第 3 天和第 7 天做复盘，总结下一轮策略。

验收标准：

- 每条内容都能追溯到至少一个 claim 或 feature。
- 没有收益承诺和自动交易暗示。
- 至少发布 3 条内容并登记效果。

### P1：检索增强内容生成

目标：接入轻量 RAG，让 Agent 能从 repo 文档和素材库召回上下文。

任务：

1. 建 marketing source manifest。
2. 实现 BM25 或简单关键词召回。
3. 可选接向量检索。
4. 加 rerank 和引用片段输出。
5. 生成内容时附带 source_refs。

验收标准：

- 生成内容引用的材料可定位到文件和段落。
- 同一 brief 能生成面向不同 persona 的差异化版本。
- Review Gate 能拦住无证据卖点。

### P2：效果闭环

目标：把发布数据变成下一轮生成策略。

任务：

1. 聚合 `marketing-performance.jsonl`。
2. 按 persona/channel/hook/claim 输出表现表。
3. 生成 winning patterns 和 avoid patterns。
4. 自动生成下一轮 content brief 草案。

验收标准：

- 能回答“哪个卖点在哪类人群上表现更好”。
- 下一轮 brief 明确引用上一轮表现。
- 人工仍保留最终发布决策。

### P3：平台与投放集成

目标：在内容和复盘稳定后，再评估平台 API 或投放 API。

进入条件：

- 至少 4 周发布数据。
- 明确知道核心受众和高表现内容类型。
- Review Gate 足够稳定。
- 用户明确确认预算和合规边界。

## 16. 非目标

P0/P1 不做以下事项：

- 不接广告平台 API。
- 不自动发布。
- 不自动调预算。
- 不做复杂 Web UI。
- 不把私有仓库细节直接公开。
- 不把金融 Agent 包装成投顾或自动交易系统。
- 不批量读取知识库正文。
- 不把营销素材写入知识库事实层。

## 17. 开放问题

这些问题不阻塞 P0，但进入 P1/P2 前需要决策：

1. 对外主阵地优先级：X/即刻、公众号/知乎、B 站/抖音、小红书，哪个先做主渠道。
2. FinHot 是否要单独做 public landing page，还是先用现有 README 和截图发布。
3. 金融 Agent 是否对外开源部分能力，还是只做建设日志和产品 demo。
4. 是否引入 finance-research-site 作为公开内容承载面。
5. 对外内容中是否允许展示真实 A 股案例；若允许，需要定义脱敏和免责声明模板。

## 18. 第一批建议内容清单

全部围绕产品介绍主线：产品是什么、解决什么问题、核心功能 demo、真实使用场景。

短视频：

1. FinHot 60 秒产品 demo：多源聚合 + AI 摘要 + 官方披露查新，一条信息流搞定金融阅读。
2. 金融 Agent 产品 demo：一次题材研究从盘面到证据的完整工作流。
3. FinHot + 金融 Agent 组合场景：从信息流发现线索，到 Theme Radar 验证题材。

长文：

1. FinHot 是什么：本地优先的金融信息流阅读器，功能全景介绍。
2. 金融 Agent 是什么：A 股主题研究工作台的核心能力（每日复盘、Theme Radar、Evidence Graph、Perspective Lab）。
3. 从 FinHot 到 Theme Radar：一条信息如何变成研究线索（产品组合使用场景）。
4. 我为什么不做“荐股 AI”，而做证据驱动的金融 Agent（产品定位与边界）。
5. 用 video-use 把金融研究产物变成短视频（产品间协作场景）。

短帖：

1. FinHot 把 RSS、微博、雪球、微信、X 聚合成一条可打分、可摘要的信息流。
2. 一个金融阅读器如果不能查源头证据，就只能帮你更快刷噪音——所以 FinHot 做了官方披露查新。
3. 金融 Agent 的每日复盘：市场强弱、板块信号、涨停连板、策略矩阵，一次跑完。
4. Theme Radar：把题材定义、产业链、公司分层、证据强度放在一张图里看。
5. 我不想让 AI 告诉我买什么，我想让它告诉我为什么这个判断可能错——这就是金融 Agent 的定位。

## 19. 下一步

用户审阅本 spec 后，如果方向确认，下一步进入 implementation plan：

1. 创建 `docs/marketing/` 数据契约。
2. 写第一批 YAML/JSONL 样例。
3. 做一个只读生成脚本或 CLI 草案。
4. 生成第一批 launch batch 内容。
5. 记录发布效果并复盘。

