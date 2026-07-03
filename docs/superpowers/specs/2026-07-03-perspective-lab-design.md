# Perspective Lab 多角色认知编程模块设计

- 日期：2026-07-03
- 状态：设计稿，已经用户审阅确认，进入实现计划
- 目标版本：P0 可用闭环，P1 接入 ask，P2 做多角色长期胜率评估

## 1. 背景与目标

用户希望新增一个模块：可以上传一个博主的文章，让系统学习他如何分析市场，并在之后用这个角色的视角分析市场。角色可以是用户认可的博主，也可以是巴菲特这类经典投资者。

本模块的核心不是模仿文风，而是学习并复用“市场认知框架”。数据仍然是硬资产，角色视角只是解释同一份硬数据的不同镜头。

第一版选择 C 方案：多角色辩论台。

一句话目标：

> 对同一份市场数据，让多个角色分别给出分析、互相反驳，再由系统做交叉验证，输出更稳的条件化结论和可证伪假设。

## 2. 关键原则

### 2.1 事实层和认知层分离

事实层包括 DuckDB 盘面数据、知识库证据、研报/公告/互动易/年报等硬证据。它们回答“发生了什么”。

认知层包括博主、巴菲特、趋势交易者、用户自己的复盘框架。它们回答“从这个视角会如何解释这些事实”。

角色不得改写事实，不得把自己的偏好当成事实。输出中必须标明：

- 哪些是事实；
- 哪些是角色解释；
- 哪些是推演；
- 哪些是证伪条件。

### 2.2 学框架，不学口癖

对博主文章的学习目标不是复刻语言风格，而是抽取可迁移的分析结构：

- 关注的首要变量；
- 对行情的阶段划分方式；
- 机会类型偏好；
- 风险厌恶点；
- 常用证据；
- 常用反证；
- 对错时如何修正。

这能避免“角色扮演”变成玄学 prompt。

### 2.3 每个角色都要可审计

每个角色输出都应该能追溯到：

- 当前使用的数据快照；
- 被召回的角色原文片段；
- 角色画像中的规则；
- 最终判断对应的证伪条件。

### 2.4 多视角不是投票器

多角色输出不是简单少数服从多数。不同角色的价值在于暴露盲区：

- 巴菲特视角可能提醒估值和护城河；
- 趋势交易者视角可能提醒资金选择和相对强度；
- 博主视角可能提醒产业链二阶导或市场情绪；
- 用户自己的框架可能负责最终条件化结论。

最终合议要解释“为什么采纳/降权某个角色”，而不是只数票。

## 3. 技术选型与替代方案

### 3.1 推荐方案：结构化画像 + RAG 原文召回 + 多角色合议

RAG 是“检索增强生成”，即生成答案前先从资料库里检索相关原文，再基于原文和当前硬数据回答。这里用它检索博主历史文章中与当前行情相似的片段。

推荐数据流：

```
博主文章
 -> 文章 ingest
 -> 结构化抽取 perspective profile
 -> 建索引

今日市场问题
 -> 读取 DuckDB/知识库硬数据
 -> 为每个角色检索相似历史片段
 -> 每个角色独立分析
 -> 多角色交叉质询
 -> 裁判合议
 -> 输出结论 + 分歧 + 证伪点
 -> 可选登记 checkpoint / forecast ledger
```

优点：

- 可追溯，不靠一句 prompt 装成某个角色；
- 能复用现有 ask 编排层、experience_cards、checkpoint 和 forecast ledger；
- 后续可以评估不同角色在不同市场阶段的有效性；
- 能迁移到其他角色和其他垂直 Agent 场景。

缺点：

- 工程复杂度高于纯 prompt；
- 第一版需要先设计角色画像 schema；
- 博主文章质量差时，抽取出的画像也会噪声较大。

### 3.2 替代方案 A：纯 prompt 角色卡

做法：用户上传文章后，让 LLM 总结成一段角色 prompt，回答时直接注入。

优点：

- 最快能跑；
- 文件和索引都简单。

缺点：

- 不可追溯；
- 容易模仿语气而不是学框架；
- 无法稳定评估某个角色为什么判断对/错。

适合做 demo，不适合作为本项目长期模块。

### 3.3 替代方案 B：只做结构化规则，不做原文 RAG

