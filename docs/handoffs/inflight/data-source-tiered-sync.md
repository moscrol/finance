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
**已合 main**：PR #578 → `gitea/main@9bec1f49`（2026-09-04 20:45，用户口令「确认」）。合并树 = 分支 ∪
`gitea/main@40f84567`（并入 #573/#574/#575 十八个提交，零冲突、零重叠文件），在合并树上重跑：ruff 绿、
pytest **7678P/15S/1x**、frontend lint/typecheck/test 71/build 全绿。远程分支已由 Gitea 删除。
**生产未切档**：主树 `/Users/a77/finance-workspace-private` 仍在 `feat/content-ops-copilot`（该分支比 main 多两个
内容运营迁出提交，未合），夜跑跑的是主树当前 checkout，所以新代码还没进夜跑路径；两个 LaunchAgent 仍未加载；
Chrome 仍未登录 fupanhui。切档四步见「下一步」。

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

## 下一步（切档四步，都在仓外/主树，等用户口令）
1. 主树换到含 #578 的 main（先确认 `feat/content-ops-copilot` 那两个提交是否还有人在用；主树 155 条他人未跟踪文件
   不受 checkout 影响）：`cd /Users/a77/finance-workspace-private && git checkout main && git pull gitea main`
2. 档位：在 `~/.local/bin/nightly-full-review-s7.sh` 的 `export MARKET_FEATURE_STORE_DB=…` 附近加一行
   `export REVIEW_SYNC_PLAN="${REVIEW_SYNC_PLAN:-auto}"`（子进程继承；`run_review_sync.py` 默认读它）。
   不设则仍是 full，不会静默切档。
3. 重新加载夜跑：`launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.financeworkspace.daily-full-review-sync.plist`
   与 `…-finalize.plist`（它们当前不在 `launchctl list` 里——先弄清是不是有人刻意停的）。
4. Chrome 登录 fupanhui.com（preflight 当前 `login: no`，不登录任何档位都 rc=3）。
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
