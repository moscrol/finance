# Theme Radar 目标功能对齐清单：截图竞品复刻与超越

更新时间：2026-06-01

## 目标

这份文档用于长期记住用户提供的 8 张截图中展示的功能形态。后续 Theme Radar 的每一轮开发，都要对照本文检查：

1. 是否至少 1:1 覆盖截图功能。
2. 是否利用我们的私有深度研究库、知识图谱、证据索引、PDF ingest、report_contexts 做出更强版本。
3. 是否避免只做漂亮报告，而忽略证据链、验证链和可复盘性。

## 截图系统的核心能力画像

截图展示的不是单纯问答，而是一套“题材机会发现 + 产业链拆解 + 市场发酵验证 + 公告交叉确认”的研究工作流。它的关键能力是：

- 从公告、电话会、盘口、行业趋势、历史题材记忆中捕捉新机会。
- 将用户“不懂的词”快速翻译成产业链框架。
- 在几分钟内输出可读、可追踪、可行动的题材深挖报告。
- 不只是解释产业，而是判断市场是否正在发酵、哪些方向最值得跟。
- 通过时间线、认知度演变、Tier 分层、验证清单，将“盘中灵感”变成“跟踪计划”。

## 必须 1:1 复刻的模块

### 1. 一句话定锚

截图功能：

- 对陌生技术词快速给出一句话定义。
- 例：mSAP 是 PCB 精细线路制造工艺，线宽/线距可做到 20-25μm，平衡精度与量产成本。
- 同时解释它和相邻工艺的区别，例如减成法、全加成法、SLP、HDI。

我们当前状态：

- Theme Radar deep-dive 已有“一句话定锚”。
- 但有时依赖外部输入或 report_contexts，不一定稳定从方向池生成。

差距：

- 需要建立 `definition_profile`：定义、类比、边界、相邻概念、误区。
- 需要自动引用证据来源和概念图谱。

超越点：

- 用知识库 concepts + aliases + raw/full source 支撑定义，而不是只靠模型常识。

### 2. 为什么现在爆发 / 三大需求引擎

截图功能：

- 解释题材为什么“现在”值得看。
- 按需求场景拆解，例如 1.6T 光模块、DDR5/存储模组、CoWoP 先进封装。
- 每个需求场景给出逻辑和工艺要求。

我们当前状态：

- 已有 `demand_bottleneck_map`。
- 报告有 `需求-瓶颈-环节传导表`。
- 但 `需求场景表` 仍可能待补。

差距：

- 需要把需求场景结构化为 `demand_scenarios`。
- 每个需求场景要包括：需求来源、逻辑、工艺要求、受益环节、证据、验证点。

超越点：

- 将需求场景和 concept_graph / entity_exposures / evidence_index 绑定。

### 3. 产业链全景图

截图功能：

- 用简单图示展示上下游：
  - 下游终端需求
  - 中游制造
  - 上游材料/设备
- 标出代表公司、份额、市场空间、未来翻倍逻辑。

我们当前状态：

- 有 `industry_chain_map_section` 和 `demand_bottleneck_map`。
- 方向池中有 `chain_bucket`、`beneficiary_links`、`representative_entities`。

差距：

- 还没有形成截图那种“一眼看懂”的链路图。
- 上中下游映射仍偏表格，部分链路依赖方向池推断。

超越点：

- 生成 Markdown ASCII 图 + JSON 结构，后续可直接转 UI 图谱。
- 每个链路挂 evidence item_id。

### 4. 工艺/材料级扫描表

截图功能：

表格列包括：

- 工艺/材料
- 所属大赛道
- 景气判断
- 每日复盘提及
- 自进化认知
- 分类
- 核心催化

截图中的例子：

- mSAP 半加成法：发酵，中频，L2-L3，核心催化为 Rubin 试产。
- 感光干膜：布局，低频，L1-L2。
- 磷化铟 InP：发酵，中频，供需缺口至 2027。

我们当前状态：

- 方向池已有 `direction_scan`。
- 已有 recognition stage、opportunity tier、validation plan。

差距：

- 缺少“每日复盘提及频率”字段。
- 缺少“自进化认知层级”字段的历史演变。
- 缺少“分类 = 发酵/布局/观察”的独立标签。
- 缺少工艺/材料专属 schema。

超越点：

- 用 source_date + source_systems + report_contexts 做频率统计。
- 用多次运行 snapshot 形成认知演变，而不是一次性判断。

### 5. 布局区深度展开：催化日历与验证清单

截图功能：

