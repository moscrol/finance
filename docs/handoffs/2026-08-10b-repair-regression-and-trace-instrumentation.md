# 修复轮回退缺陷 + trace 仪表 — 交接（2026-08-10 晚）

> **读法**：§1 总目标与本轮在其中的位置；§2 做了什么（含推翻的三条判断）；
> §3 **验证手段的分工**——这是本轮真正的产出，接手前必读，否则会重走弯路；
> §4 后续要做的，带开工判据。
>
> **范围**：分支 `fix/tool-contracts-remaining-six`，17 个提交，**已推送、未合 `main`**。
> 本轮新增 3 个提交：`9a87c2dd` / `e06e01e7` / `d1eb77e8`。
> 主树 43 个他人未提交改动全程未受影响（全程 pathspec 提交，无 `git add -A`）。
>
> 前置：`docs/handoffs/2026-08-10-seam-ladder-live-and-budget-calibration.md`
> （该文档内的三处 🔁 更正块由本轮写入）。

---

## 1. 总目标：这一串工作到底在解决什么

**目标**：让 episode 运行时**可靠地**把一个金融问题变成一份有证据支撑的答案，
并且在它失败时能**定位到是哪一层**失败的。

硬约束（出自 `docs/superpowers/specs/2026-08-09-episode-seam-ladder-design.md`）
**不是**"能力越多答案越好"，而是：某一阶不得暴露未开放工具、不得绕过 verifier、
不得因新 capability 使固定控制链路异常。

### 进度盘

| part | 状态 |
|---|---|
| P1–P6 阶梯骨架、契约派生、离线回路、live 模式、离线回归门、入口路由 | ✅ |
| **P7 live smoke 实跑** | ⚠️ 生产线 n=3：S1 2/3、S3 1/3 达标 |
| P8 断言扩到"防犯错" | ⚠️ 工具契约 12/12 已补齐；出口侧三类程序检查未做 |
| P9 题型分类层 | ❌ 未动（建议先不动） |
| P10 Engine A 出口闸门 | ❌ 未动（证据把优先级往后压了） |

### 本轮在其中的位置

**本轮没有推进 P7 的达标率，推进的是"能不能查得出来"。**

这是有意的：上一轮花了整天在错误的诊断上，根因不是分析能力不够，
而是**证据不足以证伪**——收据里只有一个终态数字，没有过程。
在观测补齐之前继续跑 live，只会再攒一批读不懂的收据。

---

## 2. 做了什么

### 2.1 修掉一个真实缺陷：修复轮失败会吞掉上一轮的答案（`9a87c2dd`）

**链路**（离线可复现，两个测试先红后绿）：

1. episode 产出可用的 partial 草稿（有绑定，只是缺格）
2. 结构修复轮启动 → 模型调用超时
3. `_stopped_outcome` 返回 `draft=""` / `bindings=()`
4. `continuous_turn_adapter.py` 的 `outcome, structural, _ = repaired` 是
   **无条件替换** → "partial 但有答案" 降级成 "什么都没有"
5. 语义验证拿到空草稿 → `unavailable`，judge 一次没跑

第 5 步正是被误读成"judge 没轮到 ⇒ 草稿在首轮就超时"的那个现象。

**修法（两处，是有意的）**：

- **源头**：`agent_episode._stopped_outcome` 增加 `carried_draft` / `carried_bindings`，
  `resume()` 的**七个**失败出口全部结转上一轮的草稿与绑定。
  `run()` 侧默认为空，行为与改动前逐字相同。
- **兜底**：`continuous_turn_adapter._resume_for_gap` 加同一条不变量。
  `openai_agents_runtime.py:1545` 与 `codex_headless_runtime.py:1526` 各自还有一个
  `draft=""` 的失败出口；适配器是所有 runtime 的共同下游，放一道覆盖全部实现。

`status` / `stop_reason` / `gaps` 一律沿用候选的——**失败必须留痕**，
不能因为保住了答案就把这一轮伪装成成功。

