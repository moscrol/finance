# feat/registry-knowhow-recipes

## 这个分支做什么
把 `market_feature_store/consumption_registry.yaml` 里三条 `pending-grilling` 的 knowhow recipe
（`theme_logic_cycle` / `ma5_rotation_cycle` / `money_effect_clustering`）按 2026-09-04 grilling round 1
的决策编译成 `status: note`：`joins` 写成可实施的联立方式、`proactive` 写成触发条件，另加
`decisions`（采纳的选型 + 被弃的替代方案）与 `open`（round 2 待敲定项）。

决策来源：agent 出六道题各附推荐答案与替代方案对比，用户令「按照最优执行」= 推荐全部采纳。
决策**可推翻**——改 registry 里的 `decisions` / `open` 即可，没有任何代码依赖这些文本的具体措辞。

配套改测试 `tests/test_consumption_registry.py`：原来断言「至少留一条 pending-grilling」在三条全部编译后会
永久红，且守不住真正的漂法（改 status 却留「待编译」）。改为逐条 recipe 判：`pending-grilling ⇔ joins/proactive
含「待编译/待定义」`，且 `proactive` 非空。

## 当前状态
- **PR #588（round 2：四簇命名 + 规则草案回写）已合入 `gitea/main@2087c730`**（2026-09-05，派单口令「合 #588」= 用户确认；
  门禁收据 `~/.finance-runtime/test-receipts/20260904T153528Z-bf7a8f4a.json` 7710P/0F/15S）。主树已 `--ff-only` 到同一 SHA，
  `registry-check` 通过（`recipes 6（pending-grilling: -）`）。
- **Round 3（2026-09-05）在分支 `feat/money-effect-regime-rules` 上，PR 已开、未合**：赚钱效应规则模块 + CLI + 15 条测试落地，
  但分位阈值版回放一致率 57.8%（< 70% 门槛；同子集绝对阈值 83.9%）→ **不翻 live、proactive 未接线**；MA5 (a′) 不成立；
  题材周期 KB 材料定位完成（方法论类 0 篇）。三条 recipe 仍 `note`。详见下「Round 3」节；门禁读数见该 PR 正文。
- registry 编译完成：`registry-check` → `recipes 6（pending-grilling: -）`；`pytest tests/test_consumption_registry.py
  tests/test_tiered_sync_local.py` 18 passed；ruff 绿。
- 全量门禁（`run_main_gate.sh`，干净树 `92dab79e`）：ruff 绿、pytest **7700P/0F/15S/1x**，收据
  `~/.finance-runtime/test-receipts/20260904T145*-92dab79e.json`；diff 不触碰 `intelligence/webapp`，frontend/e2e 叶子不受影响。
  PR #586 **已合入**（用户口令「合并」，`gitea/main@2c5520b3`，2026-09-04 23:0x）。worktree `/Users/a77/fwp-wt-tiered-sync`
  仍停在已合并的本地分支 `feat/registry-knowhow-recipes`，远程分支已由 Gitea 删除。
  round 2 默认值已向用户提出（赚钱效应 k=4 + 切换去抖 2 日；MA5 两榜 Top 20 + Jaccard + 先独立脚本；题材退潮 N=3 + 等权），
  等用户命名四簇 / 反对即改。
- `money_effect_clustering` 的第一段探索（两段式里的「聚类找边界」）已跑，结论回写进 recipe 的 `decisions`，见下。
- 另两条只到文本层，未做任何探索或派生表。

## 怎么验收
1. `python3 -m market_feature_store.cli registry-check` → 通过，pending 列表为 `-`。
2. `pytest -q tests/test_consumption_registry.py` → 全绿，其中 `test_recipe_status_matches_placeholder_state`
   守 status ↔ 占位一致。
3. 读 registry `recipes` 段：三条各有 `joins`≥4 条、`proactive` 非「待定义」、`decisions` 2~3 条、`open` 1 条。

## 探索结论（money_effect_clustering 第一段，只读生产库，实验代码不入仓）
脚本与三份输出留在 `~/.finance-runtime/experiments/money-effect-20260904/`（`/tmp/mfs-analysis/` 同份）。

