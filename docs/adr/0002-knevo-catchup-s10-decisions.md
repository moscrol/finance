# Knevo 追赶 §10：生产身份指向，不建第四本台账

2026-08-17 实测后拍板：生产记忆身份钉 `linxiaoqi5111`（恢复指向，不迁回、不拷进 `default`、不新建路径）；KC-09/10/11 扩现有 `judgments.jsonl` + `checkpoints.jsonl`/`verdicts.jsonl`，禁止再开 `judgments-ledger.jsonl`。港股本周期不做；多标的并行排到单标的答厚之后。批次按「无 #153 依赖的快胜仗先跑」，KC-07 从批 A 挪走。详见 `docs/learning/knevo-catchup-spec-2026-08-17.md` §10。

---

## 实测（2026-08-17 23:40，8792=`877e1f72`）

7 月诊断「`intelligence/users/linxiaoqi5111` 迁进 `.bak`、default 无台账」**已过时**：

- `.migrated-to-foresight.bak` 本机找不到。
- 真本在 `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`。
- `linxiaoqi5111`：corrections 61 / checkpoints 50 / verdicts 104；**两边都没有** `judgments.jsonl`。
- `default`：1 条 corrections（风远视角占位），无判断/可证伪点/裁决。
- launcher 设了 `FORESIGHT_USERS_DIR`，**不设** `FORESIGHT_USER`；`resolve_user_id(None)` → `default`。
- 交互 ask 有的已落到 `linxiaoqi5111`（如 `run_20260817_165919_410570`），CLI/评测/未带 user 的路径仍会掉进 `default`。
- `[M]` 校准行被 `if j_hit` 卡住：没有判断命中就不渲染 50/104 的回检胜率。
- 连续对话走 `memory_lookup` 工具，不是自动注入 `[M]` 块；身份没传到 `memory_user` 时工具不注册（`app.py` 已修穿透，但读的仍是 `RunStore.user_id`）。

C 方案已经在：`intelligence/services/checkpoints.py` + CLI `checkpoint register/due/recheck/score`。交易日历 `question_non_trading_note` 已注入 task frame 假设，缺的是短路检索。KC-12 已有选角设计稿，不是从零。

## 考虑过的替代

| 选项 | 为何不选 |
|---|---|
| 迁回仓库 `intelligence/users/` | `FORESIGHT_USERS_DIR` 才是跨机大脑；仓库内用户目录是残留。 |
| 把 61/50/104 拷进 `default` | 双脑分叉；`default` 还扛着 sptfei 视角沙箱。 |
| 新路径 / 新开 `judgments-ledger.jsonl` | 第四本台账，和 B/C 方案平行词表。 |
| 逐条 CLI accept | 本机 agent 跑不了 `-i`；已有 `checkpoint` 批处理。 |

## 后果

- 批 D 的前置是**身份指向 + 扩现有 B/C 台账**，不是「先重建一本空账」。
- Q5 既有优势：61 条纠偏在身份对上时就能进 `[M]`；判断台账仍空，要等 KC-09 往 `judgments.jsonl` 写，或先把校准从 `j_hit` 门上解下来。
- 改 launcher `FORESIGHT_USER` 是配置，不是代码 PR；未在本 ADR 里动 8792。
