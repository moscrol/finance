# Workbench P0 Routing Maturity Implementation Plan

> **执行说明：** 本计划把总体设计中的 P0 路由成熟度拆成可独立验证的小步。严格采用 TDD：每个行为先写失败测试，再写最小实现，最后重构和提交。不要在本批顺手实现 P0.5/P1/P2。

**目标：** 让本地工作台对个股、板块、产业链关系和省略式追问形成统一、可解释、可回归的查询解析结果，并把受治理的金融研究稳定交给唯一 owner workflow。

**架构原则：** 新增一个轻量 `QueryResolver` 作为查询入口，先做确定性实体锚定和指代分类，再调用现有 `understand_query` 生成 `QueryEnvelope`。`TurnController` 只根据统一解析结果选择 lane/owner，不再自行重复解析；`research_contract` 和 `conversation_orchestrator` 复用同一套追问判定。实体词典按 relation 文件指纹缓存，避免每次请求读取大 JSON。低置信度 LLM 分类器保留为后续增强点，本批不引入新的模型依赖。

**技术栈：** Python 3.11、标准库 `dataclasses/re/threading/pathlib`、现有 `KnowledgeAdapter`、pytest、现有 Workbench 单元/集成测试。

**不在本批：** 可终止子进程、BGE-m3 常驻 worker、AkShare 独立环境、followups v2、胜率看板、canonical 8792 部署。

---

## Task 1：建立业务黄金路由回归集

**文件：**

- 新建：`intelligence/tests/fixtures/workbench_routing_golden.json`
- 新建：`intelligence/tests/test_workbench_routing_golden.py`
- 参考：`intelligence/tests/test_turn_controller.py`
- 参考：`intelligence/services/research_contract.py`

### Step 1：写最小黄金样本

JSON 用业务语言描述预期，不绑定内部正则：

```json
[
  {
    "id": "stock_entity_opinion",
    "query": "中际旭创怎么看",
    "expected": {
      "lane": "research",
      "question_type": "stock_deep_dive",
      "subject": "中际旭创",
      "owner": "stock-deep-dive"
    }
  },
  {
    "id": "theme_opinion",
    "query": "光模块怎么看",
    "expected": {
      "lane": "research",
      "question_type": "theme_analysis",
      "subject": "光模块",
      "owner": "theme-research"
    }
  },
  {
    "id": "logic_followup",
    "query": "这个逻辑呢",
    "previous": {
      "subject": "中际旭创",
      "question_type": "stock_deep_dive",
      "owner": "stock-deep-dive"
    },
    "expected": {
      "lane": "research",
      "subject": "中际旭创",
      "owner": "stock-deep-dive",
      "inherited": true
    }
  },
  {
    "id": "chain_followup",
    "query": "这条链有哪些公司",
    "previous": {
      "subject": "光模块",
      "question_type": "theme_analysis",
      "owner": "theme-research"
    },
    "expected": {
      "lane": "research",
      "subject": "光模块",
      "owner": "theme-research",
      "operators": ["company_mapping"],
      "capabilities": ["graph"]
    }
  },
  {
    "id": "marginal_change_followup",
    "query": "边际变化呢",
    "previous": {
      "subject": "中际旭创",
      "question_type": "stock_deep_dive",
      "owner": "stock-deep-dive"
    },
    "expected": {
      "lane": "research",
      "subject": "中际旭创",
      "owner": "stock-deep-dive",
      "operators": ["market_change"]
    }
  }
]
```

再加入两个反例：无上下文的“这个逻辑呢”必须澄清；“你怎么看”仍必须澄清，防止扩大召回后吞掉普通闲聊。

### Step 2：写参数化测试加载器

```python
@pytest.mark.parametrize("case", load_cases())
def test_workbench_routing_golden(case, monkeypatch, wiki_root):
    monkeypatch.setenv("KNOWLEDGE_WIKI", str(wiki_root))
    previous = build_previous_intent(case.get("previous"))
    decision = decide_turn(
        case["query"],
        previous_intent=previous,
        previous_turn_id="golden-previous" if previous else None,
        llm_complete=_no_llm,
    )
    assert_decision(case["expected"], decision)
```

fixture 只写一个极小 `relations/entity_exposures.json` 与 `aliases.json`，包含“中际旭创→CPO/光模块”，不得读取生产知识库正文。

### Step 3：确认测试按预期失败

运行：

```bash
python -m pytest intelligence/tests/test_workbench_routing_golden.py -q
```

预期：个股/板块“怎么看”、三类追问至少 4 个失败；两个反例保持通过。

### Step 4：提交测试基线

```bash
git add intelligence/tests/fixtures/workbench_routing_golden.json \
  intelligence/tests/test_workbench_routing_golden.py
git commit -m "test: add workbench routing golden set"
```

