# Perspective Lab / 视角实验室（P0 使用说明）

> 设计文档：`docs/superpowers/specs/2026-07-03-perspective-lab-design.md`
> 服务代码：`intelligence/services/perspective_lab.py`；CLI：`perspective` 子命令

## 这是什么（原理速讲）

上传博主文章 → 学习他的“市场认知框架”（不是文风）→ 用多个角色视角（博主 / 趋势交易者 /
价值投资者 / 用户框架）对同一份硬数据做合议，输出区分「事实 / 角色解释 / 证伪条件」的
结构化报告。

核心架构取舍：**事实层与认知层分离**。DuckDB 盘面 / 知识库证据是 ground truth；角色只是
解释镜头（overlay），不改写事实、不写入知识库实体层。这是垂直 Agent 的通用模式（法律/医疗/
投研/代码审查都能用）：事实库 + persona overlay + 审计验证闭环。

技术选型（P0 为什么这么做）：

| 方案 | 做法 | 取舍 |
|---|---|---|
| 纯 prompt 角色卡 | 文章总结成一段 prompt 注入 | 最快，但不可追溯、学的是口癖，弃 |
| **结构化画像（P0 采用）** | 文章 → JSON 画像（镜头/机会偏好/风险信号/证伪风格） | 稳定、便宜、可测试；缺原文上下文 |
| 画像 + BM25/向量 RAG（P1/P2） | 回答时再召回相似历史片段 | 可追溯最强，工程重，后续接 |

P0 完全确定性（不调 LLM、不建索引）：ingest 只抽确定性字段；debate 用画像信号词对硬事实
摘要做子串命中 + 交叉对比。LLM 抽取/合成是 P1 的开关。

## 怎么用

### 1. 创建角色

```bash
# 博主角色（画像为空，需 ingest 文章训练；<3 篇时置信度 low，只能作候选视角）
python3 -m intelligence.cli perspective init --user <id> --id blogger_x --name "某博主" --type blogger

# 内置角色（带基础画像，可直接 debate，也可手工编辑 JSON 定制）
python3 -m intelligence.cli perspective init --user <id> --id trend_trader --type trend_trader
python3 -m intelligence.cli perspective init --user <id> --id value_investor --type value_investor
python3 -m intelligence.cli perspective init --user <id> --id user_framework --type user_framework
```

### 2. 上传文章（本地私有，不进仓库）

```bash
python3 -m intelligence.cli perspective ingest \
  --user <id> --perspective blogger_x \
  --input /path/to/article.md --title "某篇市场复盘" --date 2026-07-03 --source "某博主"
```

- 原文存 `intelligence/users/<id>/perspectives/articles/blogger_x/raw/`；
- `manifest.jsonl` 按内容哈希去重（同一篇改标题重传不会重复计数）；
- 自动更新画像样本数与置信度（≥3 篇 → medium）。

### 3. 查看画像

```bash
python3 -m intelligence.cli perspective profile --user <id> --perspective blogger_x [--json]
```

博主画像的认知字段（market_lenses / risk_triggers / falsification_style 等）P0 由人工编辑
profile JSON 填写（对照文章原文提炼）；LLM 自动抽取是 P1 开关。

### 4. 多角色合议

```bash
python3 -m intelligence.cli perspective debate \
  --user <id> --query "明天市场怎么看，AI硬件还能不能继续" \
  --perspective blogger_x --perspective trend_trader --perspective value_investor \
  --date 2026-07-03 \
  --facts-file /path/to/今日硬事实摘要.md
```

- P0 硬事实由你提供（`--facts` 或 `--facts-file`）；P1 起自动接 `ask` 证据链；
- 报告结构：硬事实底座 → 角色独立判断 → 固定三问质询 → 裁判合议 → 可证伪假设表；
- 若各角色信号命中完全一致，报告会给「本次辩论无增量」退化提示（防假分歧）；
- 每次合议落 `perspectives/debates.jsonl`（带 schema_version，供 P2 胜率聚合）。

## 常见误用边界

- **不冒充本人**：输出只是“某博主视角 / Buffett-inspired 价值投资视角”；
- **不污染事实层**：文章里的公告/订单等硬事实要走 disclosure / l3-ingest 流程，不因博主提到就入库；
- **版权**：文章只本地私用（gitignore），报告只允许短摘录；
- **样本不足**：<3 篇文章的博主角色输出会标注“只能作为候选视角”；
- **过拟合**：某角色在某阶段准 ≠ 全阶段准，P3 按市场阶段分桶评估胜率。

## 后续分期（2026-07-03 修订：学习闭环先于检索增强）

- **user_framework 是主坐标系**（spec 2.5）：外部角色只能 challenge/supplement，
  裁判最终按用户主框架的结论格式落结论与证伪——多视角不是多声音。
- P0 角色容器（本期）→ P1 先固化 user_framework 六层认知框架（市场阶段/题材生命
  周期/盘面确认/证据硬度/反证降级/二阶导发散），再做博主文章 LLM 抽取（单篇结构化
  卡片 + candidate 人工确认后才写 profile）→ P2 BM25 召回原文例证 → P3 盘后结果
  评价角色有效性（接 checkpoint，按市场阶段分桶）→ P4 自动生成 profile 修正建议。
  详见 spec 第 16 节。

## 角色胜率怎么看

P3 才做（`outcomes.jsonl` + 按市场阶段分桶统计）；在那之前可先把 debate 的可证伪假设
人工登记到 `checkpoint register`，用现有回检闭环打分。
