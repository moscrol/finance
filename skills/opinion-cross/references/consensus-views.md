# 认同度 staging / 时间轴 / theme-radar 桥

## 认同度 staging + 时间轴（演化视图层 · `consensus_staging.py`）

`opinion_store` 把事件累积进库、`summary` 给一张静态聚合表；但"同一标的被反复提"到底**走到哪一阶、哪天跳的阶、和别的方向比发酵到什么程度**，静态表看不出。`consensus_staging.py` 是库的**演化视图层**：把每个标的/方向的事件按时间累积，映射到 `theme-radar` 已有的认同度阶梯，回答"认同度演变"。

```
opinion-events.jsonl
  → [按标的/方向分组 + 按报告日累积]
  → [可数信号]  跨天数 / 来源数 / 硬度是否升级(软→硬) / 催化 / 最佳Tier / 多空
  → [映射认同度阶梯·下限语义]  观察池(覆盖不足)· → 萌芽★★ → 第一轮(第一枪)★★★ → 催化共振★★★★ → 一致认同★★★★★
  → stage(下限+覆盖度+事实轨/广度轨+理由+升阶/待补触发) / timeline(逐日跳阶轨迹) / board(跨方向横向对比)
```

### ★ 沉淀层适配（核心设计）

库是 **append-only + 去重**、且**持续回补历史卖方研报** → 任何「当前快照」都是**不完整**的，会随回补单调增长。所以**不能把"数据没补够"误读成"市场没认同"**。三条铁律：

1. **阶段 = 下限语义**：输出的是"已入库证据**至少**支撑到哪一阶"。库 append-only，回补只让某标的的 来源/跨天/硬证据 单调增加 → 阶段**只升不降**，绝不把低覆盖当"市场冷"。
2. **单来源软料不判阶**：仅 1 来源且只有软推演的标的 → 归「观察池·覆盖不足(待回补)」，**不**硬扣暗流/萌芽。出现**事实锚点（🟢硬证据/催化）或多来源广度**才正式上阶梯。
3. **两条轨道分离**：事实硬度轨（robust，1 条硬证据即成立、**不随回补变含义**，是阶梯主锚点）vs 舆情广度轨（回补敏感，几家在喊/跨几天，只作覆盖度修饰、标"随回补上升仅供参考"）。

**认同度阶梯（下限）（镜像 `radar.py` recognition 体系，同一把尺）**：

| 阶段 | ★ | 基分 | 判定（高阶优先；事实锚点优先于广度） |
|---|---|---|---|
| 观察池·覆盖不足 | · | 20 | 仅 1 来源、仅软推演 → 不判阶，待回补 |
| 萌芽 | ★★ | 45 | ≥2 来源 或 ≥2 天的软推演共识（广度轨，回补敏感）|
| 第一轮(第一枪) | ★★★ | 60 | 出现🟢硬证据 / 硬度升级(软→硬) / 催化（**单来源也成立**，硬证据 robust）|
| 催化共振 | ★★★★ | 78 | ≥3 来源跨 ≥2 日共振 + 🟢硬证据 |
| 一致认同 | ★★★★★ | 90 | ≥5 来源跨 ≥3 日 + 🟢硬证据（Tier1 加分；越靠此阶越接近透支）|

> 下限分 = 阶段基分 + min(提及数,10) + 多来源(+5) + 硬证据(+8) + 催化(+3)，封顶 99，与 radar `recognition_score` 同公式。阈值集中放脚本顶部常量，便于调松紧。

**用法**：

```bash
STORE="<KB>/wiki/raw/theme-radar/opinion-store/opinion-events.jsonl"

# 三视图一起出（默认）
python3 skills/opinion-cross/scripts/consensus_staging.py --store "$STORE" --term CPO

# 单标的逐日认同度演变（哪天跳阶、被什么信号推上去）
python3 skills/opinion-cross/scripts/consensus_staging.py --store "$STORE" --view timeline --target 中际旭创

# 跨方向横向对比发酵进度（图1 那块）
python3 skills/opinion-cross/scripts/consensus_staging.py --store "$STORE" --view board

# 参数：--view stage|timeline|board|all  --term/--concept/--since 过滤
#       --hide-watch 隐藏观察池只看已上阶梯  --markdown 落地  --json 结构化
```

