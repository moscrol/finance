# 防坑、launchd、Devin 隧道

### 关键防坑点（顺/坑 速查）

- **limit-heat 被 PIPE 吞进度 = 看起来挂死**：通过子脚本 `backfill_review_hot_data.py`
  跑时 stdout 被 PIPE 缓冲，看不到 chunk 进度会误判挂起。**直跑 `sync-limit-heat`
  继承 stdout** 就能看到 `detail chunk i/N`，2026-06-16 验证 25 个 chunk 顺利跑完。
- **limit-heat 个别题材失败**：整体跑完会打印 `失败 N: code/题材`（如 储能/机器人概念/
  军工）。逐个 `--sector <题材> --detail-chunk 1` 重试即可补齐明细，避免质检报
  "有涨停但明细为空"。
- **单日复盘用东财快照（snapshot）而非 mootdx**：`sync-stock-daily-snapshot` 盘后一次性
  拉全市场当日行情，秒级完成、当日值与 mootdx 一致；mootdx（`sync-stock-daily`）逐只慢，
  仅用于首次建库/历史多日回填。编排器 stock-daily 步已默认走 snapshot。
- **stock-daily 会静默挂（mootdx 全 A）**：低 CPU 且持 DB 写锁。别死等，**直接切
  `fill-stock-daily-fallback`**，当日用 `fact_sector_stock_daily` 聚合补，并复算上证
  周均线/偏离度。
- **sector-stocks 逐板块提交**：默认跳过已抓板块，超时杀掉再跑会从断点续，安全。
  用 `count(distinct sector_ts_code)` vs `dim_sector` 判断完成度。
- **strategy1 矩阵不要喂 evolution record**：那是另一个流程的坑。策略一走
  `skills/strategy1-matrix`，本 skill 只管同步段。
- **`member_count_surplus` = 宇宙声明过时，不是抓取失败**：盘后 live 成员比 18:30
  快照 `expected_stock_count` 多 1–2 只时，写入会被拒、same-day 报「无当日成员行」。
  **不要手改 expected**。正规路径：`sync-sectors` 重发 published 快照 → 再跑
  `sync-sector-daily` **和** `sync-sector-stocks`（VIEW 只暴露新快照，旧 generation 会隐形）。
- **生成段子步骤用 PATH 里的 `python3`，不是启动器那个**：workflow `CommandSpec`
  写死 `python3 scripts/...`。venv-workbench 没有 `markdown`/`matplotlib` 时会
  `ModuleNotFoundError` 或静默不写涨家数图。与夜跑一致：`PATH` 以
  `/opt/homebrew/bin` 开头。不要把 `.venv-workbench/bin` 放到 PATH 最前再跑
  `intelligence.cli daily`。
- **agent-daily `content delta exceeds maximum size`（10MB）**：会扫知识库 wiki
  相对 HEAD 的改动 + **未跟踪目录**（gitignore 不能缩小 delta，保真契约要求 ignored 也进快照）。
  常见撑爆源：`wiki/raw/disclosures/review-queue/reports/`（每日 L3 json/md）和
  `wiki/raw/cross-repo-ingest-queue/`（kb-queue-receive 归档，复盘自己写入、次日再扫）。
  研究队列因此缺档**不阻断**矩阵/驾驶台。不要在复盘补跑里扩 cap，也不要把这些归档
  commit 进别人的知识库分支。正规临时手法：只把上述**未跟踪**目录移到 wiki 外
  （如知识库根 `.delta-park-<日期>/`），跑完 `agent-daily` 再移回；**不要搬**
  `review-queue/` 根上已跟踪的 `cninfo-rss-*.json`。08-25 实测 park 后 delta ~3MB。
  L3 `--apply` 会改 `wiki/sources` / `wiki/entities`：知识库在别人的脏分支上只 dry-run；
  dry-run 0 候选不要 apply。

