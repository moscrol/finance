# intelligence/ — 统一检索与工作流 CLI

`intelligence` 是金融仓的产品化检索/编排层，对外暴露一条命令行入口 `python3 -m intelligence.cli`。

```
ask            统一多源问答：KB 图谱(G/R) + 盘面候选快照(S)，六段式输出（本文重点）
adapter-smoke  只读 adapter 冒烟检查（需要 duckdb + 本地 db/market.duckdb）
daily          每日复盘工作流
theme          题材雷达工作流
```

## 数据来源（多源召回）

| 标记 | 含义 | 来源 |
| --- | --- | --- |
| `S` | 盘面 | `market_feature_store/exports/<date>-theme-candidates.json`（已入库快照，默认取最新一天） |
| `G` | 图谱 | 知识库 `wiki/relations/concept_graph.json` + `entity_exposures.json` |
| `R` | 证据 | 知识库 `wiki/relations/evidence_index.json` + 盘面候选自带 `knowledge_evidence` |
| `G`（模块） | theme-radar 六模式产出 | 产业维 `brief`/`front-map`/`deep-dive` 调本仓 `skills/theme-radar/scripts/radar.py --mode ...`；时间维 `replay` 调知识库 `generate_fermentation_report.py`（模块7）；横截面 `scan` 调 `generate_scan_table.py`（模块4 全库横扫）、`migrate` 调 `generate_migration_scan.py`（模块8 横向迁移） |

## source-routing + 模块 fan-out

`ask` 不重写题材雷达的报告生成器，而是把它们当**召回后端**按问题路由并 fan-out 调用，再把产出折进「证据链/后续验证点」并带 `[G#]` 编号引用（见 `services/theme_modules.py`）：

产业维按**深度**收敛到最深的命中模式（避免 brief+front-map+deep-dive 同时跑）；横截面/时间维独立触发，可叠加：

- 「深拆/上车/值不值/共识/个股逻辑」 → `deep-dive`；否则「信息地图/前瞻/有哪些公司/公司地图/全景」 → `front-map`；否则「是什么/产业链/谁受益/细分/核心个股」 → `brief`。
- 「发酵/起涨/时间线/复盘/认同度/谁先」 → `replay`（时间维 模块7）。
- 「全市场/全库/横扫/共振/什么方向/工艺/材料级」 → `scan`（模块4 全库横扫）。
- 「类比/横迁/对标/参照/还有哪些和它一样/相似方向/同阶段」 → `migrate`（模块8 横向迁移）。
- 不带意图的纯题材词（如「液冷服务器」）→ 默认 fan-out 到 `brief + replay`。
- `replay`/`migrate`/`scan` 走知识库 `theme_signals.json` 等底层；`replay` 需要题材有发酵信号，查询词会先做主题键归一（如「液冷服务器」→ 主题键「液冷」）。`scan`/`migrate` 是全库级（无主题入参），主题键仅用于在结果里高亮该题材所在细分/阶段。
- 每个后端都是**防御式 subprocess 调用**：超时 / 非零退出 / 脚本缺失 / 无匹配主题都只记一条警告并跳过，不影响其它源（接线是真实的，即便某后端在当前环境跑不起来）。`deep-dive` 子进程超时下限抬到 300s。

`ask` 默认 **不依赖外部 LLM、也不依赖 DuckDB**：盘面取已提交的 theme-candidates 快照，图谱/证据走只读 JSON。
`证据链` / `分歧反证` / `引用来源` 始终为真实检索结果，每条事实带 `[S#]/[G#]/[R#]` 编号引用。

## ② LLM 精修（可选，默认关闭）

加 `--llm` 后，`ask` 会把已检索到的「证据链 + 分歧反证」喂给一个 OpenAI 兼容的 `/chat/completions`，让它**只改写**`结论` / `交易含义` 两段（要求：只用证据里出现的事实、每条判断带 `[编号]` 引用、不得编造、不出买卖指令）。见 `services/llm_refine.py`。

- **无 key 自动降级**：未检测到任何 LLM 凭据时回退到原模板（即默认行为不变），并记一条警告说明如何启用。任何调用/解析失败也降级，不会让 `ask` 崩。
- **零额外依赖**：用 `urllib` 直连，无需安装 SDK。
- **多 provider 自动探测**（按序，首个命中的环境变量生效；通用 `LLM_API_KEY` 优先）：`DEEPSEEK_API_KEY` / `MOONSHOT_API_KEY`(`KIMI_API_KEY`) / `DASHSCOPE_API_KEY`(`QWEN_API_KEY`) / `ZHIPU_API_KEY`(`GLM_API_KEY`) / `OPENAI_API_KEY`，或通用 `LLM_API_KEY`(+`LLM_BASE_URL`,+`LLM_MODEL`)。可用 `--llm-model` 覆盖模型。

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

# 显式指定 fan-out 的模块（默认按问题自动路由）；可选 brief,front-map,deep-dive,replay,scan,migrate
python3 -m intelligence.cli ask "液冷服务器" --kb-wiki ... --modules brief,front-map,deep-dive,replay,scan,migrate
# 只走 G/R/S 三源，关闭模块 fan-out
python3 -m intelligence.cli ask "液冷服务器" --kb-wiki ... --no-modules
# 开 LLM 精修结论/交易含义（无 key 自动降级回模板）
DEEPSEEK_API_KEY=sk-... python3 -m intelligence.cli ask "液冷服务器" --kb-wiki ... --llm
```

固定六段输出：`结论 / 证据链 / 分歧反证 / 后续验证点 / 交易含义 / 引用来源`。

## 现状与后续

这是 TRW `ask` 外壳在本仓的可跑原型，已打通 G/R/S 三源 + theme-radar **六模式**（`brief`/`front-map`/`deep-dive`/`replay`/`scan`/`migrate`）的真实接线，以及可选 LLM 精修层：

- ✅ 六模式全部接成召回后端（产业维 3 + 时间维 1 + 横截面 2），按问题 source-routing fan-out。
- ✅ 可选 LLM 精修 `结论`/`交易含义`（`--llm`），无 key 自动降级回模板。
- 待补 Temporal Facts 层：把会过期/被证伪的事实建成带 `status(active/superseded/invalidated)` 的时序边，让 `ask` 默认只用 active 证据（当前仅按 `source_date` 标注新鲜度）。
- 待接 `daily-loop`：把盘面候选升级成「盘前预测 → 盘后多周期验证 → 写回记忆」闭环。
