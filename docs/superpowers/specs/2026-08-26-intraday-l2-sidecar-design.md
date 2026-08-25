# 设计：盘中可用性探针 + 关注池边车（摸底剩余三步）

- 日期：2026-08-26
- 状态：Draft **v1.1**（门 A = **A1**���门 B = **B1**，用户 2026-08-26 拍板，P1/P2 解锁，仍以 P0 收据为前置；P0 前置=鉴权恢复，见 §5.1 前置与 §8.1。08-26 夜校正，探针脚本已落地）
- 来源：2026-08-25 Claude 摸底（对话 `715ff429-cce6-4c56-ba67-ce00a54dd53d`）的后三步。第一步已在 PR **#396** 做完，本稿不再登记表。
- 核稿：同日对摸底的复核（同对话后半）——外部事实（Knevo / fupanhui / ClickHouse / push2delay）站得住；「6 张表 0 引用、可答面翻倍」那截已推翻，见 §3。
- 代码树：从 `gitea/main` 开干净树 `docs/intraday-l2-sidecar`（本稿所在）。实施 P1/P2 另开 `feat/intraday-l2-sidecar`，仍从当时的 `gitea/main` 拉，不叠 #396 的脏区。
- **禁止**在主检出 `feat/reading-rules-baseline-batch1` 脏树上改 runtime。
- **禁止**在 `/Users/a77/fwp-wt-technical-daily`（#396）上做本稿。那棵树只登记库存表。
- **禁止**动 8792 / 8796 / 8802。
- 相邻稿（本单不重做、不抢合）：
  - `2026-08-24-market-watch-component-first-design.md`——**盘后**四袋换座位，不是盘中监控。题型 `market_watch` ≠ 本稿的盯盘边车。
  - `2026-08-24-personalized-join-kernel-design.md`——明确把「盘中推送监控」划出范围。
  - PR #396 / `docs/handoffs/inflight/feat-finance-query-technical-daily.md`——库存暴露 + 棘轮门禁，已收口（合 main 仍等用户）。
  - `scripts/moneyflow/README.md` + `.claude/skills/l2-moneyflow/SKILL.md`——现役 L2 **刻意只盘后**。
  - `intelligence/services/market_moneyflow.py`——D9 证据块，被动塞上下文，不是工具。

## 0. 一句话

库存表 agent 够不着，#396 已经在补。剩下的上限不在再注册一张表，而在：**还不知道 ClickHouse 盘中写不写，以及研究回答要不要看见盘中结构变化。** 本稿只收这三步：证伪盘中写入 →（你拍两扇门之后）最小边车 → 再谈 L2 工具。

**判别变量**（整份稿只锁这一条）：下一个交易日 10:00–14:30 必须留下一份可复验收据，写明深/沪两张逐笔表的 `max(成交时间)` 相对墙钟的滞后。没有这份收据，禁止开边车，禁止给 agent 加 L2 工具。不是「多接一个行情源」，不是「把 D9 改成 finance_query dataset」，也不是「四袋盘后包再跑一遍」。

人话：仓库已经能看见昨天的货。现在要先问清冷库白天进不进货；进了，再决定是给研究台换新鲜样品，还是装铃铛。没问清之前，不准先砌传送带。

### 0.1 和邻单的边界（实施前先认，认错就停）

| 邻单 / 现状 | 它管什么 | 本稿管什么 |
|---|---|---|
| #396 `finance_query` 登记 | 已入库日频表进语义层 | **不再登记。** `feature_l2_*` 继续走 D9 `dedicated_path` |
| market-watch 四袋 | 「今天市场怎么样」盘后确定性查询 | 对话轮次之外的常驻采集 |
| D9 `market_moneyflow` | 用户问到资金流词面时，读**盘后**特征表 | 要不要有一份**盘中**本地快照可读 |
| l2-moneyflow skill | 人在盘后跑扫描、写日频特征 | 禁止把 skill 挂进 agent 工具表来「顺便实时」 |
| 飞书 bot launchd | 长连接常驻的**部署骨架** | 边车抄 plist 形状，**不**塞进 bot 进程 |

### 0.2 摸底原话怎么拆（校正后）

Claude 原排期四步，只有第一步属于 #396：