- ⛔ **`fast_daily_sync.py` 已于 2026-08-02 停用，不要跑**（脚本自带闸门，默认
  退出码 2）。两个原因：① 它 INSERT 的 `fact_sector_daily` /
  `fact_sector_stock_daily` 在生产库里已是 VIEW，写入直接 Catalog Error；
  ② 它的 sector-stocks 是「拷昨日的行、改个日期」，只保留 sector→stock 归属，
  price/pct_chg/amount 全为 NULL——**行数和 `COUNT(*)` 覆盖率都正常，值却是空壳**，
  这类问题只有跨日期 diff 能抓到。2026-06-22 就是这样致 `fact_stock_daily` 全空、
  daily-review §7 个股发动机 / §12 加权涨幅全部"暂无"。
  提速价值现由夜跑拆分（sync@18:30 + finalize@20:40）承接；单步补数走
  `python3 -m market_feature_store.cli <子命令>`。
  历史上的补救手法（若在旧库上复现）：`sync-sector-stocks --trade-date D --refresh`
  拉真实行情；超时就 `--limit 30` 分批，每批确认 `COUNT(*) WHERE price IS NOT NULL` 增长。

- **fill-stock-daily-fallback 依赖 fact_sector_stock_daily 有实际行情**：
  fallback 从 sector_stock_daily 聚合写 fact_stock_daily，但若 sector_stock
  本身也是空壳（price=NULL），fallback 产出同样全空。
  **正确顺序：先 sync-sector-stocks --refresh 补行情 → 再 fill-stock-daily-fallback**。
  若两步都失败，可写临时脚本从 sector_stock_daily (price IS NOT NULL)
  批量 UPDATE fact_stock_daily。

- **Eastmoney API 502 + akshare 断连 = 双源失效**：
  东方财富 sync-stock-daily-snapshot 和 akshare stock_zh_a_spot_em 会同时
  不可用。此时 **唯一可靠源是 fupanhui（sync-sector-stocks）**。
  应对路径：sync-sector-stocks --refresh → fill-stock-daily-fallback → daily-review。
- **fupanhui 公开端点转登录（2026-08-24 起）**：/data/theme/panels、
  /topics/mainline-* 等历史「公开」端点开始校验登录，匿名直连 401；
  批量板块 K 线/成分股的页面内 fetch 同样要带 Bearer。
  已修（fix/fupanhui-auth-fallback）：api_get_public 401 自动回落 CDP
  带登录态路径；批量 JS 带 localStorage user_token。前提不变：
  Chrome 已登录 fupanhui.com + CDP proxy 在跑。若批量抓取返回
  `code:-1 板块已切换为复盘会 FP 代码`，是旧 BK/TI 码，按当日宇宙过滤。

- **代理掐 SSL 的识别与绕过**：本机代理（Clash TUN 等）会把新浪/东财/腾讯
  的 HTTPS 掐成 `SSLEOFError`（curl 同样空响应）。特征：requests 超时挂死、
  `qt.gtimg.cn` 市值请求每批 4×15s 空转。应对：指数走
  reviews/market.volume.indices 兜底；成分股市值列可空（跳过 _tencent_market_caps），
  行情本体从 fupanhui 拿不受影响。**不要用「重试更多次」对抗被掐的 TLS**。

- **驾驶台 cockpit 三个每日更新项**：
  1. 每日复盘（daily-review）→ `render_daily_review_briefing.py`（夜跑 canonical）
  2. 机构胜率（winrate）→ `skills/opinion-cross/scripts/render_winrate_html.py --vault <KB_WIKI> --date D`
  3. 晨会边际变化（morning briefing）→ 需知识库 `wiki/briefings/D.md` 源文件存在
     → `<KB>/skills/morning-briefing/scripts/render_briefing_html.py D --vault <KB_WIKI>`
  **`render_cockpit.py --knowledge-root <KB 仓根>`**（例如 `/Users/a77/knowledge-base-private`）。
  没有 `--kb-briefings-dir` 这个参数。默认 `ROOT.parent / "知识库"` 在本机对不上，必须显式传。
  研究队列若是 `cli daily --skip-agent` 之后才补的，必须再跑 workbench + cockpit，否则卡片仍缺「研究队列」。

