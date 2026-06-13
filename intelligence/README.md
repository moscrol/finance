# intelligence/ — 统一检索与工作流 CLI

`intelligence` 是金融仓的产品化检索/编排层，对外暴露一条命令行入口 `python3 -m intelligence.cli`。

```
ask            统一多源问答：KB 图谱(G/R) + 盘面候选快照(S)，六段式输出（本文重点）
adapter-smoke  只读 adapter 冒烟检查（需要 duckdb + 本地 db/market.duckdb）
daily          每日复盘工作流
theme          题材雷达工作流
```

## 数据来源（两源召回）

| 标记 | 含义 | 来源 |
| --- | --- | --- |
| `S` | 盘面 | `market_feature_store/exports/<date>-theme-candidates.json`（已入库快照，默认取最新一天） |
| `G` | 图谱 | 知识库 `wiki/relations/concept_graph.json` + `entity_exposures.json` |
| `R` | 证据 | 知识库 `wiki/relations/evidence_index.json` + 盘面候选自带 `knowledge_evidence` |

`ask` **不依赖外部 LLM、也不依赖 DuckDB**：盘面取已提交的 theme-candidates 快照，图谱/证据走只读 JSON。
`结论` / `交易含义` 为模板化骨架（待接 LLM 精修）；`证据链` / `分歧反证` / `引用来源` 为真实检索结果，每条事实带 `[S#]/[G#]/[R#]` 编号引用。

## 路径配置

`ask` 通过环境变量或参数定位知识库 wiki 根（含 `relations/`）：

- `KNOWLEDGE_WIKI=/path/to/知识库/wiki`（或 `--kb-wiki`）
- 盘面快照目录默认取本仓 `market_feature_store/exports/`，可用 `--exports-dir` 覆盖。

## 用法

```bash
# 取最新一天盘面快照 + 知识图谱，跑「液冷服务器」这条链
KNOWLEDGE_WIKI=/path/to/知识库/wiki \
  python3 -m intelligence.cli ask "液冷服务器"

# 指定盘面日期、限制召回公司数、并落工作流 summary JSON
python3 -m intelligence.cli ask "液冷服务器" \
  --kb-wiki /path/to/知识库/wiki \
  --date 2026-06-11 --top-companies 12 \
  --summary-json /tmp/ask-summary.json
```

固定六段输出：`结论 / 证据链 / 分歧反证 / 后续验证点 / 交易含义 / 引用来源`。

## 现状与后续

这是 TRW `ask` 外壳在本仓的最小可跑原型，目前只打通 G/R/S 三源：

- 待接 LLM provider 精修 `结论`/`交易含义`。
- 待补 Temporal Facts 层：把会过期/被证伪的事实建成带 `status(active/superseded/invalidated)` 的时序边，让 `ask` 默认只用 active 证据（当前仅按 `source_date` 标注新鲜度）。
- 待接 `daily-loop`：把盘面候选升级成「盘前预测 → 盘后多周期验证 → 写回记忆」闭环。
