# L3 Evidence Orchestrator

## 目标

把最新公告、问询函、交易所互动问答这类 L3 官方证据接入问答闭环，但不把每天海量短期材料全部塞进知识库或向量库。

人话版：知识库负责稳定资产和结构化认知；外接工具负责“用时查最新硬证据”；真正有沉淀价值的事实，再进入 entity/evidence_index。

## 当前实现

金融 repo 新增 `intelligence/services/l3_evidence.py`，接在 `ask --compose` 的证据链之后：

1. `answer_orchestrator` 先判断问题类型。
2. `l3_evidence.detect_l3_gaps` 检查是否缺客户、订单、量产、产能、公告、问询函等硬证据。
3. 如果用户显式打开 `--l3-lookup`，则按命令模板调用外接 CLI。
4. CLI 返回会被归一成 `L3EvidenceBundle`，注入 compose prompt 和结构化证据链。
5. 如果没有配置命令、超时或失败，只写 warning，回答降级但不中断。

## 使用方式

默认入口已经按验证过的组合 CLI 固化：

```bash
{python} -m disclosure_lookup.cli company {company} --days 30 --source cninfo,sse_einteract
```

直接打开开关即可：

```bash
python3 -m intelligence.cli ask "深挖瑞华泰，重点看客户和订单" \
  --compose \
  --l3-lookup \
  --l3-lookup-timeout 480 \
  --l3-lookup-limit 5
```

默认 `{python}` 会使用当前运行 finance CLI 的同一个解释器，也就是 Python 里的 `sys.executable`。如果 `disclosure_lookup` 安装在另一套 venv，显式指定：

```bash
export FINANCE_L3_PYTHON='/path/to/disclosure-lookup/.venv/bin/python'
python3 -m intelligence.cli ask "深挖瑞华泰，重点看客户和订单" --compose --l3-lookup
```

如果 `disclosure_lookup` 没有 pip install，只是存在另一个 repo 目录里，还需要告诉子进程去哪里找包：

```bash
export FINANCE_L3_PYTHON='/Users/a77/worktrees/finhot-disclosure-lookup/finhot/.venv-disclosure/bin/python'
export FINANCE_L3_PYTHONPATH='/Users/a77/worktrees/finhot-disclosure-lookup/finhot'
export FINANCE_L3_CWD='/Users/a77/worktrees/finhot-disclosure-lookup/finhot'
```

人话版：`FINANCE_L3_PYTHON` 决定“用哪个 Python 跑工具”；`FINANCE_L3_PYTHONPATH` 决定“这个 Python 到哪里找 `disclosure_lookup` 包”；`FINANCE_L3_CWD` 决定“工具从哪个工作目录启动”。这三个变量解决的是多 repo 本地开发最常见的问题：代码能在工具仓跑通，但主项目 subprocess 找不到模块。

如果要覆盖默认组合命令，可配置：

```bash
export FINANCE_L3_COMPANY_CMD='{python_sh} -m disclosure_lookup.cli company {company_sh} --days {days} --source {sources}'
```

也可以退回单源命令：

```bash
export FINANCE_L3_COMPANY_CMD=''
export FINANCE_L3_CNINFO_CMD='python -m disclosure_lookup cninfo --query {query_sh} --limit {limit}'
export FINANCE_L3_SSE_EINTERACT_CMD='python -m disclosure_lookup sse-einteract --query {query_sh} --limit {limit}'
```

模板变量：

- `{query}` / `{query_sh}`：原始问题，后者适合命令行安全引用。
- `{python}` / `{python_sh}`：运行 disclosure lookup 的 Python 解释器，默认 `sys.executable`，可由 `FINANCE_L3_PYTHON` 覆盖。
- `{company}` / `{company_sh}`：从问题粗提取的公司名；如果提取不到则退回原始问题。
- `{stock_code}` / `{stock_code_sh}`：从问题中粗提取的 6 位代码。
- `{stock_name}` / `{stock_name_sh}`：从问题中粗提取的公司名。
- `{sources}` / `{sources_sh}`：本轮需要的源，例如 `cninfo,sse_einteract`。
- `{limit}`：最多返回条数。
- `{days}`：查询近 N 天，默认 30。

已验证口径：

