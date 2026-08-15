# Round 4 · 轨道 B：勘误 + 聚合口径修复 + R-08 + 基线批 #2

- 日期：2026-08-15 · 角色：执行方（轨道 B）· 检阅方：本 handoff 作者
- 协议母本：`docs/handoffs/2026-08-15-runtime-trace-triage-loop.md`——§1 红线、
  §1.5 并行协调、§2 七步、§6 打回条件全部沿用。开工前读母本「轮次记录」
  的「检阅方批注 · Round 3」勘误门段（E-r3-1 / E-r3-2）。

## 0. 检阅结论（先读）

Round 3 干净基线批 **PASS，勘误门 ×2 + rebase 后可合**。你的 C1/C2 报数、
gap_zeroed=0、not_run 归零、B1/B7 形状迁移、身份盖戳、sha256 全部经独立
复核成立。开批前拦下 `FORESIGHT_USERS_DIR` 静默降级是本轮最佳实践。

## 1. 任务 1：勘误 + rebase（合 PR 前完成，先行）

1. **E-r3-1**：报告 L129「`bound_but_dropped` 由 3 归零」→ 按轮 1 例
   （C10 第 3 轮，两格 `n=0`+gap，no_hash 侧）、按 case 聚合 0 例。
   成因写明：tally 把多轮题 C10 计为 `delivered`，case 级字段却显示
   turns[-1]，同一产物两口径矛盾。`gap_zeroed` 归零结论不受影响。
2. **E-r3-2**：报告 L17/L281 + 账本 R-07 行「本批另贡献 4 个 `no_hash`
   真缺口格」→ **6 格**（补 C10 `direct_answer` + `evidence_boundary`）。
3. **rebase 到 `f43f2507`**（#19 之后的 main）：你的分叉点 `23e2a07e`
   早于 #19，现分支直接合并会回退 A 的 R-21 预注册文本并删掉 canary 报告。
4. 批产物 JSON **不改**——它是冻结证据，聚合缺陷属量具，修复见任务 2。
   勘误后推分支，PR 由检阅方代开或你自开均可。

## 2. 任务 2：多轮题五态聚合口径（新缺陷，EVAL_ONLY）

1. 在 acceptance 里**定义**多轮 case 的聚合规则并写成代码注释 + 文档：
   建议 tally 按轮计数（附 per-turn 明细），case 级另立字段
   `execution_state_aggregate` 并写明取法（如「最后一轮」或「最坏轮」，
   二选一，写死）。当前 tally 与 case 字段各说各话是缺陷本体。
2. C10 冻结 run 目录作夹具：断言聚合字段与 tally 在多轮题上口径一致。
3. 账本登记一条新预测（你的命名空间顺延），falsifiable 判据照 R-08 风格。

## 3. 任务 3：实现 R-20260815-08（users 目录响亮失败）

按你登记的行实现：验收台从 `/api/health` 取服务端 users 目录，或在自身
env 与服务端不一致时响亮失败。负夹具：错目录 + 对目录各跑同题，断言前者
**不产出**「看起来正常」的五态分布。独立 PR。

## 4. 任务 4：干净基线批 #2（live-lock 归你）

1. 前置：确认 8792 身份仍为 `cb09f895` + porcelain 空（若已变，停，
   报检阅方，不开批——批 #2 的可比性依赖同身份）。
2. 同 qc28 全集、同预算、同超时，产物命名 `*-r4-clean-baseline-2.json`
   （UTC 日期照 §2 规范），sha256 进 git。
3. 读数按 **R-10 口径**：B 组按题报「N 批中交付次数」（现 N=2），
   禁止单批布尔名单结论；顺带监测 `gap_zeroed` 与 slips 分布
   （RU-2 的连续 N≥3 批处方，本批是第 2 点）。
4. B1/B7 若再次 `invalid_repair_finish`：只记形状与频次，**不开根因分诊**
   ——R-09 的原因码本轮由 A 实现、尚未部署，判据变量还不在产物里。
   等下一轮部署后再收 L0。

## 5. 边界与缝

- 可改：`intelligence/eval/`（acceptance/normalize）、其测试、
  `docs/verification/`、账本你的段。
- 不可改：`episode_protocol.py` / `agent_episode.py` /
  `continuous_turn_adapter.py`（A 的缝；R-04 继续挂起，理由同你 Round 3
  的记录——等 R-09 落地再单变量动它）。
- 独立 worktree + 独立分支，不碰主 checkout。

## 6. 交付四样（不变）

报告（validate-report.sh RC:0）、账本 diff、PR（gitea）、轮次小结
（≤10 行，追加母本「轮次记录」）。勘误（任务 1）可并入 Round 3 分支
supersede，也可单独小 PR——先勘误后批 #2，顺序不得倒置。
