# Runtime 分诊-修复循环 · 轨道 A（A 组修复链形状）Handoff

**日期**: 2026-08-15
**规划/检阅**: Cursor 侧 agent（下称「检阅方」）
**执行**: 接到本文件的 agent（下称「轨道 A 执行方」）
**目标**: 对 A 组修复链的「待立案」失败形状做标准 agent-run-triage 分诊与单变量修复。
与轨道 B（B 组绑定链）并行，互不越界。

---

## 0. 你的定位与共享协议

**主协议在 `docs/handoffs/2026-08-15-runtime-trace-triage-loop.md`**，开工先读它的：

- §0 认知与必读清单（trace 基建已建好、两本账、skill 及 references）；
- §1 环境与红线（Gitea 工作流、CI 四件套、Stop-the-Line、防污染、脱敏）；
- §1.5 并行协调（**你是轨道 A**：分支 `fix/trka-*`、账本条目 `R-20260815-2x`、
  报告名 `docs/verification/<日期>-trka-*.md`、live 互斥锁
  `/tmp/finance-8792-live.lock`、明早 10:00–11:00 禁跑 live）；
- §2 七步循环、§5 盲区、§6 打回条件、§7 升格线。

本文件只定义轨道 A 的靶子、边界与轮次任务，不重复协议正文。

**Step 1（回填账本）对你的替换**：`R-20260804-02` / `R-20260804-10` 的回填由
轨道 B 独占。你只**读** `docs/prediction-ledger.md` Open 表确认不与你的靶子冲突，
不写这两行。你自己的新预测正常追加（ID 用 `R-20260815-2x`）。

---

## 1. 靶子：修复窗内 provider 到货，但模型没吐合法 FINISH

出处：`docs/handoffs/2026-08-13-repair-timeout-retry-loop.md` §判决与新形状——
「**新形状（待立案）**：修复窗内 provider 到货但模型没吐合法 FINISH」。
#296/#297 修好了「重试窗口拿不到/太小」，这个形状是修好之后**剩下的**失败族。

已知同形状样本（全部有冻结 artifact，在 `intelligence/eval/runs/`）：

| 轮 | artifact | 通道/时段/服务 | 同形状 case | 读数 |
|---|---|---|---|---|
| R5 | `20260813T0245Z-r5-headroom-fix.json` | 中转/凌晨/8794 | `repair_model_stop`×4 + `invalid_repair_finish`×1 | A4–A10 段 |
| R6 | `20260813T0314Z-r6-glm-qc.json` | GLM Coding Plan/凌晨/8794 | A3、A10 `repair_model_stop` | A3 交付 3 证据、A10 交付 0 |
| R7 | `20260813T0333Z-r7-relay-daytime.json` | 中转 terra/白天/8792 | A7 `repair_model_stop` | **交付 0 证据，episode 内有 17 条** |

配套材料：

- 生产 run 目录（逐步 trace、修复收据的原始来源）：
  `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`
- `scripts/dump_episode_receipts.py`：验收 run → 逐题修复收据表
  （`repair_model_retry` 带 `timeout_asked/seconds_granted` 落产物）。
- 字段陷阱先读 `docs/trace-profile.md` §2（尤其 arm 级 vs 事件级 `stop_reason`
  不一致、`elapsed` 删失语义）。

### 失败标准（起点；开工时冻结，之后不悄悄挪）

单 case 判定：终态为 `repair_model_stop` 或 `invalid_repair_finish`，**且**交付
证据 = 0，**而**同 case episode 内绑定证据 > 0 或修复轮已产出合法 partial——
即「修复轮拿到了窗口、也拿到了产物，但没有转化为合法 FINISH / 交付」。

按主协议 §2 Step 2 回读两问自查。锚点忠实：这条的否命题必须正好是
「修复链把交付救回来了」。注意 R6-A3（交付 3 条仍 `repair_model_stop`）
可能不满足此标准——如实把它划出靶内或另立标准，不要为凑样本放宽判定。

### 前人 ad-hoc 结论：当假设对待，不当结论沿用

08-13 handoff 对三题的归因**没走四阶段、没进账本**，只能作你 ≥3 条竞争假设的候选：

- A7:「修复轮产出合法 partial + 绑定；语义核验没完成 → 交付层按证据边界过滤；
  优化点在核验预算」；
- 竞争假设方向（不限于）：核验预算不足；修复轮 prompt/协议让模型产不出
  FINAL_JSON；预算/deadline 交互（授予恰好够产 partial、不够收尾）；
  交付层过滤契约本身。
