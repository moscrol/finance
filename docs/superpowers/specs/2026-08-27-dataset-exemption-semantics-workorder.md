# 工单 · dataset 豁免语义整改——「代码消费得到」≠「模型够得着」

- 日期：2026-08-27
- 状态：**本单随实施 PR 同批交付**（发现→工单→实施同 session，用户裁决「立工单推进执行」）
- 来源：P0 D6 复跑附带发现①（`R-20260827-07a` 行、`docs/superpowers/specs/2026-08-27-longtail-react-gap-remediation-workorder.md` 战线的旁产物）
- 台账：`R-20260827-12`（随实施 PR 同提交预注册；原号 `-11` 与并发 #468 撞号，后落盘者改号）

## §0 · 问题（实证）

`intelligence/services/finance_query.py::_UNREGISTERED_TABLES` 的豁免理由里，
`dedicated_path` 前缀把两件不同的事混成一件：

- **「代码消费得到」**：pack / timeline / analogs 构建器、adapter、证据块在读这张表——这些是**预取注入面**，模型不能主动查询；
- **「模型够得着」**：表暴露为 `_DATASETS` dataset（`finance_query` 工具可查）或经 12 注册工具之一可达。

两次翻案已实证这个混淆会遮蔽真缺口：

1. `fact_limit_advance_daily` / `fact_theme_limit_stock_daily`（#454，2026-08-27）：
   原豁免理由「dedicated_path：adapter 与多处 service 已消费」，A3 live 实测
   （`run_20260827_145613_094860`）「6 连板、当日高度标、题材=电站」躺在库里够不着；
   注册后 D6 machine-truth rate 0.0→1.0（`R-20260827-07a`→`-10` 链）。
2. 门禁 `audit_dataset_registration.py` 对豁免理由**只查存在、不查语义**——
   `dedicated_path` 挂着，dataset 注册门发绿（#454 提交时亲历 ✅）。

同前缀今天仍挂 4 张：`feature_l2_capital_flow_daily` / `feature_l2_quant_orders_daily` /
`fact_mainline_stock_daily` / `fact_sector_period_rank_daily`。

## §P0 · 豁免理由类别白名单（门禁语义）

**动作**：`audit_dataset_registration.py` 加规则 3——豁免理由必须以白名单类别前缀开头
（前缀 = 首个冒号前的 token，全角/半角冒号皆可）：

| 类别 | 语义（回答「为什么模型不该/不需要够到」） |
|---|---|
| `no_writer` | 无写入链，注册即永久空 dataset |
| `internal` | 基础设施（代际物理表/台账），不是市场事实面 |
| `stale_materialized` | 物化窗口，无活跃消费者、可能过期 |
| `stale_since` | 曾在更但已断更，注册会喂旧数据；**理由须写断更日与复活条件** |
| `candidate` | 有数据未对账，先量后判 |
| `kb_side` | 正文在知识库，偏检索面 |
| `overlap` | 完整数据在另一已注册 dataset |
| `model_reachable_via` | 模型经另一**可达**通路（12 注册工具或已注册 dataset 之一），**须点名通路** |

**`dedicated_path` 明确不在白名单**——它陈述的是消费方存在性，连方向都不对。
未知前缀同样红（fail closed：认不出来就拦）。

**判据（可判定）**：
- 真仓 audit `invalid_exemptions == []` 且 exit 0（存量 4 张清理后）；
- 证伪：任一豁免理由换回 `dedicated_path:...` → audit `ok=False`、`invalid_exemptions` 点名该表；
- 证伪：未知前缀 `whatever:...` → 同红。

## §P1 · 存量 4 张逐表裁决（先量后判，2026-08-27 实测）

| 表 | 实测 | 裁决 |
|---|---|---|
| `fact_sector_period_rank_daily` | 1720 行，05-06~**08-27 活**、54 天；四档 period_type（daily/day3/day5/day10）各 top10；badge ∈ sharp/fund/width/None | **转正注册 `sector_period_rank_daily`**——「adapter ALLOWED_TABLES 按需直查」与 #454 同形状（adapter 不是模型查询面）；「近5日哪个板块最强/连续在榜」正是查询面问题 |
| `feature_l2_capital_flow_daily` | 7243 行，06-15~**08-07 断更 20 天** | 不注册，理由改 `stale_since`：注册停更表=喂旧数据；**复活条件=恢复日更后按 #454 形状转正** |
| `feature_l2_quant_orders_daily` | 2600 行，同上断更 | 同上 |
| `fact_mainline_stock_daily` | 4221 行，06-22~**08-27 活** | 不注册，理由改 `model_reachable_via:mainline_context`——模型经注册工具已可达（episode 级快照注入，合同文案明确覆盖个股表），再开 dataset 双口径。⚠ 顺带发现：CLAUDE.md「mainline stock/theme 停在 07-03」描述过时（实测日更到 08-27），文档修补另行，不入本单 |

**新 dataset 判据**：注册断言钉（生效值：population=subset、coverage 含防分母坑指针
「榜单 top10 非全量」与 sector_daily 回指）+ 夹具查询锚（period_type 过滤 + 截止日不越界）。

## §P2 · 验收

1. TDD 先红后绿（新钉：审计规则 3 证伪 ×2 + 白名单通过面 + dataset 注册钉 + 查询锚）；
2. 变异：删规则 3 → 证伪钉红；`dedicated_path` 塞回清单 → audit 红；
3. 真仓五道 registry 等价 + crosswalk 全绿；
4. live（切流后）：sector_period_rank 类问题（如「近5日涨幅榜哪个板块连续在榜」）episode
   trace 出现 `dataset=sector_period_rank_daily`——记入 `R-20260827-12` 行回读。
