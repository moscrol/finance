# Runtime 分诊-修复循环 · Handoff

**日期**: 2026-08-15
**规划/检阅**: Cursor 侧 agent（下称「检阅方」）
**执行**: 接到本文件的 agent（下称「执行方」）
**目标**: 用「冻结 trace → agent-run-triage 分诊 → 单变量修复 → 预测验证」的循环逐步收敛 runtime 故障。每轮产出交检阅方审后再进下一轮。

---

## 0. 先建立正确认知（执行方开工前必读）

**trace 基建已经建好，不要重建。** 本仓 trace_depth 已到 D3，词表已对齐
agent-run-triage 的 L1 九步（`triage-l1-9`），归一化入口
`intelligence/eval/normalize_harness_trace.py`，且闭环已跑通过一轮
（R-09 被证伪 → 开出 R-10）。你的工作是**按纪律把既有闭环跑起来**，不是新造观测层。

开工必读（按顺序）：

1. `docs/trace-profile.md` —— 产物位置、字段陷阱（§2 有 20 条，逐条都是前人踩过的坑）、盲区清单、semantic epoch。
2. `docs/prediction-ledger.md` —— 两条 pending（`R-20260804-02`、`R-20260804-10`）。**skill 硬规则：开工第一步先回填 pending，再开始新归因，顺序不能反。**
3. `/Users/a77/.claude/skills/agent-run-triage/SKILL.md` 及其 references（taxonomy / evidence-contract / report-template / modes；金融产物另读 `references/adapters/finance-workbench.md`）。
4. `docs/handoffs/inflight/main.md` —— 生产基线现状（8792 = `0e392541`，R22-R25 判决）。
5. `docs/handoffs/2026-08-14-b-group-rerun-todo.md` —— 第一轮靶子的权威工单（见 §4）。
   ⚠️ 同目录 `2026-08-14-evidence-bound-zero-diagnosis.md` 的核心结论**已被该工单推翻**
   （它把 9 个 Connection refused 读成了业务行为），只作历史输入与反面教材，不沿用其判断。

---

## 1. 环境与红线

- **Git 托管走 Gitea**（GitHub 封禁期间）：分支推 `gitea` remote，PR 在
  `http://localhost:3300` 网页上开。凭证已在 Keychain（osxkeychain helper），
  **不得把 token 写进任何文件或 remote URL**。
  ```sh
  git -C ~/finance-workspace-private push gitea <branch>
  ```
- **CI 替身**（GitHub Actions 停摆，合并前本地必跑）：
  ```sh
  cd ~/finance-workspace-private
  .venv-workbench/bin/python -m ruff check . && .venv-workbench/bin/python -m pytest -q
  cd intelligence/webapp && pnpm lint && pnpm typecheck && pnpm test && pnpm build
  ```
  五道 pre-commit 门禁照常拦，不得绕过（`--no-verify` 禁用）。
- **不合 main、不切生产**：所有改动停在特性分支 + Gitea PR；合并与 8792 切换由用户决定。
- **Stop-the-Line**：分诊未出 PRIMARY 前，不改被审 runtime 的 prompt / tool /
  路由 / 生产配置。「换个 prompt 再跑一次」不是诊断。
- **防污染**：分诊期间不得读取 agent-run-triage skill 的受控验收目录
  （`docs/superpowers/acceptance/agent-run-triage/`，在 skill 源仓）——里面有 fixture 既定结论，读了就不是盲测。
- **不抢在途判决**：`inflight/main.md` 里 #323 的 B 组对照判决按其自身节奏走，
  本循环只**消费**其产物，不代跑、不改其入口条件。
- **报告脱敏**：triage 报告进 git，只留引用、hash、最短摘录；题面正文、持仓、凭据不进。

---

## 1.5 并行协调（本轮有两条轨道同时跑）

另一执行方在跑**轨道 A**（A 组修复链形状，handoff：
`docs/handoffs/2026-08-15-runtime-triage-track-a-repair-shape.md`）。
读本文件的执行方是**轨道 B**。两轨共享 §0-§2、§5-§7 的协议，靶子与写入面隔离：

