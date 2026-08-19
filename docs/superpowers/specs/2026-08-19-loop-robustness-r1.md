# Loop 鲁棒性批次 R1 —— 七个工作流施工 spec

- **状态**：R1（2026-08-19）。基线 `gitea/main@441c60f2`（已部署 8792）。
- **来源**：#224（G7/G11/A2 门禁放宽）上线后的整体架构评审。结论：产品能稳定跑出输出，但有七处结构性弱点会持续制造「假回归 / 假绿 / 越修越薄」。本文把它们落成可并行施工的工作流。
- **读者**：各落地 agent。**每个工作流独立分支、独立 PR，合并回 `main` 必须等用户确认。**
- **与在途批次的关系**：`docs/handoffs/2026-08-19-depth-gap-execution-dispatch.md` 的 Track A–E 仍在途。共享施工缝的让位规则见 §派单表。

## 定位纪律（先读）

本文引用的行号是 `441c60f2` 时点的**参考值，会漂**。动工时一律用给出的 `rg` 模式重定位，不要按行号直接跳（本仓 CLAUDE.md 有「固定行号数数翻车」的在案教训）。

## 全局纪律（每个工作流都适用）

1. 解释器用 `.venv-workbench/bin/python`；合并前 `ruff check` + 全量 `pytest` 收据（`scripts/check_test_receipt.py` 可对账）。
2. 提交一律 pathspec（`git commit -- <文件列表>`），禁 `git add -A`。
3. 涉及行为验证的，用 sidecar（`scripts/live_probe.py start-sidecar` 或临时端口），**不碰 8792 生产**。
4. 每个工作流开工先写 `docs/handoffs/inflight/<分支>.md`，收工回写。
5. agent 工具红线不变：只读 + 无外呼；capability 仍受 `contract.allowed_capabilities` 门控。
6. 判官不变量不变：**judge may reject or narrow an answer, never add**（`episode_semantic_verifier.py` 模块 docstring）。任何「补内容」都不得发生在判官内部。

---

## W1 结构化 issue 契约（P0）

### 失败形状（现状证据）

验证器、放行门、修复器之间用**自然语言字符串**握手：

- 产生端：`episode_verifier.py` 有 11 处 `issues.append(...)`（`rg -n "issues.append" intelligence/services/episode_verifier.py`）；语义层另有 `_NUMERIC_CONDITION_ISSUE = "unsupported numeric condition without bound evidence"`（`episode_semantic_verifier.py` ~L202）。
- 消费端：`_can_semantically_release_partial`（同文件，6 个调用点）靠**前缀白名单**匹配字符串决定 partial 放行。
- #224 的改法本质是「往白名单再加两条前缀」。**改文案 = 改放行行为**，测试全锚在子串上，词表漂移即静默改变门禁语义。

已有仓内先例：同文件 `_CLAIM_POLICY` 是键控 dict（`"unsupported_numeric_trigger_rejected": True` 等），说明「策略用 key 不用文案」在本仓已开过头。

### 目标

新模块 `intelligence/services/episode_issues.py`，单一真本源：

```python
class IssueCode(StrEnum):
    EVIDENCE_TYPE_STRIPPED = "evidence_type_stripped"   # G7 剔除非法类型后保留合法哈希
    EVIDENCE_TYPE_UNSUPPORTED = "evidence_type_unsupported"
    NUMERIC_UNSUPPORTED = "numeric_unsupported"          # 原 _NUMERIC_CONDITION_ISSUE
    FINANCIAL_ANCHOR_MISSING = "financial_anchor_missing"
    # ……穷举现有 11+ 种

@dataclass(frozen=True)
class Issue:
    code: IssueCode
    subject: str      # slot id / 句索引等定位对象
    message: str      # 人读文案，仅用于日志与报告，不参与任何判定

RELEASE_POLICY: dict[IssueCode, ReleaseAction]  # block / partial_ok / strip_ok
```

- G7（`episode_verifier.py`）产 `Issue`；G11（`_can_semantically_release_partial`）**只判 code 查 `RELEASE_POLICY`**，不再碰文案。
- 收据序列化格式：`code=<CODE> subject=<slot> :: <message>`（人可读、机器可切，老收据 grep 习惯不断）。
- **穷尽性 fail closed**：`RELEASE_POLICY` 缺项一律按 `block` 处理，并有穷尽性测试（每个 IssueCode 必须显式登记）。