**输入**：`market_regime_analogs.load_market_regime_vectors` 的每日情绪向量 + `standardize_vectors` 全历史 z 标准化；
413 个交易日中 **281 天**九维全非空（2025-01-07 ~ 2026-09-02）；剔 `sh_deviation_pct`（只 221 天有值，tooltip 源
2026-07 起失效）。情绪维（advancers / limit_up / limit_down / max_boards / top1_theme_share）权重 1.0，其余 0.6。
numpy 手写 k-means++，30 次重启取最优惯性，k ∈ {4,5,6} 按轮廓系数选。

**假设**：交易日可按情绪结构聚成少数可命名的「赚钱效应状态」，且状态有持续性（否则「切换日报警」无意义）。

| 聚类单位 | 最优 k（轮廓） | 相邻日换簇率 | 同簇连续天数中位 / 最长 | 重启收敛到最优±1% |
|---|---|---|---|---|
| 单日向量 | 6（0.160） | **71%** | **1** / 6 | 27% |
| trailing 3 日均值 | 4（0.172） | 21% | 3 / 35 | 43% |
| trailing 5 日均值 | 5（0.216） | **10%** | **6** / 42 | 20%（k=4 为 53%） |

**结论（状态：探索性，成立条件 = 上表窗口与维度）**
1. 单日聚类不能当状态用——天天换簇。聚类单位改成 trailing 5 日窗口（无前视）后才有状态持续性。已写进 recipe。
2. 轮廓系数最高 0.22，按常规判读 <0.25 = 没有清晰簇结构：赚钱效应是**连续谱上的软区域**，不是硬状态。
   所以「规则守生产」那一步不能照抄簇边界，只能取几条可解释的轴（涨家数 / 涨停 / 成交额 / 连板高度 / 第一题材份额）定阈值。
3. k 的取舍是 round 2 决策：k=4 重启稳定（53%）但分离差（0.174）；k=5 分离好（0.216）但 30 次重启只有 20% 收敛到同一解。
   要给规则用的边界，稳定比分离更重要 → 倾向 k=4。

**5 日窗口 k=4 四簇质心（原始量纲，供命名；不是规则阈值）**

| 簇 | n | 成交额(亿) | 涨家 | 涨停 | 跌停 | 最高连板 | 双红题材 | 第一题材份额 | 新高家数 | 直观形状 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| id2 | 91 | 15.9k | 3031 | 67 | 24 | 5.6 | 17 | 26 | 631 | 缩量、涨家多、无主线——温和普涨 |
| id0 | 60 | 17.9k | 2914 | 73 | 15 | 6.9 | 20 | 35 | 817 | 高度高、第一题材份额高、新高多——抱团有主线 |
| id1 | 85 | 24.3k | 2667 | 67 | 20 | 5.0 | 17 | 29 | 736 | 放量、涨家中性——放量分化 |
| id3 | 41 | 30.0k | 2464 | 87 | 23 | 4.3 | 33 | 31 | 335 | 巨量、涨停多但涨家少、新高少——「涨停多而涨跌家数弱 = 抱团非普涨」的形状 |

「直观形状」是 agent 按质心写的描述，**命名权在用户**（方法论 §六「情绪回答赚钱效应是否扩散或收缩」的词表是候选）。

## Round 2（2026-09-04 深夜，用户「你来命名，没有异议」）
脚本与输出：`~/.finance-runtime/experiments/money-effect-20260904/money_effect_rules*`、
`~/.finance-runtime/experiments/ma5-cycle-20260904/ma5_cycle_cases*`（不入仓）。

