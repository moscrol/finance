# V6 deadline 预算对照实验（R-20260821-18）

> 任务书：[`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md`](../superpowers/specs/2026-08-21-inputside-closeout-r2-design.md) §V6。
> 上游观测：[`docs/verification/2026-08-21-deadline-exhausted-repro.md`](2026-08-21-deadline-exhausted-repro.md)（R-10）。
> 台账：`R-20260821-18`（`pending`；结论未出不得 confirmed）。
> 纪律：实验报告 + 分臂 harness，**生产 timeout / 预算默认值一个字不动**。受 `R-20260816-07`「无实测不得抬 T」约束。

## 0. 先讲原理（为什么这是预算结构实验，不是「把 T 调大」）

R-10 已证：近 8 日 410 run 里 `deadline_exhausted` 占 79%，`carried=0` 且全走 `repair_reentry` 占全部 run 的 67%。共享 deadline 下，工具轮吃掉墙钟，成稿轮只剩残值（有埋点 n=39，median 13s），修复窗反而独立新授 30–40s，变成事实主生成窗。

这和「总时长不够」不是同一件事。总时长 T 是整条链的硬截止；**reserve** 是从剩余时间里扣一块留给成稿。本仓已经有 `_BALANCED_SYNTHESIS_RESERVE=60`：非 finalize 轮 `stage_timeout = remaining − 60`。R-20260816-09 的讨论是：这 60s 税把成稿前的那一轮饿到 13–18s，模型还在 planning 态写稿，于是超时 → 修复窗成稿。

**可迁移点（面试也常问）**：deadline 是绝对时刻（全链传 `expires_at`，不传相对秒数，避免每跳重新计时膨胀）；reserve 是会计预扣。预扣如果只减 `asked`、不改变「何时进入 finalize」，成稿轮仍可能拿不到那块预扣。这和 RAG 里「检索预算」vs「生成预算」的切分是同一类问题。

替代方案对比：

| 做法 | 改什么 | 好处 | 代价 |
|---|---|---|---|
| 抬 T | 总墙钟 | 所有轮都更宽 | 触 R-07 绊线；成本线性涨；不修分配 |
| 候选① 成稿轮 reserve | 何时把 60s 交给 finalize | 不抬 T，只改切点 | 可能更早停工具，检索变浅 |
| 候选② carried 门槛 | 残稿不够就不进修复窗、直接续写 | 少一次修复 LLM | 要定义门槛，假残稿会空转 |
| 候选③ 修复窗正名二段生成 | 承认修复窗是第二段成稿并配足预算 | 与现状行为对齐 | 把 workaround 做成产品，主稿轮更废 |

本单只跑 **对照 vs 候选①**。②③ 在 harness 里留臂名，未做影子。

## 1. 预注册（开跑前锁死，逐字抄 spec §V6）

判据：

> 候选臂 model_finish 率较对照 +15pp 以上且答案长度不降 → 该候选进实施立项；否则记「未达标」并留读数。

- 样本量：每臂 n≥50（基线 79%，检出 15pp 变化的最小可用量）。n<50 结论栏只写「进行中/未达标样本量」。
- 指标：model_finish 率、carried>0 率、修复窗依赖率、答案长度、judge_status 分布。
- 探针用户：`probe-v6-0821`（字段是 `user` 不是 `user_id`）。
- 分臂：对照（现状）+ 至少候选①；时段交替（R-10 已证无时段聚集）。

字段路径（与 R-10 观测单同一套，不另造）：

| 指标 | 路径 |
|---|---|
| 终止方式 | `events[kind=finish].payload.stop_reason`（取首条 finish） |
| model_finish | `stop_reason == "model_finish"` |
| carried>0 | `events[kind=finish].payload.carried_draft_chars > 0` |
| 修复窗依赖 | 存在 `events[kind=repair_reentry]` |
| 答案长度 | `outcome.draft` 字符数 |
| judge_status | `semantic_verifier.judge_status` |

缺字段报「不可判」，不报 0（沿 W5 量纲诚实）。

## 2. 分臂设计

| 臂 | 进程 | 配置 | 用户 |
|---|---|---|---|
| control | 生产 8792 | 现状默认。`MIN_PLANNING_TURN_SECONDS=8`，`_BALANCED_SYNTHESIS_RESERVE=60` | `probe-v6-0821` |
| reserve60（候选①） | sidecar 默认 8803 | 进程内影子：`MIN_PLANNING_TURN_SECONDS=60`。其余常数与生产相同 | 同名用户，落独立 `FORESIGHT_USERS_DIR` |