### 非目标

- 不重写历史收据、不做旧格式迁移脚本。
- 不动判官 prompt 的 `issues` 输出（那是判官→系统的另一条信道，本流只管验证器→放行门）。
- 不动 `scripts/smoke_workbench_self_use.py` 的 `semantic_answer_issues`（它按 `answer_status` 判、有自己的词表，已解耦，验证过）。

### 取舍（为什么不做更便宜的版本）

把白名单集中成常量表更便宜，但治不了根病——「文案即行为」还在，只是搬了个家。枚举 + 策略表把「哪类问题允许哪种放行」变成一张可 review、可穷尽测试的表，这才是 #224 想表达而没表达干净的语义。

### 验收判据

1. 全量测试绿收据。
2. **防倒退测试**：只改某条 `Issue.message` 文案，release 行为不变（这条测试直接钉死本流的目的）。
3. SPT 三题 sidecar 重放，`verified_status` 与 #224 后基线一致。
4. 穷尽性测试如上。

### 冲突面

与 Track C（E2）/ Track D（E1/E3）同在 `episode_semantic_verifier.py`。**建议等 C/D 合并后动工**；若先动工，后合方 rebase。

---

## W2 判官降级的诚实化 + 后验复核（P0，本批只做 Phase 1）

### 失败形状

2026-08-19 对 8792 的验收探针 `degrade_count=1`，归因是**判官 transient**（provider 下午延迟 + 25s 窗口），不是内容回归。窗口历史在代码注释里自证（`rg -n "罩住尾部" intelligence/services/episode_semantic_verifier.py`）：上次把 `semantic_judge_window_seconds` 定 25s 罩住 13.3–24.1s 尾部，这轮 5 次 live 又把尾部推出窗外——**追着尾部调常数是打地鼠**。判官不可用时报告带「本次未完成独立复核」帽子照发（`JudgeStatus="unavailable"`），但 degrade 统计不区分「供应商抖动」和「内容真退化」，A/B 信号被污染（今天差点记成 #224 回归）。

### Phase 1 目标（本批）

1. **degrade 分类**：产物与探针汇总把 `judge_unavailable` 与 `content_degraded` 分列。判定材料已在 `SemanticEpisodeOutcome` 现有字段（`timeout_asked` / `timeout_configured` / `remaining_seconds_at_entry` / `exc_class`），只差分类与透出。
2. **后验复核台账**：`judge_status="unavailable"` 的 run 落一条 pending 记录（产物内标记 + 汇总索引）；新脚本 `scripts/rejudge_pending.py` 离线重跑判官，**只写收据、不改已发布答案**，累计统计「事后复核翻案率」。
3. 窗内保证至少一次完整判官尝试：剩余窗不足一次完整尝试时不再发起半截调用，直接记 `unavailable` + 原因字段（避免烧窗口还得不到结论）。

### Phase 2（不在本批，数据说话后另立 spec）

翻案率低 → 维持现状，`unavailable` 从质量口径中永久分列；翻案率高 → 才考虑发布后可见的追加批注（改 UX 契约，需用户拍板）。

### 非目标

不改「判官只删不加」；不做已发布答案的事后修改；不做自适应窗口放大（全链 deadline 传绝对时刻是本仓已立原则，放大判官窗=挤压下游，且救不了 provider 整体抖动；后验复核不占在线预算，这是选它的原因）。

### 施工缝

`episode_semantic_verifier.py`（`semantic_judge_window_seconds` / `_JudgeCall` / `JudgeStatus`）；产物写出处加 pending 标记；新脚本 `scripts/rejudge_pending.py`。今天的 transient 样本可直接当测试材料（`~/fwp-wt-live-verify/state/live-verify/20260819T06*/`）。

### 验收判据

1. 用今天的 transient 案例离线走通 rejudge，出翻案收据。
2. 探针与 eval 汇总输出分列的 degrade 两类计数。
3. 全量测试绿。

### 冲突面

与 W1 同文件，排在 W1 后（分类要用 IssueCode）。

---

## W3 双引擎产物同构（P1）

### 失败形状