### 赚钱效应：命名（agent 定）+ 校验
| 簇名 | n | 成交额₅ | 涨家₅ | 涨停₅ | 连板₅ | 第一题材份额₅ | 新高₅ | 集中月份 | fupanhui 六段里的分布 |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 缩量普涨 | 91 | 1.58 万亿 | 2962 | 65 | 5.4 | 25% | 600 | 2025-04~07（49 天）、2025-12 | 顶部横盘 32 / 横盘 22 / 探底 10 / 下跌 9 / 主升 7 |
| 主线引领 | 60 | 1.77 万亿 | 2923 | 75 | 7.1 | 35% | 783 | 2025-01/02（26 天）、2025-11 | 顶部横盘 16 / 主升 14 / 底部横盘 10 |
| 放量分化 | 85 | 2.43 万亿 | 2734 | 68 | 5.0 | 29% | 769 | 2025-08/09（32 天）、2026-04/05 | 顶部横盘 34 / 主升 21 / 横盘 18 |
| 巨量轮动 | 41 | 3.04 万亿 | 2431 | 87 | 4.3 | 31% | 346 | 2026-06/07（36 天） | 顶部横盘 10 / 反弹 9 / 下跌 8 / 底部横盘 8 / **主升 0** |

命名依据：每个名字带「量能 + 结构」两个词。巨量轮动 = 巨量、涨停多、双红题材多（33 个）、但连板低、新高少、涨家少——
资金在题材间快速轮动无持续性，且一天主升都没有；主线引领 = 连板高度 7.1 + 第一题材份额 35% + 新高多 + 跌停少；
缩量普涨 = 成交最低、涨家最多、无主导题材；放量分化 = 放量、涨家中性、新高多（强者恒强）。

### 赚钱效应：规则草案（「规则守生产」的输入，未进生产）
在 5 日 trailing 原始均值上学浅决策树（numpy，叶≥12）：depth-2 一致率 79%（两条轴：成交额₅ 22114 亿 ／ 第一题材份额₅ 29% ／ 新高₅ 464 家），
depth-3 86% 但有三片纯度 40~54% 的脏叶子（软区域）。手工收成 **4 条决策表**（按序命中）：

1. 成交额₅ > 26196 亿 且 新高₅ ≤ 464 家 → **巨量轮动**
2. 成交额₅ > 22114 亿 → **放量分化**
3. 第一题材涨停份额₅ > 29% 且 最高连板₅ > 6 板 → **主线引领**
4. 其余 → **缩量普涨**

与簇标签 in-sample 一致率 **81%**；主要混淆是 主线引领→缩量普涨 19 天、放量分化→缩量普涨 19 天（「其余」兜住了软边界）。
切换：决策表 29 次 / 277 窗口，**2 日去抖后 21 次 ≈ 每 13 个交易日一次**（约 1.5 次/月，可当报警频率）。
最近窗口：08-14~08-25 放量分化 → 08-26 起 缩量普涨（去抖后 09-01/02 仍缩量普涨，簇标签已跳放量分化——软边界实例）。
**成立条件**：in-sample、277 窗口、2025-01~2026-09；成交额阈值 22114 / 26196 亿 ≈ 样本第 59 / 78 百分位，
绝对亿元会随市值漂移，生产版应改滚动 250 日分位再重测。

### MA5 交替：假设 (a) 未获支持，提出 (a′)
72 段（37 谷 / 36 峰，MA5_MIN_SWING 默认；段长中位 6 天，确认滞后中位 2 天），每段两榜 Top 20：

- 两榜确实是两群人：J(R,W) 中位 0.21（上升）/ 0.18（下降）；W 榜个头（榜内中位成交额/全市场中位）25x，R 榜 4.5x。
- 但**每段换人**：与上一同向段 J(R)=0.00、J(W)=0.03。
- **下一段没有延续也没有反转**：R 榜均收益中位 +0.1%（>0 占 52%），W 榜 +0.1%（51%）。
- **交替检验不成立**：相邻上升段 R 榜个头「大/小」序列 `小大小小小小小小大大小小大大大大小小大大大大小大大大大小小大大大小小小小`，
  相邻翻转率 34%，低于随机 50%——是**多周期 regime**（连续几个周期小票领涨、再连续几个周期大票），不是逐周期交替。