1. ~~本周：6 张表进 `_DATASETS` + 棘轮门禁~~ → **已做**（校正：空表 `fact_top_gainers` 不注册；多登记了 `fact_regulation_event_daily`）。
2. 跑 SQL，确认 L2 盘中写不写 → **本稿 P0**。
3. 定 3–5 个盯盘事件，0 档 + 关注池做最小边车 → **本稿 P1**，被门 A 挡住。
4. L2 升成 agent 可主动调用的工具 → **本稿 P2**，被门 B 挡住。

原报告里「可答问题面翻倍」「6 张表 intelligence/ 0 引用」已核实为夸大或失实，**不要当本稿的收益预期**。净增量是个位数 dataset，而且那是 #396 的账。

## 1. 范围

### 1.1 做

- **P0（无产品决策）**：下一个交易日盘中，用现役 `scripts/moneyflow` 客户端（不是新连法）对深/沪两张逐笔表做一次只读探针，写下收据。
- 把「实时」拆成四层（L1 快照 / L1 推送 / L2 逐笔 / 交易接口），后续只在 0 档 L1 与已付费 L2 之间选；不上 3/4 档。
- 边车架构写死：**采集进程外呼 → 本地缓冲 → agent 只读本地。** agent 每轮不直连行情、不直连 ClickHouse。
- 关注池宇宙 = 用户画像 `watchlist`（真身 `~/.local/share/finance-workbench/users/linxiaoqi5111/`），上限 300。名单空则 fail closed，不准回退成全 A 轮询。
- 0 档行情只走东财 `push2`（实时 host），**另起**采集入口；不准改 `sync_eastmoney_stock_snapshot.py` 的默认 `push2delay`（那是盘后 daily-full 的设计）。
- 从 fupanhui 继续只拿加工品（板块边际量、主线、连板），每天一次就够。禁止把 fupanhui 当 3 秒级原始行情。

### 1.2 不做

- 不在本稿再往 `_DATASETS` 加表，不把 `feature_l2_*` 改注册进 `finance_query`（会和 D9 双口径）。
- 不把 `l2-moneyflow` / `top-gainers` / `ifind` / 其它拉实时或写回的 skill 挂进 `research_tool_registry`。
- 不把边车写进 `fact_stock_daily` / `feature_l2_*_daily`。日频事实表被盘中快照污染之后，复盘和 PIT 会对不上。
- 不把边车塞进飞书 bot 同一个进程。只复用 launchd 的 `KeepAlive` 骨架，另起 Label。
- 不做全市场 tick、不做 Redis、不上券商 miniQMT / Wind 实时。
- 不改 8792/8796 生产配置，不在脏树改 runtime。
- 不把「现价多少」写成 P1 验收。研究型 agent 上，现价边际价值低；P1 锁的是**结构变化事件**或**更新鲜的本地快照**，由门 A 二选一。
- 不在 P0 没跑完时实现 P1/P2。盘后跑那条 SQL **没有判别力**（批量入库同样会留下 14:5x 时间戳）。

## 2. 术语

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **盘中写入** | ClickHouse 在 9:30–15:00 持续追加当日逐笔，`max(成交时间)` 跟着墙钟走 | 盘后批量把当天 tick 一次性灌进库（时间戳仍是 14:5x） |
| **边车** | 不依赖对话轮次的常驻采集进程，只写本地缓冲 | agent 工具里 `for` 循环拉行情；飞书 bot 本身 |
| **关注池** | 用户画像里已钉住的个股名单，硬顶 300 | 东财全 A clist；fupanhui `watchlist/limit-distribution`（那是涨停分布接口，不是你的自选） |
| **0 档** | 东财 `push2` 快照轮询，只打关注池 | 把 daily-full 的 `push2delay` 改成实时 host |
| **D9** | 问到资金流词面时，只读盘后 `feature_l2_*` 的证据块 | 一个 agent 可点的 `l2_flow_lookup` 工具 |
| **门 A** | 实时目的：盘中提醒 vs 研究回答更新鲜 | 「先把管道铺上再看谁用」 |
| **门 B** | 对话回合可不可以触发外呼（CH / push2） | 「只读」——本地 DuckDB 只读和「回合里打外网」不是同一条红线 |
| **四袋 / market_watch** | 盘后组件包，回答「今天市场怎么样」 | 本稿的盯盘事件 |

## 3. 已核实事实（实施时不要再探一遍）

写稿日 2026-08-26 对代码与 08-25 复核的交叉验证。数字会漂，形状不要重发现。

