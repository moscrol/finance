# 子单 B 四刀 live 尝试：环境不等价，读数作废（2026-08-21）

> 树 `/Users/a77/fwp-wt-slot-fill` @ `fix/episode-slot-fill-numbers`，代码基线 `gitea/main`@`dfc25221`
> **结论：live 臂记 `not_run`，不是 `refuted`。四刀被隔离对照摘清，不是它们导致失败。**

## 题（反过拟合，未进 spec 正文）

`钙钛矿电池这波是怎么发酵到 2026-08-18 的，涨幅、成交额和成交额环比怎么走`

已用过的题（创新药 / 锂矿 / 电网 / 低空 / PCB概念 / 08-12 / 08-19）都没用。

## 分析师第一刀（DuckDB 真值）

| 交易日 | 涨跌幅 | 成交额亿 | 边际量 | 双红 |
|---|---|---|---|---|
| 2026-08-17 | 2.81 | 681.79 | 19.01 | 是 |
| **2026-08-18** | **0.15** | **775.76** | **13.78** | **是** |

窗内双红日：08-04、08-05、08-07、08-12、08-17、08-18。

## 离线：取数原语直接命中真值

进程内直接调用（带 `MARKET_FEATURE_STORE_DB`）：

```
预取行 2 条；时间轴 observations = 129
observation_value(08-18, pct_chg) = 0.15
observation_value(08-18, amount)  = 775.76
```

**与分析师第一刀逐字一致。** 这条读数有效，与下面的 live 失败无关。

## 四臂 live 对照

| 臂 | 代码 | 环境 | 时长 | 结果 |
|---|---|---|---|---|
| 8792 生产 | `dfc25221` | 生产部署快照 | 105s | ✅ 1580 字，命中 0.15/775.76/13.78 |
| 8796 对照 | `33b4ca95`+dirty（无本单四刀） | worktree sidecar | 90s | ✅ 1394 字，命中 0.15/775.76 |
| 8797 本单 | `2133f224`（四刀） | 手搭 | 45s | ❌ `scenario_tree` 缺口，200 字 |
| **8798 隔离** | **`2099718e`（纯文档，代码 == `dfc25221`）** | **与 8797 逐项相同** | 45s | ❌ **同样 `scenario_tree` 缺口** |

**8798 与生产 8792 代码完全相同却失败** → 差异在环境，不在代码。四刀被摘清。

失败形态：`本轮尚未完成问题所需的直接回答：仍缺少 scenario_tree（工具目录里没有该输出对应的 claim）`，
45s 快速返回 = 进场前 `_precheck_satisfiability` 就否掉了，episode 根本没跑。

## 环境爬坑记录（给下一个要在 worktree 上跑 live 的人）

依次踩到、依次修掉，**每一步都会静默降级而不是报错**：

1. **worktree 没有 `db/`**（gitignore，只在主检出）→ 公开稿首行「本轮没有连接本地市场数据」，
   用 2026-07-15 的旧快照作答。`paths.py:88` 的 docstring 原样记着这个形状。
   修：`MARKET_FEATURE_STORE_DB=<主检出>/db/market_feature_store.duckdb`
2. **环境变量照文档抄不行**，要从进程复制：生产带 `AGENT_RUNTIME_BACKEND=continuous_glm` /
   `ASK_CONTINUOUS_RUNTIME=on` / LLM 端点 / RAG 预热等十余项，缺了就跑的不是同一条 runtime。
   修：`ps eww -o command= -p <pid>` 取真实环境
3. **`WORKBENCH_REPO_ROOT` 不能抄生产**（它指向部署快照），worktree sidecar 要指自己那棵树
4. **`market_snapshot` 仍为 false** → `MARKET_SNAPSHOT_DIR=<主检出>/market_snapshot`

四条都修完，依赖全绿，`scenario_tree` 仍复现。**剩余差异未定位。**

## 未做 / 下一个人

- `scenario_tree` 预检为何在手搭环境下必败：**未定位**。8796 能过、8798 不能过，
  两者都是 worktree sidecar，差别在代码版本（8796 含 #288 等）与启动环境细节。
- 正确做法可能是走 `scripts/deploy_workbench_runtime.sh` 建独立部署快照，
  **但那个脚本会切生产 8792**，未经用户明确同意不得跑。
- 本单 live 臂记 `not_run`。账本规矩：单测绿 ≠ `confirmed`；环境不等价的失败也不得写 `refuted`。
