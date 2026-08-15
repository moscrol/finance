# Round 4 · 轨道 A：R-21 收口 + 条件靶了结 + 哈希誊抄契约修复

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

## 3. 任务 3：修哈希誊抄契约（根因已定，你的缝）

**背景变更**：检阅方已在冻结 run 目录把 B1/B7 定到根因——读母本批注
「检阅方勘探 · Round 3 之后」段（四个标本：换位/插入/删除/拼接）。
修复轮模型引用**真实证据**但逐字誊抄 16-hex `content_hash` 出错，
fail-closed 正确拒收 → 零绑定 → eb=0。原 R-09「加原因码以判别 L0」的
判别目的已达成（`invalid_action` 事件本就带 reason），任务改为修根因：

1. **终局契约改证据序号引用**：提示中的证据表编号 E1..En（episode 内
   稳定、与呈现顺序一致），FINAL_JSON 绑定用序号，
   `validate_episode_finish` 解析序号 → `content_hash`。低熵 token，
   誊抄错误率崩塌。若你评估后选「唯一前缀 ≥12 hex 解析」替代方案，
   写明理由，二选一不并行。
2. **保持 fail-closed**：解析失败、越界、歧义引用仍拒收。B1 的拼接标本
   同时近配两条真哈希——歧义必须拒，**不做模糊自动纠正**。
3. **R-09 缩水版顺手做**：把 `invalid_action.reason` 提升进 finish
   payload（`caveat_slips` 同款风格：无拒收时字段在场为空），验收台
   不再需要扫事件流。B 登记的 R-09 行由 B 按此回填口径。
4. 单测：四个标本进夹具（换位/插入/删除/拼接各一）+ 正常序号路径 +
   越界/歧义拒收路径。B1/B7 冻结 run 目录作形状参照。
5. 账本登记新预测（你的命名空间）：fix 部署后，同形 case（主路径
   deadline 耗尽、修复轮携证据收尾）绑定应成功、eb>0；unknown-hash
   拒收在下一批**再现即 refuted**。
6. **只实现不部署**。生产身份变更属用户裁决；B 的批 #2 要在
   `cb09f895` 不变身份上跑，你的改动本轮不上 8792。
7. 数据层第一环（B1 数据源不可用、B7 新鲜度缺口）**不归本缝**，
   不要顺手修——已在母本批注中另行立项待用户排期。

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