交替：`--arm both` 时按试次奇偶交替（先对照后候选）。题池 10 道发酵/题材题，走 `POST /api/conversations` → `/messages`（continuous episode），**不用** `live_probe ask` / `POST /api/runs`（那条是 ask 泳道，R1 已踩过）。

## 3. 影子配置机制（为什么选双实例，不选改 8792 环境变量）

三种候选实现：

1. **环境变量分臂**：在 `glm_agent_runtime` / `agent_episode` 加读 env。生产代码要改，默认值即使不变也是「生产代码改动」。本单禁止。
2. **请求级覆盖**：API 没有 budget override 字段。现加等于改生产契约。
3. **双实例 sidecar（本单采用）**：8792 一个字不动。候选臂在非保留端口起第二份 uvicorn，启动前 `install_candidate1_shadow()` 只改本进程的 `MIN_PLANNING_TURN_SECONDS`。8792 的 live.lock 是防第二份**生产实例**顶掉 8792，不是禁旁路口；sidecar 拒绝 8792/8793/8795/8799/8801。

候选①影子在做什么（人话）：

生产已经把 60s 从 planning 的 `asked` 里扣走，但「何时 finalize」仍看 `planning_timeout < 8`。所以 remaining=78 时，成稿还在 planning 态，只拿到 18s。影子把门槛改成 60：`remaining − 60 < 60`（即 remaining < 120）就进 finalize，成稿轮改走 `synthesis_timeout = remaining`（含那块 reserve）。**不抬 T，不改 60 这个常数本身。**

## 4. 冒烟（正式跑臂前，n=1）

命令：

```bash
.venv-workbench/bin/python scripts/v6_deadline_budget_ab.py smoke \
  --question "CXO概念这波是怎么发酵到 2026-08-20 的"
```

| 项 | 值 |
|---|---|
| 结果 | **走到 episode**（`ok=true`） |
| 墙钟 | 171s |
| `user` | `probe-v6-0821` |
| `run_id` | `run_20260822_001908_936624` |
| `conversation_id` | `conv_d1dc88be48b94431a25672714bb54879` |
| 8792 指纹 | `source_revision=6320b3bc` / `source_dirty=true`（生产树，非本实验分支） |
| `has_episode_file` | true |
| `tool_events` / `model_turns` | 7 / 3 |
| `stop_reason` | `deadline_exhausted`（R-10 同形） |
| `carried_draft_chars` | 632（>0） |
| `used_repair` | true |
| `answer_chars`（draft） | 529 |
| `judge_status` | `unavailable`（公开稿首句「复核服务超时」） |
| `public_degraded` | false（不是 R1 的 URLError 模板路径） |

链路判断：conversations → continuous episode → 工具调用 → 成稿轮。与 R1 三探针（probe-w1/w2/w3-0821）的 URLError 降级模板不同。**本机出口此刻可走 episode。**

候选① sidecar 通路验证（**不计入实验 n**）：8803 `healthy`，启动日志 `MIN_PLANNING_TURN_SECONDS 8.0 -> 60.0`，`source_revision=dd6ca952` dirty。试发 `run_20260822_002306_795111`（减肥药发酵题）：有 `continuous-episode.json`、`model_turn=2`、`finish=deadline_exhausted`、`carried=355`、`judge=passed`，**零 `tool_request`**——planning 地板抬到 60 后提早 finalize 的预期形状，不是 URLError。正式 n≥50 未开。

## 5. 每臂 n 与五项指标（2026-08-22 01:01–04:00 采满）

冒烟行记在 `phase=smoke`，**不计入**实验臂 n。正式批 `phase=run`，题池 10 道 × 每臂各 5 遍，
两臂题分布逐题相同（同题配对）。分段交替执行（每段 10 发换臂），横跨全夜，无时段聚集。

| 臂 | 实验 n | 走到 episode | model_finish 率 | carried>0 率 | 修复窗依赖率 | 答案长度中位数 | judge_status |
|---|---|---|---|---|---|---|---|
| control | **50** | 50/50 | **44%** | 60.7%（n_judgeable=28） | **64%** | **752.5** | repaired 39 / passed 4 / unavailable 7 |
| reserve60 | **50** | 50/50 | **90%** | 100%（n_judgeable=5） | **42%** | **705.5** | repaired 31 / passed 13 / unavailable 6 |

