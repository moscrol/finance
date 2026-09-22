# 东财快照传输层修复（在途）

分支 `fix/eastmoney-snapshot-direct-ip-0922`，基线 `gitea/main@a2c8d1f90`，工作树
`~/fwp-wt-eastmoney-direct-ip-0922`。**未部署、未合并、未重跑流水线。**

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
- 未碰任何数据库、未部署、未重跑、未动他人工作树。
