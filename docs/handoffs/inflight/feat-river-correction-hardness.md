# feat/river-correction-hardness

## 这个分支做什么

让时间长河能表达**认知的演变**，不只是某天快照。三步：补契约后半的载体（`hardness` /
`expired_at` / `superseded_by`），定「投影该吃点还是吃段」这份从未存在过的契约，再按
审阅意见把契约的模糊点在写代码之前收紧。基线 `gitea/main@1fef3d27`，四提交，未合 main。

## 决策与被否方案

完整对比表在 **spec §4.5「被否方案」** 与各 commit message 里，此处只留最咬人的两条：

| 决策 | 否了什么 | 为什么 |
|---|---|---|
| 区间投影**按变化选，不按天铺** | 每天全铺 / 固定间隔采样 / 让模型自己找变化 | 前两者丢掉「哪天变的」——区间唯一要答的东西；后者把确定性计算推给模型 |
| `expired_at` 只填**标注动作的当下时刻**（时钟 2），禁止回填 | 填「回头看它何时开始错」 | 回填会让已发生的 `slice(T,C)` 在回检跑过之后变内容，破 §7.9 回放幂等；旁边 verdict.valid_from 用到期日是时钟 1 的合法先例，最容易被抄错 |

## 当前状态

- `1ee6a881` 载体 + `slice` 第三条过滤 + `HARDNESS_RANK` 下沉
- `f8fc5e5b` spec §4.4 区间 / §4.5 投影 / §4.6 锚点 + 指针悬空门禁
- `459dac29` 审阅落地：§4.1 expired_at 时钟归属；§4.5 验收 (b) 改「两种去向必居其一」
  （投影内逐字节可取回 / 进 `omitted_refs`，不许静默消失）、验收 (d) 改**平坦尾巴不变量**
  （右端延长 k 天无新派生对象 → 块数与内容逐个不变）+「投影层不得自造派生对象」、
  `selected_by` 多重命中定为字典序 `+` 连接（类型仍 str）、修正链标注不进投影
  （哈希/正文双禁，新测试钉白名单）、六元组可复原要求；§4.4 `cumulative` 涉及涨幅必须走
  `river_query.range_aggregate` 正门；§4.6 补 lookback 验收；指针门禁 glob 化
  （写死名单当时就漏着 `river.py` §4.2 与 `river_window.py` §4.4 两个现存引用）
- **只加载体，不给 track 填 `hardness` 值**

## 下一步

1. **按 §4.5 实现区间投影**。原料齐：`river_derive` 的 `transition` / `first_event` 就是
   变化点与催化点，每条带 `member_refs[]` 可下钻。⚠ `window()` 默认**只挂 `cumulative`**，
   其余四类要显式派生。验收测试直接抄 §4.5 (a)–(d)：(b) 两种去向、(d) 平坦尾巴夹具。
   ⚠ `cumulative` 涉及涨幅/成交额时调 `range_aggregate`，不自算（§4.4 新增硬约束）。
   ⚠ 实现时顺带补证 checkpoints 登记的六元组可复原（§4.5 新增，现状只存 hash + framework_version）。
2. **接自动触发**（本分支之外最大的一块）：回检 miss → 标 `expired_at`、纠偏 → 写
   `superseded_by`。**动手前先按 §4.1 新条款写「标注后历史切片逐字节不变」的测试**——
   expired_at 填当下时刻不是 verdict 到期日，两种填法只有这条测试分得出来。
3. **给各 track 填 `hardness`**。⚠ `ProjectedBlock.hashed_dict()` 含 `hardness` 且进
   `projection_hash`——填值后投影哈希会变，不是 bug，但要预期并重绑基线。
   （`expired_at` / `superseded_by` 相反，**不进**哈希与正文，测试已钉住白名单。）
4. `river_anchor.lookback` 仍是 v0 占位。补它按 §4.6「骨架 / 特化」分工切，完成判据已
   写进 spec：tracer 时间轴段引用 anchor 输出 ref、SKILL.md 无自拼时间轴步骤。

## 未验证 / 已知边界

- **没有生产者填 `hardness`**，「硬度降序」今天仍全部平局。本轮只证明载体就位 + 消费者
  读得到（`hardness_of` 的 `obj.get("hardness")` 分支此前永远取不到值）。
- **回检 verdict 不会给河上对象标 `expired_at`**——`checkpoints.py` 判了 miss，河上那条旧
  判断仍算有效（grep expired_at/superseded/river 零命中，2026-09-15 复核仍成立）。
- `superseded_by` 只是指针不参与过滤；各 track 构造点与 `river_frozen` 回放路径未压到。
- 「记忆长河炼化」全景（2026-09-15 审阅查证）：载体 ✅ 本分支；§5.1 候选经验生命周期队列
  ✅ 已合 main（4b5b78d9）；judgment_maintenance（证据哈希变→需复核）⚠ 在未合分支
  `feat/research-evolution-06-workbench`；自动触发（上面第 2 条）❌；G-02 验收 (i) 五种旧
  状态字段→契约的映射测试 ❌。
- 已合入的六个 river 系分支（slice-v0 / window-contract / range-aggregate / recorded-at-ledger /
  pit-strict-gate / context-projection）与三棵干净 worktree 已清理（2026-09-15）。

## 踩过的坑

**变异测试前必须先提交。** 拆门用 `git checkout --` 还原，实现当时未提交，还原点是 HEAD
——连实现一起清掉了。两门于是跑在原版代码上，读数无意义且差点被当成「测试不承重」。
每门加 `grep -c` 自检替换数；本轮 M2 预期 1 实际 2（facts / collapsed 两类块各一个构造点，
同一形状），替换数偏离预期要能说出原因才算自检通过。

## 已验证

- `459dac29`：**全量 9630 passed / 0 failed / 77 skipped / 2 xfailed**（上轮 9629，+1 为新增
  白名单测试）；ruff 绿；pre-commit 11 道全过。
- 本轮两门变异各自见红、还原后树干净：M1 spec §4.2 改号 → 指针门禁红（红的正是 glob 新
  覆盖的 `river.py` 引用，证明扩圈真实承重）；M2 投影块 object_refs 泄入 `expired_at` →
  白名单测试红。
- 上轮（`1ee6a881`/`f8fc5e5b`）：全量 9629 passed；五门变异各自见红（`expired_at` 过滤 3/8、
  封顶 1/10、投影层常量副本 1/10、spec 改章节号、模块指针改错——后两门证明指针门禁双向承重）。
