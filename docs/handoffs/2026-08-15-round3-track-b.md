# Round 3 · 轨道 B：干净身份基线批 + R-07 落地

- 日期：2026-08-15 · 角色：执行方（轨道 B）· 检阅方：本 handoff 作者
- 协议母本：`docs/handoffs/2026-08-15-runtime-trace-triage-loop.md`——§1 红线、
  §1.5 并行协调、§2 七步、§6 打回条件全部沿用。开工前读母本「轮次记录」
  两轨 Round 2 检阅批注。

## 0. 本轮新事实（已由检阅方独立核实）

1. **生产首次可从 git 复现**：pid 30091（03:03:11 起），加载
   `~/.finance-runtime/finance-workspace-cb09f895734a` @ `cb09f895`，
   porcelain 为空，tool60 保留。`R-20260815-06` 已 confirmed（#17）。
2. R-001 + `caveat_slips` + 你的全部 Round 2 量具（五态 `execution_state`、
   eb 三元组、修复版 codex mapper）都在这个身份里。
3. **本轮唯一 live 批归你**（live-lock 按 §1.5 声明）；轨道 A 只离线消费
   你的批产物，其 R-21 canary 判据会**先于开批**预注册进他们的分支。

## 1. 任务 1：干净基线批（本轮主靶）

- **等 A 的预注册分支推上 gitea 再开批**（查
  `docs/verification/2026-08-15-trka-r3-r21-canary.md` 是否在其分支存在，
  或由检阅方/用户通知）。
- 题集与 Round 1 基线同源（qc28 同款 A/B/C 全量），runner 与 rerun-todo §3
  同款；前置检查照 rerun-todo §2 四条 + §2 Step 3 三读数
  （期望 `cb09f895` + porcelain 空 + tool60）。
- 产物命名 `20260814TxxxxZ-r3-clean-baseline.json`——**日期用 UTC 实时**，
  别复现 0815 那次命名滑档；产物带 sha256 随 PR 进 git（沿用你 Round 2
  勘误后的做法）。
- 盖戳：revision / porcelain / 时段 / 通道 / 窗口，五项齐。

## 2. 任务 2：读数（修复后首个干净基线）

- 五态分布 vs Round 1 `qc28-full` 基线：`not_run` 应只剩真连接失败，
  B 组各题落哪一态逐题列表；
- `caveat_slips` 分布（供轨道 A 收口 R-21——你出数，不替他判）；
- per-slot 原始形状计数：`gap_zeroed`（有哈希带 gap）vs `no_hash`（真缺口），
  为任务 3 提供真数据。
- 判据一律取结构化字段；拿不到就 `undetermined`，不猜。

## 3. 任务 3：实施 `R-20260815-07`（EVAL_ONLY，单 PR）

`bound_but_dropped` 细分 `gap_zeroed` / `no_hash`。夹具 = B1/B3/B7 三个
冻结 run + 本批新数据。按账本里 -07 行的预注册断言逐字自证后回填。

## 4. 任务 4（可选，独立 PR）：`R-20260815-04` draft_source 埋点

暂缓已解除（episode 缝已合并部署）。若做：必须在基线批**之后**动手
（不污染本批身份）、独立 PR、新预测行（`R-20260815-08` 起）、动
`continuous_turn_adapter` 前先确认 A 本轮没有触碰同文件的计划（§1.5 相邻缝）。

## 5. 边界与账本

- 不碰 `episode_protocol.py` / verifier 判据（A 缝）。
- 独立 worktree；主 checkout 只读。
- 账本只写 B 段（新行从 `-08` 起）。**开工第一步**顺手核对 #17 对 `-06`
  的关闭行：出处、三读数证据、格式是否合账本模板；不合规就在你的 PR 里修正
  （只修格式与证据引用，不改 outcome）。
- 报告命名 `docs/verification/2026-08-15-trkb-r3-<slug>.md`。

## 6. 交付四样

报告（validate RC:0）、账本 diff、分支推 gitea（PR 可报检阅方代开）、
轮次小结写 PR 描述与报告末尾（不编辑母本）。