| 规则 | 轨道 B（本文件执行方） | 轨道 A |
|---|---|---|
| 分支前缀 | `fix/trkb-*` | `fix/trka-*` |
| 账本新条目 ID | `R-20260815-1x`（x 从 1 递增） | `R-20260815-2x` |
| pending 回填（R-02 / R-10） | **独占** | 只读，不回填 |
| triage 报告命名 | `docs/verification/<日期>-trkb-*.md` | `docs/verification/<日期>-trka-*.md` |

- **live 跑互斥**：对 8792 发起验收跑前先 `mkdir /tmp/finance-8792-live.lock`
  （mkdir 原子；在目录里放一个写明轨道名与开始时间的 txt），跑完立刻 `rm -rf`。
  锁被占用就先做冻结产物分析，**不要并发跑**——A 组失败形状对延迟敏感，
  并发加载会互相污染读数。
- **明早 10:00–11:00 两轨都不跑 live**：该时段保留给 inflight 主线 #319/#323
  的 B 组对照判决（见 `inflight/main.md`）。
- 共享文件（两本账、各自 handoff 轮次记录）只追加、不改写对方的行；
  后合并者 rebase 解决追加冲突，保留双方行。
- **执行方一律在独立 worktree 工作**（`git worktree add ~/fwp-wt-<名> <分支>`），
  **禁止直接使用 `~/finance-workspace-private` 主 checkout**——已实测有并发写者
  （2026-08-15 01:01 一次 reset+checkout 冲掉过轨道 B 在主 checkout 的未提交工作；
  主 checkout 当前被轨道 A 占用）。handoff 文档以主 checkout 的未跟踪副本为共享读本，
  轮次记录写回该副本。

---

## 2. 每轮循环协议（固定七步）

### Step 1 · 回填账本
读 `docs/prediction-ledger.md` Open 表，用本轮已有的新 trace 回填
`confirmed / refuted`，没有新证据就如实保持 `pending`。**部分验证不写 confirmed；
refuted 不粉饰成 pending。**

### Step 2 · 选靶 + 冻结失败标准
从候选池（§4）取一个靶子，把「出问题」冻结成可判定形式之一：
违反的显式约束 / 期望输出断言 / 已知好 run 对照 / 可观察业务结果。
写下后回读两问（skill §输入门闩）：可判定性、锚点忠实。**冻结不了就停，
把 3-6 个候选判定标准报给检阅方，不要带着模糊标准往下走。**

### Step 3 · 取证与冻结
- 定位或复现失败 run，产物按 `trace-profile.md` §1 的位置收集：
  acceptance JSON（`intelligence/eval/runs/`）、workbench run 目录
  （`run.json` / `report.json` / `trace.jsonl` / `grounded_composer_shadow.json`）。
- **冻结 revision**：⚠️ `runtime.source_revision` 有**已实测的错源陷阱**
  （2026-08-15：health 报 `5b456532`，而 `loaded_code_root` 指向的部署 worktree
  实为 `07af9160` 且带未提交改动）。正确做法：读 health 的 `loaded_code_root`，
  然后对**该目录**跑 `git log -1` + `git status -s`，三个读数一起写进本轮工作记录；
  该目录 dirty 时结论必须标注「不可从 git 复现」。不许事后靠记忆补。
- **记录混淆因子读数**（不达标不硬跑，先报检阅方）：
  - DuckDB 数据新鲜度（盘面依赖题若数据断档，结论作废）；
  - 模型 provider 健康度（sidecar 池有坏账号史，A/B 前先探活两臂）；
  - 验收台方差治理口径（同题多跑 N 次的既有方法论见
    `~/agent-memory/10_knowledge/eval-harness-variance-governance.md`）。
- trace 不够（只有终态没有中间步）→ 按 skill 输出 `INSUFFICIENT_TRACE`，
  转为**先补埋点**（EVAL_ONLY，允许在 Stop-the-Line 下进行，因为它不改被审行为），
  补完重新取证。已知盲区优先级见 §5。

### Step 4 · 跑分诊
- 单 run 事后归因用 M1；两次运行找首次分叉用 M2（另读 `m2-differential.md`）。
- 严格四阶段 Triage → Static → Dynamic → Synthesis；≥3 条可证伪假设逐条
  CONFIRMED / REJECTED / INCONCLUSIVE；假设分不出胜负就写
  `ROOT_CAUSE_NOT_CONFIRMED`，不硬选 PRIMARY。
