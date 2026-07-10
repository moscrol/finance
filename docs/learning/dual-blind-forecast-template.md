# 双盲同题答卷模板

> **目的**：同一份冻结数据下，比较两个 Agent 对**市场结构**的理解差异，不是判胜负。
> **纪律**：考生只独立答卷，**不做对比/批注/裁决**（那些归用户 + 统一指标）。
> **流程**：同一份 DuckDB + 同一份复盘材料 → Claude / Codex 各自独立（互不可见）→ HTML 并排 → T+1/T+3 统一指标回检 → 用户批注 → 沉淀经验卡。
> **比的是 5 个理解差异**：谁更重双红 vs 新高/涨停；谁易从板块强度跳到个股追高；谁能区分"市场路径命中"vs"标的路径命中"；谁的标的池 T+1/T+3 更稳；谁的验证条件更清晰可证伪。
> **工装**：`scripts/dual_blind_forecast.py`——答卷前 `manifest` 冻结输入，答卷后 `validate` 校验 JSON 答卷，跨期 `aggregate` 看长期统计（单期噪声大，结论看聚合）。

## 工装流程（强制，2026-07-02 起）

1. **答卷前**：主持人先跑
   `python3 scripts/dual_blind_forecast.py manifest --date <研判日> --perspective <视角日> --material <材料文件>... [--kb-root <知识库仓>]`
   生成 `forecast-review-ledger/<date>.manifest.json`（DuckDB 截止日 + 材料 sha256 + 知识库 commit + `manifest_sha`）。两个考生只能用清单里列出的输入。
2. **答卷**：每个考生除 markdown 正文外，同时落一份机器可读答卷
   `forecast-review-ledger/<date>.answer.<agent>[.<source>].json`（schema 见下），`manifest_sha` 必须引自当日清单。
   `source` 段可选（duckdb/briefing/sellside），同日同 agent 按流各落一份时用它区分文件名，
   且必须与答卷 JSON 内的 `source` 字段一致（validate 会校验）。
3. **收卷**：`python3 scripts/dual_blind_forecast.py validate <答卷.json>...` 必须全 OK。
4. **回检**：数值类指标由脚本自动回填：`python3 scripts/dual_blind_forecast.py recheck <答卷.json>...`（从 DuckDB 算 `pick_returns_t1/t3`、`benchmark_return_t3`、`beat_benchmark_t3`；基准统一为上证指数 `sh000001`，写进 recheck 块保证跨期可比）。`market_threshold_hit` 是自然语言阈值，仍由人判定回填，脚本不覆盖人工字段。人只负责批注归因。
5. **盘后验证**：逐假设裁定写验证草稿 JSON（`{date, verdicts:[{id, agent, verdict, actual, evidence_ref}]}`，
   可选字段 `stream`（盘面/晨汇/卖方，缺省盘面）、`horizon`（T+1/T+3/T+5，缺省 T+1）、
   `failure_mode`（miss/partial 归因，优先用 [forecast-scoring-frameworks.md](forecast-scoring-frameworks.md) 六类代码 A1-A6，可附注如「阈值定早」）），
   `python3 scripts/dual_blind_forecast.py verdict <草稿.json>` 校验后落盘 `forecast-review-ledger/<date>.verdict.json`
   （盘后验证唯一写入口），并自动把回检表渲染进当日 `<date>.md` 的标记区——**当日 md 回检表不再手填**。
6. **状态总表**：`python3 scripts/dual_blind_forecast.py index` 重建 `index.md` 的机检状态总表（manifest/答卷/校验/验证/命中率）。
7. **看趋势**：`python3 scripts/dual_blind_forecast.py aggregate` 出按 agent 的跨期统计表（含按流×时点命中率与 miss 归因分布）；系统性偏差确认后才沉淀经验卡/rubric 检查项。

> 每日出题按三条信息流（DuckDB 盘面流 / 晨汇事件流 / 晚间卖方流）的固定问句模板，见 `forecast-question-templates.md`。

### 答卷 JSON schema（v1.1）

