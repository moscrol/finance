# 在途交接 · feat/market-staleness-disclosure-p0-0929

2026-09-29，隔离树 `/Users/a77/fwp-wt-staleness-0929`，基线 `gitea/main@2b66c3740`。接手 `2026-08-27-staleness-disclosure-workorder.md` P0（`R-20260827-13` 在主干台账已有 pending 行）；不做 P1 巡查、不改生产 DB/部署/告警。

## 本次代码

`market_watch_pack.py` 服务层**新增独立** `market_staleness_disclosure(standing, today)`：上海交易日历对照库的真实站立日；周末与 2026 公告休市日不误报，日历不支持则不猜。既有 `_structured_freshness_floor`、PIT 钳制、`calendar_disclosure`/`should_stop` 均未改。新增 `MarketWatchPack.staleness_disclosure`，渲染仅消费事实；`run_market_watch_pack` 在四袋读出后算一次，正常 Ask binder 与公开稿合成透传。`today` 注入仅用于离线确定性测试，生产默认上海市场日期。

`intelligence/tests/test_market_staleness_disclosure.py`：周末/公告休市、T-2 停更披露与 `should_stop=False`、四袋和公开稿、fresh/显式题、未知年 fail-closed、渲染不判定。先红（新增 helper 缺失）后绿；定向 29P（含原盘面包与替补探针），Ruff 绿。**完整门禁、五项变异、真实停更日/构造夹具的独立回读尚未完成**，不把台账 pending 改 confirmed，不宣称合并/部署。

## 复核义务

1. 提交后五项变异逐条杀：自然日计数、滥用 calendar 字段、基准改成数据自身、判定挪进 render、PIT 原语改值（用既有 as_of/历史授权回归钉）。
2. 全量 pytest 读数 + `check_test_receipt.py --expect-revision <tip>`，Ruff、registry-check 与独立 reviewer 检验公开稿链路。
3. 合并需单独批准，部署/切流与真实用户验收仍未做。当前函数对未知交易所年历 fail-closed。
4. **盘中时点已定案（2026-09-29 夜，Claude Code 云端会话，用户授权「按最优方案推进」）**：上海时间 21:00 前当日会话不计入期望（`MARKET_DATA_READY_HOUR`，夜跑同步约 18:50 发布、收尾约 20:56）。否则每个交易日开盘到夜跑发布之间每条盘面回答都挂「今日数据未更新」。盘中只与上一交易日比，缺的是它时文案点名「最近交易日（X）」。被否：按自然日/按收盘 15:00 划界（15:00–18:50 仍会误报）。