1. **#396 已做完摸底第一步（校正后）。** 活树 `/Users/a77/fwp-wt-technical-daily` @ `6b6d9f36`，Gitea #396。登记的是有数据的日频表 + 棘轮门禁；`fact_top_gainers` / `fact_high_volume_gainers` 是 0 行空 schema，故意不注册。合 main 未授权，从未 live。本稿不碰它。
2. **`_DATASETS` 不是 agent 的全部读口。** 另有 `MarketAdapter`（`tool_search_market_live`）、`market_data` → ask_blocks、以及 D9 等证据块。拿「dataset 数 / schema 表数」当可答面会夸大。
3. **L2 现役链路是盘后、被动、本地。** `l2-moneyflow` SKILL / `scripts/moneyflow/README.md` 原文「仅盘后运行」「禁止盘中大批量查询」。扫描写 `feature_l2_capital_flow_daily` / `feature_l2_quant_orders_daily`；`scan_limitup.py` 的名单查询带 `TradeTime >= 14:50`，消费者按收盘截面写的。D9 命中词面才注入，覆盖口径写在代码里：榜单只扫涨停股 + 成交额 top100，**缺行 ≠ 无资金流入**。
4. **ClickHouse 底料在，连接件也在。** 深 `share.trans`（`TradeTime` / `ExecType='1'`），沪 `share.ngts_tick`（`TickTime` / `TickType='T'`），库 `db.base32.cn`，原生协议端口 9000，`clickhouse_driver`。凭证只走 `CH_HOST` / `CH_PORT` / `CH_USER` / `CH_PASSWORD`，禁止写进稿或 commit。`make_client()` 已处理 Fake-IP（Shadowrocket 198.18.0.0/15）和 `CH_HOST_FALLBACK`。P0 **必须**走这套客户端，禁止另写一份连法。
   **（2026-08-26 01:5x 校正）连接件在，但鉴权自 08-08 起已失效**：生产 `feature_l2_*` 停更于 08-07；08-18 用户指示挂账（`state/l2-paused.flag`，`reason=l2-datasource-auth-pending`，见 `docs/handoffs/2026-08-18-daily-full-review-recovery.md`）；当晚探针 `--check-only` 实测 Code 516 Authentication failed（`hisdata180@36.139.233.80`，凭证文件还是 07-07 的）。08-25 摸底与本稿初版都没交叉引用那份挂账交接——「底料在」不等于「现在够得着」。
5. **「盘中写不写」仍是未知。** README 的「盘后运行」约束的是**我们的扫描**，不是上游是否在交易时段追加 tick。这条只能盘中证伪。写稿时是 2026-08-26 凌晨，当时跑 SQL 没有判别力。
6. **0 档东财已经在用，但是盘后 host。** `sync_eastmoney_stock_snapshot.py`：默认 `push2delay`，失败回退 `push2`；注释写明部分 IP 对实时 host SSL 超时/限流。字段目前是 `f12,f13,f14,f2,f3,f18,f6,f8`——**没有涨停价**。开板/炸板事件要另加字段（常见 `f16`/`f17`），只许出现在边车自己的请求里，不准改 daily-full 那份字段表。
7. **agent 工具表 12 个，没有 L2 工具。** 权威清单在 `intelligence/services/research_tool_registry.py` 的 `_DEFAULT_TOOL_METADATA`。`web_search` / `news_search` 已经在表里，所以红线不是「agent 永远不碰网络」；CLAUDE.md 那句「只读 + 无外呼」管的是：**不要把会拉 fupanhui / iFinD / AKShare / 写飞书 DuckDB 的 skill 挂进 agent。** ClickHouse 属于「对话回合触发的行情外呼」，和这条同族，不和网页检索自动等同。
8. **常驻进程只有飞书 bot 这条 launchd 骨架**（`intelligence/chat/com.financeworkspace.feishu-bot.plist`，`KeepAlive`）。它不是采集器。
9. **关注池已有真身，不是 300 只空名单。** 画像模板字段是 `watchlist`；生产画像在 `~/.local/share/finance-workbench/users/linxiaoqi5111/`，**不是**仓内 `intelligence/users/`。fupanhui 路径里的 `watchlist/limit-distribution` 是涨停分布 API，禁止拿来当自选宇宙。
10. **Knevo 卡在 L1 快照、每轮一次。** 这是对话 agent 的调用形状，不是他们偷懒。要突破「快照不是监控」，必须有不依赖回合的采集进程——或接受「只在提问那一刻更鲜」这条更小的路（门 A）。