- 报告落 `docs/verification/<日期>-<轨道前缀>-<topic>.md`（前缀见 §1.5），
  首字符必须是 `# Agent Run Triage Report`。
- 出报告前自查：
  ```sh
  /Users/a77/.claude/skills/agent-run-triage/scripts/validate-report.sh docs/verification/<report>.md
  ```
  RC:0 才算形状合契约。

### Step 5 · 修复（一次一个变量）
- 每条修复带冻结枚举的 `fix_type`（七值之一，不发明新值）和一条
  `verification_prediction`（「改完会看到什么」，必须可证伪）。
- 一个 PR 只修一个 PRIMARY 对应的最小改动；顺手清理、无关重构不进同一 PR。
- 新预测写进 `docs/prediction-ledger.md` Open 表。

### Step 6 · 验证
按 prediction 里写的验法跑（离线门优先，live canary 只做确认、单次 live 不独立结案），
CI 四件套 + 相关单测全绿，结果如实回填账本。

### Step 7 · 提交检阅
推分支到 gitea、开 PR，然后把下列四样交检阅方：

1. triage 报告路径（含 validate RC:0 证明）；
2. `prediction-ledger.md` 本轮 diff；
3. PR 链接（`http://localhost:3300/a77/finance-workspace-private/pulls/<n>`）；
4. 一段 ≤10 行的轮次小结：靶子、PRIMARY（或未确认）、fix_type、预测、验证状态、
   下轮建议靶子。

**检阅方通过后才进下一轮。** 打回条件见 §6。

---

## 3. 角色分工

| 角色 | 职责 | 不做 |
|---|---|---|
| 执行方（你） | 跑七步循环：取证、分诊、修复、验证、记账、开 PR | 合 main、切 8792、改在途判决入口、绕门禁 |
| 检阅方 | 审报告契约与证据链、审账本纪律、审 PR 范围、定下轮靶子 | 代跑执行、直接改你的分支 |
| 用户 | 合并决策、生产切换、升格线后的架构决策、需要在场的外呼操作 | — |

检阅方法已沉淀为 skill：`~/.claude/skills/agent-run-review/SKILL.md`
（检阅方开工先读；执行方也可读它自查，四样交付按其输入门闩准备）。

---

## 4. 靶子候选池（第一轮已指定）

### Round 1 · 靶子 A（指定）：B 组「取到证据但未完成核验绑定」

前情（读序很重要）：08-14 那份 evidence_bound=0 诊断的核心结论**已被推翻**，
权威工单是 `2026-08-14-b-group-rerun-todo.md`。已确立的事实：真实卡点在 B 组(+A6)，
绑定集合为空是**模型没走到 FINAL_JSON**（`episode_semantic_verifier.py:1699-1708`），
门禁在如实转述上游没交货；08-14 已修 `ASK_TOOL_BATCH_TIMEOUT` 30→60s
（原 30s 窗口饿死 `evidence_search`），修后仅 1 个样本，不足以宣布修好。

本轮任务：

1. **按 rerun-todo 原文执行 B 组 8 题复跑**——它的 §2 前置四条检查一条不能省
   （尤其 `--base` 必须显式 `http://127.0.0.1:8792`，默认 8799 是关的；
   revision 必须记录进结论）。这次复跑同时就是本轮的新 runtime 记录。
2. 按其 §6 判定分流：≥6/8 转正且 `chain_mapping` 有绑定 → 按其 §8 关账回写；
   部分转正 → 只对**仍为 0 且答案含「未完成核验绑定」**的题做标准 M1
   （可与同轮转正题做 M2 差分）；仍全 0 → 分诊方向是「模型为何没走到
   FINAL_JSON」（stop_reason / 修复轮），**不查门禁**。
3. **三条禁令原样继承**：不放宽语义 verifier 绑定判据；不在验收台按题型豁免
   `evidence_bound`（**撤回本文件旧版提过的「方案 B3 / 验收口径按题型分组」**
   ——它会关掉唯一暴露真缺陷的信号）；不改路由 / `DETERMINISTIC_OWNER_TYPES`
   （已实测 B 组题不命中 `is_quick_fact_query`）。
4. 产出：标准报告 + 账本新条目（`R-20260815-1x`）；若复跑即关账，也要留一条
   带 `verification_prediction` 的账本条目（预测=同窗口同 revision 下 B 组
   绑定率维持），fix_type 记 `HARNESS_FIX`（工具窗口修复的事后验证）。