```json
{
  "schema_version": "1.1",
  "date": "2026-07-03",
  "agent": "codex",
  "source": "duckdb",
  "manifest_sha": "<来自当日 manifest>",
  "evidence_catalog": {
    "M1": {
      "level": "L4",
      "source": "fact_market_daily",
      "source_time": "2026-07-02",
      "entity": "market",
      "field": "advancers",
      "value": 3210,
      "direction": "support"
    },
    "R1": {
      "level": "L2",
      "source": "strategy1-matrix",
      "source_time": "2026-07-02",
      "direction": "neutral"
    }
  },
  "stage": "底部横盘第3天",
  "stage_features": {
    "rule_id": "market-stage-v1",
    "as_of": "2026-07-02",
    "metrics": {"advancers": {"value": 3210, "evidence_ref": "M1"}},
    "evidence_refs": ["M1"]
  },
  "main_judgment": "一句话市场结构判断",
  "direction_ranking": ["储能", "创新药"],
  "picks": [{
    "code": "688323",
    "name": "瑞华泰",
    "strategy": "策略三",
    "reason": "绑定§1字段证据",
    "evidence_refs": ["M1"],
    "evidence_as_of": "2026-07-02"
  }],
  "thresholds": {"market": "涨家数>3500", "direction": "储能 diff 继续>0", "targets": "逐只触发价", "falsify": "什么信号推翻主判断"},
  "threshold_provenance": {
    "market": {"origin": "backtest", "evidence_ref": "M1", "as_of": "2026-07-02"},
    "direction": {"origin": "fixed_rule", "evidence_ref": "R1", "as_of": "2026-07-02"},
    "targets": {"origin": "mechanical", "evidence_ref": "M1", "as_of": "2026-07-02"},
    "falsify": {"origin": "heuristic", "evidence_ref": "R1", "as_of": "2026-07-02"}
  },
  "hypotheses": [{
    "id": "market",
    "category": "market",
    "claim": "T+1 涨家数超过 3500",
    "horizon": "T+1",
    "confidence": "medium",
    "confidence_probability": 0.6,
    "evidence_refs": ["M1"],
    "evidence_as_of": "2026-07-02",
    "falsify_when": "T+1 涨家数低于 2500"
  }],
  "recheck": {}
}
```

`origin` 只能取：`fixed_rule`（固定规则）、`backtest`（回测校准）、
`mechanical`（机械推导）、`heuristic`（经验值）。经验值可以使用，但不得冒充硬门槛。
所有引用必须先登记到 `evidence_catalog`，并标 L1-L4、来源、时间和支持/反证方向。
校验会拒绝晚于 `perspective_date` 的证据，并核对阶段特征值与证据行是否一致。

`source` 三流分账（可省略，默认 `duckdb`）：`duckdb`=盘面流（T+1 回检）、`briefing`=晨汇事件流（当日/T+1）、`sellside`=晚间卖方流（T+3/T+5）。三流验证窗口和评判标准不同，`aggregate` 按 `agent/source` 分开统计，不混池。各流的标准问句/检测点/证伪点见 [forecast-question-templates.md](forecast-question-templates.md)。

---

## F<date> 双盲答卷（agent: ___）

### 0. 输入冻结
- DuckDB 截止：<perspective_date>
- 复盘材料：<同一份；卖方/外盘/晨汇 或标注缺口>
- 答卷人：Claude / Codex（各自独立）
- 数据缺口：<列出>

### 1. 统一字段（必填，约束项，全部要落到数值）
- **阶段**：<市场阶段 + 切换判断>
- **量能**：<成交额 / 量比 / 20日均量回归 / 环比>
- **广度**：<涨家数 / 涨家MA5拐头 / 涨停 / 跌停>
- **双红**：<真双红板块清单(pct>0 且 diff>0)，按 diff 排序>
- **涨停**：<涨停热度 top 板块 + 家数>
- **新高**：<新高集群 / 历史新高数 / 容量核心新高名单>
- **核心股**：<发动机 / 容量核心>

### 2. 主判断
一句话市场结构判断（不是涨跌预测）。

### 3. 方向排序
优先级 + 理由（用策略一二三四的市场状态语言：主线流动性池/强趋势延续/分歧回流/流动性切换）。
先判场景（A 恐慌反弹 / B 主升浪 / C 高位拥挤），再按 [forecast-scoring-frameworks.md](forecast-scoring-frameworks.md) 五维（确定性/弹性/兑现时间/拥挤度/已定价）打分排序，给出总分与第 1/2 名分差；异动性质用四分类（情绪脉冲/资金切换/主线扩散/假突破）语言描述。

### 4. 标的池（5 只）
| 标的 | 所属策略 | 选择理由（绑定 §1 字段证据） |
|---|---|---|
| ... | ... | ... |

### 5. 验证条件（T+1/T+3，**强制数值阈值，可证伪**）
- **市场**：<涨家数区间 / 量能正负 / 阶段切换阈值>
- **方向**：<双红板块 diff 转换条件>
- **标的**：<每只票的价格/新高/涨停触发>
- **证伪**：<什么信号推翻 §2 主判断>

---

### 6. T+1/T+3 统一回检（客观指标，非考生填写）
| 指标 | T+1 | T+3 |
|---|---|---|
| 涨家数 / 量能符号 / 阶段 | | |
| 真双红板块数 | | |
| 关键板块 diff 符号（计算机设备 / 半导体） | | |
| 涨停 top 数变化 | | |
| 新高数变化 | | |
| 标的池 5 只均值 / 跑赢板块比例 | | |

### 7. 用户批注（留空）
> 哪段更接近真实交易理解；理解差异点（双红 vs 新高权重 / 是否追高 / 市场路径 vs 标的路径 / 池子稳定性 / 验证可证伪性）。

### 8. 经验卡沉淀（多次验证后）
> 候选 → `intelligence/users/<user>/experience_cards.jsonl`；反复有效 → `agent-memory/10_knowledge/`。