做法：文章只抽取成 JSON 画像，回答时只读取画像，不检索原文。

优点：

- 稳定、便宜、可测试；
- 角色边界清楚；
- 不依赖向量索引。

缺点：

- 丢失上下文；
- 博主的细腻判断容易被压扁；
- 很难处理“这次行情像他过去哪一类场景”。

适合作为 P0 的最低可用版本，但 P1 应接 RAG。

### 3.4 当前取舍

- P0 先做“结构化画像 + 人工/LLM 摘要落档 + 单次多角色合议”，让流程跑通。
- P1 再接入本地 RAG，用文章原文片段增强角色输出。
- P2 接入 forecast ledger/checkpoint，长期评估各角色在不同市场阶段的胜率和盲区。

可复用知识点：

> 这是垂直 Agent 常见架构：事实库负责 ground truth，角色/偏好/方法论是 overlay，最终输出要有审计和验证闭环。这个模式在法律、医疗、投研、代码审查、产品策略 Agent 都能用。

面试可讲点：

> 这里体现了 RAG、persona memory、multi-agent debate、evaluation loop 的分层设计。重点不是“用了多个 Agent”，而是把事实、观点、推理、验证四层解耦。

## 4. 模块命名

推荐模块名：

- 人读名称：Perspective Lab / 视角实验室
- CLI 名称：`perspective`
- 服务文件：`intelligence/services/perspective_lab.py`
- 运行时目录：`intelligence/users/<user>/perspectives/`

原因：

- perspective 比 persona 更强调“视角”，少一点角色扮演感；
- lab 表示实验场，天然支持多角色对照和回测；
- 与现有 `users/<user>/` 用户态数据隔离方式一致。

## 5. 数据落点

### 5.1 用户私有运行时数据

落点：

```
intelligence/users/<user>/perspectives/
├── profiles/
│   ├── blogger_x.json
│   ├── buffett.json
│   └── user_framework.json
├── articles/
│   └── blogger_x/
│       ├── manifest.jsonl
│       └── raw/
│           └── 2026-07-03-article-title.md
├── notes/
│   └── blogger_x.md
├── debates.jsonl
└── outcomes.jsonl
```

这些默认 gitignore，不进仓库，因为包含用户认可的博主文章、个人偏好和使用历史。

### 5.2 项目内文档

人读说明文档：

- `docs/learning/perspective-lab.md`

后续实现后记录：

- 如何创建角色；
- 如何上传文章；
- 如何跑多角色合议；
- 如何看角色胜率；
- 常见误用边界。

### 5.3 不写入知识库事实层

博主文章和角色画像默认不写入知识库 entities/concepts/relations。原因是它们不是事实 ground truth，而是认知样本。

如果文章里出现公告、订单、合同、产能等硬事实，应该另走现有 disclosure/l3-ingest 或知识库 ingest 流程，不能直接因为博主提到就写实体正文。

## 6. Perspective Profile 角色画像 Schema

每个角色一份 JSON：

```json
{
  "schema_version": 1,
  "id": "blogger_x",
  "display_name": "某博主",
  "type": "blogger",
  "created_at": "2026-07-03T00:00:00+08:00",
  "updated_at": "2026-07-03T00:00:00+08:00",
  "source_policy": {
    "allowed_sources": ["uploaded_articles"],
    "citation_required": true,
    "min_articles_for_confident_profile": 3
  },
  "market_lenses": [
    {
      "name": "市场阶段",
      "description": "先判断指数、量能和赚钱效应处于启动、主升、分歧、兑现还是退潮",
      "weight": 0.25
    },
    {
      "name": "主线强度",
      "description": "看容量行业、涨停扩散、新高集群和核心股承接",
      "weight": 0.25
    }
  ],
  "opportunity_preferences": [
    "主线第一次分歧后的核心回流",
    "低位题材出现双红和涨停扩散",
    "产业催化与盘面确认共振"
  ],
  "risk_triggers": [
    "缩量上涨且后排不跟",
    "高位核心放量滞涨",
    "产业催化已被卖方一致覆盖"
  ],
  "evidence_hierarchy": [
    "盘面选择",
    "公告/订单/产能",
    "产业链验证",
    "卖方观点",
    "情绪传闻"
  ],
  "reasoning_patterns": [
    {
      "name": "先阶段后方向",
      "rule": "先定市场阶段，再讨论题材和个股；不能脱离市场状态判断空间"
    }
  ],
  "anti_patterns": [
    "只看产业逻辑不看盘面承接",
    "把卖方观点当硬证据"
  ],
  "falsification_style": [
    "如果核心股跌破关键均线且题材无新高扩散，则降低判断级别",
    "如果消息兑现当天放量滞涨，则优先判断一致预期兑现"
  ],
  "voice_guidance": {
    "style": "清晰、直接、少口癖",
    "forbidden": ["复刻私人语气", "冒充本人"]
  },
  "confidence": {
    "article_count": 0,
    "profile_confidence": "low",
    "known_gaps": ["样本不足时只能作为候选视角"]
  }
}
```