- **S7 staging：夜跑失败补洞，不要直写生产**：18:30 包装
  `~/.local/bin/nightly-full-review-s7.sh` → `nightly-review-sync-staged.py`，写锁落在
  `db/market_feature_store.duckdb.staging`，same-day 全绿才 `atomic_swap_into_place`。
  不过门则生产停在昨日、staging 残留。补跑：
  `MARKET_FEATURE_STORE_DB=$FINANCE/db/market_feature_store.duckdb.staging`
  在 staging 上补模块 → `--phase data` 过门 → 换名 → 再跑生成段。
  直写生产会和残留 staging 分叉，换名时可能把补上的数盖回去（08-20 有过反例）。

- **sector-stocks「20 轮无 published universe」经常是时序**：宇宙可能在 18:39 才 published，
  18:30 那轮空转不是抓取脚本坏了。等 published 后再跑；若随后 `member_count_surplus`，
  走上面「重发快照」路径，不要手改 `expected_stock_count`。

- **public-assets 夜跑「ok」仍可能当日行是空的**：08-25 该步 61s 标 ok，staging 上 08-25
  行仍空（假绿）。same-day 不一定覆盖所有公开资产表。补跑后按日对账
  `fact_core_stock_daily` / `fact_global_*` / `fact_dragon_tiger_daily` / `fact_auction_stock_daily`
  行数须与最近交易日同形（core=50、global index=5 这类恒定宇宙）；不要只看步骤 rc。
  `fact_leader_height_daily` 每日 **1 行**（最高板），不是 120 只名单。

- **题材雷达 HTML 被质量门拦截**：
  `render_market_triggered_theme_brief_html.py` 内部先调 build_* 脚本，
  若 quality-gate INCOMPLETE 则 exit(1) 不生成 HTML。
  可绕过：直接读已有的 `exports/D-market-triggered-theme-brief.md`，
  用 render 脚本的 HTML 模板手工渲染（参照 render 脚本 main() 后半段）。

- **cockpit CSS 与 daily-review 主题解耦**：
   的  原先从最新 daily-review HTML 提取 CSS，
  但 daily-review 已升级为暗色主题（/），cockpit 的 HTML 结构仍
  使用浅色主题 CSS var（//），导致 var 未定义、界面崩溃。
  **已修复**： 固定返回 FALLBACK_CSS（cockpit 自带的浅色主题），
  两套界面各自独立。若未来要让 cockpit 也用暗色主题，需重写 FALLBACK_CSS + EXTRA_CSS
  的 var 名映射。

### 夜间 launchd 定时运维（2026-07 踩坑沉淀）

夜间自动复盘走 `nightly_full_review.sh`（launchd），**已拆成两个 job**——因为
**L2 逐笔资金流数据 ~20:30 才入 ClickHouse，18:30 跑必空**（连续两天因此 fail、需手动补跑）：

| job | 时间 | 命令 | 跑什么 |
|---|---|---|---|
| `com.financeworkspace.daily-full-review-sync` | 18:30 | `nightly_full_review.sh sync` | 同步段（全 fact 同步 + same/cross-day 门），不依赖 L2 |
| `com.financeworkspace.fidelity-daily-agent` | 20:05 | `run_fidelity_daily_agent.sh` | theme-candidates 合同校验 + agent-daily（`--semantic-rag-top-n 0`）+ kb-queue-receive |
| `com.financeworkspace.daily-full-review-finalize` | 20:40 | `nightly_full_review.sh finalize` | sync 守卫（复查 same-day-gate）→ L2 → 生成段（含研究队列 + receive）→ 终极门 |

