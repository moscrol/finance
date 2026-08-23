# 设计：8792 与手调对照的质量分层（日程 / 盘面输入槽）

- 日期：2026-08-23
- 状态：Draft **v1.1**（P0 补 B1 包装层 + B2 语义写明 + B3 验收解释器；P1/P2 未做）
- 触发：knevo「周末发酵 / 下周大事」对照；8792 产品路径 `run_20260823_222835_095674`；复盘会 `/workspace/review` 日历盘点
- 代码树：`/Users/a77/fwp-wt-event-calendar-serving` @ `feat/event-calendar-serving`，底 `gitea/main`。禁止在主检出 `feat/reading-rules-baseline-batch1` 脏树上改
- 相邻（不重叠）：
  - `2026-08-20-episode-public-answer-quality-design.md`——投影修好后的**丢数路径**（截断看不见 / 资讯被 cutoff 滤空）。本单是**日程槽根本没接到表**
  - `2026-08-23-publication-and-contract-subtract-design.md`——同属「先减契约再加输入」，现场是周一 SPT 题，不是周历
  - `docs/handoffs/2026-08-13-fupanhui-public-assets-and-consume.md`——写过「稀疏表 event **故意不注册**」。本单**推翻这一条**，理由见 §4
- 实测：
  - 8792 run：`~/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260823_222835_095674/continuous-episode.json`
  - 库内 `fact_event_daily`（2026-08-23 读）：2531 行，未来侧已有「英伟达2026Q2财报」(08-26)、「杰克逊霍尔全球央行年会」(08-27)

## 0. 一句话

8792 和手调的差距不是文笔，是**四层输入槽**：范围契约收成 A 股新闻、事件表在库却不在工具面、检索词被范围污染、空日程仍 `complete`。本单先把已有 `fact_event_daily` 接进 `finance_query`，并允许「事件发生日晚于信息截止日」——否则问「下周大事」在周五 cutoff 下会整表被挡。

人话：菜在冰箱里（夜跑已经写入），菜单上没这道菜（dataset 没注册），服务员还按「本店只做 A 股家常菜」点单。先改菜单和点单规则，不要再写一本「周末周报 cookbook」。

**判别变量**（P0 离线必须锁死）：

| # | 冻结条件 | 必须成立 |
|---|---|---|
| 1 | `event_daily` | 在 `_DATASETS`，物理表 `fact_event_daily`，有非空 `coverage` |
| 2 | cutoff=08-21，`time_range`=08-24..08-28 | **不**报 `time range conflicts with information cutoff` |
| 3 | 同上，行里有 `updated_at<=08-21` 的未来事件 | 返回（英伟达 / Jackson Hole 形状） |
| 4 | 同上，行里 `updated_at=08-24` | **不**返回（信息时点，不是发生日） |
| 5 | `market_daily` 的 `time_range.end` > cutoff | 仍拒绝（不得把 #2 做成全局松绑） |
| 6 | 同上窗口，走 `build_episode_registry` + `registry.execute` | 不得 `future_of_cutoff`，不得把标题改写成「晚于问句日」；英伟达 / Jackson Hole 在观察正文里 |
| 7 | 全部 future 行共享一个 `updated_at` 日期 > cutoff | 0 行（生产 last-touch 形态，不是夹具里「同窗新旧混排」） |

P1/P2 的判别变量见 §6，本树不证。**P1/P2 开树前必须先有 #6**：`episode_answer_hygiene` 把 `future_of_cutoff` 算作 attempted，B1 不修会让 P2 建在假绿上。

---

## 1. 两个「日历」先拆开

`https://fupanhui.com/workspace/review` 工作台里至少有两套完全不同的东西。混用会把「再抓一遍」做成重复建设。

