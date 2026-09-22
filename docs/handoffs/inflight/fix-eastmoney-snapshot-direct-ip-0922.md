# 东财快照传输层修复（在途）

分支 `fix/eastmoney-snapshot-direct-ip-0922`，基线 `gitea/main@a2c8d1f90`，工作树
`~/fwp-wt-eastmoney-direct-ip-0922`。**未合并。**

> 状态更新 2026-09-22 20:10：`b1d797593` 的两个文件**已热部署到 sync 代码根**并**已重跑
> 今晚 sync 段**（授权范围内；PR 仍未合）。重跑仍失败，但**失败原因已不是本 PR 修的那个**。
> 详见文末「运行验证」——**下一个接手的人先读那一节再动手**。

## 为什么

09-21 与 09-22 连续两晚 `sync-stock-daily-snapshot` 失败 → 兜底无源 → 其后 11 个本地
计算步骤全红 → same-day-gate rc=2 → finalize 守卫中止、staging 不晋升 → 主库停在
09-18 → `/api/readiness` 一直 503（`missing_critical=["market_data_consistency"]`）。

实测根因两条（证据 `~/.finance-runtime/reviews/market-source-probe-20260922T1840/`）：

1. **重试从来没生效**。`_get_json` 的捕获子句是 `(URLError, TimeoutError, ValueError)`，
   接不住 `http.client.RemoteDisconnected`——urllib 只把「发请求阶段」的 OSError 包成
   URLError，而连接断在 `getresponse()` 阶段。6/6 探针样本
   `caught_by_pipeline_except_clause: false`；日志里也没有重试耗尽才会抛的那句
   `东财快照请求失败`。所以翻页途中一次断连即整段崩，双 host 兜底一次都没走到。
2. **本机代理 fake-IP 劫持**。系统 DNS 把 push2delay/push2/push2his 全解析到
   `198.18.0.x`，表现为建连成功随即断开、~90ms（不是超时、不是限流）。同一时刻公共
   DNS 取真实 IP 直连（SNI 仍填域名）两个 host 都 200、`f297=20260922`——**源是好的**。
   `sync_eastmoney_fund_flow` 2026-09-11 已为 push2his 踩过同一坑并写明「别再误判成
   限流」，但快照模块没用上那套绕法。

## 改了什么

- `sync_eastmoney_stock_snapshot.py`：`TRANSIENT_FETCH_ERRORS`
  = `(OSError, HTTPException, ValueError)`；新增 `_system_ip` / `_looks_hijacked` /
  `_direct_ip` / `_tls_connection` / `_direct_get_json` / `_urllib_get_json`；`_get_json`
  改为——系统解析落在 `198.18/15` 直接走真实 IP 直连，否则仍走 urllib（**链路正常时行为
  不变**）；失败一次即把该 host 记为 `direct`，不让 60 页每页都白打一发。
- `sync_eastmoney_fund_flow.py`：删掉自己那份重复实现，改从快照模块导入（单一真相）。
  副作用：公共 DNS 顺序由 `8.8.8.8` 优先改为 `223.5.5.5` 优先（国内解析更快）。
- 新增 `tests/test_eastmoney_transport.py`（19 例）。

## 证据

- 定向回归 494 passed / 1 skipped（所有涉及 eastmoney/fund_flow/daily_full 的测试文件）。
- 变异验证：换回旧捕获子句 → 7 红；关掉劫持判据 → 2 红。
- 真网络单发（修复后代码、当前被劫持的本机）：182ms、`total=5918`、`f297=20260922`、
  f8 在，`transport_cache` 为空（判据一次直中，零浪费请求）。收据
  `fixed-get-json-live.json`。
- ruff 三个文件 clean。

## 需授权才能做的下一步

1. 部署到 sync 代码根 `~/.finance-runtime/finance-sync-adcda94b5e40`（生产发布）。
2. 重跑今晚 sync 段（写库；finalize 定时 20:40，须避开正在跑的夜跑，勿并发写）。
3. 合并 PR（需本机等价 CI 四叶子全绿 + 独立审核）。

## 边界