---

## Task 2：给实体锚定增加文件指纹缓存

**文件：**

- 修改：`intelligence/services/entity_anchor.py`
- 修改：`intelligence/tests/test_entity_anchor.py`

### Step 1：先写缓存行为测试

新增三项：同一文件连续解析只加载一次；文件 `mtime_ns/size` 变化后刷新；两个 wiki root 的缓存互不污染。

```python
def test_entity_records_are_cached_until_relation_changes(monkeypatch, knowledge):
    calls = 0
    original = knowledge.load_relation

    def counted(name):
        nonlocal calls
        calls += 1
        return original(name)

    monkeypatch.setattr(KnowledgeAdapter, "load_relation", lambda self, name: counted(name))
    resolve_entity_anchor("中际旭创怎么看", knowledge)
    resolve_entity_anchor("中际旭创估值", knowledge)
    assert calls == 1
```

### Step 2：确认失败

```bash
python -m pytest intelligence/tests/test_entity_anchor.py -q
```

预期：缓存测试失败，原有锚定测试通过。

### Step 3：实现线程安全缓存

在 `entity_anchor.py` 中引入不可变缓存项，不缓存整个 `KnowledgeAdapter`：

```python
@dataclass(frozen=True)
class _EntityLexiconCacheEntry:
    fingerprint: tuple[int, int]
    records: tuple[_EntityRecord, ...]

_LEXICON_CACHE: dict[str, _EntityLexiconCacheEntry] = {}
_LEXICON_LOCK = threading.RLock()


def _relation_fingerprint(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _cached_entity_records(knowledge: KnowledgeAdapter) -> tuple[_EntityRecord, ...]:
    path = knowledge.relation_path("entity_exposures").resolve()
    fingerprint = _relation_fingerprint(path)
    if fingerprint is None:
        return ()
    key = str(path)
    with _LEXICON_LOCK:
        cached = _LEXICON_CACHE.get(key)
        if cached and cached.fingerprint == fingerprint:
            return cached.records
        records = tuple(_load_entity_records(knowledge))
        _LEXICON_CACHE[key] = _EntityLexiconCacheEntry(fingerprint, records)
        return records
```

`resolve_entity_anchor` 改用 `_cached_entity_records`。测试辅助函数可以清缓存，但生产 API 不暴露可变内部状态。

### Step 4：运行测试并提交

```bash
python -m pytest intelligence/tests/test_entity_anchor.py -q
git add intelligence/services/entity_anchor.py intelligence/tests/test_entity_anchor.py
git commit -m "perf: cache entity anchor lexicon by relation fingerprint"
```

---

## Task 3：建立统一 QueryResolver 与指代分类

**文件：**

- 新建：`intelligence/services/query_resolution.py`
- 新建：`intelligence/tests/test_query_resolution.py`
- 修改：`intelligence/services/query_understanding.py`
- 修改：`intelligence/tests/test_query_understanding.py`

### Step 1：先写 resolver 契约测试

覆盖：名称/代码命中实体；“这个逻辑/这个方向/这条链/边际变化”被标为 context-dependent；“这个公司”兼容；普通完整问题不是追问。

```python
def test_resolver_anchors_known_entity(knowledge):
    resolution = QueryResolver(knowledge).resolve("中际旭创怎么看")
    assert resolution.envelope.subject == "中际旭创"
    assert resolution.envelope.subject_kind == "entity"
    assert resolution.reference_kind == "none"


@pytest.mark.parametrize(
    ("query", "kind"),
    [
        ("这个逻辑呢", "logic"),
        ("这个方向怎么看", "direction"),
        ("这条链有哪些公司", "chain"),
        ("边际变化呢", "market_change"),
    ],
)
def test_resolver_classifies_contextual_reference(query, kind, knowledge):
    resolution = QueryResolver(knowledge).resolve(query)
    assert resolution.context_dependent is True
    assert resolution.reference_kind == kind
```

### Step 2：确认失败

```bash
python -m pytest intelligence/tests/test_query_resolution.py \
  intelligence/tests/test_query_understanding.py -q
```

### Step 3：实现统一解析结果

```python
ReferenceKind = Literal[
    "none", "entity_pronoun", "logic", "direction", "chain",
    "market_change", "continuation"
]

@dataclass(frozen=True)
class QueryResolution:
    envelope: QueryEnvelope
    anchor: EntityAnchor | None
    reference_kind: ReferenceKind = "none"
    context_dependent: bool = False


class QueryResolver:
    def __init__(self, knowledge: KnowledgeAdapter | None = None):
        self.knowledge = knowledge or KnowledgeAdapter()

    def resolve(self, query: str) -> QueryResolution:
        anchor = resolve_entity_anchor(query, self.knowledge)
        reference_kind = classify_reference(query)
        return QueryResolution(
            envelope=understand_query(query, anchor=anchor),
            anchor=anchor,
            reference_kind=reference_kind,
            context_dependent=reference_kind != "none",
        )
```