| 页面 | API | 是什么 | 仓库现状 | 本单 |
|---|---|---|---|---|
| `/workspace/review/calendar` | `/calendar/month` | **交易日盘面**月投影（涨跌家 / 量能 / 冰点） | 已由 `/reviews/market` → `fact_market_daily`；MCP / limit-advance 拿它找交易日 | **不新抓** |
| `/workspace/news/events` | `/news/events/future` 等 | **事件 / 催化日程** | `daily-full` → `sync-fupanhui-public-assets` → `fact_event_daily`（08-21 15:43 仍在写） | **P0 接到 `finance_query`** |

复盘页那本月历补不出 Jackson Hole。事件日历已经在库里，8792 那轮 0 次 `finance_query`，合同里也没有这张表。

---

## 2. 质量分层（8792 React 产品路径 vs 手调）

对照题：`周末发酵了什么新闻？下周（8月24日-8月28日）有什么大事？`

「React」= 工作台默认 hybrid + 空技能，走生产 8792 `continuous_episode`，**不是**另开一条前端渲染 bug。手调 = 同一题人工选组件（DuckDB 盘面 + 官方日程 + 已有事件表），用来标定槽位，不当作产品文风目标。

| 层 | 名字 | 8792 `run_20260823_222835_095674` | 手调 | 本单 |
|---|---|---|---|---|
| **L0** | 范围 / 题型契约 | `general_finance_qa`，置信度 0.4，`market_scope=A股`，timeframe=`8月` | 跨市场周历 + 盘面背景 | P1 |
| **L1** | 输入可达 | `finance_query` 授权但 0 次；`fact_event_daily` 未注册 | 查 `market_daily` / `sector_daily` + 事件表 | **P0** |
| **L2** | 检索卫生 | `web_search`「下周 **A股** 重要事件」→ 维基年历 / 世界杯；`news_search` 只拿到标题，无 fetch | 官方源点名（BEA / NVIDIA IR / KC Fed） | P1 减污染；确认级官方源是 P2 另源 |
| **L3** | 槽位诚实 | 自写 gaps（PCE 未核、行情停 8/21）仍 `answer_status=complete` | 空槽标明，不拿新闻标题当日历 | P2 |
| L4 | 成文 | 不锁 | 不锁 | **不做** |

拆三层看「差在哪」：

1. **盘面**：授权了 `finance_query`，没用。手调读到 08-21 缩量 / 双红（小金属、动力电池回收）。这是「授予的额度没传到最下游」的现场版——额度在合同里，执行者没点。
2. **日程**：库里已经有英伟达、Jackson Hole；模型去搜网页。根因是 L1 表不可达 + L0 把题收成 A 股新闻。
3. **确认级时点**：复盘会编辑日历日期粗（Jackson Hole 标 08-27 开幕，演讲 08-28 10:00 ET），且没有 PCE/GDP、贝森特、美团/理想/B 站。**不能假装 `fact_event_daily` 是全球官方日历。**

---

## 3. 已经成立 / 不要重做

| 已成立 | 不要再做 |
|---|---|
| `fact_event_daily` 写入链（`sync_events`，timeline + future） | 再爬 `/calendar/month` 或再写一条 events 同步 |
| `finance_query` 语义层 + `population` / `coverage` 目录（A5 之后） | 给事件表另做一套 SQL 工具 |
| 信息截止日挡**行情前视**（`trade_date <= cutoff`） | 全局放松 cutoff，让 `market_daily` 也能查未来交易日 |
| 08-20 公开稿质量单的截断可见 / 资讯滤空标注 | 把本单收成「再写一个 weekly-calendar skill」 |
| 产品 skill 七个（daily-review / news-impact 等） | 给 `news-impact` 加触发词「下周」——那条契约是「一条消息传导」，不是一周日程 |

---

## 4. 为什么推翻「稀疏表故意不注册」

08-13 消费层收口（#305）写过：auction / event / regulation / mapping **故意不注册**，收敛工具面。当时判据是「天然稀疏、不进覆盖率断档门，挂上去会稀释 enum」。