`intelligence/api/app.py` 自己承认双入口（~L1368 docstring：`POST /api/runs → _run_ask is a second entry point, independent of ...`）：`/api/runs` 走 ask 引擎、`/api/conversations` 走 episode 引擎。两套产物形状不同，今天验收时 `live_probe`（ask 产物）和 `smoke_workbench_self_use`（episode 产物）只能各比各，跨入口 A/B 没法并排。

### 目标

1. 定义统一 `gate_receipt` 块（字段至少：`rev` / `verified_status` / `judge_status` / `issues[]`（W1 落地后为 code 化条目）/ degrade 两类计数 / 关键耗时），**两引擎产物都携带**。
2. 探针与 eval 汇总读同一块出同一张表；一次 sidecar 双入口对拍收据作为样例入库。

### 非目标

**不合并引擎。** 引擎归一是另一个量级的决定，本流只附带交付一份《两入口真实消费者盘点》（谁在调 `/api/runs`：followups、eval、checkpoint-recheck……逐个列），供用户后续决策，不擅自动。

### 施工缝

`intelligence/api/app.py`（`_run_ask` 产物落盘处、episode 路径 `report.json` 写出处，`rg -n "api/runs|api/conversations" intelligence/api/app.py`）；`scripts/smoke_workbench_self_use.py` / `scripts/live_probe.py` 的汇总函数。

### 验收判据

同一问题过两入口，`gate_receipt` 可并排 diff；汇总脚本消费新块；测试绿 + sidecar 对拍收据。

---

## W4 混合意图的车道组合（P1）

### 失败形状

`route_table.py` 的 `RouteRow` 单行命中、`capabilities` 定死。混合题（隔夜美股 + A 股推演）曾直接漏 news/web，P0-A 的修法是在 `resolve_evidence_plan`（`evidence_capabilities.py` ~L282）里打了一个专用 if（`_has_overnight_external_premise`，~L239/314）。**每种混合形状再出现一次，就再打一个 if**——补丁会越积越多且互相看不见。

### 目标

把「主车道 + 叠加规则」显式化：

- `route_table.py` 增加声明式组合规则表：`(谓词, 追加 capabilities, 规则名)` 元组列表；`resolve_evidence_plan` 通吃整表。
- 把 overnight 那个 if **迁成表里第一条规则**（行为等价）。
- 边界：主 `question_type` 不变、验证契约不变；叠加只放大证据 capabilities，**不新增 required_output、不越权**（capability 仍受 `contract.allowed_capabilities` 门控，红线不动）。

### 非目标

不做多契约合并；不改车道判定本身；不引入 LLM 全权规划 capabilities（灵活但不可审计，声明式表保住「路由行为可 review」）。

### 验收判据

1. overnight 行为等价回归（迁移前后同题同 plan）。
2. 新增至少一条真实第二规则（从 eval 错题里挑，如「美联储决议后 A 股 XX 板块」类外部事件 + 本地推演）。
3. 规则表穷尽测试：每条规则至少一条对应测试。

---

## W5 回填式 repair（P2，依赖 Track D + W1）

### 失败形状

`_repair`（`episode_semantic_verifier.py` ~L1744）只会 `_drop_rejected_sentences` 后重验——**答案只能越修越薄**。而数字型阻断（`NUMERIC_UNSUPPORTED`）常常只是「缺一次 market_data 调用」，现状只能删句或降级。判官不变量「never add」本身是对的，所以**回填不能发生在判官里**。

### 目标

在 episode 层加一种 repair turn：release 被特定 IssueCode（`NUMERIC_UNSUPPORTED` / `FINANCIAL_ANCHOR_MISSING`）阻断时，允许**一次**窄契约补证回合——只开缺口对应 capability、预算 ≤ 原回合 25%、产物并入证据池后**走全套 G/A/T/S 重验**。判官仍然只删不加。

### 依赖

- Track D（E1：`contract_missing_outputs` → repair 接线）先落——它定义 repair turn 的管道，本流扩展触发集与 repair 种类。
- W1 的 IssueCode 是触发判定的输入。

### 验收判据

