# Handoff — 证据生命周期改造已落地，及同批发现的未决项（2026-08-06）

## 0. 一句话现状

`main@7129d01a` 已把「旧证据按天数标过期」换成「按 `logic_lifecycle` 七阶段表述」；
同一批工作中另外发现 8 项未决问题，**其中 3 项有明确的用户语义要求、5 项是观测/环境层
的洞**，本文按可独立开工的粒度列出，每项都带证据位置与已验证的事实，避免接手方重新踩坑。

## 1. Git 与运行时现状

| 项 | 状态 |
|---|---|
| main | `7129d01a`（已推送 origin） |
| 本次合并 | `merge: 旧证据按逻辑生命周期表述` ← `fix/evidence-logic-lifecycle@2731823a` |
| 全量测试 | `intelligence/tests` **3795 passed / 13 failed**；13 条是宿主环境基线（`test_userspace` 3 + `test_subconscious` 8 + `test_acceptance_board` 2），与改动无关，逐条同名可对照 |
| 解释器 | **必须** `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；宿主 `python3` 缺依赖 |
| 8792（生产） | launchd 拉起，cwd = `/Users/a77/.finance-runtime/finance-workspace-8ccca8ca`，**跑的是 08-06 之前的旧快照**，本次改动不在其中。切换靠改符号链接 `/Users/a77/finance-workspace-runtime` 再重启，**不可手工 kill** |
| 8801（canary） | 我起的普通进程（非 launchd），`nohup /tmp/start-canary-8801.sh`，日志 `/tmp/canary-8801.log`，cwd = 仓库主树。**它加载的是 `main@dc7378a4`，不含本次改动**，要验证需重启。关掉：`kill $(lsof -ti :8801)` |
| 主树分支 | ⚠️ 主树当前在 `fix/llm-error-handling`（另一条线在用，独占 0 提交）。**不要抢主树切分支**，开 worktree 工作 |

## 2. 本次已完成（不用重做）

**语义变更**：`ask` / `agent` 路径对旧证据不再输出「⚠️过期，需复核是否被新数据证伪」，
改为报本轮题材的逻辑生命周期阶段：

```
川环科技：券商研报…（2026-05-20, 质量 ? ｜新出现·首次进入观察）
还缺：川环科技 证据 2026-05-20｜该题材当前逻辑生命周期：新出现·首次进入观察；
     按盘面阶段而非天数判断这条是否仍然成立