- 分支：`origin/feat/disclosure-lookup`，提交 `89aefd4`。
- `cninfo` 单源：约 1.4 秒返回瑞华泰公告。
- `sse_einteract` 首跑：会构建 `sse_uids.json`，2304 条映射，`688323 -> 201868`；实测静默等待 411.5 秒，不是坏了。
- `sse_einteract` 缓存后：约 24 秒返回大量互动问答，含 `[P1] / [P2]`。
- 组合命令缓存后跑通：

```bash
python -m disclosure_lookup.cli company 瑞华泰 --days 30 --source cninfo,sse_einteract
```

工程提示：SSE 首跑体验容易误判卡死，后续更好的改法是给 uid 缓存构建加逐页进度日志，或改成按股票代码定向解析 uid，避免 72 页全量扫描。

## 推荐缓存策略

这里的“缓存”分三层，不等于把公告、互动易、问询函全部入库或全部向量化。

第一层是工具内部缓存。`sse_einteract` 最慢的是把股票代码映射到交易所 uid，首跑会构建 `sse_uids.json`。这个缓存应该预热和复用，而不是每次问答时重建。理想做法是每日或每周定时刷新一次；问答时只读现成缓存。

第二层是运行时查询结果缓存。按 `(source, stock_code/company, days)` 做短 TTL 缓存，例如当天有效。这样同一只股票一天内多次深挖，不必重复打公告/互动易。它保存的是原始工具返回和解析摘要，定位是“可复查的短期证据”，不是长期知识资产。

第三层才是知识库沉淀。只有订单、合同、中标、客户验证、量产、产能、问询函关键回复、风险澄清这类能改变公司判断的硬事实，才从运行时结果里提炼进 `evidence_index` / entity 页面。短期提示公告、重复可转债公告、泛泛互动问答，不进入长期 RAG。

运行时查询结果缓存可用环境变量打开：

```bash
export FINANCE_L3_CACHE_DIR="$HOME/.cache/finance-workspace/l3-evidence"
export FINANCE_L3_CACHE_TTL_SECONDS=86400
```

缓存 key 会包含 source、渲染后的命令、工作目录和 `PYTHONPATH`。这样同一家公司、同一源、同一命令可以复用；但如果换了查询天数、换了 source 或换了工具路径，会自动变成另一份缓存。当前只缓存成功 stdout，不缓存失败，避免把网络抖动、登录态异常或限流错误固化。

当前同步问答建议采用“两档查询”：

```bash
# 快路径：默认用于 ask --l3-lookup，1-2 秒级，先查公告/问询函/风险提示
export FINANCE_L3_COMPANY_CMD='{python_sh} -m disclosure_lookup.cli company {company_sh} --days {days} --source cninfo'
export FINANCE_L3_LOOKUP_TIMEOUT=60

# 慢路径：需要互动易/董秘问答时显式打开，或在缓存预热后打开
export FINANCE_L3_COMPANY_CMD='{python_sh} -m disclosure_lookup.cli company {company_sh} --days {days} --source cninfo,sse_einteract'
export FINANCE_L3_LOOKUP_TIMEOUT=480
```

为什么不把 `sse_einteract` 默认放进每次同步问答？因为首跑可能接近 7 分钟，且互动问答噪音更高。更合理的是：公告快查先约束事实边界；当问题明确问客户、订单、材料国产化、董秘回复、公司口径，或者公告没有回答关键缺口时，再走 SSE 慢源。

## L3 ingest CLI

`ask --l3-lookup` 是“回答时临时补证据”，`l3-ingest` 是“把有价值公告/互动易抽成可复核候选事实”。两者共用底层 `disclosure_lookup`，但目的不同：

- `ask --l3-lookup`：服务当前回答，证据只注入 prompt。
- `l3-ingest company`：服务知识沉淀，生成候选 payload，默认不写知识库。

P0 命令：

```bash
python3 -m intelligence.cli l3-ingest company 瑞华泰 \
  --source cninfo \
  --days 30 \
  --limit 20 \
  --out-json exports/l3-ingest/瑞华泰-20260701.json
```

输出分三层：

- `raw_items`：工具原始返回，保留来源、标题、摘要、链接和 raw。
- `candidates`：命中订单/合同/客户/认证/量产/产能/收入/出货/问询函/风险澄清等高价值关键词的 L3 候选。
- `rejected`：可转债赎回提示、例行治理公告、低信号互动问答等默认不沉淀项。