08-23 现场证明这条省错了对象：

- 稀疏 ≠ 没人问。周历 / 周末大事是高频题，不是拍卖冷表。
- 不注册的失败形状和 #300→#305 自己写过的一模一样：**入库 ≠ agent 能查到。**
- enum 已经用生成目录（`_dataset_catalog_text`）而不是手抄 15 个光秃名；再多一张有 `coverage` 的表，成本是一行目录，不是 2026-08-13 担心的「光秃 enum 再胀一号」。

auction / regulation / mapping **仍不注册**。只翻 event。

---

## 5. P0 设计：`event_daily` + 双时点

### 5.1 语义字段

| 语义名 | 物理列 | 角色 | 说明 |
|---|---|---|---|
| `event_date` | `event_date` | 时间维 / 维度 | **事件计划发生日**，可以是周末，可以晚于 cutoff |
| `event_id` | `event_id` | 维度 | 主键之一 |
| `title` | `title` | 维度 | 标题 |
| `content` | `content` | 维度 | 正文，可选；长文本可能触发行字节上限 |
| `event_type` | `event_type` | 维度 | 可空 |
| `sectors` | `sectors` | 维度 | 关联板块，复盘会口径 |
| `is_future` | `is_future` | 维度 bool | sync 写入时的未来标记 |
| `source` | `source` | 维度 | 同步来源 |
| `importance` | `importance` | 度量 max | 复盘会重要性，1–N，**不是**官方权重 |

`population=subset`。`coverage` 必须写清：复盘会**编辑**催化日历，不是 BEA / 公司 IR / 交易所官方日程；缺行是编辑没收，不是库坏了。

### 5.2 为什么默认 cutoff 会把这张表废掉

`_compile_query` 今天做两件对行情正确、对日历致命的事：

1. `time_range.end > cutoff` → 直接 `time range conflicts with information cutoff`
2. `WHERE event_date <= cutoff`

周日问「8/24–8/28」，cutoff 常是上一个 A 股交易日（08-21）。两刀都会把整周切掉。这不是模型懒，是**工具合同把「发生日」当成了「信息日」**。

行情的 `trade_date` = 信息日 = 发生日，三者重合。日历的 `event_date` 是发生日，信息日是「我们何时写入 / 何时知道」。

### 5.3 数据集旗标（只挂在 event_daily）

在 `_DatasetDefinition` 上加两个默认关闭的旗标，**禁止**改成全局行为：

| 旗标 | 默认 | `event_daily` | 作用 |
|---|---|---|---|
| `allow_future_time_range` | `False` | `True` | 允许 `time_range` 两端晚于 cutoff；且 **不要** 再施加 `time_field <= cutoff` |
| `cutoff_column` | `None` | `"updated_at"` | 信息截止打在写入时点。`CAST(updated_at AS DATE) <= cutoff`；`updated_at IS NULL` 放行（旧行） |

`time_range` 仍然约束 `event_date`（问哪一段日程）。

`cutoff_column` 存在时，`__source_date` **必须取它**（信息日），发生日只留在行内容（`event_date` / `title`）。`source_date` 全仓语义就是信息日：`research_tool_registry.fetch()` 对所有工具无条件跑 `filter_future_dated(..., date_getter=item.source_date)`。发生日若流进这个字段，SQL 层正确的未来事件会在包装层被整批改写成「晚于问句日」——v1 只测 `FinanceQuery.run`，看不见这一层。

`served_date` 跟着变成 `max(信息日)`，不再是最晚发生日。代价：会过 `_is_current_query_stale`。若事件同步比行情落后一天，整表可能被判 stale。被误伤时再给 `allow_future_time_range` 的表单独豁免 floor，**不要**改通用 `filter_future_dated`（那会波及 kb/news）。

**`updated_at` 的真实语义（v1 写乐观了）：**