## 4. 两扇决策门（P1/P2 的阻断条件）

Claude 写明不替你定。本稿也不假装已经拍板。**P0 可以先跑。P1/P2 在两行都填上之前禁止写代码。**

**（2026-08-26 已拍：门 A = A1，门 B = B1。P1 按 A1 形态做（本地快照 + 读口，无推送）；P2 按 B1 形态做（工具读本地，不连 CH）。仍以 P0 收据为前置——收据不是 live 则 P1 只有 0 档 L1，E4 删除。）**

你要改默认，改表里「本稿推荐」那一列即可；实施 agent 只认填好的值，不认本节的推荐理由。

### 4.1 门 A —— 实时是为了什么

| 选项 | 工程形状 | 量级 |
|---|---|---|
| **A1 研究回答更新鲜**（本稿推荐） | 边车按分钟写本地快照；用户提问时证据块读最新一行。无推送、无事件铃 | 小：一个进程 + 一个读口 |
| **A2 盘中提醒** | A1 的采集 + 事件定义 + 去重 + 飞书/本地推送 + 值班失败处理 | 大约大一个数量级 |

推荐 A1 的理由：Knevo 自己也认「分析引擎不是行情终端」；「现价多少」对研究问答边际低；A2 可以在 A1 的缓冲上后装，反过来不行。

**未填时的行为：** 只许做 P0。不准「先把轮询写了，推送以后再说」——那会在没人看的管道上烧 0 档限额。

### 4.2 门 B —— 对话回合能不能触发外呼

| 选项 | 含义 | 红线怎么改 |
|---|---|---|
| **B1 外呼只留在边车**（本稿推荐） | agent 工具 / 证据块只读本地缓冲或盘后 `feature_l2_*`。回合内不连 CH、不打 push2 | 红线原句不用改。和 D9、和「圈小而稳的一侧」同构 |
| **B2 给 L2（或 0 档）开口子** | 某次 `l2_lookup` 可以在本回合打 CH 或刷新边车 | 红线改成带条件的表述，并写进 capability 门控；要论证并发预占、超时、限流 |

推荐 B1 的理由：Claude 自己写的目标架构就是「采集边车 → 本地 → agent 只读」。P2「升成可调用工具」在 B1 下仍然成立——工具读本地，不读 CH。缺的是**主动点名**（D9 只在词面命中时被动注入），不是缺一条连 CH 的 socket。

B2 才是「红线不再干净」的那条路。不要把「加一个工具名」默认理解成 B2。

### 4.3 门填好之后怎么走

```
P0 收据
  ├─ 盘中写入 = 否  → L2 保持 T+1 / D9；P1 若开门，只用 0 档 L1
  └─ 盘中写入 = 是  → 边车允许对关注池做 CH 服务端聚合（仍禁止全市场、禁止 agent 直连）
门 A = A1 → P1 只做本地快照 + 读口
门 A = A2 → P1 加事件 + 推送
门 B = B1 → P2 = 新工具读本地（或把 D9 收成可点名工具）
门 B = B2 → P2 = 回合可触发外呼；另开设计，不在本稿展开
```

## 5. 阶段

### 5.1 P0 —— 盘中写入探针（可立即做，无门）

**窗口：** 下一个 A 股交易日 **10:00–14:30**（避开 9:30 集合竞价噪声和 14:50 之后与盘后批量不可区分的区间）。写稿时是 2026-08-26 01:31；若当日开市，就当天盘中跑。休市日不准补跑冒充。

**前置（2026-08-26 夜补）：** 先恢复 ClickHouse 鉴权（供应商侧续期或取新密码，更新 `~/.secrets/clickhouse.env`；见 §3.4 校正与 08-18 挂账交接）。鉴权未恢复时跑探针只会得到 `connect_error` 收据——合法但无判别力，不解锁 §4.3 任何分支。不要拿 `connect_error` 当「不写」。

**客户端：** 复用 `scripts/moneyflow/moneyflow.py` 的 `make_client()`。禁止 `clickhouse-client` 另连、禁止把密码写进命令行历史能看见的地方（用已有环境变量）。