说明：

- `market_lenses` 是角色看市场的固定镜头；
- `opportunity_preferences` 是偏好的机会类型；
- `risk_triggers` 是主动降权信号；
- `evidence_hierarchy` 是证据排序；
- `reasoning_patterns` 是可复用推理模板；
- `anti_patterns` 是角色容易批评或避免的误区；
- `falsification_style` 决定角色如何设计证伪点。

## 7. 文章 Ingest 设计

### 7.1 输入形式

P0 支持：

- Markdown 文件；
- TXT 文件；
- 从剪贴板保存出的纯文本；
- 手工指定标题、日期、来源、角色 id。

暂不做：

- 网页自动抓取；
- 微信公众号自动爬取；
- 图片 OCR；
- 版权内容批量同步。

原因：第一版要先把认知抽取闭环跑通，自动采集会引入权限、登录、版权和清洗问题。

### 7.2 命令草案

```bash
python3 -m intelligence.cli perspective ingest \
  --user linxiaoqi5111 \
  --perspective blogger_x \
  --input /path/to/article.md \
  --title "某篇市场复盘" \
  --date 2026-07-03 \
  --source "某博主"
```

输出：

- 保存原文到 `articles/<perspective>/raw/`；
- 在 `manifest.jsonl` 追加文章元信息；
- 可选生成本篇文章的结构化抽取结果；
- 更新角色画像候选。

### 7.3 单篇文章抽取字段

每篇文章抽取：

```json
{
  "article_id": "pa-<hash>",
  "perspective_id": "blogger_x",
  "title": "某篇市场复盘",
  "date": "2026-07-03",
  "market_context": {
    "mentioned_indices": ["上证指数", "创业板指"],
    "mentioned_themes": ["AI硬件", "机器人"],
    "mentioned_stocks": ["中际旭创"]
  },
  "claims": [
    {
      "claim": "AI硬件不是结束，而是高位分歧后的核心回流",
      "claim_type": "market_phase",
      "evidence_used": ["核心股承接", "成交额维持"],
      "falsifiers": ["核心股跌破趋势", "后排无扩散"]
    }
  ],
  "reasoning_moves": [
    "先判断市场阶段",
    "再判断主线是否被资金继续选择",
    "最后看个股承接和扩散"
  ],
  "risk_notes": [
    "一致预期过高时不追后排"
  ],
  "profile_updates": [
    {
      "field": "risk_triggers",
      "value": "高位后排放量冲高回落",
      "supporting_quote": "原文短摘录"
    }
  ]
}
```

## 8. 多角色合议流程

### 8.1 角色配置

P0 默认支持四类角色：

- `user_framework`：用户自己的复盘框架；
- `blogger_x`：用户上传文章训练出的博主视角；
- `trend_trader`：趋势/盘面资金视角；
- `value_investor`：价值/护城河/估值视角，后续可做巴菲特风格 profile。

注意：巴菲特视角应叫“价值投资者视角”或“Buffett-inspired”，避免声称系统真正代表本人。

### 8.2 输入

用户可以问：

```bash
python3 -m intelligence.cli perspective debate \
  --user linxiaoqi5111 \
  --query "明天市场怎么看，AI硬件还能不能继续" \
  --perspective blogger_x \
  --perspective trend_trader \
  --perspective value_investor \
  --date 2026-07-03 \
  --compose
```

### 8.3 流程