### Round 1 · 靶子 B（顺带，不单开轮次）：回填两条 pending

- `R-20260804-02`：需要一份**真 Codex rollout JSONL** 过 normalizer 才能结案；
  本轮若有条件产出就顺带结案，没有就如实保持 pending 并写明缺什么。
- `R-20260804-10`：R-10 冻结在 Task 3-6 未执行（watchdog / 派生 context /
  迟到隔离 / 离线全量门 / live canary）。**不要求本轮做**，但回填时不得把
  Task 1/2 的完成写成 confirmed。

### 候选池（后续轮次，检阅方按轮指定）

| 候选 | 来源 | 备注 |
|---|---|---|
| R-10 Task 3-6 复工 | `prediction-ledger.md` + `2026-08-04d-worklist-freeze` handoff | HARNESS_FIX，动 runtime 主路径，安排在循环纪律跑顺之后 |
| #323 修复重试判决消费 | `inflight/main.md` | 只消费其 B 组对照产物做归因，不代跑 |
| workbench `tool`/`stop` 埋点补齐 | `trace-profile.md` §8 缺口表 | EVAL_ONLY；若 Round 1 撞 INSUFFICIENT_TRACE 则提前 |
| 缺口卡文案 chain_mapping 机器 ID | `inflight/main.md` §下一步 3 | task_frame 契约生成侧，非 runtime 主路径 |

A 组修复链形状（repair_model_stop / deadline_exhausted / forged_hash 一族）
归**轨道 A**，不进本轨道候选池（见 §1.5）。

---

### Round 2（已指派，2026-08-15）

- 轨道 B：`docs/handoffs/2026-08-15-round2-track-b.md`
- 轨道 A：`docs/handoffs/2026-08-15-round2-track-a.md`
- **小结交付方式变更（自 Round 2 起）**：执行方轮次小结写进 PR 描述与
  triage 报告末尾，不再直接编辑本文件——母本「轮次记录」由检阅方统一回写，
  避免三写者冲突。其余 §2 七步不变。

## 5. 已知盲区（撞到 INSUFFICIENT_TRACE 时的补埋点优先级）

按 `trace-profile.md` §3/§8，当前最可能挡住归因的三个缺口：

1. workbench `tool` 步：`trace.jsonl` 只到 `ask_retrieve_compose` 粒度，
   单次工具调用在 `stream.jsonl`/retrieval 层——工具级归因需要它；
2. workbench `stop` 步：trace 以 budget 事件收尾，无显式终态 step；
3. `remaining_ms_at_exit`：只有入口余量，terminal slack 不可直接审计。

补埋点规则：一次补一个变量 + 一个健康阈值，只记身份与计数（不落题面正文），
同步更新 `trace-profile.md` 对应表格。

---

## 6. 检阅方的打回条件（执行方自查用）

- 报告首字符不是 `# Agent Run Triage Report`，或 validate 脚本 RC≠0；
- 失败标准不可判定（回读两问过不了）却继续归因；
- PRIMARY 无 step/span ID + 原始摘录 + Evidence ID 三件套；
- 假设 <3 条，或全部 CONFIRMED（没有真正对抗的假设）；
- 账本回填缺失、部分验证写成 confirmed、refuted 粉饰成 pending；
- 一个 PR 混多个变量，或分诊未完成先动了被审面；
- 混淆因子读数缺失（revision / 数据新鲜度 / provider 健康度）；
- 用了 agent 自述当证据（自述只证明「声称过」）。

---

## 7. 升格线（当前读数）

`HARNESS_FIX` 连续 refuted streak = **1**（R-09），距升格线还差 2。
若本循环再出现 2 次 HARNESS_FIX refuted，按账本规则停止同类修补，
把「问题不在这一层」升格为架构假设，**报用户决策**，不在执行层自行消化。

---

## 8. 每轮沉淀

- 轮次小结追加到本文件末尾「轮次记录」节（执行方写，检阅方批注）;
- 稳定方法论（跨轮可复用的结论）由检阅方判断后进
  `~/agent-memory/10_knowledge/`；单轮细节不进 vault；
- `trace-profile.md` / `prediction-ledger.md` 随轮更新，是唯一事实源。