**必须两张表都探。** 原摸底只写了 `share.trans`。现役 `fetch_trades` 深/沪分表，只探深圳会把「沪市盘中不写、深市写」判成全市场 live。

```sql
-- 深圳成交
SELECT
  max(TradeTime) AS max_ts,
  count()        AS n
FROM share.trans
WHERE TradeDate = today();

-- 上海成交（TickType 与现役 fetch 一致）
SELECT
  max(TickTime) AS max_ts,
  count()       AS n
FROM share.ngts_tick
WHERE TradeDate = today()
  AND TickType = 'T';
```

可选加一道轻量样例（沿用 preflight 的 300308，再加一只沪市关注股，例如画像里的上证代码），确认不是「表有今日行但都是昨夜残留」：

```sql
SELECT max(TradeTime) FROM share.trans
WHERE TradeDate = today() AND SecurityID = '300308';
```

**判读（写进收据，不要只贴原始时间戳）：**

| 观察 | 结论 |
|---|---|
| 两表 `max_ts` 都在墙钟前 **≤ 120 秒**，且 `n` 明显大于 0 | **live**：边车可以按关注池做 CH 聚合 |
| `max_ts` 停在今日 09:2x 或昨日，墙钟已过 10:00 | **不写 / 延迟写**：L2 当 T+1；P1 只用 0 档 |
| `max_ts` 已是 14:5x，而墙钟仍在午市 | 可能是截面快照不是逐笔流；记 `suspect_batch`，不要当 live |
| 墙钟 ≥ 15:00 | **作废**，等下一个交易日重跑 |
| 连接失败 / Fake-IP / 无密码 | 记 `connect_error`，不是「不写」 |

**收据落点（下一手 agent 先读这里，不要口头转述）：**

`~/.finance-runtime/intraday-l2-probe/YYYYMMDDTHHMMZ.json`

最少字段：`wall_clock_cst`、`trading_day`、`host_note`（`make_client` 的解析备注，**不要**写密码）、每表的 `max_ts` / `n` / `lag_seconds`、`verdict ∈ {live, batch_or_stale, suspect_batch, connect_error, invalid_window}`、`sz_verdict`、`sh_verdict`。

P0 **可以**是一次性命令，不必先合代码。若要留脚本，只许加 `scripts/moneyflow/probe_intraday_write.py`（只读、默认不写 DuckDB）。不准顺手改扫描阈值、不准盘中跑 `scan_top100` / `scan_limitup`。

（2026-08-26：探针已按该路径落地在本分支。比上表多四道防误判，均写进收据：① `SELECT now()` 实测服务器时钟偏移再算滞后——现役 `fetch_trades` 按 UTC 解析再转 +8，说明服务器时间戳未必是北京时间，直接比墙钟会凭空多 8 小时；② 滞后按交易时段秒数算（`session_lag_seconds`），否则午休 11:30–13:00 会把 live 误判成 stale；③ 间隔 90s 双采样，墙钟在时段内走了 ≥60s 而全市场 `max_ts` 纹丝不动 → `suspect_batch`，防「刚落地的批量」冒充 live；④ 交易日守门不用 `market_feature_store.trading_days`——它按「当日日线 ≥3000 行」判定，日线盘后才同步，盘中恒 False；改用周末硬挡 + 腾讯行情时间戳核对今日开市（`moneyflow.stock_info` 在用的同一端点），失败则记 approximate。`--check-only` 只验链路不写收据。）

**P0 完成标准：** 收据文件存在，窗口合法，深/沪都有一行结论。不是「我连上了」。

### 5.2 P1 —— 最小边车（门 A 填了才做）

**宇宙：** 画像 `watchlist` 解析成 `ts_code`，硬顶 300。0 只 → 进程起来后立刻退出非 0，并写「宇宙空」。不准用涨停榜、不准用全 A clist 凑数。

**采集（0 档）：**

- 独立进程 + 独立 launchd Label（例如 `com.financeworkspace.intraday-sidecar`）。
- HTTP 打 `https://push2.eastmoney.com/api/qt/clist/get`，**只请求关注池代码**（`secids` / 等价过滤），3–5 秒一轮。禁止把 daily-full 那套全 A 翻页（`EM_FS` + `pz=100`）拿来盯盘。
- 字段：现役快照字段 + 涨停/跌停价（开板事件需要）。这是边车自己的请求，不动 `EM_FIELDS`。
- SSL/限流：沿用现有退避；实时 host 失败时**降级为本轮空快照**，不准默默切回 `push2delay` 还标成 realtime（收盘前 delay 和 live 不是同一个数）。
- 限流、重试、降级全收在边车。agent 侧永远只读。