- 对新增优先级方向做深度展开。
- 输出催化时间线：即时、6月、Q3、Q4。
- 输出验证清单：跟踪涨价、扩产、导入进度、ASP、国产替代等。
- 给出 V2 相比 V1 的核心增量。

我们当前状态：

- 已有 `validation_plan`。
- 报告已有 `### 催化日历` 和 `### 通用验证`。

差距：

- 验证清单偏模板化，尚未按材料/设备/芯片/应用等方向类型生成专属检查项。
- 没有 V1/V2 增量比较。
- 没有明确区分“新增高优先级方向”。

超越点：

- 为每个方向生成 `validation_type`、`validation_status`、`supporting_item_ids`。
- 记录每次方向池运行 snapshot，自动比较 V1/V2 变化。

### 6. 行情发酵全景：从无人信到一致看好

截图功能：

- 复盘题材发酵路径：暗流期、萌芽、第一轮、催化共振、一致认同。
- 给出关键时间节点：3月、4月中、4月下旬、5月中、5月20日。
- 用认知度演变图展示市场关注度上升。

我们当前状态：

- 已有 `recognition_profile.stage`。
- 已有发酵进度排序。

差距：

- 当前是静态阶段判断，不是历史时间序列。
- 没有 `attention_timeline` 或 `recognition_history`。
- 没有“从无人信到一致看好”的趋势图。

超越点：

- 从 source_date、行情数据、每日复盘、研报时间戳中生成认知曲线。

### 7. 多方向发酵进度横向对比

截图功能：

- 用统一标尺比较多个方向：
  - 暗流
  - 萌芽
  - 第一轮
  - 催化共振
  - 一致认同
- 横向比较 PCB 油墨、电子氟气、球硅、EMC、Low-CTE、ABF、感光干膜、载体铜箔、mSAP。
- 输出最值得重点跟踪方向。

我们当前状态：

- 已有 `progress_ranking_section`。
- 已有 Tier 和 opportunity score。

差距：

- 没有可视化横向标尺。
- 没有跨方向发酵轨迹区间。
- 没有同主题内全部方向的“阶段条形图”。

超越点：

- 基于 recognition_profile + source_date 生成 Markdown 可读进度条，后续可转 UI timeline。

### 8. 核心结论与最值得跟踪方向

截图功能：

- 最后压缩成核心结论。
- 明确指出最值得跟踪的 2-3 个方向。
- 给出操作建议：最优先、次优先、观察。
- 每个方向有核心逻辑和操作思路。

我们当前状态：

- 已有 `opportunity_profile` 和 `### 跟踪优先级`。
- deep-dive 有核心结论。

差距：

- 操作建议还不够像截图中那样明确。
- 当前不展示“最优先/次优先/观察”的中文行动分层。
- 缺少“为什么现在买/等/观察”的短句。

超越点：

- 输出 `action_plan`：跟踪优先级、等待条件、验证触发、风险条件。
- 明确声明不是投资建议，而是研究跟踪策略。

### 9. 公告 × 产业趋势 × 市场热点 三维交叉分析

截图功能：

- 读取今日公告。
- 将公告和产业趋势、市场热点交叉验证。
- 分为 Tier 1 / Tier 2 / Tier 3。
- 每个 Tier 1 机会用表格展示：公告、产业、盘面、关键增量。
- 直接判断“公告验证小批量供货 + 市场热点 + 产业趋势”的共振程度。

我们当前状态：

- 有 direction pool 和 evidence trace。
- 但公告扫描不是当前 deep-dive pipeline 的一等公民。

差距：

- 缺少 `announcement_signal_pool`。
- 缺少 `market_hotspot_signal_pool`。
- 缺少三维交叉评分：公告 × 产业 × 盘面。
- 缺少“今日公告机会榜”。

超越点：

- 接入 disclosure archive / 公告归档后，公告证据可直接进入 evidence_trace，并和方向池匹配。

### 10. Tier 机会分层

截图功能：

- Tier 1：三重共振机会（公告 + 产业 + 盘面验证）。
- Tier 2：双重验证机会（公告 + 产业共振）。
- Tier 3：独立逻辑 / 需观察。
- 对 Tier 3 还会标注是否匹配主线。

我们当前状态：

- 已有 `opportunity_profile.tier`。
- 已有 `follow_up_priority` 和 `opportunity_score`。

差距：

- 当前 Tier 主要来自方向池内部评分。
- 还没有显式三维共振维度：announcement / industry / market。
- Tier 3 没有“匹配度”列。

超越点：

- 新增 `resonance_profile`：announcement_signal、industry_signal、market_signal、cross_validation_level。

