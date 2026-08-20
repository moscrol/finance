# fix/repair-carry-just-written-finish

## 这个分支做什么

`resume()` 的截止路径不再丢掉修复轮**刚写出**的合法 FINAL_JSON。
单笔 `a2f8ec30`，从 `gitea/main`(=`be7c1e7e`) 长出，未推未合。

## 当前状态

**离线全绿，live 臂未跑。** 5776 passed / 12 skipped；9 道 pre-commit 全过。
账本新开 `R-20260820-01`（`pending`）。

改动只有三处：新增 `_carry_repair_finish`（`agent_episode.py:2495`），接在
`resume()` 两条「模型刚返回、预算随即耗尽」的路径上（`:1533` / `:1647`）。
其余五条停机路径**故意不动**——那里的 turn 按定义不可能是合法 finish
（还没调模型 / 已报错 / 是工具轮 / finish 校验已失败）。

## 怎么来的

液冷同题 `run_20260820_032014_595378`（凌晨生产实测）：seq18 首轮合成
TimeoutError 空稿 → seq23 修复轮写出 1586 字合法 FINAL_JSON（draft 814、
四格 bindings 全绑）→ seq25 `carried_draft_chars=0`、公开答卷降级成
「现有证据不足」、判官走跳过路径盖 `null`。

根因是 `run()` / `resume()` 的对称洞：`_carry_just_written_finish`
（R-20260817-01 给 `run()` 加的）全仓只被调用一次；`resume()` 七条路径
一律结转 `previous.draft`，从不调它。设计假设「上一轮已经有稿」，首轮空稿
时假设破了。

## 下一步

1. **live 臂**：同形液冷重放。预期 last finish `carried_draft_chars>0`、
   公开 `gate_receipt` 不再四格全 `missing_required_output`、
   `judge_status != unavailable`（有稿才测得到独立判官，`correlated_judge`
   应为 `false`）。**单次 live 不得写 confirmed**。
2. 8792 当前钉 `be7c1e7e`，本分支未部署——要跑 live 得先切窗，那是另一个决定。

## 踩过的坑

- **夹具必须连 33 条证据一起冻。** `_carry_repair_finish` 先过
  `validate_episode_finish`；seq23 的 bindings 用 `E1…E32` 序数，缺证据集会
  `forged_hash` 被拒 → 照样结转空串，**测试会绿在错的分支上**。
  夹具在 `intelligence/eval/fixtures/repair-carry-seq23-*`。
- 变异已验：把 `_carry_repair_finish` 的偏好改回 `previous.draft` → 转红，
  失败读数正是生产那个数（`assert 0 == 814`）。
- `ruff format` **不是**本仓门禁（只有 `ruff-check`），`agent_episode.py`
  在 baseline 就不合 format，别顺手全文件重排。
- 账本住址漂了：主检出 `docs/prediction-ledger.md` 停在 08-15，
  `be7c1e7e` 这棵树是 08-17。本轮写的是后者（=`gitea/main`）。

## 红线

未调 T / `_REPAIR_SECONDS_CAP` / 档位（`R-20260816-07` 绊线）。
液冷这次 `judge_status=unavailable` 是跳过路径，**不是** Grok ACP 回归——
同窗长电 `correlated_judge=false` + `passed`。