- 结论状态：(a) 在本样本**不成立**，不写规则；新假设 **(a′)** 「领涨个头大小是 regime 变量」，下一步与赚钱效应四簇做交叉表
  （直觉：缩量普涨 ↔ 小票领涨，放量分化/巨量轮动 ↔ 大票领涨）。
- 边界：2~3 天的碎段（#53/#56/#61/#71）是 zig-zag 阈值偏小的产物，Top 20 在 2 天段上噪声大；MA5_MIN_SWING 敏感性未测。

## Round 3（2026-09-05，接手单 C；用户不在线，判断写在「决策与被否方案」）
分支 `feat/money-effect-regime-rules`（树 `/Users/a77/fwp-wt-money-effect-regime`，基线 `gitea/main@6cc238df`）。
实验产物：`~/.finance-runtime/experiments/money-effect-20260905/`（簇标签重出 + 分位反推 + 回放诊断）、
`~/.finance-runtime/experiments/ma5-cycle-20260905/`（(a′) 交叉表 + MIN_SWING 三档），均不入仓。

### 3-A 赚钱效应进生产：机制落地，**不翻 live**
做了什么：
- `market_feature_store/money_effect_regime.py`：4 条决策表（形状冻结自 round 2）、阈值改「最近 250 个窗口的经验分位」
  （分位数从绝对阈值反推一次：26196 亿→P78、22114 亿→P59、464 家→P36、29%→P50、6 板→P75，唯一定义 `THRESHOLD_QUANTILES`）、
  trailing 5 日均值、MIN_HISTORY 60（不足不出簇名）、**因果** 2 日去抖、fail closed、不落表；`forward_facts` 以切换日起算只列事实。
- CLI `python3 -m market_feature_store.cli money-effect-regime [--as-of] [--json] [--replay-since D --cluster-labels PATH]`。
- `tests/test_money_effect_regime.py` 15 条；**变异测试**：`DEBOUNCE_DAYS` 2→1 → `test_scenario_switch_count_with_production_debounce` 红
  （1 failed / 14 passed，已还原）。
- 取数层下沉：`FEATURES / _AUX_QUERIES / load_market_regime_vectors` 从 `intelligence/services/market_regime_analogs.py` 搬到
  `market_feature_store/market_regime_vectors.py`，原处 re-export（既有 import 与双红棘轮测试不用改）。

回放（真库只读，簇标签同 SEED 重出、四簇规模 91/60/85/41 与 round 2 一致）：

| 标签器 | 窗口 | 与簇标签一致率 | 去抖后切换 |
|---|---:|---:|---:|
| round 2 绝对阈值（全 277 窗口） | 277 | 80.9%（复现 81%） | 21 |
| round 2 绝对阈值（同 218 窗口子集） | 218 | **83.9%** | - |
| **round 3 分位版（滚动 250，MIN_HISTORY 60）** | 218（2025-05-21~2026-09-02） | **57.8%**（去抖后 56.4%） | 14（≈ 每 15.6 窗口） |
| 分位版，扩张窗口 lookback=∞ | 218 | 57.8%（与滚动 250 完全相同） | - |

混淆（行=簇，列=分位规则）：巨量轮动 38/3/0/0；放量分化 23/51/0/6；主线引领 0/26/**0**/0；缩量普涨 2/32/0/37。
按 lookback 长度：60~119 → 60%，120~199 → 34%，200~249 → 100%，=250（2026-08，28 窗口）→ 46%。

**为什么低**（不是窗口长短——滚动 250 与 ∞ 结果相同）：簇标签是**全样本 z 标准化**（固定基线）的产物，因果分位基线在
2025→2026 量能 1.5→3 万亿的单向趋势里必然滞后（2025-09 滚动 P59 只有 16,291 亿 vs 全样本 22,114），于是簇的「放量分化」被判
「巨量轮动」，「主线引领」在规则②就被截走（0 命中）。样本末端两版阈值收敛（2026-08 P59 22,318 / P78 26,594 vs 22,114 / 26,196），
今日两版同判。语义交叉表：分位版仍保「巨量轮动 → 主升 0 天」，但主线引领消失、放量分化膨胀到 112/218。
**这条回放测的是趋势不是规则质量**：277 窗口不到 lookback 的 2 倍，只有 28 个窗口是满基线；拿因果-相对标签器对全样本-绝对标签器，
分歧就是趋势本身。成立条件：对 2025-01~2026-09 这段单向抬量样本成立。

