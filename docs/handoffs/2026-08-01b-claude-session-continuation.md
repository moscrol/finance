# Session continuation handoff — Claude 断线续聊（2026-08-01b）

**用途**：旧 Claude 会话 `59d587aa-05e4-4e60-8c59-d3696e8f0fb4` 因超长上下文 + 空 thinking + 代理重传卡住；**不要续那个 jsonl**，用本文件在新会话接着干。

**先读（按顺序）**

1. `docs/handoffs/2026-07-31-harness-goal-and-references.md`（Start Here / 总入口）
2. `docs/handoffs/2026-08-01-exposure-selection-and-sealed-fixture-risk.md`（本段主 handoff，十节齐全）
3. **本文件**（断线后的增量 + 未完成的那一刀）

**Claude 旧会话**（只作考古，勿再 `继续`）：

- `~/.claude/projects/-Users-a77/59d587aa-05e4-4e60-8c59-d3696e8f0fb4.jsonl`（~3.3MB，1215+ messages）
- 用户最后几句：评估 knevo → 吸取优化 →「继续」→「继续啊，怎么老断电」
- 卡住模式：大量 thinking-only / no visible output；最后一轮卡在 `platform.claude.com` 代理链路上

---

## 0. 一句话现状

**暴露取舍（排序 + 意图选择器 + 截断留证）已上线且可用；盘面数据曾停在 7-30（CDP）；knevo 对比已出结论（L 降级、M 优先）；断在「高频/长尾覆盖信号能不能 join 进暴露选择」的数据可行性验证上。**

---

## 1. 工作目录与代码指针

| 角色 | 路径 / 值 |
|---|---|
| 工作 clone（本段主仓） | `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17` |
| 分支 | `fix/exposure-ranking-truncation` |
| 工作 clone HEAD（断线时） | `881efc3c`（含数据仓 main merge + H/K 文档） |
| 暴露三连 commit（已上线意图） | `2634d6ef` → `4404db41` → `751ef706` |
| runtime 软链 | `/Users/a77/finance-workspace-runtime` → `.../finance-workspace-751ef706` |
| 用户数据仓（另一 clone） | `/Users/a77/finance-workspace-private`，当前检出可能是别的分支，**别当本段工作区** |
| 工作台 UI | `http://127.0.0.1:8792/`（user `default`） |
| 属主 | launchd `com.a77.finance-workbench` |

**⚠️ 续聊先核 runtime 一致性**（断线后曾观测到异常）：

```bash
readlink /Users/a77/finance-workspace-runtime
# 期望含 751ef706

curl -sS http://127.0.0.1:8792/api/health | python3 -m json.tool | head -40
# 若 source_revision 不是 751ef706 前缀、或 source_dirty=true，
# 说明「软链」和「进程实际加载」不一致——先 kickstart / 查 start 脚本，再谈功能。
# 2026-08-01 实测曾出现：软链 → 751ef706，但 health 报 0430d544 + dirty。
```

**GitHub**

- `origin/fix/exposure-ranking-truncation` 已推（历史上到 `751ef706` / 后续 docs 到 `881efc3c` 一带，续聊时 `git fetch && git log -1`）
- **`origin/main` 未动**（仍约 `0430d544`），卡在待办 **K**

**软回滚选择器**（不退代码）：`ASK_EXPOSURE_SELECTOR=off` 写入启动脚本再 kickstart。

---

## 2. 本会话已完成（可当已交付）

### 2.1 产品 / 线上

1. **图谱暴露不再按中文字典序静默截断**  
   - 根因：86 家候选 score 全并列 20 → tiebreaker 公司名  
   - 修：排序键 `(-score, strength, confidence, company)` + 截断 telemetry/warnings  
2. **按问题意图的暴露选择器**（`exposure_selector.py`）  
   - 候选 60 → 模型挑 `top_companies`（默认 12），失败 fail-closed 回退确定性排序  
   - 实测 trace：`mode=llm`, `llm_selected=12`, `hallucinated=0`  
3. **留证口径与真实路径一致**（`751ef706`）：`mode=llm` 不得再说「按名称排序」  
4. **用户可直接用**：题材+产业链类问题会打到选择器  

验收命令与期望见主 handoff §7。

### 2.2 工程 / 决策已拍板

