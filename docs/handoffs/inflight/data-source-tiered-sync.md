# data-source/tiered-sync

## 这个分支做什么
把 daily-full 从「整锅每天煮」拆成 identity / value 分档：名单（谁在板块里）慢刷，数字（今天多少钱）
换源日更。复盘会请求量 full ≈ 900/日 → cheap ≈ 30~45/日。单一事实源
`market_feature_store/consumption_registry.yaml`（22 数据族 × 4 档 + 两档计划步骤 + 6 条 recipe 骨架，
其中 3 条 knowhow 待 grilling）。

新增：`consumption_registry.{yaml,py}`、`sync/sync_local_sector_members.py`（identity 探针 + 成分拼接器）、
`sync/sync_local_sector_daily.py`（板块日行情本地派生 + 周抽样对账）、`sync/sync_akshare_dragon_seats.py`
（席位换源）、`ops_sector_search_payload_daily`（宇宙请求随行情字段落库，含 raw_json）。
改动：`sync_fupanhui_sectors.py` 落 payload；`sync_fupanhui_public_assets.py` 加 plan（竞价停、席位
akshare 优先回退复盘会、研报增量翻页）；`cli.py` 加 `--plan` 与 5 个子命令；`run_review_sync.py` 加
`--plan full|cheap|auto`（env `REVIEW_SYNC_PLAN`），cheap 计划把 stock-daily/stock-high/limit-heat 前移到拼接前。

## 当前状态
**已合 main 且已切档（等 Chrome 登录）**：PR #578 → `gitea/main@9bec1f49`，收口 #579；2026-09-04 20:56~21:05 按用户「确认/继续」完成切档前三步：
1. 主树 `/Users/a77/finance-workspace-private` 已从 `feat/content-ops-copilot` 切到 `main@fbb82c71`（含 #578）。
   阻塞 `pull` 的 142 个未跟踪文件：141 个与 main 提交版本哈希完全一致 → 删除（零丢失）；1 个
   `docs/handoffs/workspace-cleanup-claim-list-2026-09-03.md` 本地是 **0 字节**（main 有 387 行完整版）→ 移至
   `~/.finance-runtime/untracked-backup-20260904/`。其余 43 个未跟踪文件被新 `.gitignore` 覆盖，未动。
2. `~/Library/LaunchAgents/com.financeworkspace.daily-full-review-sync.plist` 的 `EnvironmentVariables` 加
   `REVIEW_SYNC_PLAN=auto`（备份 `*.plist.bak-pre-tiered-20260904T205642`）；主树上零副作用验证：周一 → cheap、周五 → full、无变量 → full。
3. 两个 LaunchAgent（sync 18:30 / finalize 20:40）在 launchd override 库里是 **disabled**（某 agent 09-03 晚~09-04 傍晚未记录的
   `launchctl disable`/`unload -w`；全仓文档与 `disabled-by-devin/` 均无记录，用户 18:57 仍预期夜跑在跑）→ `launchctl enable` + `bootstrap`，
   现 `launchctl list` 可见、`print` 显示 `REVIEW_SYNC_PLAN => auto`。周六 18:30 会记一条「周末跳过」当冒烟。
4. **Chrome 登录 fupanhui.com 仍未做**（preflight `login: no`）——不登录周一 18:30 会 rc=3 停在 preflight，任何档位都一样。

## 怎么验收
1. `python3 -m market_feature_store.cli registry-check` → 校验通过，两档步骤与 build_plan 一致。
2. `pytest -q tests/test_consumption_registry.py tests/test_tiered_sync_local.py` → 17 passed。
3. 快照回测（/tmp/mfs-analysis/snapshot.duckdb，2026-09-02）：
   - 拼接干跑：395/395 板块可拼，49,970 配对行 price 零差异、high_status / limit_times 零不一致、
     无 NULL 三件；pct/amount 差异全是复盘会 2 位小数尾巴（pct 最大 0.01）；拼接漏 19 行 = 名单噪声。
   - 板块本地派生（克隆库真写）：403 行，成交额相对误差中位 0.007%，边际量误差中位 0.008pp / p95 0.08pp，
     等权涨幅符号不一致 14/403，**严格双红零翻转**；payload 官方涨幅优先生效。