### 11. 风险提示与判断

截图功能：

- 每个 Tier 1 机会后有风险提示。
- 有明确判断：收购逻辑补的是工艺纵深而非单纯扩规模，追高需谨慎。

我们当前状态：

- 已有 `risks`、`downgrade_risks`。

差距：

- 风险提示不够口语化、结论化。
- 没有针对公告/行情/验证节奏的特定风险。
- 没有“追高风险 / 兑现风险 / 证据不足风险 / 主题偏离风险”分类。

超越点：

- 结构化 `risk_profile`，同时输出短句判断。

## 我们要做得比截图更好的地方

截图强在“快”和“会抓主线”。我们的优势应该是：

1. 私有知识库更深：PDF ingest、raw/full、entities、concepts、relations。
2. 证据链更严：每个判断都能回到 item_id、source_path、line_no、evidence_index。
3. 可复盘：每次运行保存 snapshot，比较 V1/V2 变化。
4. 可校准：多题材 regression，避免模型主观漂移。
5. 可审计：区分 official / curated_research / graph_only / needs_review。
6. 可积累：每次发现新方向，可回写 taxonomy / concept / relation 候选，而不是一次性报告。

## 功能覆盖矩阵

| 模块 | 截图功能 | 当前 Theme Radar | 差距 | 优先级 |
|---|---|---|---|---|
| 一句话定锚 | 有 | 部分有 | 缺定义 profile 和相邻概念边界 | P1 |
| 需求引擎 | 有 | 部分有 | demand_scenarios 待结构化 | P1 |
| 产业链全景图 | 有 | 表格化已有 | 缺图形化和证据绑定 | P2 |
| 工艺/材料扫描 | 有 | direction_scan 部分覆盖 | 缺每日频率/分类/历史认知 | P0 |
| 催化日历 | 有 | 已有 v1 | 缺状态化和 item_id 绑定 | P0 |
| 验证清单 | 有 | 已有 v1 | 缺方向类型专属验证和状态流 | P0 |
| 认知演变 | 有 | 静态 stage | 缺 timeline/history | P0 |
| 多方向进度对比 | 有 | 排名表已有 | 缺横向进度条 | P1 |
| 核心结论 | 有 | 有 | 缺行动分层和短句判断 | P1 |
| 今日公告交叉 | 有 | 未系统化 | 缺公告 × 产业 × 盘面三维信号池 | P0 |
| Tier 分层 | 有 | 有 v1 | 缺三维共振解释 | P0 |
| 风险提示 | 有 | 有 v1 | 缺风险分类和操作判断 | P1 |
| 证据追踪 | 截图弱展示 | 我们已有 v0 | 需绑定每个结论 | P0 |
| V1/V2 增量 | 有 | 未做 | 缺 snapshot diff | P0 |

## 下一步推荐顺序

### 第一阶段：复刻截图核心判断能力

1. `resonance_profile`：公告 × 产业 × 盘面三维共振。
2. `signal_frequency_profile`：每日复盘提及、来源频率、关注度。
3. `recognition_timeline`：暗流到一致看好的时间序列。
4. `supporting_item_ids`：把 recognition / validation / opportunity / catalyst 全部绑定 evidence_trace。
5. `validation_status`：验证项状态化。

### 第二阶段：复刻截图表达形态

1. Tier 1 / Tier 2 / Tier 3 分组展示。
2. 多方向发酵进度横向对比图。
3. 产业链 ASCII / Mermaid 图。
4. 核心结论 + 操作建议汇总表。

### 第三阶段：超越截图

1. 接入 Disclosure Archive 生成今日公告机会榜。
2. 接入行情和板块热度生成 market_signal。
3. 保存 snapshot，实现 V1/V2 增量。
4. 多题材 regression 校准评分。
5. 后续再做 Web UI / Workbench。

## 当前最建议先做的模块

建议优先做：`resonance_profile`。

原因：截图最核心的能力不是单纯解释 mSAP，而是识别“公告 + 产业趋势 + 市场热点”三维共振，并据此分 Tier。我们当前已有 opportunity tier，但还缺三维共振解释。补上以后，Theme Radar 会更接近截图中的“盘中发现机会”能力。

目标字段：

```json
"resonance_profile": {
  "announcement_signal": "none|weak|medium|strong",
  "industry_signal": "none|weak|medium|strong",
  "market_signal": "none|weak|medium|strong",
  "cross_validation_level": "single|double|triple",
  "tier_reason": [],
  "risk_flags": [],
  "supporting_item_ids": []
}
```