**已验证（CPO + 6.8/6.9/6.10 机器人三批库，223 事件）**：
- stage（下限语义生效）：罗博特科/兆驰/工业富联（有🟢硬证据，单来源）→ 第一轮(下限，标"广度待回补")；新易盛（2 来源软推演）→ 萌芽；天孚/中际旭创/炬光/联特/矽电（单点软料）→ **观察池·覆盖不足**，不再被误判暗流。
- timeline：**中际旭创**（全库口径）`06-08 第一轮 → 06-09 催化共振(下限分97，3来源跨2日+硬证据) → 06-10 催化共振`——跨日跳阶轨迹正确。
- board：1.6T CPO/半导体设备/人形机器人 已到催化共振(较充分覆盖)，CPO/半导体材料 第一轮(有限)，单点软料方向归观察池——同尺横向可比，覆盖度一目了然。

**边界**：staging 的**库内信号**轨（来源数/跨天/硬度）一直在；认同度的「市场是否兑现/透支」一维**已接 b（盘面回溯 `outcomes.jsonl`）**——`consensus_staging` 的 stage/board 视图新增「盘面兑现(b)」列，`main` 加 `--outcomes`（默认取 `--store` 同目录 `outcomes.jsonl`，**存在才接**，缺则该列照旧标「待接」），由 `pan_realize.py` 把 T+N 盘后回测聚成 `已兑现持稳/兑现中/冲高透支/未兑现·跑输/待观察`，喂回升阶触发；**一致认同 + 冲高透支 = 透支区**（热点≠机会）。纯派生视图，**只读库不写库**。回补越多，下限越准、观察池越少。

## 桥：观点库 → theme-radar 信号层（`consensus_bridge.py`）

`consensus_staging` 是 CLI 视图；`consensus_bridge.py` 把同一套**下限语义**聚合结果**持久化**进
theme-radar 的 `wiki/relations/theme_signals.json`，让 `radar.py` 里长期「待补」的三块变真数据：
**信号层**（order_signals/industry_progress/sell_side_coverage/market_heat）、**认知演变时间线**
（recognition_timeline）、**多方向发酵进度横向对比**（progress_ruler）+ 方向级**操作建议**（action_plan）。

**聚合口径**：方向(concept)为信号原子单位、**全库聚合**；每个方向归属其**主 term**（事件最多的 term），
term 条目 = 其名下各方向的全库事件并集 → 与 `consensus_staging --view board` 完全一致（避免 term-scoping
把跨 term/跨日的同一方向证据割裂而低估阶段）。`price_signals` 留空待 **b**。

```bash
STORE="<KB>/wiki/raw/theme-radar/opinion-store/opinion-events.jsonl"
SIGNALS="<KB>/wiki/relations/theme_signals.json"

# 预览将写入的 theme 列表（不落盘）
python3 skills/opinion-cross/scripts/consensus_bridge.py --store "$STORE" --theme-signals "$SIGNALS" --dry-run

# 落盘（append-only 友好：只覆盖本桥写的条目 _source==consensus_bridge，保留其它来源 theme；
#       --also-concepts 额外为每个方向单独建条目）
python3 skills/opinion-cross/scripts/consensus_bridge.py --store "$STORE" --theme-signals "$SIGNALS" --also-concepts

# 验证三块不再「待补」
python3 ../theme-radar/scripts/radar.py --term CPO --vault "<KB>/wiki" --mode deep-dive
```

**幂等**：整库重算、事件分区守恒（不重不漏）；剪除上轮本桥写、本轮不再生成的陈旧条目。
**radar 侧**：`radar.py` 在 `load_signal` 后把 theme_signals 里的这三块注入 context（不覆盖
`--theme-supplement-pool` 已提供的同名数据），故 plain `--term X` 即可渲染。