writer 是 `ON CONFLICT ... DO UPDATE SET updated_at = excluded.updated_at`，`_now()` 为 **UTC** 墙钟，DuckDB 存 naive TIMESTAMP。只要事件还在 future 源里，每次 sync 都把该行刷成**最后一次看见**，不存在「同窗口新旧混排」。生产库 08-21 那批 future 行 `updated_at` 对齐 runlog 北京 23:45 ↔ 库内 15:43 UTC。

三个后果：

1. 判别变量 #4 的夹具（同窗一条早写入、一条晚写入）**不代表生产**。生产是全部 future 行共享一次 last-touch。
2. 静默清空：比 cutoff 更晚的北京日补跑 daily-full，未来行 `updated_at` 一起跳过 cutoff，整窗 0 行，长得像稀疏表本来没有。#7 锁这个形状。
3. PIT 只成立于向前：更早的 cutoff 会把当时已知、但后来被 last-touch 刷掉时间戳的事件藏掉（偏保守）。另外 UTC 比北京早 8 小时，北京 00:00–07:59 写入的行 `CAST(updated_at AS DATE)` 落回前一天，是亚日级反向渗漏。

本单不改 writer（不引入 `first_seen_at` / 不改打 `trade_date`）。后续若要真 PIT，另开单把 insert 时点冻住。

### 5.4 工具说明书

`coverage` 进 schema 目录（已有生成器，`test_dataset_catalog_covers_every_dataset` 会逼写）。`research_tool_registry` 的 `finance_query` 长说明加一句：周历 / 周末大事用 `event_daily`，且它**不是**官方日程全集。

不改 `produces`（`event_facts` 仍只挂在 `web_search` / `news_search`）。可满足性预检因此仍可能 fail-open——P1 再考虑给 `finance_query` 补 `event_facts`，本单不扩。

---

## 6. P1 / P2（本树不施工）

### P1 减契约 + 强制上桌

现场：`task_frame._market_scope` 认不出「美股 / 港股 / 全球」时**默认 A 股**；问句没有这些词、只有「周末 / 下周大事」，就会把检索词染成「A股 重要事件」。

要做：

1. 跨市场周历题不得继承默认 `market_scope=A股`。没有显式市场词时，范围应是未指定 / 跨市场，而不是 A 股。`assumptions` 里「按A股市场理解」不得再写进这类题。
2. 问句匹配「下周 / 本周 / 周末 + 大事/日历/催化/事件」时：`finance_query` 必须真正被调用——至少一次 `event_daily`，盘面背景至少一次 `market_daily`（或留下「查了、库无行」）。授权但 0 次，算 L1 失败，不能靠 prompt「请记得查」。
3. `news_search` / `web_search` 的查询串**禁止**被默认 A 股污染。范围未指定时不要塞「A股」。

不做：新 skill `weekly-calendar`；不把「下周」加进 `news-impact` 触发词。

### P2 空槽不能 `complete`

1. 日程槽（未来 N 日事件）若既没有 `event_daily` 行、也没有官方确认级抓取，公开状态不得是 `complete`。现有 gaps 自述不算填槽。
2. `news_search` 标题不得填日程槽。标题可以当「有一篇周历稿」的线索，必须 `web_fetch` 或官方源才能升格。
3. 官方确认级（BEA 发布日历、公司 IR、央行议程）是**另一张源**，不写进 `fact_event_daily` 冒充。缺就标明「复盘会日历未收 / 未核官方」。

顺序：先有 §0 #6（包装层不再把发生日标成越界），再开 P2。`episode_answer_hygiene` 把 `future_of_cutoff` 算 attempted；B1 不修，空日程槽会被当成「查过了」。

---

## 7. 明确不做