```

**用户给的判据（原话转述）**：过去的逻辑不代表过期，要看到的是逻辑的**周期变化**。
在 `logic_lifecycle._stage()` 里 `old_material_hit` 是**正面信号**——它导向
`STAGE_WAKEUP`（旧逻辑唤醒），而 `_next_actions` 给该状态的动作是「进入 front-map/
deep-dive 验证发酵阶段」。原先的天数阈值把这个最高价值信号标成了风险。

**实现要点**：
- `ask._theme_lifecycle_stage()` 取「阶段·阶段变化」，整轮只算一次，经
  `EvidenceContext.lifecycle_stage` 下发；`agent.AgentSession._lifecycle()` 同源懒加载
- 判定仍归 `logic_lifecycle` 单点所有（daily_agent 与 ask 必须同阶段，不建第二套词表）
- 延迟导入避开既有反向依赖 `logic_lifecycle → ask.load_theme_candidates`
- `superseded`（被新证据顶掉）保留原样，那是证据层面的真失效，与「旧」无关

### ⚠️ 接手方必须知道的一个传导坑

证据行的 mark 会拼进 `line`，而 `line` 紧接着过
`research_brief.classify_evidence_line` 做 L1-L4 分层。**mark 文案里不能出现
`research_brief._L4_TERMS` 里的任何词**（涨停/新高/双红/边际量/成交/量能/相对强度/
涨跌家数/MA5/盘面/信号/市场环境/容量前三/连板/强势股）。

初版 fallback 写「待**盘面**复核」踩中，后果不是文案错，而是：该知识证据被误判成
L4 盘面证据 → `audit.has_l4` 翻 True → `build_counterevidence_plan` 的反证从
「盘面未验证」跳成「拥挤度」。**一个纯文案改动穿过分类器改变了风险结论**，是 golden
快照抓出来的。已改为「周期待判」，并实测 7 个阶段名 + 9 个阶段变化共 17 条均不撞词表。

同批同步了 `intelligence/eval/agent_eval.py::STALE_MARKS`——不同步的话该观测指标会
**静默恒 False**（答案里明明有旧证据，观测方报「一条都没有」）。**以后再改这类文案，
先 grep 谁在按文案做匹配。**

---

## 3. 未决项（按建议优先级）

### P0-1 · `logic_market_match` 四分类未接入 ask（用户已明确问过）

**这是本次只做了一半的那一半。** 用户要的「逻辑和盘面的对照分析」有两个互补模块，
本次只接了时序那个：

| 模块 | 维度 | 现状 |
|---|---|---|
| `services/logic_lifecycle.py` | **时序**：连续天数/priority/强势股变化 → 七阶段 | ✅ 已接入 ask |
| `services/logic_market_match.py` | **当期**：盘面有没有 × 知识侧有没有 → 四分类 | ❌ 未接入 |

四分类（`logic_market_match.py:211 _classify`）：
```python
LABEL_OLD_WAKEUP    = "old_logic_wakeup"      # 盘面有 + 概念/暴露/证据齐
LABEL_NEW_CANDIDATE = "new_logic_candidate"   # 盘面有 + 知识无
LABEL_DATA_GAP      = "data_gap"
LABEL_NOISE         = "noise_or_unconfirmed"
```

它还带 `_next_actions()`（每个分类对应的下一步动作）和 `check_source_trace()`
（证据可追溯性）。接入方式可参考本次 `lifecycle_stage` 的做法：ask 侧算一次 →
经 `EvidenceContext` 下发 → 证据渲染处消费。

**注意同一个坑**：四个 label 是英文不撞 `_L4_TERMS`，但如果要输出中文描述，
先跑一遍词表检查。

### P0-2 · 答案自评 12/100（F）的口径可能对不上

三次真实 run 的自评都是 `12/100（F）`，评分器给的缺口是：

```
证据标记不足(2/8)：只有关键词、缺股票代码/日期/引用编号/带单位数字
证据分层不足：缺少 L1-L4 或事实/情绪/基本面分层
```

**但答案正文里明明有** `[W5]` `[G1]` `[R2]` 这类引用编号、`603267` 这类股票代码、
`2026-06-03` 这类日期。要么评分器解析的口径和输出格式对不上，要么它看的是另一段文本
（比如只看了 compose 后的自然语言段而没看结构化证据段）。

台账在 `/Users/a77/agent-memory/.foresight/linxiaoqi5111/answer_scores.jsonl`。
**这是「仪表读数与实际不符」类问题，优先级高于它看起来的样子**——一个长期报 F 的
评分器等于没有评分器，真的质量下降时没人会注意。

### P1-1 · 8801 canary 需要重启才能验本次改动

它加载的是 `main@dc7378a4`（合并前）。重启：

```bash
kill $(lsof -ti :8801)
nohup /tmp/start-canary-8801.sh > /tmp/canary-8801.log 2>&1 &
```

起来后 `curl -s http://127.0.0.1:8801/api/health/ready` 应为 `ready`、
`missing_critical: []`。**验证加载的是哪份代码只认 cwd**：
`lsof -a -p $(lsof -ti :8801) -d cwd`，不要信 health 里的 `source_revision`
（实测与 cwd 打架）。

前端已构建（`intelligence/api/static/` 有产物），浏览器直接开 `http://127.0.0.1:8801`。

### P1-2 · `graph_audit.py` 的 `@branch` 行缺到期检查

能力图谱支持写 `path::symbol@branch` 表示「在途、未合并」。但审计对这类行标
`UNVERIFIED` 直接跳过，于是**两个方向都会发绿光**：