> 📌 **可迁移**：任何 repair / retry / refine 阶段都是对产物的一次**写**。
> 如果它的失败路径写空值，而安装点是无条件赋值，那么"修复"就可能比"不修"更差。
> 检查方式：在安装点搜 `x = candidate`，问"候选会不会严格劣于被它替换的东西"。

### 2.2 补上诊断字段（`9a87c2dd`）

`repair_reentry` 事件现记 `granted_seconds` / `timeout_asked` /
`timeout_configured` / `research_tools_open` / `previous_draft_chars`，
收据两条路径都出 `repair_calls`。

判读方式与 judge 那次同源（见前一份交接 §4.1）：`timeout_asked` ≪ `timeout_configured`
说明时钟已被上游耗光，此时加预算没用。
注意 `repair_deadline` 的 `synthesis_reserve` 是 **0**（`agent_episode.py:1001`），
拿到的就是纯残余时钟，**塌缩的先验概率不低**。

### 2.3 试验台按生产 schema 写 `trace.jsonl`（`d1eb77e8`）

- `run_store` 抽出 `build_trace_step()`，`append_step` 改为调它。
  **schema 从此只有一处定义**；落盘方式各自负责。
- `_EpisodeLedger.add` 给每条事件记发生时刻 `at`。
  **下一条事件的时刻就是这一步的结束时刻**——相邻差值即耗时，不必每步单开 span。
  放 payload 而非 `EpisodeEvent` 字段：`task_frame_hash` 已是同样做法，
  而 `EpisodeEvent` 是 services 层冻结 dataclass、全 runtime 共用。
- 试验台新增 `episode_trace_steps()` + `write_trace_sidecar()`，
  产出 `<收据>.trace.jsonl`。逐步 payload **移出**收据而不是复制
  （实测 24KB 收据 + 45KB trace，收据内已无 `trace_steps`）。
  `model_turn` 正文按 2000 字截断，且把原长度写进串里——
  否则下游会把「被截了」读成「模型只说了这些」。

### 2.4 接上 `agent-run-triage` skill

```
~/.claude/skills/agent-run-triage -> /Users/a77/Documents/skill/skills/agent-run-triage
```

**放用户级而不是仓库内**：仓库的 `.claude/skills/` 受 git 跟踪，
塞指向 `~/Documents/` 的绝对软链会让别人 clone 下来即断链；
复制进 `skills/` 又会变成第二个事实源。软链到用户级 = 一份源、全项目可用、不进 git。

### 2.5 本轮推翻的三条判断

**都写进了前一份交接的 🔁 块，不要重走。**

| # | 上一轮写的 | 实测 |
|---|---|---|
| 1 | prompt 侧输出量约束**未做** | ❌ 一直都在：`episode_protocol.py:192` + `agent_episode.py:1584`，且在生效（出稿 357–486 字符，从未逼近 1000 上限） |
| 2 | 主方差源是 provider 出参长度 | ❌ 证据不成立。8338 token 来自 `probe_provider_latency.py:48` 的 `LONG_INSTRUCTION="请据此写一份**尽可能详尽**的市场结构分析"`——测量条件与生产相反 |
| 3 | 草稿在首轮就超时 | ❌ 收据自己否掉：4 个 case 里 3 个走过 `finalization → model_turn → finish` |

其中 #1 是**负面断言没先 grep**（CLAUDE.md 点名的红线）；
#2 与刚作废的 `evidence_search` 那节同源——**试验台不复刻生产**。

---

## 3. 验证手段的分工（本轮最值钱的产出）

上一轮的教训不是"分析得不够仔细"，而是**用错了工具**。四种手段各有天然盲区，
不知道盲区在哪就会在错的工具上反复挖。