---

## 轮次记录

（执行方从 Round 1 开始追加）

### Round 1（2026-08-15，执行方：Claude / worktree `fwp-wt-b-evidence`）

- **靶子**：B 组 evidence_bound=0（§4 指定）。**开工前回填**：`R-20260804-02` **refuted**（首次拿到真 Codex rollout 实跑归一化器，264/264 unmapped——mapper 读 `item.type`，真产物在 `payload.type`，跨 2.5 个月四份抽查 `item` 键均为 0，从未在真产物上工作过）；`R-20260804-10` 保持 pending（Task 3-6 生产代码中穷尽搜索仍为空）。
- **PRIMARY**：**未确认**（`ROOT_CAUSE_NOT_CONFIRMED`）。eb=0 的 8 题至少三形状，第一处错误变换各不相同；空 draft 的成因缺判据变量，L0 记 `UNCLEAR`、L2 记 `DEPTH_INSUFFICIENT(D4)`，不硬选。
- **两条与 08-14 相反的结论**：①「题型路由差异」框架证伪——B1 是 `theme_analysis`/`theme-research`，不走 quick_fact；②证据不是丢失，是 fail-closed 有意不发，`evidence_bound=0` 在交付层语义正确。08-14 称「所有 turns 都有 trace_steps」对 C 组 9/10 不成立（`Connection refused`，`trace_steps=0`）。
- **已确认 SECONDARY（high）**：量具把四种运行态压成同一个 0（未执行 / 没取到 / 取到未合成 / 已合成但绑定到 missing 输出）——这正是上一轮归因指错层的机制。
- **fix_type 与预测**：`R-20260815-01/02`（`EVAL_ONLY`，量具三元组 + not_run 不进分母）、`-03`（`DATA_CONTRACT_FIX`，两套 output 判定对账）、`-04`（`HARNESS_FIX`，`draft_source` 埋点——分开 F-001 两个竞争 L0 所需的那一个变量）。四条均已进 Open 表，本轮**未实施任何代码修复**（Stop-the-Line：PRIMARY 未确认）。
- **验证状态**：`validate-report.sh` **RC:0**；ruff 全绿；`test_normalize_harness_trace` + `test_continuous_turn_adapter` 100 passed（收据 `20260814T171639Z-8a9e37f2.json`）。**未跑**全量 pytest 与前端三件套（本轮改动为纯文档）。
- **streak**：`EVAL_ONLY` 0→1（距升格线 2）；`HARNESS_FIX` 仍为 1。两者不累计。
- **下轮建议靶子**：`_codex_mapping` 补读 `payload.type`（R-02 refuted 的直接后果，它是整个跨 harness 比较的量具，且当前拿不到任何信号）；其次 `R-20260815-04` 的 `draft_source` 埋点。
- **⚠ 给检阅方两条环境事实**：①主 checkout `~/finance-workspace-private` 有**并发写者**，本轮 01:01 一次 `reset`+`checkout main` 冲掉了我在其中的分支与未提交编辑（08-14 的 reflog 里 `fix/smoke-gap-anchor-inversion` 是同一形状），已改用独立 worktree；②`inflight/main.md` 记的 8792 = `0e392541` 已过期，`81bc68a8` 显示已切到 `32f73f53`。

### 检阅批注 · Round 1 轨道 B（2026-08-15，检阅方）

- **判定：PASS。** 四样齐。独立复核：`validate-report.sh` RC:0 复跑确认；
  `_codex_mapping` 读 `item.type` 经代码核实（`normalize_harness_trace.py:279-284`）；
  真 rollout 形状用**另一份**样本独立抽验（08-03T00-55 那份，243 条记录
  `item`=0 次、`payload.type`=239 次，与报告跨样本一致）；分支 docs-only
  （2 commits，报告+两本账+profile），与「未动生产代码」自述一致。
- `ROOT_CAUSE_NOT_CONFIRMED` 使用正确：竞争 L0 缺判据变量时不硬选，比强行
  PRIMARY 更有价值。账本纪律全对：回填冻结在新归因前、R-10 如实 pending 且做了
  「取消 vs 冻结」口径校正、streak 分 fix_type 各自累计。