```
用户问题
 -> QuestionPlan 识别问题类型
 -> 读取 ask 现有市场/知识库证据
 -> 对每个 perspective 召回画像和相似文章片段
 -> 角色独立作答
 -> 角色互相质询
 -> 裁判合议
 -> 输出主结论、分歧、验证指标、证伪点
 -> 可选写入 debates.jsonl
```

### 8.4 角色独立作答结构

每个角色必须输出：

- 核心判断；
- 该判断依据的事实；
- 该角色特有解释；
- 最关心的确认信号；
- 最关心的反证信号；
- 不确定性；
- 对其他角色可能的反驳。

### 8.5 互相质询结构

角色之间不是自由聊天，而是固定三问：

1. 你认为对方忽略了什么关键变量？
2. 你认为对方把哪类弱证据当强证据？
3. 如果明天只能看三个指标，你会用哪三个指标验证谁更接近现实？

### 8.6 裁判合议结构

裁判不是新角色，而是系统合成层。它必须输出：

- 哪些事实是所有角色都承认的；
- 主要分歧在哪里；
- 哪个角色在当前市场阶段更该被加权；
- 哪些结论需要降权；
- 最终的条件化判断；
- 盘后可验证指标。

## 9. 输出报告格式

P0 Markdown 输出：

```markdown
# Perspective Debate：<query>

## 0. 输入与证据边界
- 市场数据日期：
- 知识库/研报证据：
- 角色：
- 缺口：

## 1. 硬事实底座
- 市场阶段：
- 题材结构：
- 个股/板块信号：
- 外生变量：

## 2. 角色独立判断
### 2.1 <角色 A>
- 核心判断：
- 依据事实：
- 角色解释：
- 确认信号：
- 反证信号：
- 盲区：

### 2.2 <角色 B>
...

## 3. 多角色分歧表
| 分歧点 | 角色 A | 角色 B | 角色 C | 裁判处理 |
|---|---|---|---|---|

## 4. 裁判合议
- 最终判断：
- 采用哪些角色观点：
- 降权哪些角色观点：
- 明日验证指标：
- 错了怎么办：

## 5. 可证伪假设
| id | 假设 | 验证窗口 | 指标 | hit 条件 | miss 条件 |
|---|---|---|---|---|---|
```

## 10. 与现有模块的关系

### 10.1 接入 ask

现有 `ask --compose` 已有：

- QuestionPlan；
- DuckDB/知识库/Hybrid RAG；
- experience_cards；
- output_review；
- checkpoint；
- forecast ledger。

Perspective Lab 不应重写 ask，而是作为 ask 之后的“视角 overlay”。

P1 设计：

```bash
python3 -m intelligence.cli ask \
  "明天 AI硬件怎么看" \
  --compose \
  --user linxiaoqi5111 \
  --perspective blogger_x \
  --perspective trend_trader \
  --debate
```

### 10.2 接入 experience_cards

如果某个角色输出反复有效，可以沉淀为经验卡：

- 适用场景；
- 修正原则；
- 下次 prompt_rule。

但角色文章原文不应直接写入 experience_cards。经验卡只写验证后可复用的回答行为。

### 10.3 接入 checkpoint / forecast ledger

多角色合议中的“可证伪假设”可以登记到：

- checkpoint register：长期可证伪点；
- dual_blind_forecast：盘前/次日/多日市场判断台账。

这样能长期回答：

- 哪个角色在主升期更准；
- 哪个角色在高位分歧期更准；
- 哪个角色经常低估流动性；
- 哪个角色经常高估基本面。

### 10.4 接入 opinion-cross

opinion-cross 处理卖方/机构观点流，Perspective Lab 处理“角色分析框架”。二者可以互补：

- opinion-cross：这批观点里有哪些标的/硬证据/共识升温；
- perspective：不同角色如何解释这些观点和盘面。

## 11. P0 要做的内容

P0 目标：不用复杂索引，先跑通“角色画像 + 多角色合议 + 落档”。

### 11.1 文件与数据结构

新增：

- `intelligence/services/perspective_lab.py`
- `intelligence/tests/test_perspective_lab.py`
- `docs/learning/perspective-lab.md`

扩展：

- `intelligence/cli.py` 增加 `perspective` 子命令；
- `intelligence/users/README.md` 增加 perspectives 目录说明。

### 11.2 CLI 子命令