1. 构造 SPT 式阈值题 sidecar 案例：首轮 `numeric_unsupported` → 回填 turn 拉到数据 → `completed` 放行；收据显示两回合与预算占用。
2. **防倒退测试**：回填回合不得引入新主张——diff 只允许证据绑定与被阻断句的改写，新增句子 fail closed。
3. 预算上限测试：补证回合超预算即放弃回填、回落到现有 partial/删句路径。

---

## W6 部署切换审计账本（P0，小）

### 失败形状

8792 出现过一次**无记录的切换**（a7e2d74f，2026-08-19 验收时靠人对 readiness 才发现）；生产台账 `docs/handoffs/inflight/main.md` 是人写的，会漏。

### 目标

**单一写入者 = 启动路径自报**（事实投递 > 提醒，BUILD.md 已立模式）：

1. 服务启动时追加一行 JSONL 到 `state/deploy-ledger.jsonl`（gitignored）：`ts / rev / snapshot_path / port / pid / argv`。
2. `scripts/deploy_workbench_runtime.sh` 在切 symlink 处同样落一行 `action=switch`。
3. 校验脚本 `scripts/audit_deploy_ledger.py`：ledger 尾行 vs readiness 实报 rev 对比，不一致报警；可挂夜间回检。

### 取舍

launchd watcher 也能做，但「启动自报」比「旁观者推断」可靠——watcher 挂了没人知道，启动自报挂了服务本身就没起来。

### 验收判据

sidecar kickstart 一次见 startup 行；手动跑一次部署脚本见 switch 行；audit 脚本对 8792 跑通出对账结果。

---

## W7 评测方差基线（P0，小）

### 失败形状

单次探针的 `degrade_count=1` 今天差点被记成 #224 回归；判官 transient、provider 时段延迟都能翻单次结果。**A/B 没有方差底就没有显著性**——目前所有验收结论都建立在 N=1 上。

### 目标

1. 新脚本 `scripts/eval_variance_baseline.py`：同 rev 同题跑 N 次（默认 N=5，qc28 子集或指定题），产出每题 outcome 分布 + 翻转率收据（`intelligence/eval/runs/` 命名带 `-varN` 后缀）。
2. A/B 判定规则写进 `docs/learning/acceptance-workflow.md`：**观测差异小于基线翻转率，不得下回归/改善结论**；`judge_unavailable` 类 degrade 单列不计入内容质量（衔接 W2 分类）。

### 验收判据

对 `441c60f2` 出第一份基线收据；acceptance-workflow.md 更新；脚本有 `--help` 与最小测试。

---

## 派单表

| 组 | 工作流 | 建议分支 | 前置 | 冲突面 |
|---|---|---|---|---|
| G0（立即并行） | W6 部署账本 | `feat/deploy-ledger` | 无 | 无（新文件 + 部署脚本尾部） |
| G0（立即并行） | W7 方差基线 | `feat/eval-variance-baseline` | 无 | 无（新脚本 + 文档） |
| G1（立即并行） | W3 产物同构 | `feat/gate-receipt-unify` | 无 | `api/app.py`、两个探针脚本 |
| G1（立即并行） | W4 车道组合 | `feat/lane-composition-rules` | 无 | `route_table.py`、`evidence_capabilities.py` |
| G2 | W1 issue 契约 | `fix/issue-contract-codes` | 建议等 Track C/D 合并 | `episode_verifier.py`、`episode_semantic_verifier.py` ↔ Track C/D |
| G3 | W2 判官诚实化 | `feat/judge-pending-review` | W1 | 同 W1 文件 |
| G4 | W5 回填 repair | `feat/repair-backfill-turn` | Track D + W1 | repair 路径 |

- G0/G1 四条现在就能并行开工，互不相交。
- W1 是 W2/W5 的词表地基；若 Track C/D 迟迟不合，W1 可先行、C/D rebase（二选一，先动工者赢）。
- 所有 PR 合并需用户确认；每流收工回写各自 inflight handoff + 本文状态行。

## 状态跟踪

| 工作流 | 状态 | PR | 备注 |
|---|---|---|---|
| W1 | 未开工 | — | |
| W2 | 未开工 | — | Phase 2 需另立 spec |
| W3 | 未开工 | — | 附消费者盘点交付 |
| W4 | 未开工 | — | |
| W5 | 未开工 | — | 等 Track D |
| W6 | 未开工 | — | |
| W7 | 未开工 | — | |