决策与被否方案（用户不在线，按工单「< 70% 停下写原因，不硬上」）：
- **不翻 live**，`status` 留 `note`；`joins` 写了实施路径；`open` 列 round 4 三条出路：(1) 绝对阈值 + 定期重校准（每 250 窗口重跑反推，
  同子集 83.9%，可即刻翻 live；代价是校准日进 decisions）；(2) 保留分位版等库内 ≥ 500 窗口再评（≈ 2027 下半年）；(3) 换比较基准——
  用滚动标准化重跑 k-means（本轮禁）。我的推荐是 (1)：「阈值会漂」的标准解法本来就有两种——动态基线与定期重校准，样本不够长时后者可测、前者不可测。
- **proactive 未接线**：工单步骤 4 要接进一个消费者，但步骤 6 说不过门槛就停。接一个一致率 58% 的标签进日报，下游 agent-daily 会把它当事实
  归因（本仓有「未映射」被解释成方向的前例）。选定落点 `market_feature_store/reports/daily_review.py`「市场情绪」节
  （每日必跑、已读 `fact_market_daily`、有测试）；接法一行：`state = money_effect_regime.load_regime_state(con, td)` →
  切换日 `_note(switch_headline)` + `_table_block(axis_rows)` + `_note(forward_facts_text)`，非切换日 `_note(one_line)`，不可用 `_note(one_line)`
  也是一行。被否：接线但加「校准中」字样（下游模型不会因此少推一段）。
- **取数层下沉**而不是从 `market_feature_store` 反向 import `intelligence`：此前两包之间零向上依赖，第一条就是包级环。被否：
  模块改放 `intelligence/services/`（那样 daily_review 接线时还是要反向 import）。
- 5 日窗口在**可用日序列**上滚（不是日历连续交易日），照实验口径；库里 2026-01~03 整段缺口会被窗口跨过——记在 `open`。
- 今日（2026-09-02）：**缩量普涨**（连续第 9 窗口；成交额₅ 20,363 亿 / 新高₅ 858 / 份额₅ 26% / 连板₅ 6.0；只命中 boards_high）。

### 3-B MA5 (a′)：**不成立**；碎段是 round 2「多周期 regime」的来源
- R 榜个头 × 段内主导簇（k-means 与绝对规则两份标签，62/72 段有标签）：四簇 R 榜个头中位 4.0~4.5x，大/小对半
  （巨量轮动 4/5、放量分化 8/8、主线引领 8/6、缩量普涨 11/12）→ regime 不区分 R 榜个头。
- 随 regime 单调的是 **W 榜个头**（37.5x → 29.9x → 19.0x → 16.2x）与 **J(R,W)**（0.11 → 0.25）：量越大两榜越是两群人。
  若继续，改问 (a″)；但 W 榜按 √amount 加权、与量能 regime 部分同源，先排除同源性再当发现。