- 只证明「此刻单发可达」，不证明 60 页整跑必成；劫持是本机网络状态，随时可能变。
- 09-21 那个洞是历史回填，归 `fix/market-recovery-0921`，不由这条分支解决。
- 未碰任何数据库、未部署、未重跑、未动他人工作树。（以上为本 PR 编写阶段的边界；
  部署与重跑发生在其后，见下节。）

---

## 运行验证（2026-09-22 19:17–20:10，另一 agent，用户逐项授权）

授权范围：**只**热部署这 2 个文件 + **只**重跑今晚 sync 段。未合 PR、未改计划/门禁/定时、
未动 8792 服务树。完整证据：`~/.finance-runtime/reviews/eastmoney-hotfix-20260922T1917/`
（含 `FINDINGS.md`、`deployment.json`、各探针 JSON、`rerun-out.log`）。

### 部署收据（怎么验、怎么回滚）

- 目标树 = `~/.finance-runtime/finance-sync-adcda94b5e40`。**注意前一份交接把它写成了
  `finance-workspace-runtime`，那是 8792 Web 服务树，不是夜跑导入的树。**三方互证：
  plist 的 `FINANCE_SYNC_CODE_ROOT`、18:30 失败堆栈路径、干净 shell 导入探针。
- 校验：两文件 sha256 与 `b1d797593` **逐字节一致**；`git status` 仅这两文件 + `runlog.md`。
- 回滚：`original-files/` 存有打补丁前的原件（保留目录层级），覆盖回去即可。
- 已部署树上跑定向测试 **49 passed**、ruff clean、
  `fund_flow._direct_get_json is snapshot._direct_get_json` 成立（单一真相源确实生效）。

### 重跑结果：rc=2，闸门 fail-closed，主库未受损

19:21:25 `launchctl kickstart`（不带 `-k`）触发原任务，plan=local、date=2026-09-22，
19:44:50 以 `rc=2` 结束。`fact_market_daily`/`fact_stock_daily` 仍 `2026-09-18`，**未被写入**。
S7 保护按设计生效：写只落 staging，同闸门判 INCOMPLETE → 不换名。

**补丁确实在工作**：snapshot 步骤耗时从 18:30 的 41.7s 变成 **90.9s / 58.4s**，
说明重试阶梯真的跑起来、断连被正确归类为瞬时错误、不再一撞就穿。

### 但今晚真正的阻塞是另一件事：东财按出口 IP 在应用层拒绝

| 探针 | 结果 | 排除了什么 |
|---|---|---|
| `_direct_get_json` pz=1 / pz=100 | 均 RemoteDisconnected | 不是请求体积/翻页 |
| 百分号编码 / 最小字段集 / push2 备用域 | 全断 | 不是 query 形状、不是单域名 |
| `curl --noproxy '*' --resolve` 打真实 IP | `curl: (52) Empty reply` | **不是 Python 代码** |
| 223.5.5.5/119.29.29.29 vs 8.8.8.8 | 前者给的 IP 连上即断；后者给的 IP 回 **502 nginx** | **加多 IP 轮换也救不了** |
| `openssl s_client` 两种 SNI | 均握手成功，证书 `*.eastmoney.com` 验证 OK | 不是 SNI 拦截、不是中间人，对端是真东财 |
| 对照 baidu / quote.eastmoney.com | 均 200 | 大网与东财主站均正常 |

即：**TLS 全程正常、对端是真东财，但它接下连接后对 `/api/qt/clist/get` 不给响应体**。
18:59 同样的单发还能拿到 5918 只（就是本 PR 的 `fixed-get-json-live.json`），19:2x 起全废，
中间隔着 18:30 与 19:21 两轮「60 页 × 重试」的密集翻页。20:00 冷却 40 分钟复测仍被拒。

### ⚠ 给本 PR 的设计反馈（合并前建议处理）

**本补丁提高了重试压力**（41.7s → 90.9s 就是证据）。如果上面的封禁确实是我们自己的
翻页量打出来的，那么「更顽强的重试」会**加深**封禁而不是绕过它。建议合并前补一条
熔断：同一 host 连续 N 次「连上即空回应」时**立即停止本轮**并报独立错误码，
与「瞬时抖动」区分开——现在这两种形状在代码里是同一类，会被无差别重试。
（这条只是建议，未实现、未改代码。）

