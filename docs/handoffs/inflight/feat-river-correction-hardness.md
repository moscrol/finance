# feat/river-correction-hardness

## 这个分支做什么

让时间长河能表达**认知的演变**，不只是某天快照。两步：补契约后半的载体（`hardness` /
`expired_at` / `superseded_by`），再定「投影该吃点还是吃段」这份从未存在过的契约。
基线 `gitea/main@1fef3d27`，三提交，未合 main。

## 决策与被否方案

完整对比表在 **spec §4.5「被否方案」** 与两条 commit message 里（含「两个 NULL 反向处置」
那条，`_enforce_cutoff` docstring 也写了），此处只留最咬人的一条：

| 决策 | 否了什么 | 为什么 |
|---|---|---|
| 区间投影**按变化选，不按天铺** | 每天全铺 / 固定间隔采样 / 让模型自己找变化 | 前两者丢掉「哪天变的」——区间唯一要答的东西；后者把确定性计算推给模型 |

## 当前状态

- `1ee6a881` 载体 + `slice` 第三条过滤 + `HARDNESS_RANK` 下沉
- `f8fc5e5b` spec §4.4 区间 / §4.5 投影 / §4.6 锚点 + 指针悬空门禁
- **只加载体，不给 track 填 `hardness` 值**

## 下一步

1. **按 §4.5 实现区间投影**。原料齐：`river_derive` 的 `transition` / `first_event` 就是
   变化点与催化点，每条带 `member_refs[]` 可下钻。⚠ `window()` 默认**只挂 `cumulative`**，
   其余四类要显式派生。验收 (d)「块数不随区间长度线性增长」可机器证伪。
2. **给各 track 填 `hardness`**。⚠ `ProjectedBlock.hashed_dict()` 含 `hardness` 且进
   `projection_hash`——填值后投影哈希会变，不是 bug，但要预期并重绑基线。
3. `river_anchor.lookback` 仍是 v0 占位。补它前先按 §4.6 的「骨架 / 特化」分工切，否则
   会有两套发酵链路且只有一套受 `knowledge_cutoff` 约束。

## 未验证 / 已知边界

- **没有生产者填 `hardness`**，「硬度降序」今天仍全部平局。本轮只证明载体就位 + 消费者
  读得到（`hardness_of` 的 `obj.get("hardness")` 分支此前永远取不到值）。
- **回检 verdict 不会给河上对象标 `expired_at`**——`checkpoints.py` 判了 miss，河上那条旧
  判断仍算有效。推翻的载体有了、触发没接上，这是本分支之外最大的一块。
- `superseded_by` 只是指针不参与过滤；各 track 构造点与 `river_frozen` 回放路径未压到。

## 踩过的坑

**变异测试前必须先提交。** 拆门用 `git checkout --` 还原，实现当时未提交，还原点是 HEAD
——连实现一起清掉了。两门于是跑在原版代码上，读数无意义且差点被当成「测试不承重」。
每门加 `grep -c` 自检替换数，为 0 说明这门没拆。

## 已验证

- **全量 9629 passed / 0 failed / 77 skipped**；`ruff check .` 全绿。收据
  `--expect-revision 1ee6a881` 七项全过。
- **五门变异各自见红、还原后树干净**：`expired_at` 过滤 3/8、封顶 1/10、投影层常量副本
  （值同对象不同）1/10、spec 改章节号、模块指针改错——后两门证明指针门禁**双向**承重。