| 事项 | 结论 |
|---|---|
| 推 GitHub | 推分支，**不**推 main |
| `.finance-runtime` 清理 | 27G→17G；**密封夹具相关 11G 全留**（磁盘不紧 + 在途实验） |
| 密封夹具 `9053b0c4` | **可重建**；路径在夹具 manifest 的 `kb_code_root`；已归档 `refs/archive/kb-phase-c-freshness-9053b0c4` |
| 待办 H | ✅ 关闭（曾误判「丢了」） |
| 数据仓 main 并入本线 | merge `78949ea6` 已落本地；**未 push main** |
| 夜跑测试红 | 多 1 条 → 待办 **K**（阻塞 main 推送） |

### 2.3 数据管线（使用时要知道）

断线前结论：**服务 healthy，但盘面 fact 曾停在 2026-07-30**。

- 原因：fupanhui / CDP proxy（`localhost:3456`）连 Chrome 反复断 → 18:30 `phase=sync` 失败 → 20:40 finalize 守卫拦住 → **当晚 L2 资金流也不算**  
- 这正是待办 **K** 描述的真实事故形状，不是假想  
- 补 7-31 需要用户侧 Chrome 登录 fupanhui；agent 不能代登  
- 续聊时先查：fact 表最新日期是否已恢复  

### 2.4 knevo 逆向转化（已写入记忆 + 主 handoff 待办 L/M）

报告：

- 精简：`/Users/a77/agent-memory/10_knowledge/knevo-harness-reverse-engineering.md`  
- 完整：`/tmp/knevo_reverse/HARNESS_REPORT.md`（可能随重启消失，以 agent-memory 为准）  

| 发现 | 结论 | 动作 |
|---|---|---|
| **A1** hitCount/core **不**回接排序，纯关键词 | 不是「它的长」；两边都没做命中回流 | **L 优先级下调**；先做 I 再谈 L |
| **A2** settle/verify 405，无自动结算 | 状态机 `pending→hit/miss→reviewed` 可借；自动结算要自建 | 记在双盲台账旁 |
| **A3** 每 2–3 轮自动提取记忆候选 | **真差距**：我们 experience_cards 偏被动 | **新待办 M**（优先于 L） |
| **V1** prompt caching 确认 | 我们非 SaaS 计费，无动作 | — |
| **B2** skill 隐式调度 | 佐证我们 dispatcher 更可控 | 无动作 |

记忆文件曾有硬矛盾（闭环图写 hitCount 影响排序 vs A1 证伪）——应已在第 79 行标注「A1 已证伪」；续聊打开确认。

knevo 登记为信源库 **第 ⑧ 类竞品源**（①–⑦ 多为 CC 同源；knevo 才是真交叉验证）。已验证交叉一例：决策结算用 hit/miss 不用 win/loss。

---

## 3. 断在哪里（新会话第一优先）

用户要求：

> 评估 knevo 执行方案，对我们 harness 有优化的都吸取；它的架构能识别**高频和长尾**信息，我们不行就要看差距。

助手已开始做、**未完成**的验证链：

1. 发现系统里已有 **`mention_frequency.json`**（约 115 个题材）：  
   `/Users/a77/knowledge-base-private/wiki/relations/mention_frequency.json`  
   → **今天做暴露选择器时没用它**（又一次「信息在系统里但没送到」）。  
2. 想用 `evidence_index` 的覆盖频次区分固态电池 86 家候选 →  
   即使用对 `items` 键（~23904 条），按 concept 含「固态」筛公司曾得到 **0 家** →  
   **concept 字段与 entity_exposures 对不上，不能直接按概念名 join**。  
3. 正要查「concept 到底怎么存」时，会话进入空 thinking / 断电循环。  

away_summary 残留意图：

> evidence_index 其实有覆盖信号（例：固态电池概念存在；宁德时代 42 hits 等）——需要正确 join；确认 coverage 能否分开 86 家候选，再谈是否建「高频/长尾」层。

**新会话建议开场任务（只做这一件直到有证据）**：

```text
完成「高频/长尾」可行性探针，输出一页结论，禁止空谈：
1) mention_frequency.json 的 schema + 谁消费它（rg 全仓）
2) evidence_index 的 concept/entity 主键真实样例（固态电池相关 5–10 条）
3) 能否稳定映射到 entity_exposures 的 86 家；不能则 gap 是什么
4) 若能映射：coverage/mention 分布是否足以分层（不要平均分、要分位数）
5) 若值得做：最小改动点（只读 telemetry vs 进排序 vs 进选择器 prompt）+ 不碰领域门禁
6) 对照 knevo：它的高频/长尾是记忆命中还是别的——我们应对哪一层
```

**不要一上来就实现 M 或改排序**，先结束上面的探针；用户原话是「评估 + 看差距」。

---

## 4. 待办总表（续聊用）