```bash
python3 -m intelligence.cli perspective init \
  --user linxiaoqi5111 \
  --id blogger_x \
  --name "某博主" \
  --type blogger
```

作用：

- 创建空 profile；
- 创建文章目录；
- 输出下一步 ingest 提示。

```bash
python3 -m intelligence.cli perspective ingest \
  --user linxiaoqi5111 \
  --perspective blogger_x \
  --input article.md \
  --title "文章标题" \
  --date 2026-07-03 \
  --source "某博主"
```

作用：

- 保存原文；
- 写 manifest；
- 用确定性规则做基础抽取；
- 如果配置 LLM，则生成 profile update candidate。

```bash
python3 -m intelligence.cli perspective profile \
  --user linxiaoqi5111 \
  --perspective blogger_x
```

作用：

- 查看角色画像；
- 展示样本数、置信度、已知缺口。

```bash
python3 -m intelligence.cli perspective debate \
  --user linxiaoqi5111 \
  --query "明天市场怎么看" \
  --perspective blogger_x \
  --perspective trend_trader \
  --perspective value_investor
```

作用：

- 生成多角色合议报告；
- P0 可先用用户提供的硬事实摘要；
- P1 再自动调用 ask 获取硬事实底座。

### 11.3 P0 不做的内容

P0 不做：

- 自动网页抓取；
- 微信文章自动采集；
- 向量索引；
- 长期胜率归因；
- UI；
- 自动把结论写入知识库实体页。

## 12. P1 要做的内容

P1 目标：接入现有 ask 和 RAG，让角色能基于真实硬数据和相似原文片段分析。

### 12.1 接入 ask

新增 AskOptions 字段：

- `perspectives: tuple[str, ...]`
- `use_perspective_debate: bool`

在 compose 前增加 perspective context：

```
QuestionPlan
 + 硬事实证据链
 + experience_cards
 + perspective profiles
 + perspective article snippets
 -> LLM compose
```

### 12.2 角色文章检索

P1 可以先用轻量 BM25，不急着接向量。

原因：

- 博主文章数量早期不会很大；
- BM25 对中文关键词、题材名、股票名、市场阶段词很实用；
- 后续再升级 hybrid 检索。

替代方案：

- 直接复用知识库 RAG：统一能力强，但会把私有博主文章和知识库事实索引混在一起，不推荐；
- 单独 SQLite FTS：比 JSONL 更工程化，但 P1 可能偏重；
- 单独向量库：适合文章数量上来以后再做。

### 12.3 输出前质检

新增 Perspective Review Gate：

- 角色有没有引用 profile 或文章片段；
- 有没有把角色观点写成事实；
- 有没有给出反证；
- 多角色是否真的有分歧，而不是三个人说同一句话；
- 裁判合议有没有说明加权理由。

## 13. P2 要做的内容

P2 目标：让角色视角可回测、可排名、可修正。

### 13.1 outcomes.jsonl

每次 debate 生成的假设和后续结果写入：

```json
{
  "debate_id": "pd-<hash>",
  "date": "2026-07-03",
  "query": "明天市场怎么看",
  "perspectives": ["blogger_x", "trend_trader", "value_investor"],
  "hypothesis_id": "h1",
  "perspective_id": "trend_trader",
  "claim": "AI硬件核心股分歧后回流",
  "window": "T+1",
  "metric": "核心股收盘强度+题材扩散",
  "verdict": "hit",
  "reason": "核心股收盘新高，后排涨停扩散"
}
```

### 13.2 角色胜率视图

按场景统计：

- 市场阶段；
- 题材类型；
- 高位/低位；
- 产业驱动/流动性驱动；
- T+1/T+3/T+5。

输出问题：

- 哪个角色更适合震荡期？
- 哪个角色更适合主升期？
- 哪个角色经常错在估值？
- 哪个角色经常错在盘面？

### 13.3 角色画像自动修正

当某个角色长期在某类场景失误，系统可以生成 profile patch candidate：

- 不是直接改画像；
- 先给用户审；
- 用户确认后再写入 profile。

## 14. 风险与边界

### 14.1 版权边界

用户上传的博主文章默认只做本地私用，不提交仓库，不公开输出大段原文。

输出报告只允许短摘录或摘要，不复制长文。

### 14.2 冒充风险

