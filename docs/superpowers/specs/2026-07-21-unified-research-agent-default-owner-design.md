# Unified Research Agent 默认 Owner 设计

## 目标

让金融 Workbench 在未命中确定性头部任务或用户显式工作流时，默认由一个受预算、白名单和证据门禁约束的 Research Agent 负责研究。新增工具和约束不得替换模型对用户问题的理解，也不得把不匹配的日报/题材模板当作终端答案。

## 现状问题

- `conversation_orchestrator.py` 只把 `general_finance_qa`、`market_cause`、`fact_check` 交给 GenericResearchOwner；其它 ownerless research 仍会进入语义 skill router。
- `agent_research.should_run()` 在 auto 模式只看 `web_search`/`market_news` 能力，因此行情、情景、比较和关系长尾通常不会启动 Agent loop。
- `SkillDefinition` 没有 workflow/profile/terminal 角色和 question-type 兼容字段；任意带 `answer_contract` 的 skill 都可能被当作终端 owner。
- `ResearchState` 虽有 hypotheses 和支持/反驳字段，但通用契约很少初始化假设，工具动作也没有把 observation 绑定到假设，Agent 最终只提交一段短 assessment。

## 设计

### 控制面

Controller 只负责确定性头部识别、显式工作流识别和研究类型的粗粒度裁决。路由表中的 `answer_owner` 仍可指定专项 owner；没有 owner 的 research 一律进入 GenericResearchOwner，不再由语义 skill router 重新抢答案控制权。

`daily-agent`、`daily-review` 和其它日报型技能只允许在 workflow lane 或用户显式选择时终结答案。终端 skill 必须声明可接受的 question type；orchestrator 在消费 `answer_contract` 前执行兼容性校验，不匹配则转 GenericResearchOwner。

### 研究面

GenericResearchOwner 先为问题生成保守 ResearchTaskContract：直接回答目标、子问题、候选假设、必要证据、时效和档位。LLM 只能在能力白名单和现有 deadline 内提出计划；解析失败时使用规则契约。

Agent loop 不再是 Ask 末端的“补检索 provider”，而是 ownerless research 的主循环。工具 observation 进入同一 `ResearchState`，记录支持/反驳、gap、query ledger 和 ProviderTrace。`finish(sufficient=true)` 只是建议，completion evaluator 逐项检查 required outputs 后才决定 completed/partial/gap。

### 出口

事实、数字、日期和关系继续必须绑定 EvidenceAtom。推论允许由 Agent 生成，但必须指向支持证据和反证；不强制每句过渡话都复制 registry。完成门和 grounding 门分离：先判断是否回答了问题，再判断写出的事实是否有依据。失败时保留已验证判断和业务化缺口，不回退到无关模板。

## 范围与非目标

本批先完成单 Owner、默认入口和长尾评测，不引入异步 sub-agent 或新 Agent 框架；已有确定性技术位、精确取数、显式日报和专项 owner 保持回归兼容。8792 正式 runtime 不在本批直接切换。

## 验收

1. “明天是反弹还是继续下跌，分别给出理由”不再进入 Daily Agent，至少出现两个情景分支和当前市场证据/缺口。
2. 任意不在路由表的金融长尾问题仍能进入 GenericResearchOwner，工具至少执行一次或明确说明无法取得数据。
3. Agent 可改写查询或换工具；重复查询、非法工具和超预算动作被拦截。
4. 完成状态、假设支持/反驳、tool step 和 provider trace 串在同一个 run。
5. 主文不出现 `研究雷达`、工具名、DuckDB、RAG、证据计数等控制面泄漏，除非用户明确询问系统方法。
6. 全套 intelligence 测试和隔离端口 E2E 通过；无回归到已修复的 market_technical、market_cause、关系题和方法论题。