- 不新抓 `/workspace/review/calendar`
- 不重写 events 同步、不把 `fact_event_daily` 拉进 `check_daily` 断档门（稀疏是真的）
- 不加 knevo 式周末简报 skill / 长 SOP
- 不改文风、不改判官量表
- 不在本单接 BEA / NVIDIA IR
- 不注册 auction / regulation / mapping
- 不合 main、不切 8792，除非用户明示

---

## 8. 验收

### P0（本树）

干净树里没有 `.venv*`。用主检出解释器，宿主 `python3` 缺依赖会给出「看起来完全合理」的偏高失败数：

```text
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_finance_query.py \
  -k "event_daily or fupanhui_assets or catalog or cutoff"
```

加锁用例：

- `test_fupanhui_assets_registered_as_datasets` 含 `event_daily`
- `test_event_daily_allows_scheduled_dates_beyond_cutoff`（§0 表 #2/#3/#4；`served_date` / `source_date` 必须是信息日）
- `test_market_daily_still_rejects_time_range_past_cutoff`（#5）
- `test_event_daily_survives_registry_future_dated_filter`（#6，走 `build_episode_registry`）
- `test_event_daily_shared_last_touch_after_cutoff_returns_empty`（#7）
- 既有 `test_dataset_catalog_covers_every_dataset` 继续绿（逼 `coverage` 非空）

### P1 / P2

另开树。P1 用问句夹具锁 `_market_scope` + 检索词；P2 用 episode 夹具锁「空日程不得 complete」。禁止用 8792 live 当合并闸。

### 回归现场（合入后、切流前，人工）

同一题再走 8792：`finance_query` 至少 1 次 `event_daily`；公开稿出现英伟达或 Jackson Hole（或显式写「复盘会日历未收」）；不得再把维基 2026 / 世界杯当「下周大事」。

---

## 9. 选型（给实施者，避免重辩）

| 方案 | 优点 | 缺点 | 决定 |
|---|---|---|---|
| 只注册、不改 cutoff | 改动小 | 周日问下周必被拒 / 被滤空，等于没接 | 否 |
| `time_field=None`，发生日走 filters | 不碰 cutoff 校验 | schema 写着「日期只能放 time_range」，模型会撞墙 | 否 |
| 新工具 `calendar_query` | 语义干净 | 第二套查询引擎；合同还要再授一次权 | 否 |
| `allow_future_time_range` + `cutoff_column`（本单） | 行情 cutoff 不动；日历用信息时点 | 多两个旗标，要测试钉死「只挂这一张表」 | **是** |
| 新 skill 周末周报 | 看起来像 knevo | 输入槽仍空，还会编时点 | 否 |

原理：信息截止日防的是**用尚未发生的事实做当下判断**。已经发布的未来日程不是尚未发生的事实；尚未写入的行才是。

可迁移：任何「日程 / 到期 / 财报日历」表，只要发生日 ≠ 信息日，就不能复用行情表的 `as_of`。拆开之后还要把信息日送进全仓共用的 `source_date` 字段，否则下一层通用过滤器会按行情语义再挡一次。面试常问 PIT（point-in-time，时点还原）就是这个拆法；last-touch 墙钟 **不是** first-seen，复现不了「那天我们知道什么」。

---

## 10. 文件

| 文件 | P0 职责 |
|---|---|
| `intelligence/services/finance_query.py` | 旗标、dataset、`_compile_query` 双时点；`cutoff_column` 存在时 `__source_date` 取信息日 |
| `intelligence/tests/test_finance_query.py` | 注册 + 未来窗 + 行情仍拒绝 + 包装层整链 + last-touch 空窗 |
| `intelligence/services/research_tool_registry.py` | `finance_query` 说明加一句 event_daily |
| `intelligence/services/episode_tools.py` | ToolSpec.description 的 dataset 名单从注册表生成，含 `event_daily` |
| 本文件 | 分层与后续刀 |

P1 才会动 `intelligence/services/task_frame.py`（`_market_scope`）和检索词装配。不改 `filter_future_dated`，不改 events writer。