系统不能声称“我是某博主/巴菲特本人”。应使用：

- “某博主视角”；
- “基于已上传文章抽取的视角”；
- “Buffett-inspired 价值投资视角”。

### 14.3 样本不足

少于 3 篇文章时，`profile_confidence` 为 low。输出必须提示“样本不足，只能作为候选视角”。

### 14.4 事实污染

角色观点不得写入知识库事实层。硬事实必须走现有 ingest/l3/disclosure 流程。

### 14.5 过拟合

一个博主在某个阶段很准，不代表所有阶段都准。P2 必须按市场阶段分桶评估，避免全局胜率误导。

## 15. 测试计划

### 15.1 单元测试

新增 `intelligence/tests/test_perspective_lab.py`：

- profile id 路径安全；
- init 创建目录和默认 profile；
- ingest 写 manifest 且去重；
- 少样本 profile_confidence 为 low；
- debate 输出包含硬事实、角色判断、反证和合议；
- 禁止把角色观点标成 fact；
- 缺 profile 时给出明确错误；
- 文章不存在时不写半成品。

### 15.2 回归测试

更新：

- `intelligence/tests/test_ask_compose.py`：加 perspective context 不破坏原 ask；
- `intelligence/tests/test_userspace.py`：确认 perspectives 路径在用户命名空间内；
- CLI parseability 测试：确保新增子命令帮助能正常解析。

### 15.3 人工验收样例

准备 2 篇模拟博主文章：

- 盘面趋势型；
- 价值基本面型。

验收问题：

- 明天 AI硬件还能不能继续？

预期：

- 趋势型角色更关注核心股、新高、涨停扩散、成交承接；
- 价值型角色更关注估值、长期现金流、护城河和安全边际；
- 裁判能说明二者分歧，并给出 T+1 验证指标。

## 16. 实施顺序建议

第一阶段：P0 基础骨架

1. 新建 `perspective_lab.py`；
2. 定义 profile / article manifest / debate record 数据结构；
3. 实现 init/profile/ingest/debate 的确定性最小闭环；
4. 写 `docs/learning/perspective-lab.md`；
5. 写单测。

第二阶段：接 ask

1. AskOptions 增加 perspective 字段；
2. compose prompt 注入 perspective context；
3. debate 可自动使用 ask 的硬事实底座；
4. 加 review gate。

第三阶段：文章检索

1. 先做本地 BM25；
2. 输出召回片段和 citation；
3. 评估文章数量增加后是否升级 hybrid 检索。

第四阶段：验证闭环

1. debate 生成可证伪假设；
2. 接 checkpoint / dual_blind_forecast；
3. 写 outcomes；
4. 生成角色胜率报告。

## 17. 成功标准

P0 成功：

- 能创建角色；
- 能 ingest 文章；
- 能看到角色画像；
- 能用多个角色对同一问题输出结构化合议；
- 输出明确区分事实、角色解释和证伪条件。

P1 成功：

- `ask --compose --perspective blogger_x --perspective trend_trader --debate` 能运行；
- 角色输出引用硬事实和文章片段；
- 不破坏原有 ask 行为。

P2 成功：

- 能跨多次 debate 聚合角色表现；
- 能按市场阶段看角色胜率和盲区；
- 能把有效认知沉淀为 experience_cards 或用户确认后的长期方法论。

## 18. 已确认的取舍（2026-07-03 用户确认）

1. 第一批默认角色采用：`user_framework`、`trend_trader`、`value_investor`、`blogger_x`。
2. P0 只做确定性字段 + 人工编辑，LLM 抽取留开关（不作为 P0 依赖）。
3. 用户上传文章默认只保存在 `intelligence/users/<user>/perspectives/`，不进仓库。
4. debate 输出优先服务“行情前瞻”，个股/题材靠 QuestionPlan 自然覆盖，不单独做。
5. 可证伪假设 P0 先只写在报告里，接 checkpoint 放 P2。

审阅补充要求：

- `perspectives/` 目录同步加进 `.gitignore` 与 `users/README.md` 文件表；
- `debates.jsonl` / `outcomes.jsonl` 从 P0 起带 `schema_version`；
- 裁判合议需输出“若各角色结论一致则本次辩论无增量”的退化提示，防止假分歧。