**本地缓冲（先小后大）：**

| 档 | 方案 | 何时用 |
|---|---|---|
| **P1 默认** | 本机 jsonl 环形文件，例如 `~/.finance-runtime/intraday-sidecar/snap.jsonl`（保留最近 N 分钟，N 先写死 30） | A1/A2 都够 |
| 以后 | DuckDB `ops_*` 表 | 真的要和 `fact_*` 做 SQL join 时再加 |
| 不做 | Redis；写入 `fact_stock_daily` / `feature_l2_*_daily` | 污染日频真本源 |

**L2 支路（仅 P0=`live`）：** 边车对关注池做 **ClickHouse 服务端聚合**（主买净额分钟差），沿用 `server_aggregation.py` 的 PREWHERE 纪律。禁止拉 raw tick 进边车。P0 不是 live 则整支路不存在。

**事件（先定义再接流。P1 只锁能在 0 档落地的三条；另两条显式延期）：**

| ID | 事件 | 数据 | P1？ |
|---|---|---|---|
| E1 | 关注池触及涨停 / 开板 / 炸板 | push2 最新价 vs 涨停价；缺涨停价则 **fail closed**，不准用「涨幅 ≥ 9.5%」冒充 | 做 |
| E2 | 关注池日内涨跌幅越过 ±5% 再越过 ±7%（每个阈值只触发一次，除非回撤后再穿越） | `f3` | 做 |
| E3 | 关注池成交额相对上一快照跳变超过阈值（阈值写死在配置，默认 30 分钟内 +100%） | `f6` | 做 |
| E4 | 关注池大单主买净额分钟跳变 | CH 聚合 | 仅 P0=live |
| E5 | 板块分钟强度突变 | 需要分钟级板块源 | **不做。** fupanhui `/reviews/sector-strength` 是加工品，3 秒轮询会撞 429；0 档东财板块另议，不在 P1 |

A1：事件可以算出来，但只当快照上的标记，**不推送**。A2：同一套事件 + 去重 key（`event_id + ts_code + trading_day + bucket`）+ 飞书文本。推送失败不得重放成风暴；丢了就记收据。

**agent 读口（A1 的完成面）：** 新增一个证据块（D9 同族：意图词面才注入，services 层纯函数，禁止 import runtime）。读环形文件最新一行，声明口径：「盘中边车快照，不是日频 `fact_stock_daily`」。不要走 `finance_query`。

### 5.3 P2 —— L2 变成可点名的工具（门 B 填了才做）

B1（推荐）：工具名可以叫 `l2_flow_lookup`，capability 仍是本地读。行为 = 把 D9 从「词面命中才出现」收成「模型可以点名一只股 / 一张榜」。数据源仍是盘后 `feature_l2_*`，外加 P1 若已存在则可读边车缓冲。**不连 CH。**

B2：回合内可打 CH。本稿只承认这是另一张设计，验收、限流、预占配额、超时全链绝对时刻都要另写。不准在 B1 的 PR 里「顺手留一个 CH 开关」。

无论哪条：`feature_l2_*` 不进 `_DATASETS`。日频榜单口径（涨停 + top100）与盘中关注池口径必须在工具返回里写明，禁止用缺行推出「没资金」。

## 6. 验收

### 6.1 P0

- [ ] 收据在 `~/.finance-runtime/intraday-l2-probe/`，墙钟落在 10:00–14:30 CST，交易日。
- [ ] 深 `share.trans`、沪 `share.ngts_tick` 各有 `max_ts` / `n` / `lag_seconds` / 分表 verdict。
- [ ] 总 `verdict` 不是 `invalid_window`。
- [ ] 没有新的盘中全市场扫描，DuckDB 日频表行数不因 P0 增加。

### 6.2 P1（仅门 A 已填）