### 备用源同样不可用（今晚没有第二条腿）

- `fill-stock-daily-fallback` 依赖 `fact_sector_stock_daily` 当日成分，而成分也来自东财 → 0 行。
- `sync-stock-daily`（mootdx / 通达信 TCP 7709，与东财 HTTP 无关）：连接正常、
  `get_universe` 返回 5335 只，但 `bars()` 在 offset=5/180/800 下**一律返回空 DataFrame**。
  「元数据能拿、批量行情拿不到」与东财形状相似，可能有共同的出口侧原因。
  收据 `mootdx-feasibility.json`。**这是独立于本 PR 的一条待查线索。**

### 今晚其实拿到了什么（在被丢弃的 staging 里）

同花顺个股日线、板块 K 线、涨停池、龙虎榜/游资、竞价 5582 行、`fact_market_daily`、
申万一级 31 行、指数点位——全是 09-22。**唯独 `fact_stock_daily` 空**，而它是 17 张
下游表的地基，所以闸门判 INCOMPLETE 是正确的，不是误判。

### 遗留状态

- 缺口是**两个交易日**（09-21、09-22），主库停在 09-18，`/api/readiness` 仍 503。
- 失败的 staging（3.5 GiB）按流水线设计留作取证，下一轮 sync 会自动清理。
- 定时完好：`daily-full-review-sync@18:30`、`daily-full-review-finalize@20:40`，均未改动。
  明天 18:30 会自动重试；**若封禁未解，它会再失败一次，且重试更久**（见上方设计反馈）。
- 另发现（与本 PR 无关）：部署树 `market_feature_store.cli --help` 会抛
  `ValueError: unsupported format character '?'`——某条 help 文案里的 `%` 与中文混用导致，
  只影响 `--help` 渲染，不影响子命令执行。未修。

---

## 数据源全景（21:20 补查，回答「不是有同花顺 key 吗」）

**结论先说：下次遇到同类断档，先读
`skills/duckdb-backfill/scripts/backfill_stock_daily_sina.py` 的 docstring，别重头调查。**
那份 09-21 写的 runbook 已经把本机各源的失败形状记完了；我 09-22 晚上又原样重踩了一遍（mootdx
全部服务器 0 根、东财先通后整站拒连），一字不差。

### 同花顺：源是通的，数据已在库里，但不能直接搬

- 今晚 `sync-hithink-stock-daily` **成功**：`fact_stock_daily_hithink` 有 09-22 的 **5554 只**。
- **降低删除：两表 `turnover` 同名反义**——canonical 是**换手率%**（中位数 1.81），
  hithink 是**成交额（元）**（中位数 1.01e8）。直接 `INSERT ... SELECT` 不报错但彻底错位。
- 换算已验（与 09-18 canonical 逐位对平）：`amount亿 = turnover/1e8`、`volume手 = volume/100`、
  OHLC 直给。缺的是 **`stock_name`**（整套 hithink ingest 都不带名字）与 **换手率**。
- 换手率可以不管：本地计算链（`compute_local_stats.py` / `compute_features.py`）**一处也不读**，
  mootdx 路径早就留 NULL。
- 名字不能不管：它被当判据用——`LIKE 'N%'/'C%'` 判新股、`LIKE '%ST%'` 判 ST。
  实测近 5 日：ST 稳定 201 只（沿用昨日名字安全），N/C 每天 2~5 只（**当日状态，沿用会错**），
  XD/XR/DR 每天 7~23 只但**不匹配任何判据**，纯显示。

### 桥已存在，但它是「对账式修复」，救不了零基线的日子

`market_feature_store/sync/repair_hithink_stock_day.py`（库内 `hithink:daily-k-10d`
5547 行 = 2026-09-11，已实战使用）。字段映射与上述逐条一致，连「名字从旧行保留、
换手率置 NULL 并在报告声明」都写了。**但它的安全模型是「重建后逐行 diff 旧值，
白名单外即 `RepairRefused`」—— 09-11 有东财部分数据当基线，09-22 一行都没，
校验模型退化。** 另需每日手写 SPEC 差异处置表 + `scripts/reconcile_hithink_gate.py`。
不是能直接跑的通用命令。

