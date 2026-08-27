# 在途交接 · docs/foresight-root-and-span-io

更新：2026-08-27 · **一处系统态修复已执行 + 一份工单已落；未开 PR、未合 main。**

## 一句话

2026-08-27 harness 六层审查（L6 缺口 + 「两个大脑」P0）经独立复核后的执行落地：
大脑根分叉已止血（系统态，`R-20260827-14`），L6 最小片收成可认领工单
（`R-20260827-13`），其余批次只留指针不并单。

## 已执行（系统态，不随分支走）

- `~/.zshenv` 的 `FORESIGHT_USERS_DIR` 由退役根改指新根（21:48）。
  机制、回滚（一行改回）、48h 判据全在台账 `R-20260827-14` 行内。
- 这是补完 08-16 的退役决定（`agent-memory/.foresight/RETIRED.md`），**不是新决策**；
  两个 launchd plist 本已显式钉新根，不受本次影响。

## 本分支内容（docs-only，基座 `gitea/main@61dd5f79`）

1. `docs/superpowers/specs/2026-08-27-tool-call-correlation-workorder.md`
   （`R-20260827-13` 预注册同提交）：`tool_result`/`tool_error` 事件补 `call_id`，
   单变量、零模型可见字节改动。⚠ 实施雷区已写死在工单 §2：那两个 payload dict
   同时是喂模型的底稿，`call_id` 只能进 `ledger.add` 展开。
2. `docs/prediction-ledger.md`：+`R-20260827-14`（已执行待 48h 回读）、
   +`R-20260827-13`（待认领）。
3. `AGENTS.md` 纠偏落点一行订正：旧文写死仓内 `intelligence/users/`，
   实际由 env 决定；写死的那个恰是冻结的第三根（12 条孤儿 corrections 实证）。

## 与 PRD 的分工

`docs/span-io-trace-prd.md`（Draft v2）管 `trace.jsonl` 面（input 接线 /
结构化 IO / `parent_span_id`），本工单只管 episode 事件面的 call 配对；
P1（PRD Phase 1）/ P2（revision 戳 + SQLite 投影）认领时另开批次另注册台账号。

## ⚠ 撞号预警（他分支，非本单）

`feat/tool-usage-differential`（未合，两份工单 docs）的台账行占了
`R-20260827-08/-09`；其后 main 上同号已被另一批工作占用（#465/#468 一线）。
该分支合并前**必须改号**（建议改 `-15/-16` 或 `-08a/-09a` 留双向指针，
先例见 `R-20260821-03a`），否则 crosswalk 重号门在合并时刻红。

> 撞号不是假想：本单自己的止血行原取 `-12`，写单到合并的一小时内就被
> #470 线（`0f6916cc` 吸收并发 main 时 `-11`→`-12` 改号）占用，已改 `-14`。
> 取号先看 `gitea/main` 台账 + 已知未合分支，取完尽快合。

## 下一步（等用户裁决）

1. 本分支开 PR / 合并——未做。
2. `-13` 派单：改动面两处展开 + 测试，可独立领。
3. 48h 后（≈08-29 晚）回读 `-12` 判据：退役根零新增、B 根持续增长。
4. 记忆根合并工单（A 独 12 corrections/21 answer_scores/14 卡 + C 独 12/2）——
   未立，等 `-12` 稳定后再立，落地前那些记录对 8792 消费者不可见。

## 坑

- 主检出全程未动（当时在他人分支且脏）；worktree `/Users/a77/fwp-wt-l6-spanio` 用后待删。
- 8792 已于 21:12 切 `3da2c712`（27f）；当晚六层审查的成立条件钉在 `41d9d8d2`，
  引用其结论时注意重锚（差异大概率 docs 为主，但按纪律须声明）。
- 台账号是跨分支全局资源：本单取号前实测 gitea/main 已用到 `-11`，
  另一未合分支占 `-08/-09`（见上）；后续取号先 `git show gitea/main:docs/prediction-ledger.md | rg -o 'R-20260827-\d+'` 再定。