- 引以为戒：B 组那份 ad-hoc 诊断已被推翻，教训是**先核基础设施因**
  （服务活着吗、窗口生效吗、打的是不是 8792），再谈业务归因。

### 本轨道禁令

1. **不放宽语义 verifier / 证据边界**。fail-closed 是价值：R6-A10 曾靠它挡住
   42 条未核验证据泄漏。若归因指向核验层，修的是预算/时序，不是判据。
2. **A4 `forged_hash` 的「唯一前缀匹配 → FORMAT」是设计口子**：整理成决策 brief
   报用户评审，**不在本轨道改代码**（回灌等于教模型换哈希，利弊要用户拍）。
3. **修复窗口尺寸机制（#296/#297）已判决收口，不重开**；governor 升帽已被取证
   证伪（成功修复调用 max=27.8s），别再立案（`inflight/main.md` §下一步 4）。
4. 不动轨道 B 的面：验收台统计口径、`ASK_TOOL_BATCH_TIMEOUT`、路由 /
   `DETERMINISTIC_OWNER_TYPES`。撞到跨轨道耦合就停下报检阅方。

---

## 2. Round 1 任务

1. **冻结产物 M1**：以 R7-A7 为主 case（R5 的 5 个、R6-A10 作旁证集），按主协议
   §2 Step 2–4 走标准四阶段。逐步 trace 从生产 run 目录取；trace 不够就如实
   `INSUFFICIENT_TRACE` + 3–6 项取证菜单，不硬归因。
2. **新鲜取证（live，遵守互斥锁）**：A 组复跑一次补样本。case id 以 R7 artifact
   `cases[].case_id` 为准；`--base` 显式 `http://127.0.0.1:8792`；开跑前过
   轨道 B 工单（`2026-08-14-b-group-rerun-todo.md`）§2 的四条前置检查
   （解释器 / health / **revision 记录** / 不覆盖已有 artifact），跑完立刻复查
   服务存活（其 §4）。**记录时段 + 通道 + revision**：本形状对时段敏感
   （R4 凌晨 vs R7 白天分布不同），结论必须携带成立条件。
   预算紧就只跑 A7 + 同形状 2–3 题。
3. **修复与验证**：按主协议 Step 5–6。一次一个变量；fix_type 用冻结七值；
   每修一条 `verification_prediction` 进账本（`R-20260815-2x`）。
4. **交检阅**：按主协议 Step 7 交四样（报告 + 账本 diff + PR 链接 + 十行小结），
   小结里额外写明：本轮新增的 runtime 记录（artifact 路径 + revision + 时段）。

---

## 3. 本轨道候选池（后续轮次，检阅方按轮指定）

| 候选 | 来源 | 备注 |
|---|---|---|
| A3 `deadline_exhausted` 档位/预算链 | R7 立案结论（ad-hoc） | standard 档检索片 ~30s、末发批量检索同一毫秒集体 `tool_timeout`；升格为标准分诊 |
| A4 `forged_hash` 前缀匹配设计评审 | R7 立案结论 | 只产出决策 brief 报用户，不改代码 |
| A9 语义/证据核验降级 | R6 唯一带降级完成题 | 与 A7 可能同链，先看 Round 1 结论 |

---

## 轮次记录

### Round 1 · 执行方（2026-08-15 01:00–01:20 CST）

- 靶子：R7-A7 全格 hashes+gap → 交付 0。R6-A3 划出（eb=3）。
- PRIMARY：`HARNESS` / `configure` / `task-instruction-category-non-compliance`（终局契约与 08-10 留 gap 冲突）。
- 否证：`repair_model_stop` 不是交付杀手；judge unavailable 是 fulfilled=0 的后果。
- 修复：`DATA_CONTRACT_FIX` `R-20260815-21`（validate 归位，不改 verifier 判据）。离线单测已绿；live canary 待切 8792。
- live：`intelligence/eval/runs/20260814T1707Z-trka-r1-repair-shape.json`；revision=`5b456532` dirty；凌晨；中转 terra；A7/A10 混槽 eb=3，A6 零证据（非本靶）。未提交该 JSON。
- 报告：`docs/verification/2026-08-15-trka-repair-finish-gap-slip.md` validate RC:0。
- 下轮建议：finish.`caveat_slips` 计数；或主路径 `carried_draft_chars=0` 丢稿。不碰 A4/A3。
