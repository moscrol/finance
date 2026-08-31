# 2026-08-31 Wiki 三铲「预算够」对照工单

> 可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
> 前置：INDEX #19 / `R-20260830-06` 已在现网 90s 下交卷「无资格」。本单**不可并行改同一旋钮文件时抢提交**；各开各的分支。
> 台账：`R-20260831-01`（`EVAL_ONLY`，分支 `eval/wiki-aperture-budget`）。

## 背景与动机

#19 两轮（stale 索引 → 结构版 `fresh`）都停在 L0：可用题 <4。轮 2 收据
`intelligence/eval/runs/20260830T171032Z-wiki-aperture-ablation.json`：0 条 stale
告警，4/6 题 A2 仍是 `remaining budget below observed query cost`。墙钟 p50
A0 19.3s / A1 88.0s / A2 100.3s。现网 90s 装不下三铲，不能谈「三铲好不好」。

#19 的档 3 是「预算够时三铲值得保留」。要回答它，必须另开一张单：变量仍是三铲，
**墙钟改成评测专用加长**，生产 `MAX_TOTAL_SECONDS=90` 常数不改。否定结论也算交卷。

## 目标

1. 评测旋钮 `ASK_WIKI_TOTAL_SECONDS`：未设 = 90 = 现网；正数覆盖闭环顶盖；非法值 fail-closed。
2. 生产默认路径：未设该 env 时，`retrieve_closed_loop` / `collect_wiki_rag` 行为与改前一致。
3. 同一 6 题、同一 `as_of`（最新导出，禁 2026-07-22）、闸 `ASK_EVIDENCE_JUDGE=off`、结构版 `fresh` 索引，用 `--wiki-seconds 240` 复跑 #19 脚本。
4. 评测侧每次 `retrieve` 传**剩余**墙钟（对齐生产 `collect_wiki_rag`），禁止每次都传满额 240。
5. L0 可用 ≥4 才写 L1 三张表、才跑 L2。L2 走真 `ask` 时必须带 `--wiki-rag-timeout 240` + 同 env，否则答案臂仍是 90s、对照无效。
6. 结论仍落预注册四档之一。可用 <4 → 仍写「无资格」，禁语「三铲无用」。

## 非目标（写死认领）

- ❌ 不改 `MAX_TOTAL_SECONDS = 90.0` 字面量，不切 8792，不合 `main`。
- ❌ 不把本单改成「顺便加速 hybrid / 打开 rerank / 默认改 agentic」。加速是另一张单。
- ❌ 不重评语义闸（继续钉 `off`）。
- ❌ 不把 90s 那两轮重写成「三铲没帮助」。
- ❌ 无 LLM key 不得用模板答案冒充 L2；可只交 L0+L1。
- ❌ 不把加长预算上成生产默认——那是本单读数出来之后的产品决策，不是本单交付。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `intelligence/services/closed_loop_retrieval.py` | `wiki_total_seconds_cap`、`retrieve_closed_loop` 与 cap 取 min |
| `intelligence/services/evidence_providers.py` `collect_wiki_rag` | 生产 W 入口也读 cap，否则 L2 `ask` 仍 90s |
| `scripts/run_wiki_aperture_ablation.py` | 同一题集；remaining timeout；L2 `--wiki-rag-timeout` |
| `intelligence/eval/runs/20260830T171032Z-wiki-aperture-ablation.json` | 轮 2 基线：哪些题卡在 90s |
| `docs/superpowers/specs/2026-08-30-wiki-aperture-ablation-workorder.md` | L0/L1/L2 门与四档原文，复用勿重造 |

## 预注册

- 臂、题、闸、as_of、L0/L1/L2 门与 #19 相同，只把墙钟从 90 改成 **240**（轮 2 最慢完整两铲约 104s，第三铲再留余量；科创 50 第一铲曾 timeout 155s）。
- 上线门（仅当 L0≥4 且 L2 跑完）：与 #19 同一公式。A2 相对 A0 低 ≥1.0/20 且挤窗 → 档 2；反向高 ≥1.0 且不挤窗 → 档 3；中间 → 档 4。6 题里 A2 低于 A0 超过 2 题 → 否决「全面更好」。
- 240s 仍 <4 可用 → 档 1，并写明「加长到 240 仍装不下」。

## 步骤

1. 开工三连。从 #19 树开 `eval/wiki-aperture-budget`（已含 `ASK_WIKI_APERTURES`）。
2. `python3 scripts/claim_ledger_id.py claim --branch eval/wiki-aperture-budget`，写入本单头部与台账。
3. 落地 `wiki_total_seconds_cap` + 单测（未设=90、240、非法 fail-closed）。
4. 评测脚本：`--wiki-seconds 240`、remaining timeout、L2 同步 timeout。
5. 确认结构版 `.rag_index` 仍 `fresh` 后再跑；stale 则先 `rag update`（不要 `--include-raw`）。
6. 先 L0。可用 <4 停。过了再 L1、L2。收据 `intelligence/eval/runs/<utc>-wiki-aperture-ablation.json`。
7. 报告 `docs/verification/2026-08-31-wiki-aperture-budget.md`。回写 INDEX #20 与台账。推分支，不合 main。

## 验收

- [x] 未设 `ASK_WIKI_TOTAL_SECONDS` 时既有 closed-loop 单测仍绿，cap=90。
- [x] `ASK_WIKI_TOTAL_SECONDS=240` 时 cap=240；非法值 ValueError。
- [x] L0 激活率写入 JSON；本轮 6/6；无「三铲无用」。
- [x] L1 仅在可用 ≥4 时报增量 / 反方出现率 / 挤窗。
- [x] L2 仅 `usable=true`；`ask` 带加长 wiki timeout；公式不反号。
- [ ] 台账号已登记；分支已推；不合 main；pathspec 提交。（本提交完成后勾）

## 红线

- 禁 `git add -A`；不合 `main`；不强推。
- 解释器：`finance-workspace-private/.venv-workbench/bin/python`。
- 台账禁手工取号。
- 默认 90s 路径不得为评测加日志噪音。
- 不提交 `.env` / duckdb / 密钥；不打印 key。
