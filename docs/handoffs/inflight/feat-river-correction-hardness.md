# feat/river-correction-hardness

## 这个分支做什么

让时间长河能表达**认知的演变**，不只是某天快照。四步：补契约后半的载体（`hardness` /
`expired_at` / `superseded_by`），定「投影该吃点还是吃段」这份从未存在过的契约，按审阅
把契约模糊点在写代码前收紧，再**按 §4.5 实现区间投影**。基线 `gitea/main@1fef3d27`，
六提交，未合 main。

## 决策与被否方案

完整对比表在 **spec §4.5「被否方案」** 与各 commit message 里，此处只留最咬人的三条：

| 决策 | 否了什么 | 为什么 |
|---|---|---|
| 区间投影**按变化选，不按天铺** | 每天全铺 / 固定间隔采样 / 让模型自己找变化 | 前两者丢掉「哪天变的」——区间唯一要答的东西；后者把确定性计算推给模型 |
| 事件日 = `transitions[].day` / `first_day`，**不是 `member_refs`** | 按 member_refs 命中日投影（§4.5 初稿原文） | member_refs 是证据链（参与计算的全部对象、覆盖区间每一天），按它选恰好退化成全铺——实现时对照 `river_derive` 才发现，spec 已改并写明 |
| `expired_at` 只填**标注动作的当下时刻**（时钟 2），禁止回填 | 填「回头看它何时开始错」 | 回填会让已发生的 `slice(T,C)` 在回检跑过之后变内容，破 §7.9 回放幂等 |

## 当前状态

- `1ee6a881` 载体 + `slice` 第三条过滤 + `HARDNESS_RANK` 下沉
- `f8fc5e5b` spec §4.4 区间 / §4.5 投影 / §4.6 锚点 + 指针悬空门禁
- `459dac29` 审阅落地：expired_at 时钟归属、验收 (b) 两种去向、(d) 平坦尾巴、selected_by
  拼接口径、修正链标注不进投影（白名单测试）、六元组可复原、cumulative 走 range_aggregate
  正门、lookback 验收、门禁 glob 化（写死名单当时就漏 `river.py`/`river_window.py`）
- `d6e4d19c` **区间投影 `project_window` 落地**（`river_projection.py`）：
  - 派生对象一等公民，`DERIVED_PRECEDENCE` 让位序排最前；事件日切片**复用单点 `project()`**，
    块原样仅换 `selected_by=derived:<rule>`（同日多规则字典序 `+` 连接）——逐字节一致是
    复用带来的结构保证，不是宣称
  - 预算先省切片后省派生；省下的 ref 进 `omitted_refs`；`gaps_applied` 非空必进 `limits`；
    日级 limits/gaps 带日期前缀并入；悬空事件日进 gaps 不静默；五类之外的 object_type 拒绝
  - `render_derived` 单列：派生 payload 插入序把 member_refs 排在 transitions 前面，
    复用 `render_object` 会让模型看到证据链看不到跃迁列表——渲染顺序也是投影决定
- **只加载体，不给 track 填 `hardness` 值**

## 下一步

1. **把 `project_window` 接进消费方**（带读 / ask_synthesis 里「这一段怎么走过来的」类问法）：
   调用链 `window()` → `derive_*`（⚠ `window()` 默认只挂 cumulative，transition / first_event /
   streak 要显式调 `river_derive` 再塞进 `RiverWindow.derived`）→ `project_window(win.to_dict())`。
   接线时顺带补证 checkpoints 六元组可复原（§4.5，现状只存 hash + framework_version）。
2. **接自动触发**：回检 miss → 标 `expired_at`、纠偏 → 写 `superseded_by`。**动手前先按
   §4.1 写「标注后历史切片逐字节不变」的测试**——expired_at 填当下时刻不是 verdict 到期日。
3. **给各 track 填 `hardness`**。⚠ 填值后 `projection_hash` 会变（hardness 在哈希白名单里，
   刻意），要预期并重绑基线；`expired_at`/`superseded_by` 相反不进哈希，测试已钉。
4. `river_anchor.lookback` 仍是 v0 占位。§4.6 分工与完成判据已写进 spec。

## 未验证 / 已知边界

- `project_window` 只被内存夹具测过，**没接过真库真 window()**——`derive_*` 产出的真实对象
  过一遍投影是接线时的第一件事（transitions 的 refs 字段、body 键序都来自 derive 真实现，
  夹具是按它抄的，但「按它抄」不是「跑过它」）。
- 事件日只认 transition / first_event；`streak.longest_end`、`cumulative.peak_date` 有语义
  但 v0 不投切片（统计量），要扩先改 §4.5 再改 `event_days_of`。
- **回检 verdict 不会给河上对象标 `expired_at`**（checkpoints.py 零命中，09-15 复核成立）。
- 「记忆长河炼化」全景（09-15 查证）：载体 ✅ 本分支；§5.1 队列 ✅ 已合 main（4b5b78d9）；
  judgment_maintenance ⚠ 未合分支 `feat/research-evolution-06-workbench`；自动触发 ❌；
  G-02 验收 (i) 五种旧状态字段映射测试 ❌。
- 已合入的六个 river 系分支与三棵干净 worktree 已清理（09-15）。

## 踩过的坑

- **变异测试前必须先提交**（还原点纪律；上轮实测被咬过）。每门 `grep -c` 自检替换数，
  偏离预期要能说出原因（上轮 M2 预期 1 实际 2 = 两类块构造点）。
- **契约写作时对着模块 docstring 拍字段名会拍错**：§4.5 初稿的「member_refs 命中」在
  river_derive 的真实形状下是全铺。提升 docstring 为 spec 条款时，引用的每个字段要回到
  产出该字段的代码看一眼语义，不能只看名字像不像。

## 已验证

- `d6e4d19c`：**全量 9639 passed / 0 failed / 77 skipped / 2 xfailed**（上轮 9630，+9 为
  §4.5 验收测试）；river 全家 65 passed；ruff 绿；pre-commit 11 道全过。
- 四门变异各自见红、替换数各 1、还原后 37 passed 树干净：M1 让位序失效 → 2 红；
  M2 gaps_applied 不进 limits → 1 红（验收 c 承重）；M3 省略不记 refs → 1 红（验收 b 承重）；
  M4 **退化成全铺 → 3 红**（验收 d 抓得住全铺回归，这正是它存在的意义）。
- `459dac29`：9630/0，两门变异见红（spec 改号 → glob 新覆盖的 river.py 引用悬空报红；
  投影块泄入 expired_at → 白名单红）。
- `1ee6a881`/`f8fc5e5b`：9629/0，五门变异见红，指针门禁双向承重。