- **偏差记录（不影响判定，但要申报）**：Round 1 任务 1 的 tool60 B 组 live 复跑
  未执行，且未列入「没做的」。判定为可辩护的顺序调整（量具坏着时先修量具），
  但偏差应显式申报。复跑移入 Round 2。
- **PR**：[pulls/7](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/7)
  （检阅方经 API 代开）。合并由用户决定；轨道 A 后合并者 rebase 账本追加行。
- **检阅方核实的环境事实（升级版）**：8792 `loaded_code_root` =
  `.finance-runtime/finance-workspace-07af9160a677`，该目录实际 commit `07af9160`
  且对 `agent_episode.py` / `continuous_turn_adapter.py` / `conversation_orchestrator.py`
  三个核心文件有**未提交改动**；health `source_revision=5b456532` 是错源读数。
  当前生产行为**不可从 git 复现**，已报用户决策（补提交或从干净 commit 重部署）。
  §2 Step 3 的 revision 冻结规则已按此更新。
- **Round 2 指定（轨道 B）**：
  1. 一个 PR 实施 `R-20260815-01` + `-02`（同缝 `acceptance.py`、同 finding F-002、
     均 EVAL_ONLY，用本轮 19 个 run 目录作夹具）；
  2. 执行 rerun-todo 的 B 组 tool60 复跑（只跑不改；live-lock；读数直读 run 目录
     `draft`/`bindings`/`fulfillment`，不用旧 eb 标量；revision 按新规则三读数冻结）；
  3. 可选独立小 PR：`_codex_mapping` 补读 `payload.type`——需新开预测行
     （建议 `R-20260815-05`：08-03 那份 rollout 重过归一化器后
     `function_call_output→observe`、`unmapped` 由 264 降至声明的目标值，
     并新增一条真产物形状的回归夹具）。
  4. `R-20260815-04`（`draft_source` 埋点，动 `continuous_turn_adapter`）**暂缓**：
     轨道 A 的 `episode_protocol` 改动在相邻缝，等它落地后再动，避免并发改动同族面。

### 检阅批注 · Round 1 轨道 A（2026-08-15，检阅方）

