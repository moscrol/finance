# 同花顺数据请求断线恢复实施计划

**Goal:** 偶发断线在请求层恢复，持续失败仍停止夜跑发布。

**Architecture:** 复用 `market_feature_store/hithink_client.py:get_json` 的请求次数、退避与失败出口，仅将标准库直接抛出的临时网络异常纳入原分支。标准库 urllib，现有 pytest 夹具；独立工作树，逐项执行。

1. 在 `tests/test_hithink_stock_daily.py` 复用 `_arm` / `_OkResp`，参数化响应前与正文读取时的 `RemoteDisconnected`、`IncompleteRead`、`ConnectionResetError`、`TimeoutError`、`SSLEOFError`。一次失败后完整响应应成功；连续失败应恰好 3 次、等待 `[0.5, 1.0]`。保存旧实现失败输出。
2. 在客户端增加 `http.client`、`ssl` 导入；将原异常分支改为：

   ```python
   except (
       urllib.error.URLError, http.client.RemoteDisconnected,
       http.client.IncompleteRead, ConnectionResetError, TimeoutError,
       ssl.SSLEOFError,
   ) as exc:
   ```

   分支内部不变；不扩大到所有异常。
3. 用已固定依赖的 `.venv-workbench/bin/python -m pytest -q tests/test_hithink_stock_daily.py tests/test_hithink_sector_kline.py tests/test_hithink_sector_capture_integration.py tests/test_review_sync_hithink_wiring.py` 跑客户端与调用者回归；Ruff 与 diff 检查通过。
4. 保存固定提交，按 `code-review` 做规格与仓库标准两轴复核。固定候选运行隔离数据续跑；保存全部失败收据，不反复运行挑绿。
5. 完成数据门禁、独立值审计、生产基线身份检查与换库备份，回读 health/readiness；开 GitHub PR 并通过 Actions。主干合入和永久夜跑代码根切换留待明确确认。
