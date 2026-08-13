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
| **画像 + 轻量 BM25（Workbench 已接入）** | 只在选中 KOL 的独立文章目录召回片段 | 可追溯且隔离事实层；文章规模大后再接向量与 rerank |

CLI 的 P0 debate 完全确定性（不调 LLM）：ingest 只抽确定性字段；debate 用画像信号词对硬事实
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
profile JSON 填写（对照文章原文提炼）；也可走下面的 P1 学习闭环让 LLM 提候选、你来确认。

> 💡 「用户发原文 → 蒸馏进画像」的端到端固定流程已沉淀为 skill：
> `skills/perspective-distill/SKILL.md`（触发词：蒸馏视角、学这个博主、喂文章），
> 含前置确认（canonical 用户空间）、原文落盘红线、patch 评审判据与验收清单。

### 3.5 学习闭环（P1，2026-08-13 上线）：文章 → 认知卡片 → patch → 人工确认

原理：画像是「慢变量」（方法论），不该每次回答现场重算，也不该永远靠手填。学习闭环把
agent book 说的记忆结构化机制做成动态版——**LLM 只产候选，人工确认才写画像**（与 P4
胜率驱动修正共用同一道人工门禁）。服务代码：`intelligence/services/perspective_learning.py`。

```bash
# 第一步：逐篇抽结构化认知卡片（需配置 LLM key；失败明确报错、不写半成品）
python3 -m intelligence.cli perspective extract-cards --user <id> --perspective blogger_x [--limit 5]

# 第二步：聚合卡片里的画像候选 → pending patch（确定性，不调 LLM，幂等）
python3 -m intelligence.cli perspective propose-patches --user <id> --perspective blogger_x

# 第三步：人工逐条确认（approve 写画像 + patch_history 溯源；reject 只改状态、不会被复活）
python3 -m intelligence.cli perspective patches --user <id> --perspective blogger_x --status pending
python3 -m intelligence.cli perspective review-patch --user <id> --perspective blogger_x \
  --patch-id pp-xxxx --approve   # 或 --reject [--note 理由]
```

证据卫生三道闸（认不出来就 fail closed）：

- **引文逐字核验**：候选的 `supporting_quote` 必须是原文逐字连续片段（空白归一后子串
  命中，且不短于 6 字——超短子串在任何文章里都能命中，不构成出处），核验不过的候选
  留在卡片里存档，但**不进入确认流**——防 LLM 编造出处；
- **字段白名单**：LLM 候选只能进四个字符串列表字段（opportunity_preferences /
  risk_triggers / anti_patterns / falsification_style）；market_lenses、
  reasoning_patterns、evidence_hierarchy 带结构或顺序语义，仍走人工编辑 JSON；
- **人工门禁**：patch 三态 pending/approved/rejected，approve 才写 profile 并在
  `patch_history` 留 patch_id 溯源；同一 (field, value) 的 patch id 是确定性哈希，
  重复 propose 幂等，rejected 不会被重新提出。

落点（均本地私有）：卡片 `articles/<id>/cards/pa-*.json`；patch `patches/<id>/pp-*.json`。

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

### 5. 在 Workbench 切换视角

Chat-first Workbench 会把视角选择作为结构化字段写入 `messages.jsonl`，而不是把
“切换视角”伪装成普通提示词：

- `数据中立`：默认模式，只使用 Provider、公开来源和本轮检索证据；
- `指定 KOL`：只加载一位 profile 与其文章召回，其他 KOL 不参与；
- `多视角并列`：固定包含数据中立视角，并把最多 3 位 KOL 分区展示、保留冲突；
- 每条用户消息和助手消息都保存 `perspective_mode` 与
  `selected_perspective_ids`，切换会话时从最近一条用户消息恢复。

文章召回使用独立的轻量 BM25，而不是把 KOL 原文并入统一知识库索引。这样能避免
观点层污染事实层；等单个 KOL 的文章规模明显增大后，可再升级为
`BM25 + vector + rerank` 的独立 Hybrid 检索。

Workbench 只展示当前用户命名空间中已创建的视角。以风远94为例：

```bash
python3 -m intelligence.cli perspective init \
  --user <id> --id fengyuan94 --name "风远94" --type blogger

python3 -m intelligence.cli perspective ingest \
  --user <id> --perspective fengyuan94 \
  --input /path/to/article.md --title "文章标题" \
  --date 2026-07-03 --source "风远94"
```

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
  卡片 + candidate 人工确认后才写 profile，**已于 2026-08-13 上线，见 3.5 节**）
  → P2 BM25 召回原文例证（Workbench 已接入）→ P3 盘后结果
  评价角色有效性（接 checkpoint，按市场阶段分桶）→ P4 自动生成 profile 修正建议。
  详见 spec 第 16 节。

## 角色胜率怎么看

P3 才做（`outcomes.jsonl` + 按市场阶段分桶统计）；在那之前可先把 debate 的可证伪假设
人工登记到 `checkpoint register`，用现有回检闭环打分。