4. `scripts/check_sector_fact_access.py --output …` → violations 0；`audit_dataset_registration.py` 通过。

## 未验证 / 已知边界
- **sectors/search payload 字段未实测**：Chrome 当前未登录 fupanhui（preflight `login: no`），拿不到响应。
  代码按候选字段名取值并落 raw_json，首个 cheap 日跑完看 `ops_sector_search_payload_daily.raw_json`
  确认 pct_chg 字段名；若没有官方涨幅就全走等权（回测双红零翻转，可接受）。
- **未在生产库跑过一次完整 cheap 计划**；夜跑 LaunchAgent 当前根本未加载（`launchctl list` 无
  `daily-full-review-sync`），09-03/09-04 都没跑。这是运维事实，不在本分支范围。
- 请求计数口径修正：批量抓取在 JS 里仍是逐板块 fetch，原「~40 chunk 请求」按 CDP eval 数的，
  按 HTTP 请求算成分是 403/日、K 线 403/日。registry 已按新口径写。
- fund_flow_1d/5d 拼接行留 NULL（复盘会独有口径，东财等价性未验证）；周五 full 补齐。
- 「expected 不变但名单微动」每天 5~63 个板块，量级落在明细接口 0.25% 随机遗漏噪声带内，
  最坏陈旧 5 个交易日由周五 full 兜底；未做更细的逐股换血检测。

## 下一步
1. 用户：Chrome 登录 fupanhui.com（周一 18:30 前）。
2. 周六 18:30 后看 `logs/daily-full-review.out.log` 有无「周末，跳过全量复盘」——有 = launchd 链路活了。
3. 周一 18:30 首个 cheap 日；若要提前手动验：`REVIEW_SYNC_PLAN=cheap` 手跑 `nightly-full-review-s7.sh sync`（需已登录）。
首个 cheap 日之后：看 `skills/daily-full-review/state/runlog.md` 的 `plan=cheap` 段；
`python3 -m market_feature_store.cli reconcile-sector-daily --trade-date <D> --sample 20`（20 请求）；
`SELECT raw_json FROM ops_sector_search_payload_daily LIMIT 3` 定官方涨幅字段名。
knowhow 轮次：registry `recipes` 三条 pending-grilling（题材逻辑周期 / MA5 交替 / 赚钱效应聚类）按约定 grilling 用户后编译。

## 踩过的坑
- 上一个 agent 的分支从 `feat/content-ops-copilot` 拉、不是 main，且主树 155 条他人未跟踪文件——
  按 AGENTS.md 另开 worktree，venv 直接用主树的（无 editable 安装，cwd 决定加载哪份代码）。
- `_existing_multi_period` 初版直读 `fact_sector_daily_generation`，`check_sector_fact_access.py`
  连读物理表也要白名单——改读 VIEW。
- 拼接基线要取「最近一次 fupanhui 名单」而不是昨日行：链式拼接会把停牌一天的股票永久丢到周五。
- 东财 fallback 源（`fupanhui:sector_stock_daily:fallback`）来自成分表自身，拿它拼接是循环，代码拒绝。

## 已验证
见「怎么验收」1~4。akshare 席位实测：002536.SZ @09-02 三席位金额/占比与复盘会逐项对上（元→亿、比例→%）。

## 工具沉淀
registry 一致性测试（YAML ↔ 管线步骤名）是「单一真本源且生成」模式的又一实例；拼接器复用深模块
公开 API 拿到同一套校验/台账，属于 BUILD.md「圈小而稳的一侧」。未新增通用零件，不回写 KIT.md。