- 2026-08-05 抓到过一次：图谱说 main 有、实际只在分支上 → exit 0
- 2026-08-06（本次）：图谱说在途、实际已合并且分支已删 → 仍然 exit 0

**建议**：`@branch` 行加一条到期检查——分支已合并进 main 或已不存在时报红，
提示「该提升为常规行」。脚本在 `/Users/a77/agent-memory/scripts/graph_audit.py`。

### P1-3 · Grounded Presenter 偶发 `HTTP 400`

三次 run 里出现一次，网关本身正常（直接 curl 返 200）。已排除：`temperature`、
`max_tokens`、`thinking` 参数、上下文长度（实测 124390 tokens 仍 200）。
需要抓实际失败请求才能定位——可以 patch `urllib.request.urlopen` 捕获
`HTTPError.read()`，方法见本次会话（我 patch 后复跑一次没复现）。

### P2 · 环境/仓库层面的三件事

1. **知识库仓不在 main 上**：`knowledge-base-private` 当前在
   `pdf-ingest/sellside-miracle-0730-0803-backfill`。我入库的 14 个 miracle 文件
   （`fb4c6f54`）之上，已有另一条线补了收尾链 `17575507`（`#3783~#3787` 的 log 登记）。
   剩 7 个未跟踪变更（`access_log.jsonl` + `raw/disclosures/` 三天公告 + review-queue），
   属另一条 ingest 线，未处理。
2. **RAG 索引与工作区的自激循环**：`wiki/relations/access_log.jsonl` 是 RAG 检索
   自己写的埋点，但 `rag_freshness` 用 `git status --porcelain` 判 stale。好在
   `PAGE_TYPE_DIRS` 不含 `relations`，所以 access_log 实际不触发；真正触发过的是
   `wiki/sources/` `wiki/synthesis/` 下未提交的 ingest 产物。**注意 `prewarm` 硬走
   `fail` 策略**（`kb_rag.prewarm` 的 argv 不传 `--stale-policy`，落到 KB 侧
   `RAG_STALE_POLICY` 默认 `fail`），而常规查询默认 `warn`——索引一 stale，
   查询能降级跑但预热必失败，导致整个服务 `not_ready`。**这是个真实的策略不一致**，
   值得单独修。
3. **agent-memory 仓**在 `docs/session-tutor-first-principles`，相对 main 独占
   **190 个提交**，全是 `auto-sync: local edits` 流水。改记忆文件不需要手动 commit
   （auto-sync 会收），但这条分支什么时候合 main 需要用户定。

---

## 4. 开工前必读（本次踩坑总结的通用纪律）

1. **改文案前先 grep 谁按文案做匹配**——本次两处：`classify_evidence_line` 的
   `_L4_TERMS`、`agent_eval` 的 `STALE_MARKS`。
2. **判断「已被取代」必须能说出被哪个 commit/哪种设计取代**，说不出就是没验。
   git 的 `cherry` / `merge-tree` / `--merged` 三种信号本次各骗过一次。
3. **验证要断言生效值不是配置值**：本次三次自纠都源于「拿自己猜的参数当生效值」
   （`kb_root` 层级、worker 请求协议、RAG 用哪个解释器）。正确做法是读真实调用方
   （`app.py` 的 lifespan、`_resolve_rag_python`）。
4. **中文路径在 git 输出里被转义**（`\345\244\215\347\233\230`），`grep 复盘/`
   匹配不到会得到假的空结果，用 `git -c core.quotepath=false`。
5. **zsh 不对未加引号的变量做分词**，`for x in $VAR` 会把整串当一个元素——本次
   据此得出过一个「5 条分支无包含关系」的假结论，实际是线性链。用数组 `BR=(...)`。
6. **改完门禁/测试必做变异测试**：把被保护的那行改坏，看测试红不红。本次写的第一版
   测试对变异不敏感，是个永远绿的测试，变异测试才抓出来。
