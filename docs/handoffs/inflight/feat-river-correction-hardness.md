# feat/river-correction-hardness

## 这个分支做什么

让时间长河能表达**认知的演变**，不只是某天快照。五步：补契约后半的载体（`hardness` /
`expired_at` / `superseded_by`），定「投影该吃点还是吃段」这份从未存在过的契约，按审阅
把契约模糊点在写代码前收紧，**按 §4.5 实现区间投影**，再落取数正门 + 六元组载体并用
真库真链路冒烟。基线 `gitea/main@1fef3d27`，八提交，未合 main。

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
- `1131bc0b` **正门 `river_range_projection.project_range` + 六元组载体，真链路已冒烟**：
  - 真库只读冒烟（2026-08-25→09-12 AIGC概念）：transition 抓到两次真实跃迁（09-01 下跌→
    底部横盘、09-03 底部横盘→下跌），selected_days 恰为这两天，**19 块 vs 全铺 ~112 块**，
    幂等成立。复现：`MARKET_FEATURE_STORE_DB=<主树>/db/market_feature_store.duckdb`，
    `project_range('2026-08-25','2026-09-12','AIGC概念',task='smoke')`
  - 正门封装「window() 默认只挂 cumulative」这条知识；标准派生集确定性固定
    （transition:market_stage + streak:dual_red_strict + streak:volume_surge）；
    first_event / signature 无无争议默认，走 `extra_derived` 显式加
  - `register_checkpoint(projection_inputs=...)`：§4.5 六元组载体（形状 =
    `projection_inputs_of(cp)`），有 inputs 无 hash 拒收；校准不读它
  - ⚠ 实体是**板块粒度**（`resolve_entity` 查 `fact_sector_daily` 精确匹配），「全市场」
    不是合法实体、六轨 entity_unresolved——问「大盘这段怎么走」要先定实体口径
- **只加载体，不给 track 填 `hardness` 值**

## 分支已就绪待验收（09-15，四叶等价 CI 全绿）

- python：ruff 绿 + 全量 **9645 passed / 0 failed / 77 skipped / 2 xfailed**（末提交为 docs-only，
  契约门禁在 spec 改后复跑 40 passed）
- frontend：`pnpm lint / typecheck / test(76 passed) / build` 全绿（worktree 内 fresh install）
- e2e：`pnpm test:e2e` **15 passed**（`WORKBENCH_PYTHON` 指 workbench venv）
- registry-check：`build_registry.py check` 注册表与源一致
- **未 push 未开 PR**（推送需用户确认）；分支 9 提交，基线 `gitea/main@1fef3d27`

## 下一步

1. **触发刀（判断轨修正链）——语义已钉进 spec §4.1「判断轨的修正链语义」，照它做**：
   真实形状 = judgment provider v1（判断活跃期逐日可见 `valid_to=due` + verdict 对象进河）
   + corrections 补 checkpoint 关联载体 + 纠偏时旧判断标 `expired_at`（当下时刻）/
   `superseded_by`。**不是给 miss 标 expired_at**——被证伪的判断必须留在历史切片里，
   「已证伪」由 verdict 对象承担；miss 的失效触发在证据边已存在（`checkpoint_writeback`）。
   ⚠ provider v1 会改变含 judgment 轨的切片内容与投影哈希——是语义升级不是回归，预期它。
2. **把 `project_range` 接进消费方**（带读 / ask_synthesis「这一段怎么走过来的」类问法）：
   正门已备好，剩 seam 选择（归消费方）、登记时传 `projection_inputs_of(cp)`、
   「全市场」类问法的实体口径（实体是板块粒度）。
3. **给各 track 填 `hardness`**。⚠ 填值后 `projection_hash` 会变（hardness 在哈希白名单里，
   刻意），要预期并重绑基线；`expired_at`/`superseded_by` 相反不进哈希，测试已钉。
4. `river_anchor.lookback` 仍是 v0 占位。§4.6 分工与完成判据已写进 spec。

## 未验证 / 已知边界

- 事件日只认 transition / first_event；`streak.longest_end`、`cumulative.peak_date` 有语义
  但 v0 不投切片（统计量），要扩先改 §4.5 再改 `event_days_of`。
- 正门标准集只覆盖 market 轨标签；题材/舆论轨的 transition（如 `opinion_stage`）等 G-06
  词表落地后再进标准集，别提前拍。
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

- `1131bc0b`：**全量 9645 passed / 0 failed / 77 skipped / 2 xfailed**（上轮 9639，+6）；
  真库真链路冒烟通过（读数见「当前状态」）；四门变异各红还原干净：标准集丢 transition、
  载体不落盘、有 inputs 无 hash 拒收门失效、六元组丢 label_version。
- `d6e4d19c`：9639/0（+9 为 §4.5 验收测试）；river 全家 65 passed。四门变异各红：让位序
  失效 → 2 红；gaps_applied 不进 limits → 1 红；省略不记 refs → 1 红；**退化成全铺 → 3 红**
  （验收 d 抓得住全铺回归，这正是它存在的意义）。
- `459dac29`：9630/0，两门变异见红（spec 改号 → glob 新覆盖的 river.py 引用悬空报红；
  投影块泄入 expired_at → 白名单红）。
- `1ee6a881`/`f8fc5e5b`：9629/0，五门变异见红，指针门禁双向承重。