| 手段 | 入口 | 变量是什么 | 能抓到 | **抓不到** |
|---|---|---|---|---|
| **playground（单工具试验场）** | `scripts/probe_tool.py` | 单个工具 | 工具自身耗时、返回形状、空结果长什么样、契约是否兑现 | 工具之间、模型与工具之间的**调度** |
| **消融实验（seam ladder）** | `scripts/run_episode_seam_ladder.py` | **能力面**（开哪几个工具） | 某个能力接入后引入的失败 | **所有档位共用的控制流** |
| **trace + agent-run-triage** | `<收据>.trace.jsonl` → skill | 时间顺序 | 第一处出错的 step/span、哪一步吃掉了时钟 | 为什么错（要靠 payload 与源码） |
| **单元测试** | `intelligence/tests/` | 代码路径 | 可复现的逻辑缺陷，且能永久钉死 | 真实 provider 行为、真实预算 |
| **provider 探针** | `scripts/probe_provider_latency.py` | 只有 LLM 快慢 | 中转是否活着、短/长输出速率 | 任何与工具或编排有关的东西 |

### 本轮的实证：同一个 bug，四种手段只有一种照到了

| 手段 | 结果 | 为什么 |
|---|---|---|
| playground | ❌ 照不到 | 12 个工具全部正常返回，失败 run 也拿到了 16 条证据哈希。**bug 不在任何工具里** |
| 消融实验 | ❌ 照不到 | 四档一起翻车。它变的是"给几个工具"，而这个 bug 与工具数量无关 |
| **trace** | ✅ **照到了** | 只有它记录**先后**：`finalization → finish` 在 `model_error` 之前 |
| 单元测试 | ✅ 事后钉死 | 定位之后用它先红后绿，两个缺陷各一条 |

> 📌 **选工具的判据**：先问"**这个故障的变量是什么**"。
> 是**零件本身** → playground；是**装了哪些零件** → 消融；
> 是**装配顺序 / 交接** → trace。
> 顺序类故障只有记录顺序的工具能抓到，这是分类学问题，不是勤奋问题。

### 具体怎么跑

```bash
# 1) 单工具试验场（最便宜，先跑它）。工具名是**位置参数**，不是 --tool
#    ⚠️ 两个坑，都吃过：
#      · --repeat 同词第二次走查询缓存，读数会是 0.00s；测稳态成本用 --queries A,B
#      · 不加 --prewarm 就不是生产状态（生产在 lifespan 里预热过 RAG worker），
#        evidence_search 会从 16-17s 变成 56-64s，看着像缺陷其实是试验台自己的
RAG_WORKER_ENABLED=1 .venv-workbench/bin/python scripts/probe_tool.py \
    evidence_search --prewarm --queries "光伏 装机,储能 出货"
RAG_WORKER_ENABLED=1 .venv-workbench/bin/python scripts/probe_tool.py \
    --all --prewarm --query "光伏"        # 12 工具耗时基线

# 2) 消融实验：离线（无配额消耗，回归门）
.venv-workbench/bin/python scripts/run_episode_seam_ladder.py --output /tmp/ladder.json
#    → 同时产出 /tmp/ladder.trace.jsonl

# 3) 消融实验：live（烧配额，需生产 env）
#    env 取法见前一份交接 §5.1；⚠️ 不要 source .env.workbench（写的是已退役的 GLM）
.venv-workbench/bin/python scripts/run_episode_seam_ladder.py --live --output <路径>

# 4) 分诊：把 trace 交给 skill，不要手工对流水账
#    Claude Code 内：调用 agent-run-triage，喂 <收据>.trace.jsonl
#    生产 run 的 trace 在 ~/.local/share/finance-workbench/users/<id>/runs/<run_id>/trace.jsonl
```

**顺序纪律**：能用离线证伪的，不跑 live；能用单工具证伪的，不跑整条 episode。
上一轮为定位一个工具跑了三次完整 live（每次 ~5 分钟 + 真实配额），
而 `probe_tool.py` 跑一次就够——**整条 episode 是诊断单个工具最贵的方式**。

---

## 4. 后续要做的

### 4.1 【首要】一次 live，读 `repair_calls` + `trace.jsonl`

开工判据很窄，一次就能定向：

| `repair_calls[0]` 读数 | 结论 | 该做什么 |
|---|---|---|
| `timeout_asked` ≪ `timeout_configured` | 修复轮进场时时钟已被前面耗光 | 动**上游**谁在吃时钟；给修复轮加预算没用 |
| `timeout_asked` ≈ `timeout_configured`（≈75s）仍超时 | provider 在修复轮真写不完 | 才轮到出参长度这条线，且必须用**真实 episode prompt** 测 |
| `previous_draft_chars` >0 而最终 `draft_chars` =0 | 结转被绕过了 | 回归，`9a87c2dd` 的不变量失效 |

