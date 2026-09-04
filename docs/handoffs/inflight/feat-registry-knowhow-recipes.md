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
- registry 编译完成：`registry-check` → `recipes 6（pending-grilling: -）`；`pytest tests/test_consumption_registry.py
  tests/test_tiered_sync_local.py` 18 passed；ruff 绿。
- 全量门禁（`run_main_gate.sh`，干净树 `92dab79e`）：ruff 绿、pytest **7700P/0F/15S/1x**，收据
  `~/.finance-runtime/test-receipts/20260904T145*-92dab79e.json`；diff 不触碰 `intelligence/webapp`，frontend/e2e 叶子不受影响。
  PR #586 待用户确认合并。
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

## 未验证 / 已知边界
- 三条 recipe 的阈值（N、Top N、权重）全部未回测；`theme_logic_cycle` 的四段判据是草案。
- 原骨架写的「知识库 36 篇文档」清单未定位 [未实测]。
- 探索只跑了 k-means；没试层次聚类或 GMM。281 天样本、9 维，结论不外推到别的库。
- 每日情绪向量里 `max_boards` / `double_red_theme_count` 分别只有 349 / 340 天有值，全维可用 281 天。

## 下一步
1. 用户命名四簇（或指定 k=5）→ agent 按命名把簇边界翻译成规则阈值草案 → 用 281 天回放看规则标签与簇标签的一致率与切换次数。
2. `ma5_rotation_cycle`：先写独立脚本跑案例表（`detect_turning_points` 切周期 × `fact_stock_daily` 两榜），出实验台账；成立再进夜跑 `features` 步。
3. `theme_logic_cycle`：先定位知识库题材周期文档清单，再做题材级向量与阶段判据回放。
4. 三条任一实施后把 `status` 翻 `live`，并把实施路径写进 `joins`。

## 踩过的坑
- `tests/test_consumption_registry.py` 原断言「必须留 pending」是个只能拦第一次、拦不住最后一次的棘轮；改成逐条 status ↔ 占位一致才守得住真正的漂法。
- 从 worktree 起 `connect(read_only=True)` 会解析到 worktree 自己的 `db/`（不存在）——探索脚本要显式 `MARKET_FEATURE_STORE_DB` 指主树。
- venv 没有 sklearn；numpy 手写 k-means++ + 轮廓系数足够（281×9），不要为探索装依赖。

## 工具沉淀
「聚类找边界、规则守生产」+「状态类特征先窗口化再聚类」是可迁移方法，未成通用零件，不回写 KIT.md。
