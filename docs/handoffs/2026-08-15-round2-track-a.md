# Round 2 · 轨道 A：caveat_slips 观测计数 + 跨组回归夹具

- 日期：2026-08-15 · 角色：执行方（轨道 A）· 检阅方：本 handoff 作者
- 协议母本：`docs/handoffs/2026-08-15-runtime-trace-triage-loop.md`——§1 红线、
  §1.5 并行协调、§2 七步、§6 打回条件**全部沿用**，本文只写本轮靶子与增量规则。
- 开工前读：母本「轮次记录」你的 Round 1 检阅批注 + 02:10 检阅方补注。

## 0. 开工前必须吸收的三条新事实

1. 你 Round 1 判定 **PASS**。R-001（`d6f50688`）还在 PR #6 未合并；
   合并次序：#7（纯文档）先合，你 rebase。
2. tool60 复跑产物 `intelligence/eval/runs/20260814T1446Z-b-rerun-tool60.json`
   （08-14 22:46，执行者不明）里 **B5=3 / B7=5 自发恢复——而 R-001 未部署**。
   含义：hashes+gap 滑档是非确定性行为。你的 live canary 判据不能用
   「单点未复现」当修复证据（R-21 已写「单次 live 不结案」，本条把它加强为
   「canary 必须多 case 窗口 + 只在修复部署后的窗口内计数」）。
3. 你 Round 1 的 live 臂盖戳 `revision=5b456532` 是错源；实际
   `loaded_code_root=07af9160` + 3 个 runtime 文件未提交改动（含
   `agent_episode.py`）。8792 处置等用户裁决，本轮**不做任何 live**。

## 1. 任务 1（主靶）：`finish.payload.caveat_slips` 计数

- `fix_type=EVAL_ONLY`：只加观测，不改任何判定行为。语义：
  `validate_episode_finish` 本次搬运了几个格（hashes+gap 滑档被挪到顶层
  `gaps` 的格数）；无滑档时计数为 0 且字段仍在场。
- 计数要在 finish payload / trace 里可见，归一化后可查（供后续轮次做
  滑档频率基线）。
- **新开预测行 `R-20260815-22`**（A 轨命名空间），预测至少覆盖三个断言：
  1. 对 Round 1 冻结主 case `run_20260813_034211_544672` 的 FINAL_JSON 重放
     validate → 计数 = 被搬运格数；
  2. 干净 finish（无 gap 或 gap 已在顶层）→ 计数 = 0；
  3. 无哈希 gap 的拒绝路径不产生搬运计数（拒绝语义不变）。
- **基线分支**：`fix/trka-repair-binding-gap-normalize`（叠在 R-001 之上；
  #6 未合并前不要从 main 分叉）。新分支命名 `fix/trka-*`。

## 2. 任务 2：R-001 回归夹具补三个跨组样本

把检阅方交叉验证的三个 run 固化成测试（源数据在各自 run 目录）：

| 样本 | run | 形状 | 断言要点 |
|---|---|---|---|
| B5 | `run_20260814_022902_659281` | 全格滑档（15/18 hashes+gap） | 搬运后全格 fulfilled |
| B7 | `run_20260814_023030_100048` | **混合** | `direct_answer` 0 hash 真缺口**必须仍不满足**；`evidence_boundary` 13 hashes 搬运后 fulfilled |
| A6 | `run_20260814_021218_897744` | 全格滑档（1/1） | 搬运后 fulfilled；终态 `repair_model_finish` 也在射程内 |

B7 是本任务的核心：它证明修复没有放宽——真缺口格照旧拒绝。

## 3. 暂缓与边界

- live canary、`carried_draft_chars=0` 丢稿分诊：**暂缓至用户裁决 8792 脏部署**
  （`agent_episode.py` 在脏文件清单里，先定生产代码身份再审那条缝）。
- 不碰 acceptance / normalize（轨道 B 的缝）；不改 verifier 判据；
  不重开 R6-A3 / A4 / A3。
- 独立 worktree 强制（Round 1 你用了主 checkout，本轮必须腾出）；主 checkout 只读。
- 账本只写 A 轨命名空间（`R-20260815-21` 起），不触 B 轨行与 R-02/R-10。

## 4. 交付四样（母本 §2 Step 7，一处变更）

报告命名 `docs/verification/2026-08-15-trka-r2-<slug>.md`。**轮次小结写进
PR 描述与报告末尾，不再编辑协议母本**——母本批注由检阅方回写。其余照旧：
报告（validate RC:0）、账本 diff、分支推 gitea（PR 可报检阅方代开）。