| ID | 内容 | 状态 | 谁定 |
|---|---|---|---|
| — | 暴露排序 + 选择器 + 留证 | ✅ 已上线 | — |
| H | 9053b0c4 / 密封重建 | ✅ 已关闭 | — |
| **探针** | 高频/长尾 × mention_frequency × evidence_index join | 🔴 **断线处** | 先做 |
| **I** | 多意图下选择器名单是否真不同（看 trace） | 🟡 可用几天自然验 | 用户用 + agent 读 trace |
| **M** | 自动经验卡提取（knevo A3） | 🟡 已立项未做 | 配额测算后 |
| **L** | 命中回流排序 | ⬇️ 降级；先 I | 原创空白 |
| **K** | 夜跑 sync 失败是否仍跑 L2 | 🔴 **阻塞 origin/main** | **用户定 a/b** |
| J | 留证强制进 answer 正文 | 未做 | 用户 |
| G | synthesize fallback 说不清原因 | 未做 | — |
| B/C/E | 工具契约 / stall / 并发 | 延后 | — |
| 数据 | 补跑断档交易日 + 稳 CDP | 视当前 fact 日期 | 用户登录 fupanhui |

**K 的两条路（勿替用户拍板）**

- (a) 认可「sync job 失败不跑 L2」→ 改测试 + SKILL 写明代价  
- (b) 资金流必须独立 → `finalize` 守卫前跑 `run_l2_branch`  
定完再 `push origin/main`（并法已 dry-run 过）。

---

## 5. 本地连接与自测问法

```
http://127.0.0.1:8792/
```

不依赖「当天盘面」也能压暴露改动的问法：

- `固态电池产业链走到哪一步了，谁最受益` ← 主战场（86→12）  
- `什么是双红题材` / 纯概念 ← 不碰盘面  
- 换意图（验 I）：`谁在扩产` / `谁受益于降价`  

看怎么选的：

```
~/.local/share/finance-workbench/users/default/runs/<run_id>/
  report.json     → 分歧反证里的截断留证句
  trace.jsonl     → graph_exposure.selector
```

---

## 6. 七（+1）份 harness 信息源

根：`/Users/a77/agent-memory/10_knowledge/`  
完整表与「按问题查」见主 handoff §8 / Start Here §5。

| # | 用途要点 |
|---|---|
| ① 马书 36 章 | 重试 ch06b；截断 ch28.4；预算模式 ch24；**动手前对 ch28 失败模式** |
| ② 十原则 | 9.5 上下文可治理不是更多 |
| ③–⑦ CC 文档/源码读 | 权限、提示词、工具契约 |
| **⑧ knevo** | `knevo-harness-reverse-engineering.md` — **唯一竞品交叉验证** |

纪律（本会话反复踩坑，必须遵守）：

1. 常量不照抄，先算自己的量纲  
2. 同名不同题（ch28.4 等）  
3. 推断不能标成发现（A1 已打脸一次）  
4. 「丢了」之前先读 **manifest / 索引**  
5. 测试先证明能变红；只测组件不测送达 = 没测  

---

## 7. 新会话开场白（可复制）

```text
读 docs/handoffs/2026-08-01b-claude-session-continuation.md 和
docs/handoffs/2026-08-01-exposure-selection-and-sealed-fixture-risk.md。

工作 clone：
/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
分支 fix/exposure-ranking-truncation。

先做 §3 的「高频/长尾可行性探针」（mention_frequency + evidence_index join），
输出一页可决策结论；不要先写大实现。
顺手核对 8792 health 的 source_revision 是否真是 751ef706、fact 表最新日期。
K/M/L 等用户点名再动。
```

---

## 8. 刻意不要做的

- 不要在旧 Claude 会话里狂按「继续」（上下文已毒化）  
- 不要为了过门禁放宽领域层  
- 不要未验证 join 就按 concept 名硬拼 coverage  
- 不要把 L（命中回流）当 knevo 现成方案抄  
- 不要在 K 未定前 `push origin/main`  
- 不要清密封夹具 11G  

---

## 9. 本 handoff 元数据

| | |
|---|---|
| 从会话抽取 | Claude Code `59d587aa-05e4-4e60-8c59-d3696e8f0fb4` |
| 抽取时间 | 2026-08-01 |
| 主 handoff 路径 | 同目录 `2026-08-01-exposure-selection-and-sealed-fixture-risk.md`（工作区可能有未提交修改） |
| 工作 clone 可能脏 | `git status` 曾见 `M docs/handoffs/2026-08-01-...md` — 续聊先 status |

*写完即可新开 Claude/Codex/Grok 会话；旧会话仅作证据库。*
