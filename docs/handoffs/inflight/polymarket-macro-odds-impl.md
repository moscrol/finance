# polymarket-macro-odds-impl

## 这个分支做什么
Polymarket 公开 API（gamma-api，只读 / 免费 / 无 key）→ 宏观·地缘·加密事件隐含概率按日快照落
`fact_polymarket_macro_odds_daily`。刻意**只落库**：不接夜跑、不进 registry——agent 怎么引用
（独立信号 or 仅人工参考）未定。

## 当前状态
已提交 `2eacbbe7`，11 道 pre-commit 全绿。**未合并 main**——合并须用户确认。

## 决策与被否方案
- **过期市场入库前剔除**（`_is_expired`）：上游 `closed=false` 不可信，实测 328/1106 行截止日早
  于快照日、324 行概率退化 0/1。否了「加 is_expired 列让下游过滤」——这些行成交量大、按 volume
  排序占头部，长得跟前瞻概率一样，指望下游记得过滤是把坑留给别人。
- **单次坍塌必须重试**（3 × 15s，天花板仍 45s）：不重试则夜跑约 1/3 夜晚落 0 行。否了「加长单次
  预算」——病态时 0.02MB/s，读完 9.85MB 要 ~500s。
- **维持「一次大请求 + 客户端白名单过滤」**：否了服务端 `tag_slug`（生效但包体由每 event 内嵌
  market 数决定 ~100KB/event，按 14 个 tag 各发一次总字节更多、各担 ~37% 坍塌率）。

## 未验证 / 已知边界
- **生产库里这张表还不存在**——没往 `db/market_feature_store.duckdb` 写过（实跑用 `MARKET_FEATURE_STORE_DB` 指临时库）。
- 3 次全挂仍会发生（5 次实测里 1 次）：耗满 45s、0 行、标 `truncated=True`、印「部分快照」。
  是诚实降级不是静默失败；接夜跑前要定「0 行算不算失败」。
- `truncated=True` 只印在 stdout，**没落库没落台账**——下游查表看不出今天是部分快照。
- 未进 `consumption_registry.yaml`；无历史回填（接口无历史参数，只能日积月累）。

## 下一步
1. 用户定这张表 agent 怎么引用，再决定接不接夜跑。
2. 若接夜跑：把 `truncated` 落进库或 ops 台账，否则下游分不清部分快照与全量。

## 踩过的坑
- 覆盖率审计只数行数，抓不到「行在、值是旧答案」这种语义陈旧（本例即 `closed=false` 的过期市场）。
- 病症不是「挂死」是**吞吐坍塌**（1.2~2.4MB/s → 0.02MB/s），字节一直涓流所以
  `urlopen(timeout=)` 的 socket 超时**永远不触发**，必须自己按时长掐。
- `deadline` 只在两次 chunk 之间查，单次 `read()` 阻塞时管不着——真实上限是 deadline +
  socket_timeout（实测 8s 预算跑到 11.7s）
- 测试假数据第一页只放 1 个事件会触发「短页 = 最后一页」提前退出，走不到第二页；要测分页 / 重试
  得让第一页「满页」（`page_size=1`）。

## 已验证
9 passed；ruff 绿；`registry-check` + `audit_dataset_registration.py` 过。真实端到端 8 次：778 行
/ 53 事件 / 389 市场、4~6s，过期残留 0、每市场概率和 = 1.00。详见 `docs/handoffs/2026-09-10-polymarket-macro-odds.md`。