手动补跑用 `nightly_full_review.sh [date]`（phase=all，全量；跨日补跑也用它）。
脚本带 phase 参数（`sync`/`finalize`/`all`），date 参数顺序无关。旧的单 job plist 已 bootout 并重命名为 `.retired`。

近期踩坑（调度/脚本层已修，记此防复发）：

- **L2 18:30 必空**：逐笔数据 ~20:30 才到，早跑 `empty_count=全量` → 资金流段 fail。
  这就是拆 sync/finalize 的根因。**手动补跑 L2 也要等 20:30 之后**（之前踩过：18:40 跑全空，过零点再跑才有数据）。
  注：全空时 scan 会 raise，**空结果不进缓存**，重跑会真扫（无需 force-rescan）。
- **preflight `wrong-host` = fupanhui 标签页没就绪**：sync 段 preflight 要挂载一个**已登录的 fupanhui.com 标签页**。
  Mac 睡眠唤醒后 launchd 补跑，常因 debug Chrome 里没有 fupanhui 标签页而 fail（proxy `/health` 显示 `managedTabs:0`）。
  排查：`curl -s http://127.0.0.1:9222/json | grep -i fupanhui`；修：在 debug Chrome（端口 9222 那个实例）开一个 fupanhui.com 标签页（登录 cookie 持久，开着即可）。
- **market-deviation tooltip 抓取 2026-07 起稳定失效**：`_fetch_market_deviation` 合成 `pointermove/mousemove`
  不再触发带「周均线」的 tooltip（活体探测：canvas 有 7 个，但 `div[style*="z-index"]` 覆盖层=0、全文无「周均线」）。
  怀疑 fupanhui 改了 tooltip DOM 或**后台标签页不响应合成悬停**。`sync-market-deviation` 因此必 fail → same-day-gate INCOMPLETE。
  **当前兜底 = 手动 MA5 复算**（`fill_stock_daily_fallback.py:recompute_deviation` 同款）：
  ```python
  from market_feature_store.db import connect
  D="YYYY-MM-DD"; MW=5
  con=connect()
  closes=con.execute("SELECT trade_date,sh_index_close FROM fact_market_daily "
      "WHERE trade_date<=? AND sh_index_close IS NOT NULL ORDER BY trade_date DESC LIMIT ?",[D,MW]).fetchall()
  ma=sum(float(r[1]) for r in closes)/len(closes); close=float(closes[0][1]); dev=(close/ma-1)*100
  con.execute("UPDATE fact_market_daily SET sh_week_ma=?, sh_deviation_pct=? WHERE trade_date=?",[round(ma,2),round(dev,2),D]); con.commit()
  ```
  ⚠ **TODO（未做）**：把 MA5 复算接成 `sync-market-deviation` 抓取失败时的**自动 fallback**，否则每晚 sync 都卡这步、finalize 被守卫拦下、自动复盘跑不完。
- **单日 sync 失败留断档 → 连锁阻断后续日期**：跨日门 `check-daily`（cross-day-gate）要求 `fact_mainline_*_daily` 连续。
  某天夜跑失败（如 2026-07-21 主线没写）→ 次日（07-22）跨日门报「主线断档 1 日」、整轮 fail。修：补跑缺数日的
  `sync-mainline-daily` + `sync-mainline-sector-daily --trade-date <缺数日>`，再重跑当日复盘。
- **缺单条板块也判 INCOMPLETE**：`fact_sector_daily` 哪怕只缺 1 个板块（如 MLCC/990001.FP 某日 fupanhui 偶发漏返，
  223/224）→ same-day-gate fail。重跑 `sync-sector-daily --trade-date D --days 25` 通常补回；
  **重跑后必校验 diff_ratio 没全零**（`SELECT count(*) FILTER (WHERE diff_ratio=0 OR diff_ratio IS NULL)`，fupanhui kline 偶发全零 gotcha）。