正则只负责语法线索，不直接决定 owner。所有追问词放在该模块，供 controller/contract/orchestrator 共享；不要在三处复制。

### Step 4：扩展研究算子

在 `ResearchOperator` 增加：

```python
"relation",
"company_mapping",
"market_change",
```

规则：

- “上游/下游/供应/客户/关系/产业链位置” → `relation`
- “有哪些公司/受益公司/公司映射” → `company_mapping`
- “边际变化/最近变化/预期差变化” → `market_change`

对应 required outputs 为 `relation_map`、`company_mapping`、`market_change`。这些是结构化研究要求，不应伪装成 question type。

### Step 5：跑测试并提交

```bash
python -m pytest intelligence/tests/test_query_resolution.py \
  intelligence/tests/test_query_understanding.py -q
git add intelligence/services/query_resolution.py \
  intelligence/services/query_understanding.py \
  intelligence/tests/test_query_resolution.py \
  intelligence/tests/test_query_understanding.py
git commit -m "feat: add unified financial query resolver"
```

---

## Task 4：让 ResearchContract 复用统一追问语义

**文件：**

- 修改：`intelligence/services/research_contract.py`
- 修改：`intelligence/tests/test_research_contract.py`

### Step 1：先补继承测试

参数化验证三种新追问继承 `primary_subject`、`answer_owner`、`evidence_atom_ids` 和 `previous_turn_id`；无 previous intent 时不能凭空继承。

```python
@pytest.mark.parametrize(
    "query",
    ("这个逻辑呢", "这个方向怎么看", "这条链有哪些公司", "边际变化呢"),
)
def test_contextual_reference_inherits_governed_owner(query, previous_intent):
    resolution = QueryResolver(knowledge).resolve(query)
    intent = build_turn_intent(
        query,
        resolution.envelope,
        previous_intent=previous_intent,
        previous_turn_id="turn-1",
        resolution=resolution,
    )
    assert intent.primary_subject == previous_intent.primary_subject
    assert intent.answer_owner == previous_intent.answer_owner
    assert intent.inherited_from_turn == "turn-1"
```

### Step 2：删除重复 pattern，接入 resolution

`build_turn_intent` 新增向后兼容的可选参数：

```python
def build_turn_intent(..., resolution: QueryResolution | None = None) -> TurnIntent:
```

有 resolution 时使用 `resolution.context_dependent/reference_kind`；旧调用方未传时调用共享 `classify_reference`，避免 API 一次性破坏。`_CONTEXT_DEPENDENT_RESEARCH_PATTERN` 只保留研究语义项，不再保存指代词。

### Step 3：验证并提交

```bash
python -m pytest intelligence/tests/test_research_contract.py -q
git add intelligence/services/research_contract.py \
  intelligence/tests/test_research_contract.py
git commit -m "fix: inherit research owner for contextual references"
```

---

## Task 5：Controller 单次解析并正确选择 owner

**文件：**

- 修改：`intelligence/services/turn_controller.py`
- 修改：`intelligence/tests/test_turn_controller.py`

### Step 1：先写 controller 失败测试

覆盖：

- 已登记实体 + “怎么看” → research / stock-deep-dive。
- 已登记主题 + “怎么看” → research / theme-research。
- 产业链公司映射 → graph capability。
- 省略式追问继承原 owner，不落到 knowledge/chat。
- `QueryResolver.resolve` 每个 `decide_turn` 只调用一次。

### Step 2：确认失败

```bash
python -m pytest intelligence/tests/test_turn_controller.py -q
```

### Step 3：把解析结果贯穿 controller

`decide_turn` 新增可注入 resolver，方便单测和未来 LLM fallback：

```python
def decide_turn(..., resolver: QueryResolver | None = None) -> TurnDecision:
    resolution = (resolver or QueryResolver()).resolve(query)
    envelope = resolution.envelope
    intent = build_turn_intent(..., resolution=resolution)
    effective_query = contextualize_intent_query(query, intent)
    deterministic = _deterministic_decision(
        effective_query,
        envelope=envelope,
        ...,
    )
```

`_deterministic_decision` 与 `_safe_fallback` 接收已解析 envelope，删除内部 `understand_query`。当 intent 发生继承时，用 intent 修正 subject/owner，不重新对拼接后的 query 做实体识别。

能力规则：`relation` 或 `company_mapping` 算子必须包含 `graph`；owner 仍由 `QUESTION_OWNER_SKILLS` 决定，算子不能创建第二个回答 owner。

主题识别只使用现有 theme config/alias relation 的确定性词典。若“光模块”不在现有配置，测试 fixture 通过 aliases 登记；不要把某个题材硬编码进正则。