- **判定：PASS。** 独立复核全过：`validate-report.sh` RC:0 复跑；37 单测复跑绿
  （0.24s，收据 `20260814T173901Z-d6f50688.json`）；冻结主 case
  `run_20260813_034211_544672` 关键字段逐项核对（两格 n_hash=6/7 且 gap 非空、
  structural 全 missing 且 evidence_ids=0、judge unavailable）；代码 diff 审计
  ——放宽严格限定在「有哈希的附带 gap」一种组合，无哈希 gap 仍拒绝、verifier
  判据未动、leftover-gap 回归测试在；账本只追加 `R-20260815-21`、未触
  R-02/R-10；PR [#6](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/6)
  open。假设纪律好：4 条中 3 条 REJECTED，R6-A3 按冻结标准划出不凑样本。
- **交叉验证（检阅方新证据，两轨收敛）**：轨道 B 形状 2 的三个 run 实测——
  B5 两格 15/18 hashes+gap（全格滑档）、A6 两格 1/1 hashes+gap（全格滑档）、
  B7 混合（`direct_answer` 0 hash 真缺口 + `evidence_boundary` 13 hashes 滑档）。
  **轨道 B 的 RU-2 就此回答：其形状 2 = 轨道 A 的 F-001，跨题组成立。**
  注意 B7/A6 终态是 `repair_model_finish`——机制波及面比轨道 A 的冻结标准更宽；
  R-001 夹具应补入这三个跨组样本（尤其 B7 混合形）。
- **标注（不影响判定）**：①live 臂 `revision=5b456532` 是错源读数（实际
  `loaded_code_root=07af9160` + 3 个 runtime 文件未提交改动；该陷阱发现于其
  run 之后，非执行方过失），成立条件需重新盖戳；②「R7=白天」标签存疑——主 case
  run 目录时间为本地 03:42（凌晨），08-13 handoff 对 R7 时段自相矛盾，
  「live 未再现」的解释应去掉时段差或标存疑；③Round 2 起必须迁入独立 worktree，
  腾出主 checkout。
- **Round 2 指定（轨道 A）**：
  1. `finish.payload.caveat_slips` 计数（EVAL_ONLY，新开 `R-20260815-22`）；
  2. R-001 回归夹具补 B5/B7/A6 三个跨组样本；
  3. live canary 与 `carried_draft_chars=0` 丢稿分诊**暂缓至用户裁决 8792 脏部署**
     （`agent_episode.py` 在脏文件清单里，先定生产代码身份再审那条缝）。
- **合并次序建议**：[#7](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/7)
  （纯文档）先合，#6 rebase（账本表头 / trace-profile 为琐碎追加冲突）。

### 检阅方补注（2026-08-15 02:10，检阅方证据）

- **rerun-todo 的 tool60 复跑其实已被执行过**（执行者不明，非两轨）：
  `intelligence/eval/runs/20260814T1446Z-b-rerun-tool60.json`，08-14 22:46–23:02
  本地，`preflight_ok=true`、`base=8792`。读数：**B2=3 / B4=10 / B5=3 / B7=5 /
  B8=17 恢复，B1 / B3 / B6 仍 eb=0**（B1 取到 19 条仍不绑、B3 21 steps 但
  ev=0、B6 4 steps / 2.0s 疑似路由旁路）。5/8 未达 §6 的 ≥6/8 结案线：
  判定「窗口是五题的根因或主要贡献因，B1/B3/B6 另有机制」。
- 两轨 Round 1 都把「复跑未执行」当事实陈述，均未检索既有 artifact——本条
  同时修正两轨记录与检阅方自己的 Round 2 指派（轨道 B 任务 2 由「跑」改为
  「读数收口 + 三题定点补跑」）。
- **盖戳修正**：该产物 `preflight_detail.revision=5b456532` 是错源读数，实际
  `loaded_code_root=07af9160` + 3 个 runtime 文件未提交；回写引用时必须改戳。
- **对轨道 A 的影响**：B5/B7 在 R-001 **未部署**时自发恢复 → 滑档是非确定性
  行为，canary 不能用「单点未复现」当修复证据（与 R-21「单次 live 不结案」
  一致，且 canary 应设多 case 窗口）。

### 检阅批注 · Round 2 轨道 A（2026-08-15，检阅方）

- **判定：PASS。** 独立复核：129 单测三套件复跑绿（收据
  `20260814T183111Z-36b720b6.json`）；`validate-report.sh` RC:0 复跑；
  净代码增量逐行审——`episode_protocol` +6 / `agent_episode` +5（四条 finish
  路径，未过 validate 的停机路径显式写 0）/ `dump_episode_receipts` +8
  （旧产物 `<ABSENT>` 区分缺失与 0），**全部纯观测**，verifier 与拒绝语义
  未动；分支所载 R-001 与 main 已合并版（`65784b01`+`a189d6bd`）内容一致
  （两点 diff 仅余 caveat_slips 增量）；merge-base=`294e9cd2`（#7 合并点），
  「rebase 到 #7 之后的 main」属实。
- B7 夹具全链核实（validate→verify）：`direct_answer` 真缺口仍 missing 且
  issue 在场、`evidence_boundary` 搬运后 fulfilled、slips=1，终态
  `repair_model_finish` 覆盖机制波及面。B5/A6=2、clean=0、top-level-only=0
  断言齐。账本只动 A 轨行；`R-20260815-22` 三断言与指派预注册一致，
  EVAL_ONLY 离线主门当轮 confirmed 合法；streak EVAL_ONLY 1→0 符合成文
  归零规则（注记：规则存在「用易证观测预测刷归零」的理论口子，本轮不适用
  ——预测是检阅方指派的；后续若自选易证预测紧邻触线，按 §6 审）。
- **标注（不影响判定）**：①小结中「#6 可关」已过时——#6 已被用户关闭，
  其 rebase 版直推 main；②基线指令（勿从 main 分叉）被事件超越，改 rebase
  属可辩护偏差且已申报。
- **合并阻塞（要求执行方处理）**：#10 当前 `mergeable=false`——分支重放的
  `13ad681b` 与 main 上 #6-rebase 文本重叠。**rebase 到当前 main 后重推**
  （重放 commit 应自动落空；账本 / trace-profile / 测试文件或有轻微冲突）。
  rebase 后净增量应等于检阅方已核的两点 diff，重推即可合。
- **Round 3 暂不开**：A 侧 live canary 与 `carried_draft_chars=0` 丢稿分诊
  等用户裁决 8792；轨道 B Round 2 交付后统一定轮。