- **周末检查按目标日期**：脚本用**目标 $D 的星期**判周末（`date -j -f "%Y-%m-%d" "$D" +%u`，非今天的 `date +%u`），
  否则跨日补跑（今天是周末、$D 是工作日）会被误跳过、什么都没跑（exit 0 但无产出）。
- **finalize 守卫是有意为之**：finalize 开头复查 same-day-gate，若 18:30 sync 没成功就中止生成（rc=2），
  **避免在残缺数据上生成报告**。看到 finalize rc=2 先去查 sync 为何没成，别绕守卫。

### Devin 远程执行专用坑（通过 Cloudflare 隧道 rx.py 跑时）

- **Cloudflare 524 超时 + 隧道重启连杀 = 长任务必须守护进程化（spawn.py）**：隧道对单次请求
  ~100s 超时（rx.py +60s overhead ≈ 160s）超过就返回 524；更坑的是隧道掉线后常用
  `launchctl kickstart -k <label>` 重启 exec 服务，`-k` 会向该 LaunchAgent **整个进程组**
  发 SIGKILL——用 `nohup ... &` 起的后台任务同属该进程组，**nohup 只挡 SIGHUP、挡不住组
  SIGKILL，会被连带杀掉**（cdp-proxy 同理）。所以所有长命令（run_review_sync.py、daily-full、
  evolve_daily.sh、cdp-proxy）一律用 `scripts/spawn.py`（fork→setsid→再 fork 守护化，脱离
  exec 进程组）启动，起完立即返回，之后 kickstart -k exec 服务不会再误杀：
  ```bash
  PY=/Library/Developer/CommandLineTools/usr/bin/python3
  # 复盘编排器（参数：<日志> <cwd> <要跑的命令...>）
  python3 rx.py -- "$PY skills/daily-full-review/scripts/spawn.py /tmp/bf/review_sync.log '/Users/lbq/Desktop/c c/金融' $PY -u skills/daily-full-review/scripts/run_review_sync.py --date D"
  # cdp-proxy（隧道重启后若 3456 不通就重起）
  python3 rx.py -- "$PY skills/daily-full-review/scripts/spawn.py /tmp/bf/cdp_proxy.log /Users/lbq \$(command -v node) ~/.claude/skills/web-access/scripts/cdp-proxy.mjs"
  # 轮询日志：python3 rx.py -- "tail -30 /tmp/bf/review_sync.log"
  # 检活：  python3 rx.py -- "ps aux | grep run_review_sync | grep -v grep"
  ```

- **短任务 vs 长任务：要不要 spawn.py 守护化的判别标准**（跨机复用，任意 Mac agent 派活可直接引用）：
  - **直跑（不守护化）**：预计 **<30s 且非常驻** 的一次性短命令——查行数、审计、`export_increment.py`
    当日增量导出（07-01 实测 ~1s/1MB）、单次文件读写等。经隧道跑也在 rx.py ~160s 超时内，跑完即返回。
  - **必须 spawn.py 守护化**：**长时（>隧道单请求超时，约 100s）或常驻**的命令——`run_review_sync.py` /
    `daily-full`（分钟级）、`evolve_daily.sh`、`cdp-proxy`（常驻），以及任何**会被 `launchctl kickstart -k`
    连带 SIGKILL** 的后台进程。判据一句话：**能秒回的直跑；要等、要常驻、怕被隧道重启连杀的，一律 spawn.py**。
  - **动态退路**：拿不准就先直跑，若**实测 >30s 或卡住**，改用 spawn.py 守护化重起。
  - 原理：spawn.py 用 `fork→setsid→再 fork` 让进程脱离 exec 服务进程组，`kickstart -k` 的组 SIGKILL 波及不到；
    短任务本就在超时内结束、不涉及进程组连杀，守护化只是徒增日志文件与排查成本。

