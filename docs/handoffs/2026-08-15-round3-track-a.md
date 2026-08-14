# Round 3 · 轨道 A：R-21 canary 预注册收口 + 丢稿条件靶

- 日期：2026-08-15 · 角色：执行方（轨道 A）· 检阅方：本 handoff 作者
- 协议母本：`docs/handoffs/2026-08-15-runtime-trace-triage-loop.md`——§1 红线、
  §1.5 并行协调、§2 七步、§6 打回条件全部沿用。开工前读母本「轮次记录」
  两轨 Round 2 检阅批注。

## 0. 本轮新事实（已由检阅方独立核实）

1. **生产首次可从 git 复现**：pid 30091（03:03:11 起），加载
   `~/.finance-runtime/finance-workspace-cb09f895734a` @ `cb09f895`，
   `git status --porcelain` 为空，`ASK_TOOL_BATCH_TIMEOUT=60` 保留。
   `R-20260815-06` 已 confirmed（#17）。
2. R-001 + `caveat_slips` 现运行在干净身份上——R-21 的 live 臂条件**首次成立**。
3. **live-lock 归轨道 B**：本轮唯一 live 批（干净基线批）由 B 执行，
   你全程离线，只读批产物与 run 目录。

## 1. 任务 1：预注册 R-21 canary 判据（开批前完成）

把判据写进报告草稿 `docs/verification/2026-08-15-trka-r3-r21-canary.md`
并**推分支**（提交时间戳必须先于 B 的批产物 `generated_at`）。判据至少含三条：

1. 批内任何 finish 的 `caveat_slips>0` 的 case：其**有哈希格**全部
   `fulfilled`、eb>0（滑档不再零交付）；
2. 真缺口格（`n_hash=0` 且带 gap）仍判 `missing`——不放宽（对照形状：
   B1@RunB / B7 混合形，见轨道 B Round 2 报告 E-002/H3）；
3. 批内 `caveat_slips>0` 的 case 数为 0 时的处置**预先写死**：
   记 `unobserved-in-window`、R-21 保持 pending，还是申请扩批——二选一，
   事后不得改口。

## 2. 任务 2：按预注册收口 R-21

批产物落盘后按预注册判据读数，账本回填 `R-20260815-21`
（confirmed / refuted / pending+unobserved 理由）。读数直读 episode
`finish.payload.caveat_slips` 与 structural outputs，不用展示话术。
盖戳按 §2 Step 3 三读数（本轮应为 `cb09f895` + porcelain 空）。

## 3. 任务 3（条件触发）：`carried_draft_chars=0` 丢稿分诊

- 批内出现 `carried_draft_chars=0` 事件 → 以其为靶开标准 M1 分诊
  （埋点已在 main，收据里可读）；
- 未出现 → 从母本 §4 候选池选靶，**报检阅方核准后**再动，不自行扩缝。

## 4. 边界

- 不跑任何 live；不碰 acceptance / normalize（B 缝）；不改 verifier 判据。
- 独立 worktree；主 checkout 只读。
- 账本只写 A 段：`-21` 收口，新行从 `R-20260815-23` 起。
- 分支命名 `fix/trka-*` 或 `docs/trka-*`；报告命名
  `docs/verification/2026-08-15-trka-r3-<slug>.md`。

## 5. 交付四样

报告（validate RC:0）、账本 diff、分支推 gitea（PR 可报检阅方代开）、
轮次小结写 PR 描述与报告末尾（不编辑母本）。