### 推荐路线：新浪回补（此刻可达，已验）

- `hq.sinajs.cn` 21:00 实测 **HTTP 200 / 0.19s**。其 09-22 数据与同花顺**逐位吻合**：
  000001.SZ `open/high/low/close` 全等、`volume=75945732` 全等、`amount=887703116.58` 全等，
  **并且多给名字与官方昨收**（=11.730）——正好补上同花顺缺的那两样。
- 库内已有先例：`fact_stock_daily.source` 出现过 `sina:stock_zh_a_daily`（10167 行，
  09-08~09-16）、`fupanhui:...:fallback`、`ifind:...`、`mootdx` 等 11 种——**多源是设计内的**，
  靠 `source` 列区分审计，质检闸门**不钉源**。
- 正规入口是 `scripts/recover_local_review.py`（新浪取数 → 写 staging → 复用双闸门 → 全绿才发布），
  不直写生产。同花顺数据别浪费，正好当**第二源交叉验证**。
- 注意：`hq.sinajs.cn` 只给**当日**；补 09-21 要走 `stock_zh_a_daily`（历史日 K）那条。

### ★ 21:40–21:55 根因修正：不是 IP 封禁，是 `clist/get` 端点被针对

前面「按出口 IP 封禁」的判断**错了**，我自己推翻。决定性实验：同一台主机、同一个 IP、
连续三发（间隔 <0.3s）：

| 路径 | 结果 |
|---|---|
| `/` | **HTTP 404**（服务器正常应答） |
| `/api/qt/ulist.np/get?secids=1.000001` | **HTTP 200，有数据** |
| `/api/qt/clist/get?...` | **连接被掉** |

即：服务器愿意服务我们，**单单拒绝 `clist/get`**（快照用的全市场列表端点）。
又测：去掉 `fs`、只留 `pn/pz`、换 `fs` 值、加全套浏览器头——**clist 任何形状均被掉**。

**更重要：打 clist 会「毒化」客户端。** 6 连发 clist 之后，原本 200 的 `ulist.np` 也转为空回应；
冷却 45s / 75s 后仍未恢复。这解释了为什么 18:59 单发还能成功、而整跑必败。

同时排除了隔离层：东财有 IPv6（`240e:e1:9600:209:1000::197`），本机原生出口正是 IPv6
（240e:391 浙江电信），而 IPv4 走 utun5 隧道。**两个地址族、两组 IP 全部同样空回应**，
所以与代理/隧道/出口 IP 均无关。

#### 对本 PR 的含义

1. **本 PR 仍然正确且必要**（fake-IP 劫持是真的，重试不生效也是真的），但**不充分**：
   传输层修好了，端点本身不侍候了。
2. **重试阶梯现在是有害的**，而且比我之前说的更实：不是「可能自招封禁」，而是
   **实测会把同主机其他可用端点一起拖下水**。熔断建议升级为**合并前必做**：
   `clist` 连续 N 次空回应即判定端点不可用，立即停本轮并报独立错误码，**不要继续翻页**。
3. **新线索：`ulist.np/get` 可用**。它接显式 `secids=` 清单，字段号与 clist 同一套。
   若能批量拿全市场（分批 secids），就是快照的替代实现路径。**待验证**：今晚客户端已被
   clist 毒化，测不准；请在**长时间未发 clist** 的干净状态下重测。

### 下一个人的待办

1. **明天 18:30 会自动重跑**，并向一个已知不侍候的端点发 60 页 × 重试，连带毒化其他端点。
   先加熔断（见上），或暂时把快照步骤改为非阻断。
2. 09-21 + 09-22 两天缺口：走新浪回补（需授权，会写库）。新浪 21:55 复测仍 200/0.18s。
3. 验证 `ulist.np` 能否批量代替 clist——若可行，这是比换源更小的修复。