配合 `trace.jsonl` 相邻时刻差，可以直接看出**哪一步吃掉了时钟**。
跑完先交给 `agent-run-triage`，不要手工对。

### 4.2 待判断：`repair_model_unavailable` 该不该算终止条件

它**不在** `_TERMINAL_REPAIR_STOP_REASONS`（`continuous_turn_adapter.py:56`），
所以 provider 超时后修复循环还会再试，受 `max_repair_cycles` 与根截止约束。
**本轮没动**——是否该列为终止条件，取决于 4.1 的读数。先别动。

### 4.3 待验证：1000 字上限是不是在锚定模型（用户提出，值得做）

**事实**：`draft` 就是用户最终看到的答案（`public_answer` 直接取自它，
中间无扩写环节）。所以 1000 汉字是**加在最终研报上的**约束。

**观察**：56 份历史样本、30 份非零，全部落在 **480–556** 字，
跨不同模型、不同题目、不同日期。最长 556，**从未触及 1000**。
这个窄带可能是"1000 以内"这句话在**锚定**模型写到一半就收手——
即上限的伤害不是截断，而是让模型主动写少了。

**另有矛盾**：另一条答案路径（`_SYNTHESIS_SYSTEM_PROMPT` /
`_GROUNDED_COMPOSER_SYSTEM_PROMPT`）明确写"篇幅由问题复杂度与证据形态决定，
不强制固定行数"，**完全没有字数上限**。同一产品两条路两套政策。

**实验（便宜，建议先做）**：把"1000 汉字以内"改成"不设上限，但必须完成结构化交付"，
跑同一批题看字数分布。变了 → 锚定为真，这个约束一直在压低研报质量；
不变 → 是题目本身不需要那么长。

> ⚠️ **不要直接删上限。** 它防的是真实故障：最终输出必须是**一个完整 JSON**，
> 同时装着正文 + 证据绑定 + 缺口。正文越长越可能写不完，
> **写不完就整个作废**，连已查到的绑定一起丢。删上限而不解耦 =
> 拿"答案短"换"更常没有答案"。
> 真正的解法是**解耦**：正文与结构化绑定分开交付。属架构改动，
> 要不要做取决于上面那个实验的结果。

### 4.4 其余（承接前一份交接 §4.4，未变）

- 检索加 `recall@k`：`cause_attribution` 缺口是召回不足还是题目超纲，目前无指标可答
- 独立出题人：18 条题集"我出题我判分"，用户抽查只有 8/10
- P10 Engine A 出口闸门：证据把它往后压了，等 4.1 稳定后再评估
- 未审计：显式截断/长输出落盘、幂等性与取消语义、KV Cache 布局

---

## 5. 验收

| 项 | 结果 |
|---|---|
| 新增测试 | 7 条（2 条缺陷回归 + 5 条 trace 不变量），**均先红后绿** |
| 变异验证 | 把 `finished_at` 取值改成 `None`，对应测试立刻红（已清 `__pycache__`） |
| 相关面 | episode / adapter / session / repair / seam-ladder / openai-runtime **223 passed** |
| 全量 `intelligence/tests` | **3939 passed**, 2 skipped |
| 既有失败 | 13 条，全部**与本轮无关**：`test_subconscious`(8) / `test_userspace`(3) 的 vault 路径 + `test_acceptance_board`(2) 的 CLI 契约。**已用 `git stash` 摘掉本轮改动复现确认** |
| `ruff check --config=ruff.toml` | 本轮 8 个文件全过（仓内另有 7 条既有报错，全在他人已提交的 `scripts/ch_*.py`） |
| pre-commit 全钩子 | 三次提交均 Passed，层级审计 ERROR 0 |
| 离线阶梯 | 全绿，产出 59 步 trace |
| 分支 | 已推 `origin/fix/tool-contracts-remaining-six`，**未合 `main`** |
