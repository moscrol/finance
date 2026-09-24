# 能力升级任务包全面质检审计报告 (2026-09-10)

> **审计基准日**：2026-09-10  
> **审计对象**：INDEX 任务包 00–10 + 历史发现 (Historical Discovery) + I2 能力集成 (Capability-I2)  
> **审计原则**：**Progress 是主张，Git / 测试收据 / 进程取证是事实。** 严格对照四项质检不变量（已实现 / 已进默认入口 / 真实验收 / 生产生效）。  
> **生产 8792 取证状态**：监听 PID `78801`，CWD 指向 `/Users/a77/.finance-runtime/finance-workspace-ac0132553aae`，`source_revision=ac0132553aae`，`code_matches_repo=true`，`source_dirty=false`。

---

## 一、 全局质检总览看板

| 编号 | 任务名称 | 已实现 (代码/单测/门禁) | 已进默认入口 (生产主入口可达) | 真实验收 (真实对话/冻结集/差量实测) | 生产生效 (8792/生产环境生效) | 综合评定与关键判定依据 |
|---|---|:---:|:---:|:---:|:---:|---|
| **00** | 真实能力基线 | ✅ 部分完成 | ❌ 旁路隔离 | ⚠️ 进行中 (6/30 完成) | ❌ 未合主干 | 30 题公开+密封题集冻结，自动化编排推进中；受网关冷却影响 6 题干净入账；B7 发现题内回指路由缺陷。 |
| **01** | 判官修复 | ✅ 已实现 | ✅ 分支默认开 | ⚠️ 5题×2臂全草稿 (受上游503影响) | ❌ 未合主干 (PR #693) | 三刀（扩展不连坐/内容进展/V11补搜）代码齐且单测全绿；真实对话 5 题全出草稿，Q5 语义更优，但 Q3/Q4 受网关波动。 |
| **02** | 深读检索 | ✅ 已实现 | ✅ 分支默认开 | ✅ 离线 19/20 + Live 3 题两臂实测 | ❌ 未合主干 | 自动深读与过期货重读落地；离线翻正 5 题 (+5 题达标)；Live 对话 3 题实测 2 题将基线"不可见"翻为"可见并用上"。 |
| **03** | Wiki研究地图 | ✅ 已实现 | ⚠️ KB已合/金融待接 | ✅ 6题知识库查询包通过 | ⚠️ 知识库main生效 / 金融未接 | 知识库侧 PR !146/!147 已合 main (`0f7ce1dfd`)；金融侧合同已定，金融端 `graph_lookup` 适配归 06/I2。 |
| **04** | 计算与产物 | ✅ 已实现 | ✅ 分支默认可达 | ⚠️ 确定性干跑6/6 + Live 跑通 1 题 | ❌ 未合主干 (依赖 #682) | 结构化财务证据+fincalc+产物渲染；干跑单季还原 6/6 逐格一致；Live 跑通茅台产物落盘，但受网关冷却阻断全量批跑。 |
| **05** | 输入理解 | ✅ 已实现 | ✅ 默认入口主路径 | ✅ Frame级 11/12 (材料答案级受限) | ✅ **已合并且生产生效** (`ac013255`) | PR #696 已合 main 并切 8792；材料身份/用户假设/竞争解释进 TaskFrame；生产 Frame 级 11/12 正确。 |
| **06** | 自适应研究 | ✅ 已实现 | ✅ 分支默认开 | ✅ 双臂 24 题全部完成 (零污染) | ❌ 未合主干 | 研究进展账注入 `runtime_budget`；候选臂下发 23 个建议码并记录模型换路；简单题 0 次 sub_research 滥用；单测 389 pass。 |
| **07** | 方法飞轮接线 | ✅ 已实现 | ✅ 默认入口主路径 | ✅ 真实对话 2 题通过 (带边界) | ✅ **已合并且生产生效** (`ac013255`) | PR #692 已合 main；观察登记为 checkpoint，到期回检消费；生产 `register` 与 `history` 已执行，前向自 09-10 起。 |
| **08** | 问题驱动补数 | ✅ 已实现 | ✅ CLI+服务就绪 | ✅ Staging 全链 (QA/QB/QC/QD) | ❌ 未合主干 | `window_uncovered` 观测事件+请求构建+自动恢复；Staging 库真实跑通 2024-06 缺口补齐与断点恢复。 |
| **09** | 连续研究 | ✅ 已实现 | ✅ 默认入口主路径 | ✅ P1(6轮)+P2/P3(各4轮) 差量判卷 | ✅ **已合并且生产生效** (`ac013255`) | PR #689 已合 main；项目只读投影+先验块+追问卡 continuation 传递；真实对话差量判卷通过；前端项目页与标签已构建。 |
| **10** | 排序与情景 | ✅ 已实现 | ✅ 分支默认开 | ⚠️ 确定性 44 条 + Live 差分初验 | ❌ 未合主干 | `ranking_contract` 公司矩阵/竞争解释/改判条件；单测 44 绿、全量 8343 绿；Live 初验 Q1 结构完整，批跑待网关恢复。 |
| **历史发现** | 事后发现特征 | ✅ 已实现 | ✅ 分支默认可达 | ⚠️ M1-M5 通过 (M6/UI 待跑) | ❌ 未合主干 | 修合法 case 引用 (B) 与空池回退声明 (A)；M1–M5 真实复验全 PASS；全仓 CI 8619P/0F 绿收据。 |
| **I2** | 能力二期集成 | ⚠️ 部分集成 | ⚠️ 分支集成中 | ⚠️ 单测通过 / Live 集成待跑 | ❌ 未合主干 (`330c2094`) | 已集成 01/02/03/05/06/07/09 部分能力，完成 graph_lookup mode 路由与 TaskFrame 对话块传递；全量集成待收尾。 |

---

## 二、 逐项质检实测与证据核验

### 00 · 真实能力基线 (Capability Benchmark)
- **Git 与分支状态**：工作树 `/Users/a77/fwp-wt-capability-benchmark-00`，分支 `baseline/capability-benchmark-00`，HEAD `cdb16985`。
- **已实现**：✅ 30 题（20 可见 + 10 隐藏）题集与仓外密封判分 rubric 冻结（`ad2cda04`）；`capability_benchmark` 模块包含 validate/overlap/seal-verify/run/review-pack/aggregate 全套工具与 10 条通过单测。
- **已进默认入口**：❌ 独立评测框架，运行在独立 sidecar 端口（如 8813），不直接修改生产入口。
- **真实验收**：⚠️ **进行中（6/30 完成）**。
  - 首跑 30 题因网关 429 烧穿与判官 grok 沙箱报错而全盘作废（已移出仓）。
  - 修复 `7180460d`（支持中断保护与干净 resume）后挂载自动化编排循环；实测抓到 6 道干净题（feel-01, feel-02, material-01, material-02 等）；
  - **B7 实测发现**：发现路由层把题面内回指（如"这条线"）误判为跨轮追问，导致引擎 A 未接手的确定性缺陷。
- **生产生效**：❌ 未合并到 main，未在生产部署。

---

### 01 · 判官修复 (Judge Recovery)
- **Git 与分支状态**：工作树 `/Users/a77/fwp-wt-judge-recovery-01`，分支 `fix/judge-recovery-01`，HEAD `0c4a0bab`，PR #693。
- **已实现**：✅ 三刀全落地：
  1. 第一刀：`EXTRA_OUTPUT_BINDING` 降级为 STRIP_OK，扩展输出不连坐核心输出。
  2. 第二刀：`ProgressSnapshot` 按内容计算进展，来源独立性 `new_source_families` 独立记账。
  3. 第三刀：`_guided_retrieve_and_rejudge` 纯语义早退点引导回检索，V11 遥测对齐。全仓全量单测 **8330 passed / 0 failed**。
- **已进默认入口**：✅ `continuous_turn_adapter` 默认路径调用 `verify(retrieve_fn=)`，V11 默认开启。
- **真实验收**：⚠️ 真实 Workbench 入口（8821/8822）5 题 × 2 臂串行跑通，两臂均出模型草稿。Q5 明确展现出分支臂判官拒绝"必涨停"前提并给出条件研判的优势；Q3/Q4 因上游 503 账号池间歇抖动导致两臂证据量不对等。离线 391 存证回放 0 差异（证明线上此前未曾自然触发该两处边界）。
- **生产生效**：❌ PR #693 尚未合入 main，生产 8792 未包含此改动。

---

### 02 · 深读检索 (Retrieval Deep Read)
- **Git 与分支状态**：工作树 `/Users/a77/fwp-wt-cap02-deep-read`，分支 `feat/cap02-retrieval-deep-read`，HEAD `63b7859a`。
- **已实现**：✅ `kb_rag.py` 自动深读命中节并切片（≤240字）；过期货命中触发重读原页 `recover_stale_hits`；web_fetch 支持按问句定向切片与来源权威度分类。43 条新增单测全绿，全量 7481 passed。
- **已进默认入口**：✅ 默认开启（`KB_DEEP_READ_TOTAL_CHARS=3000`）。
- **真实验收**：✅ 
  - **离线 20 题四臂实测**：Hybrid 模式关键短语进入模型可见从基线 **14/20 提升至 19/20 (+5 题)**，成功翻正表格行（dr-01, dr-19）与同页别节（dr-10）。
  - **Live Workbench 实测**：3 题两臂对照，进模型可见从 1/3 提升至 3/3；dr-10 成功在公开答案写出 1.22 亿；dr-19 从基线降级模板转变为带证据编号的情景推演。
- **生产生效**：❌ 未合并到 main，生产 8792 未包含。

---

### 03 · Wiki 研究地图 (Wiki Research Map)
- **Git 与分支状态**：知识库仓已合入 main（PR !146 / !147，commit `0f7ce1dfd`）；金融升级计划树 `d93d8673` 维护集成合同。
- **已实现**：✅ 知识库侧实现 `research-map`（环节/变量/暴露/支持/变化/缺口六大维度）、派生视图 SQLite、范围选择器 `research_scope.py` 与 18 条单测。
- **已进默认入口**：⚠️ 知识库 CLI 默认可用；金融侧 Workbench 默认入口需经由 06/I2 的 `graph_lookup` 适配器接通（合同见 `03-graph-lookup-adapter-contract.md`）。
- **真实验收**：✅ 知识库 6 题冻结题包实测验收 exit 0（覆盖液冷、光模块、固态电池三大题材，增益 6/6）。
- **生产生效**：⚠️ 知识库 main 即生效；金融侧生产 Workbench 尚未集成。

---

### 04 · 计算与产物 (Calculation & Artifacts)
- **Git 与分支状态**：工作树 `/Users/a77/fwp-wt-calc-artifacts-04`，分支 `feat/calc-artifacts-04`，HEAD `06724a2c`。
- **已实现**：✅ `financial_data` 挂载 `StructuredObservation` 并支持 `subjects` 多公司；沙箱内置 `fincalc` 财务助手；orchestrator 渲染 `calc-*.{json,html,csv}` 产物并通过 RunStore 暴露下载。相关 396 单测过。
- **已进默认入口**：✅ 只要授权 `financial_data` 即自动带 `derived_calculation`。
- **真实验收**：⚠️
  - **确定性干跑**：真实东财取数+沙箱单季还原，茅台 2025Q1–2026Q2 六季单季营收与参考值 **6/6 逐格一致**（514.43 / 396.51 / 398.10 / 411.50 / 547.03 / 375.75 亿）。
  - **Live 实测**：21:14 成功跑通贵州茅台单季计算并落盘 `calc-2768da969179e899` 产物；修复模型参数与 KeyError 两个交互缺陷；全量 5 题批跑受 Cockpit 冷却阻塞。
- **生产生效**：❌ 依赖底层 #682，分支未合并，生产 8792 未包含。

---

### 05 · 输入理解 (Input Understanding)
- **Git 与分支状态**：分支 `feat/input-understanding-05` 已通过 PR #696 合入 main（commit `ac013255`）。
- **已实现**：✅ TaskFrame 扩展 `user_premises / materials / competing_explanations / method_candidates`；`query_understanding` 剔除材料正文对题型路由的干扰；`episode_factory` 构造输入理解上下文。单测 195 全绿。
- **已进默认入口**：✅ 生产主路径 `decide_turn → build_task_frame`、`understand_query` 默认生效。
- **真实验收**：✅ 
  - **Frame 级**：真实对话入口 11/12 正确进入任务（基线仅 1/12）；C1–C4 追问链正确解析。
  - **材料内容使用**：生产 22:12 复验，Frame 侧材料身份全部正确登记（Q06/Q08/C2/C3）；答案侧受判官降级拦截。
- **生产生效**：✅ **已合入 main 且已切入生产 8792**（`ac0132553aae`），部署账本已双记。

---

### 06 · 自适应研究 (Adaptive Research)
- **Git 与分支状态**：工作树 `/Users/a77/fwp-wt-adaptive-research-06`，分支 `feat/adaptive-research-06`，HEAD `f189a6ac`。
- **已实现**：✅ 运行时 `research_progress.py` 跟踪证据增量、重复查询、空手连击；在 `runtime_budget` 中下发 `switch_query / switch_tool / follow_up_divergences` 等建议码。389 条单测通过。
- **已进默认入口**：✅ 进展块默认开启（`WORKBENCH_RESEARCH_PROGRESS`）；停滞收口按实测决策保持默认关（避免过早扼杀深挖）。
- **真实验收**：✅ 基线（8811）与候选（8812）各 12 题（8 复杂 + 4 简单）**24/24 全部收齐干净收据**：
  - 候选臂事件流记录 23 个建议码，并在 C2/C5/C6 捕获模型遵从建议换路；
  - 4 道简单题 0 次 sub_research 滥用，≤6 次工具完成。
- **生产生效**：❌ 未合入 main，生产 8792 未包含。

---

### 07 · 方法飞轮接线 (Method Flywheel)
- **Git 与分支状态**：分支 `feat/cap07-method-flywheel` 已通过 PR #692 合入 main（commit `794cc3e5`）。
- **已实现**：✅ 观察登记为 `method_observation` checkpoint；夜间回检按 `method_validation` 协议自动结算；`memory_lookup` 与 `[M]` 块消费方法验证读数；daily_agent 报表投影。全仓 CI 8381P/0F。
- **已进默认入口**：✅ Workbench 引擎 A（`memory_lookup`）与引擎 B（`[M]` 块）均已接通。
- **真实验收**：✅ 真实对话 2 题实测通过：题 1 调取 `memory_lookup` 并识别降级结论，题 2 语义识别接力。
- **生产生效**：✅ **已合入 main 且已在生产 8792 激活**；生产用户目录完成 `register` 与 `history` 运行，前向协议自 2026-09-10 正式起跑。

---

### 08 · 问题驱动补数 (Demand-Driven Data Requests)
- **Git 与分支状态**：工作树 `/Users/a77/fwp-wt-demand-driven-data`，分支 `feat/demand-driven-data-requests`，HEAD `3fdc1193`。
- **已实现**：✅ `tool_hunger` 挂载 `window_uncovered` 缺口事件；`data_requests.py` 实现缺口合并与自动生成；CLI 提供 `build/check/fill/resume`；修复了恢复失败重试与日历宽容带。单测 21 条全绿。
- **已进默认入口**：✅ `finance_query` 缺口自动进入遥测，CLI 与研究队列接通。
- **真实验收**：✅ Staging 库（3.4GB 隔离拷贝）全链实测：QA/QB/QC/QD 四问在补前均无法回答并产生缺口事件；合并生成 1 条请求，两轮 fill 补齐 2024-06 行情后状态转为 satisfied；resume 成功驱动 QA 答出正确历史数据。
- **生产生效**：❌ 隔离 Staging 验证通过，未合入 main，生产 8792 未包含。

---

### 09 · 连续研究 (Continuous Research)
- **Git 与分支状态**：分支 `feat/continuous-research-09` 已通过 PR #689 合入 main（commit `83e4185f`）。
- **已实现**：✅ `research_project.py` 提供会话/Run 链只读投影；先验块注入引擎 A 上下文；追问卡携带 `continuation`（kind + inherits）；前端新增「项目」面板与卡片标签。单测与前端测试全绿。
- **已进默认入口**：✅ Workbench 默认对话主路径已包含跨轮先验投影。
- **真实验收**：✅ 
  - P1（光模块，6 轮）+ P2（农业，4 轮）+ P3（创新药，4 轮）真实对话完成；
  - 差量判卷全部通过，照出并修复了两处投影缺陷（#697 / #699）；
  - 前端项目视图字段完全来自真实对象。
- **生产生效**：✅ **已合入 main 且已切入生产 8792**（`ac0132553aae`）。

---

### 10 · 排序与情景 (Ranking & Scenarios)
- **Git 与分支状态**：工作树 `/Users/a77/fwp-wt-ranking-scenarios-10`，分支 `feat/ranking-scenarios-10`，HEAD `6144f4f5`。
- **已实现**：✅ `ranking_contract.py` 实现排序意图识别、公司矩阵、竞争解释、改判条件表生成与解析；`apply_scenario` 支持机械再排序；改判条件自动登记到 `checkpoints.jsonl`。单测 44 绿，全量 8343 绿。
- **已进默认入口**：✅ 引擎 A（`episode_protocol`）与引擎 B（`ask_synthesis`）默认规则链注入。
- **真实验收**：⚠️ 候选臂实测 Q1 成功输出 4 公司矩阵与 3 条改判条件（1473 字 vs 基线 812 字无结构）；全量 6 题配对批跑受网关 57244/8080 冷却与抖动阻塞。
- **生产生效**：❌ 未合入 main，生产 8792 未包含。

---

### 历史发现 (Historical Discovery)
- **Git 与分支状态**：工作树 `/Users/a77/fwp-wt-historical-discovery`，分支 `codex/feat-historical-discovery`，HEAD `57f9f17e`（代码基线 `dea3c6fa`）。
- **已实现**：✅ 修复合法 case 引用校验缺陷（B `a963002f`）与空池回退时声明 `application_tool_call`（A `7751ab81`）；对齐历史三工具注册表元数据；全仓 CI 收据 **8619 passed / 0 failed**。
- **已进默认入口**：✅ 共享 `finance_query` 权限与装配通道，默认可达。
- **真实验收**：⚠️ 隔离 8809 实例复验 M1–M5 全部 PASS（无 `history_unknown_result`，M5 触发空池回退成功）；M6 与 UI 追问因网关冷却待跑。
- **生产生效**：❌ 未合入 main，生产 8792 未包含。

---

### I2 · 能力二期集成 (Capability Integration 2)
- **Git 与分支状态**：工作树 `/Users/a77/fwp-wt-capability-i2`，分支 `feat/capability-i2`，HEAD `330c2094`。
- **已实现**：⚠️ 
  - 已合入主干最新提交（含 05, 07, 09）；
  - 完成 `graph_lookup` 对 03 知识库研究地图的 mode 路由适配（`330c2094`）；
  - 完成 turn_controller 把对话块传进 `build_task_frame`（B05-1 解决，`b2b6e619`）；
  - 正在集成 01, 02, 04, 06 的最新进展。
- **已进默认入口**：⚠️ 集成工作树分支中，尚未成为主干默认入口。
- **真实验收**：⚠️ 局部单测通过，全量端到端联合验收待网关与各子任务稳定后启动。
- **生产生效**：❌ 未合入 main，生产 8792 未包含。

---

## 三、 横切发现与系统性阻塞点 (Cross-Cutting Findings)

1. **共享 LLM 网关容量与冷却制约批量验收**
   - 本地双网关通道呈现分化：
     - **Cockpit (:57244)**：单次 5 小时额度窗口在满负载（4–6 个 max 档 run）下约 30 分钟即耗尽，随后触发 `reset_seconds ≈ 16000s`（4.5 小时长冷）；
     - **Mirasim / Sub2API (:8080)**：上游池在高并发时频繁返回 502/503，呈现间歇性闪断或抖动态。
   - **质检启示**：各单在真实验收时必须引入单题探活、错误打标隔离（`quota_tainted`）与棘轮式 `--resume` 续跑机制，严禁将网关 429/502 误归因为系统能力缺陷。

2. **判官启动环境历史漂移**
   - 生产启动器曾钉死 `grok-1.0.5`（已被系统自动清理），且 grok 1.0.13/1.0.24 在 macOS 环境下以 `read-only` 沙箱模式启动时，会因解析 `/var/run/docker.sock` 软链接失败而退出（`GrokCliExit 1`），导致公开答案统一降级为"复核服务不可用"模板。
   - **已实施纠偏**：生产与各验收旁路实例已明确修正为 `LLM_JUDGE_GROK_BIN=~/.grok/bin/grok` + `LLM_JUDGE_GROK_SANDBOX=off`，判官链路恢复正常。

3. **生产 8792 当前版本梯度**
   - 生产当前运行在 `ac0132553aae`（2026-09-09 晚切流），已涵盖 **05 (输入理解)**、**07 (方法飞轮)**、**09 (连续研究)** 的第一刀功能；
   - **01 (判官修复)**、**02 (深读检索)**、**04 (计算产物)**、**06 (自适应研究)**、**08 (补数驱动)**、**10 (排序情景)** 均已在各自工作树完成高质量代码实现与单测/干跑验证，处于分支待合入或待部署状态；
   - 建议在 I2 工作树统一完成联合回归与网关窗口验证后，组织下一批次生产升级。

---

## 四、 质检结论与归档签名

- **审计结论**：INDEX 任务包各项推进扎实，代码与单测覆盖完备。05、07、09 已率先闭环并进驻生产；02、03、06、08、10、01、04 已具备决定性能力增量与实测证据；00 正在稳步建立标准尺度。未发现虚构事实、绕过门禁或伪造收据行为。
- **审计产物**：`/Users/a77/fwp-wt-capability-upgrade-plan/quality-audit-2026-09-10.md`
- **审计执行**：Kimi-K3（Claude Code CLI 审计会话）  
- **归档时间**：2026-09-10 02:45 CST