- **rx.py 524 后 Mac 进程不会死**：Cloudflare 超时断连，但 Mac 端守护进程仍在后台跑且可能持有
  DuckDB 写锁。**起新写操作前必须 `ps aux | grep market_feature_store | grep -v grep` 检查残留进程**，
  盲目重启会导致 DuckDB 锁冲突（"Conflicting lock"），两个进程互相卡死。

- **Python 输出缓冲 + nohup = 日志不刷新**：macOS nohup stdout 全缓冲，看不到实时进度。
  **必须用 `python3 -u`**（unbuffered）。即便如此也建议同时查 DB 行数确认进度：
  ```bash
  python3 rx.py -- "cd '/Users/lbq/Desktop/c c/金融' && python3 -c \"from market_feature_store.db import connect; c=connect(read_only=True); print(c.execute('SELECT COUNT(*) FROM fact_sector_stock_daily WHERE trade_date=?',['D']).fetchone())\""
  ```

- **不要手动逐步跑 sync、必须用编排器**：手动跑单步极易用错参数（如 `sync-stock-daily --refresh`
  默认 offset=180，遍历 5000+ 股票 ≈ 90min；编排器单日复盘已改用东财快照
  `sync-stock-daily-snapshot`，秒级完成，失败才回退 fill-stock-daily-fallback）。
  **永远先跑 `run_review_sync.py --date D`**，它已内置正确参数、逐模块超时、自动兜底。

- **agent-daily 不在 evolve_daily.sh 中**：evolve 只有 8 步（generate→validate→log→theme→backfill→review→audit→suggest）。
  agent-daily 是独立命令 `python3 -m intelligence.cli agent-daily --date D`，
  必须在 evolve 后单独跑，否则驾驶台不会显示研究队列标签。
  完整后置流程：evolve_daily.sh → agent-daily → kb-queue-receive → render_cockpit.py（重渲染）。
  **夜跑不要开 wiki RAG**：分桶不读向量索引；`--semantic-rag-top-n 0`。2026-08-13
  曾 3×120s 超时白烧 ~6 分钟。手动深挖再显式传 `--semantic-rag-top-n 3`。
  **kb-ingest-queue 只归档不入库**：`kb-queue-receive` / `kb_ingest_queue.py receive`
  写入 `wiki/raw/cross-repo-ingest-queue/` 并生成 receipt；禁止 `--apply`、禁止
  改 `auto_apply`、禁止自动写 IMA/relations。概念入库仍走人工 `concept-ingest`。
  LaunchAgent 跑的是 **runtime 快照 + 数据仓 main**；本优化在 `feat/research-queue-canonical`
  落地后，需合并进 main 并刷新 `FINANCE_CODE_ROOT` runtime，20:05/20:40 才会吃到新代码。

- **S7 夜跑 sync（2026-08-16）**：18:30 不再直接跑仓内
  `nightly_full_review.sh sync`。入口是
  `~/.local/bin/nightly-full-review-s7.sh`，写锁只落 staging，成功才
  `os.replace` 进生产库。子进程仍用 private 工作树上的
  `run_review_sync.py`（那棵树有未提交的主线 static 回退）。**不要**为了
  S7 去切 8792——S7 不在 `intelligence/`。详见
  `docs/handoffs/2026-08-16-s7-nightly-staging.md`。

- **Token 编码 U+2028/U+2029**：macOS 环境变量可能尾部带 Unicode 行分隔符，导致 hmac 校验失败返回 401。
  rx.py 必须 `TOKEN = os.environ.get("CC_REMOTE_EXEC_TOKEN","").strip().strip("\u2028\u2029")`。

- **exec service hmac bug（Python 3.9）**：`/Users/lbq/.cc-exec/server.py` 的 `hmac.compare_digest()`
  在 Cloudflare 转发的非 ASCII header 下崩溃。已修复为 `.encode("utf-8","replace")`。