- [ ] 边车进程不在飞书 bot 里；launchd Label 独立。
- [ ] 宇宙来自画像 watchlist，0 只时非 0 退出。
- [ ] 缓冲是本地环形文件（或日后才加的 `ops_*`），`fact_stock_daily` 与 `feature_l2_*` 的当日行未被边车 upsert。
- [ ] `sync_eastmoney_stock_snapshot.py` 的默认 host / `EM_FIELDS` 无 diff。
- [ ] A1：用户问关注池里某只股「现在盘中怎么样」时，公开稿能引用边车快照并带「盘中快照」限定语；不问现价的题不出现这些数。
- [ ] A2：E1–E3 各能在夹具上打出一条去重后的事件；同一 bucket 不双发。
- [ ] E5 未实现。P0≠live 时 E4 未实现。

### 6.3 P2（仅门 B 已填）

- [ ] B1：registry 多一个只读本地的工具（或 D9 可点名）；capability 门控仍挡 CH。用断网/无效 `CH_PASSWORD` 跑该工具，行为与有密码时相同。
- [ ] B2：另稿验收，不在本清单。
- [ ] 缺行披露句仍在（D9 那句不得删）。

## 7. 选型对照（为什么是边车，不是「agent 多一个工具」）

非科班容易把「实时」当成一种东西。价格、合规、能答的问题是四层，§0 表已经拆过。这里只对照**实现座位**：

| 座位 | 能做什么 | 失败形状 | 本稿 |
|---|---|---|---|
| agent 回合里直连 push2 / CH | 问一句拉一次 | Knevo 同款：快照不是监控；限流发生在对话里，用户看见的是工具失败 | 禁止 |
| 改 daily-full 的东财 host 为 push2 | 复盘脚本「顺便」实时 | 盘中跑 daily-full 会把实时价写成当日 close，污染日频真本源 | 禁止 |
| 把 l2-moneyflow skill 挂进 registry | 模型能点扫描 | 破「skill 不进 agent」；盘中全市场聚合会打爆 CH | 禁止 |
| **边车写本地，agent 只读** | 监控与问答解耦；限流关在边车 | 多一个常驻进程要看管 | **P1 默认** |
| 只在提问时由编排器打一次 0 档（仍由 services 打，不给模型 socket） | A1 的更小子集：无常驻 | 仍是快照；不问就不更新 | 若你把门 A 收到「连边车都不要」，可以再缩，但要重写 P1 验收 |

可迁移点（和 RAG / 第三方 SaaS 工具相同）：**会失败的 IO 不要放在对话回合持有。** 边车是「圈小而稳的一侧」：易变外呼圈进去，agent 只面对稳定读口。面试里这是 agent 可靠性边界的标准答法。

替代方案里，Redis 环形缓冲能做，但本仓没有 Redis，为 P1 引入新基础设施不划算。DuckDB 能做，但生产库同一时间只该有一个写入者——边车去抢 `market_feature_store.duckdb` 会重演复盘撞锁。所以 P1 先独立 jsonl。

## 8. 未决（写在门上，不写在代码里）

1. **L2 凭证续不续（2026-08-26 夜补，先于两扇门）**：鉴权自 08-08 失效、08-18 挂账至今。不恢复则 P0 / E4 / P2 数据面整体搁置，P1 只剩 0 档 L1；恢复后 P0 才有判别力，L2 欠账另按 08-18 交接的回补路径走（与本稿无关）。
2. ~~门 A：A1 还是 A2。~~ → **已拍 A1**（2026-08-26）。
3. ~~门 B：B1 还是 B2。~~ → **已拍 B1**（2026-08-26）。
4. E1 的涨停价字段以边车第一次实打 push2 的返回为准；本稿不把 `f16`/`f17` 写成已核实。
5. 画像 watchlist 是中文名还是代码、缺映射时怎么 fail closed——P1 开工时对着真身画像核一次，不要在仓内 `intelligence/users/` 上猜。
6. #396 合不合 main 与本稿无关；不要等它。

## 9. 下一步（给接手 agent）

1. 等交易时段，跑 §5.1，落收据。不要在盘后「先跑着看看」。⚠ 解释器：用带 `clickhouse_driver` 的系统 `python3`（实测 `/opt/homebrew/bin/python3`）；`.venv-workbench` 没有这个包。
2. ~~把收据结论和两扇门的选择写回本稿状态行~~ → 门已拍（A1+B1，见 §4/§8）。剩收据结论回写，升 v1.2。
3. 收据落地后开 `feat/intraday-l2-sidecar` 做 P1（A1 形态：本地快照 + D9 同族读口，无推送、无事件铃）。P0 收据不是 live 就删掉设计里的 E4，不要留死开关。