### Step 4：验证并提交

```bash
python -m pytest intelligence/tests/test_turn_controller.py \
  intelligence/tests/test_workbench_routing_golden.py -q
git add intelligence/services/turn_controller.py \
  intelligence/tests/test_turn_controller.py
git commit -m "fix: route entities themes and relations through one controller"
```

---

## Task 6：Orchestrator 复用同一追问判定

**文件：**

- 修改：`intelligence/services/conversation_orchestrator.py`
- 修改：`intelligence/tests/test_conversation_orchestrator.py`

### Step 1：先补上下文化测试

```python
@pytest.mark.parametrize(
    "query",
    ("这个逻辑呢", "这个方向怎么看", "这条链有哪些公司", "边际变化呢"),
)
def test_contextualize_new_reference_forms(query, context):
    contextual = contextualize_follow_up_query(query, context)
    assert contextual.endswith(f"追问：{query}")
```

并验证完整新主题问题不会错误拼接上一问。

### Step 2：确认失败并实现

删除 orchestrator 的 `_FOLLOW_UP_REFERENCE_PATTERN` / `_FOLLOW_UP_CONTINUATION_PATTERN`，改为调用 `classify_reference`/`is_contextual_reference`。保持 `contextualize_follow_up_query` 现有返回格式，避免影响提示词和日志契约。

### Step 3：验证并提交

```bash
python -m pytest intelligence/tests/test_conversation_orchestrator.py -q
git add intelligence/services/conversation_orchestrator.py \
  intelligence/tests/test_conversation_orchestrator.py
git commit -m "refactor: share contextual follow-up classification"
```

---

## Task 7：全量回归、业务回放与文档收口

**文件：**

- 修改：`docs/superpowers/specs/2026-07-16-workbench-product-maturity-design.md`
- 新建：`docs/verification/workbench-routing-p0-2026-07-16.md`

### Step 1：运行聚焦测试

```bash
python -m pytest \
  intelligence/tests/test_entity_anchor.py \
  intelligence/tests/test_query_resolution.py \
  intelligence/tests/test_query_understanding.py \
  intelligence/tests/test_research_contract.py \
  intelligence/tests/test_turn_controller.py \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_skill_router.py \
  intelligence/tests/test_workbench_routing_golden.py -q
```

预期：全绿。

### Step 2：运行项目既有静态/契约检查

先从仓库真实 CI 配置确认命令，不猜测；至少执行 main 上对应的：

```bash
rg -n "registry-check|workbench-check" .github Makefile pyproject.toml scripts
```

然后执行查到的本地等价命令。若 CI 依赖外部服务，记录“未在本地运行”的原因，不伪报通过。

### Step 3：跑黄金回放并保存机器可读摘要

验证文档记录每个 case 的：query、previous subject、lane、question type、subject、owner、operators、capabilities、是否继承。验收门槛：

- 黄金样本 100% 命中。
- 两个反例 100% 不误路由。
- 实体 relation 在未变化时单进程只解析一次。
- 无新增网络/模型依赖。

### Step 4：自审差异与风险文件

```bash
git diff --check
git status --short
git diff --stat origin/main...HEAD
git diff --name-only origin/main...HEAD | rg \
  '(^|/)(\.env|mcp_config\.json|feishu_config\.json|\.DS_Store)|\.(pdf|zip|duckdb|db|sqlite|pptx)$' \
  && exit 1 || true
```

检查点：没有把生产 relation JSON、缓存、数据库、密钥或虚拟环境纳入提交。

### Step 5：更新设计状态并提交

在总体设计中把 P0 标记为“代码完成，待 canonical 灰度”，把验证文档链接进去。

```bash
git add docs/superpowers/specs/2026-07-16-workbench-product-maturity-design.md \
  docs/verification/workbench-routing-p0-2026-07-16.md
git commit -m "docs: record P0 routing verification"
```

---

## 完成定义

P0 只有同时满足以下条件才算完成：

1. “中际旭创怎么看”稳定进入 `stock-deep-dive`。
2. “光模块怎么看”稳定进入 `theme-research`。
3. “这个逻辑/这个方向/这条链/边际变化”在有上下文时继承 subject、owner、evidence set。
4. 相同短句无上下文时澄清，不凭空猜主题。
5. 关系/公司映射问题显式请求 graph capability。
6. controller 单次请求只产生一个统一解析结果。
7. 实体 relation 使用文件指纹缓存，relation 变化后自动刷新。
8. 聚焦回归、既有 registry/workbench 检查和风险文件检查通过。

P0 完成后仍不部署 canonical 8792；先按同样方式制定并完成 P0.5/P1/P2，最后统一执行 runbook 灰度和黄金回放。