- MIN_SWING 300/500/800：段数 97/72/48，碎段（≤3 日）32/10/0，上升段 R 榜个头翻转率 33%/34%/**52%**——碎段清零就回到随机基线，
  说明 34%<50% 是相邻碎段共享同一批领涨股的假象。生产 `turning_points.MA5_MIN_SWING=500` 不动（那是转折信号的口径）。
- 不建 `feature_` 表、不翻 live。

### 3-C 题材周期文档定位：方法论类 0 篇，结构化材料在 relations/
只用 `rg --files` + frontmatter/标题行 + `query_relations.py stats`，未读正文。定位到：`theme_signals.json`（182 题材 ×
recognition_timeline / progress_ruler / market_heat / price_signals / action_plan / `_meta.stage_floor`）、`pattern_library.json`
（4 题材 × stages / key_signals）、`fupanhui_panorama.json`（2 全景）、27 篇 theme-radar 报告（26 篇带「## 发酵进度」）、1 篇
`fermentation_report`。「36 篇」未定位到；含「周期」的 concepts 全是商品周期。清单写进 `theme_logic_cycle.joins`。

## 未验证 / 已知边界
- 三条 recipe 的阈值（N、Top N、权重）全部未回测；`theme_logic_cycle` 的四段判据是草案。
- ~~原骨架写的「知识库 36 篇文档」清单未定位 [未实测]~~ round 3-C 已定位：方法论类 0 篇，结构化材料在 `relations/`（见 Round 3）。
- 探索只跑了 k-means；没试层次聚类或 GMM。281 天样本、9 维，结论不外推到别的库。
- 每日情绪向量里 `max_boards` / `double_red_theme_count` 分别只有 349 / 340 天有值，全维可用 281 天。
- 赚钱效应分位版的回放是 in-sample 且样本不到 lookback 的 2 倍；样本外验证要等用户补完 09-03 / 09-04 后 2026-09 起的新窗口。
- round 3 所有回放在真库只读跑；主库 mtime/体积未变（2026-09-03 15:10:52 / 1,798,320,128 字节，跑前跑后一致）。

## 下一步
1. ~~命名四簇 → 规则草案 → 回放~~（round 2）；~~D 档模块 + CLI + 测试 + 分位重测~~（round 3-A，57.8% 未过门槛）。
   **round 4 · 赚钱效应**：用户在 `money_effect_clustering.open` 三条出路里选一条；选 (1) 则把 `rolling_thresholds` 换成常量表 +
   校准日进 decisions → 翻 `live` → 接线 daily_review「市场情绪」节（一行接法见 Round 3）；选 (2) 则只等数据。
2. ~~MA5 案例表~~（round 2，(a) 不成立）；~~(a′) 交叉表 + MIN_SWING 敏感性~~（round 3-B，(a′) 不成立）。
   **round 4 · MA5**：决定这条 recipe 是否继续；若继续只剩 (a″) 两榜分离度 / W 榜个头 × regime（先排除 √amount 同源性）。
3. ~~定位知识库题材周期文档清单~~（round 3-C）。**round 4 · 题材周期**：题材级向量（逻辑轴维吃 `theme_signals.json`
   recognition_timeline / stage_floor，盘面轴维从 `fact_*` 算）→ 签名法第一期 → 阈值回放。
4. 三条任一实施并过验证后把 `status` 翻 `live`（实施路径已在 `joins`）。

## 踩过的坑
- `tests/test_consumption_registry.py` 原断言「必须留 pending」是个只能拦第一次、拦不住最后一次的棘轮；改成逐条 status ↔ 占位一致才守得住真正的漂法。
- 从 worktree 起 `connect(read_only=True)` 会解析到 worktree 自己的 `db/`（不存在）——探索脚本要显式 `MARKET_FEATURE_STORE_DB` 指主树。
- venv 没有 sklearn；numpy 手写 k-means++ + 轮廓系数足够（281×9），不要为探索装依赖。
- 用「与聚类标签的一致率」验证一个**自适应**阈值，会把样本内的量能趋势算成规则误差：k-means 用的是全样本标准化（固定基线），
  滚动分位是相对基线，两者在单向趋势样本上必然分歧，且与 lookback 长短无关（250 与 ∞ 结果一样）。要么比较基准也改相对（滚动标准化再聚类），
  要么等样本 ≥ 2× lookback。
- 实验脚本的去抖是回看式（`labels[i+1]`）——离线统计没问题，搬进生产必须改因果式；两者切换次数相同、日期差 1 日，别拿次数相同当「实现一致」。
- zig-zag 切段的碎段会让「相邻段翻转率」偏低（相邻碎段共享同一批领涨股），先扫 MIN_SWING 敏感性再解读翻转率。

## 工具沉淀
「聚类找边界、规则守生产」+「状态类特征先窗口化再聚类」是可迁移方法，未成通用零件，不回写 KIT.md。
