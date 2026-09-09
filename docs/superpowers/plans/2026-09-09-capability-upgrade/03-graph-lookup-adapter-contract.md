# 03 → 06 · graph_lookup 适配合同（知识库研究地图）

本文是 03 单交给 06 的**接入合同**，不是实现。金融侧 `intelligence/adapters/knowledge.py::KnowledgeAdapter`（`get_concept_matches` / `get_exposure_matches` / `get_evidence`）与 `agent_research.build_graph_tools` 的 `graph_lookup` 本单未改；由 06 唯一接入，避免与 01（语义准入）双改同一函数。

## 提供方（知识库仓，分支 `feat/research-map-03`）

一条 CLI、一套 Python API，全部只读、零外呼、零模型调用：

```bash
python3 <KB>/scripts/query_relations.py research-map <mode> ... --json [--wiki-root <KB>/wiki] [--as-of YYYY-MM-DD]
```

| mode | 参数 | 返回 `schema` | 回答什么 |
|---|---|---|---|
| `package` | `--theme` `--top` | `research_map.package/1` | 题材六块：scope / chain / variables / companies / conditions / recent / gaps / provenance |
| `view` | `--theme` `--no-refresh` | `{status: fresh|stale|uncached|missing, view, recheck[], diff?}` | 同上，但走派生视图：陈旧时给「回原页查证」清单并重建 |
| `trace --down` | 概念 / 需求词 `--depth` `--include-generic` | `research_map.trace_down/1` | 需求 → 环节 → 公司，多路径并列，`realization` 每家一个 |
| `trace --up` | 公司名或代码 | `research_map.trace_up/1` | 公司 → 暴露概念 → 共同需求分组（`broad` 标泛化上位） |
| `compare` | `--theme --companies a,b,c` | `research_map.compare/1` | 11 维同口径：每格 `status ∈ {known, computable, unknown}`，unknown 的 `value=null` |
| `scope` | `--question` | `{decision, plan}` | 读取范围（entity_deep / relation_path / theme_synthesis）+ 子查询 + 先读页 |

Python 等价：`sys.path` 加 `<KB>/skills/lib` 后 `from research_map import package, trace, compare, views; from research_map.loader import Snapshot`；`Snapshot(wiki_root)` 一次会话内缓存 relations JSON（约 60 MB，首载 1–2 s）。

## 取证字段 → `AgentEvidence` 的映射

所有条目都带 `page = {page_id, path, exists}`，`page_id` 与 RAG `get_page` 的页级键同形（`entities/英维克`、`concepts/液冷`、`sources/<来源页>`）。建议映射：

| 研究地图字段 | AgentEvidence |
|---|---|
| 公司 / 概念 / 来源名 | `title` |
| `evidence[:240]`、`strength/evidence_layer/realization`、cell 的 `value unit @period` | `detail` |
| `"本地知识图谱·研究地图"` | `source` |
| `page.path`（`wiki/entities/英维克.md`）或 `wiki/relations/<file>.json` | `internal_locator` |
| `source_date` / `latest_evidence_date` | `source_date` |

三条使用规则必须带进判官口径：
1. **关联 ≠ 兑现**：`realization` 只转述 `exposures.financial_validation`；`unknown` 表示库里没写，不得写成「未兑现」。
2. **unknown ≠ 0**：compare 的 unknown 格 `value=null`，`computable` 只有公式与输入，金融侧 04 才算。
3. **陈旧要声明**：`recent.stale=true`（>90 天）或 `view.status=stale` 时，答案须声明时效并按 `recheck[]` 回原页；不得把缓存视图当新答案。

## 失败与边界

- 题材无命中：`package` 仍返回，`scope.missing=true`，`gaps[0].kind=theme_not_found`；不抛异常。`trace --down` 起点无命中 → `unresolved=[start]`；`compare` 里解析不到的公司进 `unresolved`。
- 必需文件缺失（`concept_graph` / `entity_exposures` / `evidence_index`）→ `FileNotFoundError`；可选文件缺失按空处理。
- `acceptance` 返回码 0/1 是 03 单自验，不是运行时接口。
- 写副作用只有两处，都不进 git：`view/refresh` 写 `wiki/relations/research_map.db`；`package` 追加 `wiki/relations/access_log.jsonl`（与原三命令一致）。金融侧若要求零写，调用 `package` 之外的模式或以只读挂载运行。

## 建议的接入形状（06 决定）

- 与 `kb_rag.py` 一致走子进程（`--json`），或与 `KnowledgeAdapter` 一致直接读文件（import API）。两者输出同一 JSON。
- `graph_lookup` 现有实现只回「概念匹配分 + 公司暴露」两类 evidence；接研究地图后至少多出三类可直接进判官的材料：空环节 / 缺口（`gaps`）、限制条件与反证（`conditions.limits`，带来源与日期）、兑现状态（`companies[].realization`）。
- 检索联动：先 `scope --question` 拿 `plan.subqueries` / `plan.read_first`，再喂 `rag_index.py query --subquery`（遵守 `skills/rag-query` 的窄口径补跳惯例）。