规则门槛：

- `order_or_contract`、`customer_validation`、`financial_or_shipment_metric` 默认为高硬度候选。
- `capacity_or_project_progress` 默认是中硬度候选，因为项目/产能进展还要看是否真实转成收入或订单。
- `risk_or_regulatory_boundary` 是 L3 official 边界证据，用于约束预期、澄清和证伪。
- `capital_market_or_governance_noise` / `low_signal` 只保留在 rejected，不进入长期知识库。

P1 apply 已接上，但默认仍是 dry-run：

```bash
python3 -m intelligence.cli l3-ingest apply exports/l3-ingest/瑞华泰-20260701.json \
  --kb-wiki /path/to/knowledge-base-private/wiki
```

真正写入需要显式加 `--apply`：

```bash
python3 -m intelligence.cli l3-ingest apply exports/l3-ingest/瑞华泰-20260701.json \
  --kb-wiki /path/to/knowledge-base-private/wiki \
  --apply
```

当前 P1 的写入边界是保守的：

- 写入 `wiki/sources/<公司>_L3官方证据_<日期>.md`，形成可被全文/RAG召回的 L3 证据候选 source note。
- 更新 `wiki/entities/<公司>.md` 的 `## L3 官方证据` 摘要段，便于个股问答直接看到官方证据边界。
- 不直接写 `relations/evidence_index`，因为这会影响 Theme Radar 排序和图谱权重；需要后续人工复核或走 knowledge-base `disclosure-archive` reviewed apply。

`--reviewed` 只表示本次候选已人工复核，会把 source note 的 `review_required` 标为 `false`。如果没有 `--reviewed`，即使执行了 `--apply`，也仍保留 `review_required: true`，提醒后续不要把标题级抓取误当公告全文精读。

## 技术选型

**当前选 CLI 适配器。**

优点：复用现有外接公告工具；测试可以 mock `subprocess.run`；不要求常驻服务；适合本地多 repo 工作流。

缺点：跨 Agent/跨 IDE 复用不如 API 顺滑；命令模板需要配置；进程启动有开销。

**替代方案 1：HTTP API。**

优点：Claude、Codex、网站后端、finhot 都能统一调用；权限、缓存、限流可以集中管理。

缺点：要维护服务进程和部署；本地开发多一层基础设施。

**替代方案 2：MCP/tool plugin。**

优点：最贴近 LLM tool use，工具 schema 清晰，适合让模型自主选择工具。

缺点：需要 MCP 运行时和工具注册；对普通脚本/批处理不如 API 直接。

当前路径是：CLI 先打通闭环，API/MCP 后续升级。

## 触发原则

P0 触发：

- 个股深挖里缺客户、订单、合同、中标、量产、产能、投产、认证、出货等硬证据。
- 用户显式问公告、问询函、风险提示、澄清、异动。
- 新闻/公告影响题需要确认官方源。

P1 触发：

- 产业逻辑成立但证据主要来自研报/观点，需要互动易或公告验证。
- 高位票需要确认是否存在风险提示、澄清、减持、问询函。

P2 不触发：

- 纯市场风格、双红题材、策略方法论讨论。
- 本地年报/公告/互动易证据已足够，且问题不要求最新验证。

## 知识库分工

不要把最新公告/互动易全部向量化，原因是信息量爆炸且时效快，容易污染长期知识库。

推荐分层：

- 运行时工具：查最新公告、互动易、问询函。
- 短期缓存：保存原始查询结果和命中摘要，便于复查。
- L3 事实沉淀：只有订单、合同、客户验证、量产、产能、问询函关键回复等可复用硬事实，才进入 `evidence_index` / entity 页面。
- 经验卡片：回答中暴露出的推理缺口、优秀样板、用户纠偏，进入项目学习层。

## 可复用知识点

这是通用 Agent 工具编排模式：

`问题解析 -> 证据缺口检测 -> 工具路由 -> 工具适配器 -> 证据归一 -> 回答注入 -> 价值事实沉淀`

它也能迁移到舆情监控、法律检索、医学文献、企业内部知识库和代码审查工具链。