进程身份（对照臂）：8792 快照目录 `finance-workspace-6320b3bcbf82`（目录名滞后），
内容为 R-06 部署（rsync 指纹 `56270d7329b69c34` = `59ec4294` 树，2026-08-21 20:21 部署），
批期间无再部署，`/api/health` 全程 healthy。候选臂 sidecar 逐段拉起：前 10 发加载本分支
`0a28a48f`（clean），断点续跑后各段加载 `60eb4bbd`（clean，只多健康窗修复，影子行为不变）。

台账：`~/.finance-runtime/v6-deadline-budget-ab/trials.jsonl`（仓外，不提交）。
复算：`python scripts/v6_deadline_budget_ab.py score`

### 执行事故（如实记录）

原批（`--arm both` 改为分段单臂交替）跑到第 4 段（reserve60 第 10–19 发）时 sidecar
健康等待 90s 超时（`Connection refused`），链式止损生效，30/100 处中断。分诊：app lifespan
启动在当夜负载下实测 65–110s（faulthandler 探针 + 手动复现各一次），90s 窗擦线——
01:12 那段侥幸过线，01:53 越线即死。修复 `60eb4bbd`（健康窗 90→300s），02:09 从断点
续跑（reserve60 自第 10 发），04:00 满 100 发收官，全程再无 sidecar 失败。

## 6. 判据比对

**结论：未达标（预注册判据为合取，长度守门被触发）。读数已留，不改参数、不温判据。**

- model_finish 提升 **+46.0pp**（44%→90%），远超 +15pp 门槛 ✅
- 答案长度**下降**：中位 752.5 → 705.5（−6.2%），均值 737.1 → 682.8（−7.4%）❌

判据是「+15pp 且长度不降」的合取，第二支不成立 → 按预注册记**未达标**。
候选①不进实施立项。生产参数一个字未动（§9 清单复核不变）。

### 事后探索（labeled exploration，不参与判定）

同题配对：10 题配对中位差 −55 字，6/10 题变短（最大：创新药 −238、固态电池 −190、
PCB −140），4/10 变长或持平。变短最狠的题恰是对照 model_finish 最低的题
（创新药对照 1/5 完稿、固态电池 3/5），提示对照的长答案部分来自**修复窗改写膨胀**而非
更充分的成稿——与 judge 分布互证：候选 passed 13 vs 对照 4，repaired 31 vs 39。
候选臂 carried 案例几乎消失（28→5），即成稿轮真的拿到了预算、不再靠残稿续命。

含义：长度守门本为拦「reserve 饿死生成、产出残段」设计；观测到的 −6% 中位 +
judge 变好 + 修复依赖 −22pp **不是残段坍缩的形状**。若要复核「长度降的是水分还是内容」，
需按信息密度/判官通过率加权的新判据——那是**新预注册**（另立台账行），不是本行的温判。

## 7. 阻塞项（全部解除）

- ~~样本量~~：已采满 50/50。
- ~~对照臂指纹~~：已记录（见 §5 进程身份）。
- ~~候选 sidecar dirty~~：正式批全程 clean 树（`0a28a48f` / `60eb4bbd`）。
- R-07 绊线未触：本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位 / `_BALANCED_SYNTHESIS_RESERVE` 改动。

## 8. Harness

- `scripts/v6_deadline_budget_ab.py`：`smoke` / `run` / `score` / `sidecar`
- 离线钉：`intelligence/tests/test_v6_deadline_budget_ab.py`（缺字段不可判、n<50 拒判、+15pp 且长度不降才达标、影子安装可还原、零 tool 的 prefetch+finalize 仍算走到 episode）

## 9. 生产参数核验

本 PR 不改：

- `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS`
- `_REPAIR_SECONDS_CAP` / `DEFAULT_REPAIR_SECONDS_CAP`
- `_BALANCED_SYNTHESIS_RESERVE`
- 生产档位 / `ASK_TOOL_BATCH_TIMEOUT`

`install_candidate1_shadow` 只在 sidecar 入口调用；单测还原常数，避免污染其它测试。
