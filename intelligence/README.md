# intelligence/ — 统一检索与工作流 CLI

`intelligence` 是金融仓的产品化检索/编排层，对外暴露一条命令行入口 `python3 -m intelligence.cli`。

```
ask            统一多源问答：KB 图谱(G/R) + 盘面候选快照(S)，六段式输出（本文重点）
foresight      猜你想问 / 潜意识：基于盘面现实+画像，主动生成「你还没想到但该问」的追问
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

### 抽取做厚（默认）+ `--detail` 整篇钻取

每个模块的解析器都做**结构化做厚**抽取（约 8~15 行核心），而不是只取标题级几行——保留各模式真正有价值的明细：

- `brief`：产业定锚 + 相关概念 + 产业链各层（终端/中游/上游，含看点）+ 工艺材料代表公司 + 各细分核心层个股。
- `front-map`：产业定锚 + 信号水位（概念命中/公司分层/逻辑卡/概念页/合成研究/海外对标）+ 信号缺口（缺概念页/海外对标 0 张/待刷新实体）+ 产业链节点→代表公司 + 主线/相关/延伸公司名单 + 海外对标图谱状态。
- `deep-dive`：产业定锚 + 雷达速览 + 深研判断 + 三重共振核心层 / 双重验证层 / 观察弱相关层 + 发酵进度 + **个股逻辑卡（角色 + 依据片段）** + 下一步验证 + 风险提示。
- `replay`：发酵阶段 / 库内覆盖 + 一句话定锚 + **完整时间线**（首尾节点 + 证据等级）+ 产业链上中下游受益名单 + 最值得重点跟踪 + 验证清单。
- `scan`：全库扫描分布 + 题材相关方向（赛道/频次/催化）+ 全市场高频发酵方向。
- `migrate`：横向迁移标尺 + 参照模式阶段 + 关键信号标尺 + 发酵进度分布 + **类比定位（信号维度/覆盖/催化/框架评分）** + 同阶段类比方向 + 认知跃迁窗口。

加 `--detail` 后，在六段答案之后追加一节「模块完整报告（--detail 钻取）」，把每个被路由命中的模块的 **完整报告全文** 以 `<details>` 折叠块逐一附上（默认行为仍是上面的做厚融合摘要，不受影响）。

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
# 默认做厚之外，再把每个命中模块的完整报告全文折叠钻取
python3 -m intelligence.cli ask "液冷服务器" --kb-wiki ... --detail
# 开 LLM 精修结论/交易含义（无 key 自动降级回模板）
DEEPSEEK_API_KEY=sk-... python3 -m intelligence.cli ask "液冷服务器" --kb-wiki ... --llm
```

固定六段输出：`结论 / 证据链 / 分歧反证 / 后续验证点 / 交易含义 / 引用来源`。

## foresight —— 猜你想问 / 潜意识（主动追问生成）

`ask` 是「你问它答」；`foresight` 反过来——**它替你问**：基于现实主动抛出你「还没想到但最该问」的追问，就是那种「潜意识 / 猜你想问」效果。本质是一个 *proactive question generator*（与 ChatGPT 建议回复、Perplexity Related 同类），高级感主要来自提示词逼模型做二阶 / 可量化 / 可证伪，而不是模型本身。

四层流水线 + 记忆回路（见 `services/foresight.py`）：

