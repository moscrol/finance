# feat/research-evolution-06-workbench 在途交接

最近更新：2026-09-14 · HEAD 7abaa938（第七轮返修已提交）· 分支已含四轨合并（01/02/04/05 + 06 I17）

## 当前任务（第八轮 QC 复审等待中）

第七轮 P1×2 返修完成、全绿待复审。路线：「暂不扩范围」——自动认领整体移除，无身份成果统一显式确认。

## 本轮改动（相对 f90e27c5；注意四轨合并落在两轮之间）

- X1：`_link_run_event` completed 分支删除全部 auto-pick（U4 闸/历史唯一闸/候选挑选）——无 new_judgment_ref 一律 ERR_DEPENDENCY_MISSING。显式 ref 四闸（存在/同会话/不早于请求/**未被他项闭环消费**）。
- X1 过渡合同：Q2 改写为「终态保持待复核 → 显式确认闭环」（裁决授权调整）。
- X2：接受侧 bind 前查 run 既有归属，矛盾即跳过（不追加第二归属）；`_source_coordinate_conflict` 统一运行中登记与终态折回的矛盾核验——窗口期矛盾链接只作审计；`fold_run_terminal` 吞 ApiError。
- 仓内新增 X1/X2 镜像；探针 re06-9266407f 原样 2/2。

## 验证

- 组合门禁（5 套件 + round2–7 探针）**139 passed**。
- 干净候选 7abaa938（dirty=false）裸 pytest **10141 / 0F / 77S**（合并态基线 10137@3d72b53a + 4 新 = 10141 算术吻合）。
- 前端零改动（94 tests 沿用）；e2e 重跑 31/2sk；ruff 全绿。
- 沙箱两条归因口径已更正为「检出位置敏感」（/private/tmp 红、~/.finance-runtime 绿），非嵌套沙箱、非 RE06。

## 重要背景（下一个 agent 必读）

- 用户在第六轮交接后把 01/02/04/05 四轨 + 06 I17 跨轨验收**合并进了本分支**（eac41a64/d432a67b/196cfdc1/505d1747/3d72b53a/b5ecc298）。本分支不再是纯 06。
- 成果归属最终合同：只有显式确认。auto-pick 已整体删除，不要恢复计数条件。
- 若要恢复自动关闭：先扩 judgments writer（归属坐标），再升级 Q2 正例——需用户批准范围。
- 证据：`docs/verification/re06-9266407f/REWORK.md`；快照 `docs/handoffs/2026-09-14-re06-round7-x1-x2.md`。

## 合并（通过后等用户确认）

分支已含 spec 链；回 main 仍需用户确认。不部署、不动其他 worktree。
