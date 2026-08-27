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

## ⚠ 根因更正：前八次 live **根本没走 episode 引擎**，环境排查全在追错方向

读 8796 成功那次的产物才发现关键差异——**不在环境，在引擎**：

| | 8796（成功） | 我的八次（失败） |
|---|---|---|
| 关键产物 | **`continuous-episode.json`** | `answer_spec.json` + `theme-research-skill-result.json` |
| 调起技能 | 无 | `theme-research` |
| 引擎 | A：continuous episode | B：ask 管线 + 技能路径 |

我发的 `skill_mode: "auto"` 被解析成 `hybrid` → 路由去调 `theme-research` 技能 → 走进 B 引擎。
**本单四刀全长在 episode/判官那条路上，B 引擎根本碰不到它们。**

spec §7 禁止里原话就写着：「`live_probe ask` 当本单 episode 验收（**中立泳道无
`continuous-episode.json`**）」。我那八次 run 一个都没有这个文件——**从第一次起就不是
episode 验收**。下面那张排除表因此全部作废，留作反面教材：**先看产物确认走对引擎，
再谈环境**。

改用 `skill_mode: "manual"` + 空技能后：技能不再被调起（75s / 2716 字 / 无 `scenario_tree` 缺口），
但产物仍是 `answer_spec.json`，**仍未进 episode 引擎**，且出现新阻塞：

```
未配置 LLM key，有机合成降级为模板
质检 WARN 回灌修订失败，保留初稿
本轮没有连接本地市场数据，已使用截至 2026-07-15 的历史盘面快照
```

`OPENAI_API_KEY` 等 55 个变量按名验过确实带进了进程，却仍报「未配置 LLM key」——
怀疑走的是 macOS Keychain（`FORESIGHT_LLM_KEYCHAIN`），而 Keychain 访问权限取决于
**发起进程的签名**：Cursor 会话起的 8796 拿得到，我这个 Bash 工具起的拿不到。
**未验证**（碰 Keychain 需用户在场）。

### 下一步只有一条干净路

**用 8796 那套已被证明能进 episode 引擎的启动方式，只把 `WORKBENCH_REPO_ROOT` 换成本树。**
同启动器、同环境、单变量。需要用户同意停掉 8796（可原样恢复，它的完整环境已记录）。
**别再手搭**——八次已证明手搭进不去 A 引擎。

## 作废：六条假设逐条排除（追错方向的记录，保留作反面教材）

`scenario_tree` 缺口在我手搭的 sidecar 上 **7 次复现，0 次通过**，稳定复现。
八次 live 逐条排除（每条都有对照读数，不是推断）：

| # | 假设 | 怎么排除的 | 结论 |
|---|---|---|---|
| 1 | 本单四刀导致 | 隔离臂 8798 = `2099718e`（代码 == `gitea/main`，零代码改动）同样失败 | **排除，四刀摘清** |
| 2 | worktree sidecar 天生不行 | 8796 也是 worktree sidecar，正常出稿 | 排除 |
| 3 | 缺 `db/` / `market_snapshot` | 显式指两者，deps 全绿，仍失败 | 排除 |
| 4 | 环境变量抄漏（尤其 LLM key） | 按名逐项验：55 个变量含 `OPENAI_API_KEY` 等全部带到 | 排除 |
| 5 | RAG / worker 冷启动 | 等满 4 分钟 + 先打一发弃用暖机问，degrades 逐字不变 | 排除 |
| 6 | 用户画像空（LLM 配置住画像里） | 从生产画像 rsync 出专用探针画像，仍失败 | 排除 |
| 7 | agent shell 注入 `FORESIGHT_USER` | `env -u` 摘掉，仍失败 | 排除 |

**稳定的 degrades 指纹**（七次一字不差）：

```
wiki-rag 超时(>13.8~14.2s)，已跳过
counter retrieval skipped: remaining budget below observed query cost
broad retrieval empty after 1 attempts
company_mapping 超过阶段时限 40 秒
最终回答未完成任务契约，已按部分完成标记
```

`wiki-rag` 卡在 ~14s 且**与是否预热无关**，是最可疑的一处：像是 RAG worker
被 8792/8796 独占（单例/端口/锁），第三个 sidecar 拿不到，每次都等到超时。
**这条没验**——验它要停一个既有 sidecar，那会影响用户在用的服务，未经同意不做。

`_precheck_satisfiability` 已排除为拦截方：它是观测器，源码明写「不得影响执行结果」、异常全吞，
那句「工具目录里没有该输出对应的 claim」只是附在 gap 上的诊断注解。

## 未做 / 下一个人

- **别再逐个试环境变量**，上面七条已排完。下一步该验的是「RAG worker 是否单例、
  第三个 sidecar 能不能拿到」——需要用户同意暂停 8796 才能做干净对照。
- 另一条路：`scripts/deploy_workbench_runtime.sh` 建独立部署快照，
  **但它会切生产 8792**，未经用户明确同意不得跑。
- 本单 live 臂记 `not_run`。账本规矩：单测绿 ≠ `confirmed`；环境不等价的失败也不得写 `refuted`。
- 探针画像 `/Users/a77/.finance-runtime/live-probe-traceability/20260821-slot-fill`（17M）可删。