1. **上下文层**：把「它知道的一切」拼起来——盘面现实快照（最新 `*-theme-candidates.json` 的市场环境/信号汇总/热门候选）+ 用户画像（关注题材/自选股/风格/已问过的问题）+ **知识库题材**（设 `KNOWLEDGE_WIKI`/`--kb-wiki` 时读 `relations/theme_signals.json`，取认知最靠前/近期有新事件的题材当发问素材，带 ★评级/进度/Tier/事件日期；无则优雅降级，`--no-kb` 关闭）+ 可选实时情报。
2. **现实锚定层**：默认锚定在已提交的盘面快照上（**离线即可跑**，不依赖 DuckDB / 联网）；联网情报走可插拔的 `--news-file`（把今日财经日历/新闻贴进去），无则跳过并优雅降级。
3. **生成层**：一次专门「生成问题」的 LLM 调用，强角色 + 强约束提示词（二阶思维 / 跨领域 / 带具体时间窗口+可量化指标+人名事件 / 前瞻可证伪 / 呼应画像），让它先产 `--candidates` 个候选。复用 `llm_refine.complete()`（OpenAI 兼容、`urllib` 零依赖、多 provider 自动探测）。
4. **排序去重层**：按 `0.4×新颖 + 0.4×相关 + 0.2×多样` 打分，硬抑制近重复候选，并剔除与 `recent_questions` 相似的问题，取前 `-n` 条。

- **记忆回路（连续性来源）**：每次把选中的问题追加到本地 `asked_questions` 记忆（默认 `intelligence/foresight_memory.jsonl`，已 gitignore），下次自动并入 `recent_questions` 去重——所以它不会重复问，而是**在你已问过的基础上再往前推一层**（截图里「和你之前的三种情景推演对比」那种连续感的来源）。`--memory-file` 换路径、`--memory-window N` 只用最近 N 条、`--no-memory` 关闭。纯本地、零依赖。
- **无 key 自动降级**：未检测到 LLM 凭据时不报错，而是输出「上下文摘要 + 待发送提示词全文」，机制完全可审、命令仍 exit 0；配置任一 LLM key（同 `--llm` 那套环境变量）后立即真正生成问题。
- **画像**：默认读 `intelligence/foresight_profile.example.json`，可用 `--profile` 指定你自己的画像 JSON；含真实自选股/持仓的私人画像建议走 `foresight_profile.local.json`（已 gitignore）或 `--profile` 传入，不要提交。

```bash
# 取最新盘面快照 + 默认画像，生成 3 条追问（无 key 则输出摘要+提示词预览）
python3 -m intelligence.cli foresight -n 3

# 配 LLM key 后真正生成；贴入今日财经日历/新闻作为实时情报；用自己的画像
DEEPSEEK_API_KEY=sk-... python3 -m intelligence.cli foresight \
  --profile intelligence/foresight_profile.example.json \
  --news-file /tmp/today-intel.txt \
  --date 2026-06-11 -n 3 --candidates 8 --temperature 0.8 \
  --summary-json /tmp/foresight-summary.json

# 机器可读 JSON 输出
python3 -m intelligence.cli foresight -n 3 --json

# 记忆回路：连续跑两次，第二次会自动避开第一次问过的，再往前推一层
DEEPSEEK_API_KEY=sk-... python3 -m intelligence.cli foresight -n 3   # 第一次：并入 0 条、新增 3 条
DEEPSEEK_API_KEY=sk-... python3 -m intelligence.cli foresight -n 3   # 第二次：并入 3 条去重、再生 3 条
python3 -m intelligence.cli foresight -n 3 --no-memory                # 不读/不写记忆
```

## 现状与后续

这是 TRW `ask` 外壳在本仓的可跑原型，已打通 G/R/S 三源 + theme-radar **六模式**（`brief`/`front-map`/`deep-dive`/`replay`/`scan`/`migrate`）的真实接线，以及可选 LLM 精修层：

- ✅ 六模式全部接成召回后端（产业维 3 + 时间维 1 + 横截面 2），按问题 source-routing fan-out。
- ✅ 每模块抽取做厚（结构化核心 8~15 行），并提供 `--detail` 整篇报告折叠钻取。
- ✅ 可选 LLM 精修 `结论`/`交易含义`（`--llm`），无 key 自动降级回模板。
- 待补 Temporal Facts 层：把会过期/被证伪的事实建成带 `status(active/superseded/invalidated)` 的时序边，让 `ask` 默认只用 active 证据（当前仅按 `source_date` 标注新鲜度）。
- 待接 `daily-loop`：把盘面候选升级成「盘前预测 → 盘后多周期验证 → 写回记忆」闭环。
