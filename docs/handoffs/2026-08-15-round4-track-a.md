# Round 4 · 轨道 A：R-21 收口 + 条件靶了结 + R-09 拒收原因码

- 日期：2026-08-15 · 角色：执行方（轨道 A）· 检阅方：本 handoff 作者
- 协议母本：`docs/handoffs/2026-08-15-runtime-trace-triage-loop.md`——§1 红线、
  §1.5 并行协调、§2 七步、§6 打回条件全部沿用。开工前读母本「轮次记录」
  的「检阅方批注 · Round 3」，特别是批注 A-r3-1 与 R-21 裁决段。

## 0. 本轮新事实（已由检阅方独立核实）

1. 干净基线批已落盘：`intelligence/eval/runs/20260814T1926Z-r3-clean-baseline.json`
   （`sha256=b712bd2e…`，`generated_at=20260814T200212Z`，`revision=cb09f895`），
   在 B 的分支 `fix/b-group-gap-shape-split` 上，勘误 + rebase 后合入 main。
   **等它进 main 再引用**（合并队列见母本批注）。
2. 检阅方已按你预注册的判据独立复核：C1 零违反（`caveat_slips>0` 恰 9 题，
   全部 delivered 且 eb>0）、C2 零违反（4+2 个真缺口格全 missing）、C3 不适用。
   canary **通过**。
3. 你全程离线。本轮 live-lock 仍归轨道 B（批 #2）。

## 1. 任务 1：收口 R-20260815-21（你的行，你来翻）

- 账本 `R-20260815-21` → `confirmed` 进 Closed，outcome 引：批
  `sha256=b712bd2e…`、9 题 slips>0 全交付、混合形正样本 C9
  （slips=1 与真缺口 missing 同 turn 共存）、母本 Round 3 批注。
- 收口小节追加进 `docs/verification/2026-08-15-trka-r3-r21-canary.md`
  （预注册文本一字不动，收口另起 §Post-batch closure）。

## 2. 任务 2：条件靶按收窄谓词了结

预注册的字面谓词（「批内出现 `carried_draft_chars=0`」）已被检阅方证明
过宽：28/28 run 命中，因为停机路径无稿可携带时合法写 0。处置：

1. 用收窄谓词重扫批内 28 run：**同 episode 内曾有 `draft_chars>0`、
   其后事件 `carried_draft_chars=0`**（真丢稿：写了稿、携带时丢了）。
2. 命中 ≥1 → 以其为靶开标准 M1（预注册原文的本意）。
3. 零命中 → 在收口小节记「条件靶未触发（谓词过宽已修正，收窄后零命中）」，
   **不开 M1、不自行扩缝**。检阅方探针预计零命中（B1/B7 从未产生 draft）。

## 3. 任务 3：实现 R-20260815-09（拒收原因码，你的缝）

R-09 由 B 登记（账本 Open 表），但 `invalid_repair_finish` 的拒收发生在
修复轮收尾——`episode_protocol.py` / `agent_episode.py`，是你的缝。实现：

1. 修复轮 FINAL_JSON 被拒时，finish/stop 事件落盘**拒收原因码**
   （枚举，如 `missing_required_slot` / `malformed_json` / `empty_bindings`
   / `schema_mismatch`，按实际拒收分支定）+ 被拒 payload 的**结构摘要**
   （字段名与计数，**不落正文**——红线：不泄题、不落敏感文本）。
2. 无拒收时字段在场且为空/`none`，与 `caveat_slips=0` 同款契约风格。
3. 离线单测：每个拒收分支一个夹具 + 无拒收路径字段在场断言。
   B1/B7 的冻结 run 目录可作形状参照（零绑定 + `invalid_repair_finish`）。
4. **只实现不部署**。生产身份变更属用户裁决；B 的批 #2 要在
   `cb09f895` 不变身份上跑，你的改动本轮不上 8792。

## 4. 边界与缝

- 可改：`intelligence/services/episode_protocol.py`、
  `intelligence/runtime/agent_episode.py`、`scripts/dump_episode_receipts.py`、
  对应测试。
- 不可改：`intelligence/eval/`（acceptance/normalize 是 B 的缝）、
  verifier 判据本身（拒收语义不变，只加可观测性）。
- 独立 worktree + 独立分支（`fix/trka-r9-*` 或同前缀），不碰主 checkout。
- 账本：只动 R-21 行（收口）；R-09 保持 B 登记的行不动，你的实现在
  报告里引用它，验证预测的回填仍走 B 行（谁登记谁回填）。

## 5. 交付四样（不变）

报告（validate-report.sh RC:0）、账本 diff（只 R-21 行）、PR（gitea）、
轮次小结（≤10 行，追加母本「轮次记录」）。
