# 2026-09-21 同花顺 429 全局限流退避 — 决策留痕

分支 `claude/hithink-429-retry-handling-80eeca`，提交 `dd2fae334`。
代码契约（这段代码**做什么**）写在 `docs/data-sources/hithink-research-data.md`
的「429 处置」节；本文只记**为什么这么选**、否了什么。

## 背景（不读会误判后面每个决定）

09-21 10:21 盘中真实采样时，`sync_hithink_research` 第一个请求（异动）成功 191 行，
第二个（估值）返回 HTTP 429 `Global request rate limit exceeded`，整轮中止，
后面的热度请求**根本没发出**。10:24 三端点全 429，10:31 恢复——窗口约七分钟。
02:05 那次四个请求全部成功，所以**夜跑 18:30 时段会不会撞上，至今无证据**。

原始响应落盘在 `~/.finance-runtime/hithink-anomaly-sample-20260921T1020/valuation-probe.log`：
正文是**合法 JSON** `{"code":429,"message":"..."}`，头只有 Date / Content-Type /
`Server: Stargate`，**没有 Retry-After**。

## 按发现顺序

1. 本分支初始停在 merge-base（= `gitea/main` 728f32716）。先只 diff 了
   `hithink_client.py`，两边相同，据此说了一句「运行时代码两边一致」——**这是错的**。
   `git diff --stat` 全量显示 feat 多出 372 行的采集器、schema、CLI 接线和约 700 行测试。
   在 main 基线上改，既跑不了采集器也验不了。→ 快进到 `7596751d8` 再动手。
2. 读代码定位：429 走的是「code 既非 0 也非 4001 → 立即抛错」。另有一条同样不重试的路径：
   正文非 JSON 时抛「非 JSON 响应」——网关限流返 HTML 时就会走这条。
3. 算了一下现有退避总额：`retries=4` 是 0.8+1.6+3.2 ≈ **5.6 秒**，而窗口约 **7 分钟**。
   → 直接复用它等于把同一个失败推迟六秒。这一步改变了整个方案。

## 决策

| 决策 | 否掉的方案 | 理由 |
|---|---|---|
| 退避额度用**独立墙钟预算**，不占 `retries` | 复用 `retries=4` 那套指数退避 | 比值 5.6s ÷ 7min ≈ 0.013。重试的价值由「退避总额 ÷ 故障窗口」决定，不由「有没有重试」决定；该比值远小于 1 时，重试是伪装成修复的延迟 |
| 默认预算 **300 秒** | 600s+（足以覆盖整个实测窗口）；或沿用「不退避」 | 300s 能吃下瞬时限流，又不会让一次夜跑静默阻塞十分钟以上。**敢不敢覆盖整个窗口是「夜跑愿意阻塞多久」的取舍，属于用户的决定**，所以暴露成 `rate_limit_budget_seconds` 参数 + `HITHINK_RATE_LIMIT_BUDGET_SECONDS`，置 0 即回到旧行为 |
| **先判 HTTP 状态，再判业务码** | 只把 429 加进 code 白名单 | 只认 code 的话，网关返非 JSON 正文时仍撞「非 JSON 响应」并抛错。两条不重试路径要一起堵 |
| 支持 `Retry-After`（秒数 + HTTP-date），单次封顶 60s | 不支持（反正上游不发） | 上游换网关实现就会有；到那时应当听它的而不是继续按自己的指数退避猜。封顶是防上游给离谱值把夜跑挂死 |
| 耗尽仍**失败关闭**，错误带 `budget/spent/attempts` | 退化成跳过该请求继续 | 静默跳过会让一份缺数据的采集看起来成功。归因信息放进消息里，且不含 key |
| **不动编排层** | 让单请求失败不中止整轮（走已有的 `complete_with_gaps`） | 超出本轮授权范围。已记在 `hithink-research-data.md`：`_capture` 单请求失败即 `raise`，`complete_with_gaps` 对抛出型失败够不到 |
| 叠在 `feat/hithink-research-data` 之上，推**自己的分支** | 直接推 feat（更新 PR #810 head） | feat 在 `/Users/a77/fwp-wt-hithink-research-data` 有活跃 worktree、tip 是今天的；从这棵树推会让那棵树落后于自己的分支。PR 落点留给用户定 |

## 验证与收据

- 全量 pytest 在 `dd2fae334`：**11975 passed / 0 failed / 85 skipped / 2 xfailed，exit 0**。
  收据 `~/.finance-runtime/test-receipts/20260921T033414Z-dd2fae33.json`（`dirty:false`）。
  **同 revision 另有一份 `20260921T032247Z-dd2fae33.json` 是 counts 全 0 的空跑**，按 revision
  取收据时会撞上它，取最新那份。
- ruff 全树通过；12 道 pre-commit 全过。
- 三次定点变异，各只红对应层、邻层保持绿：关掉 429 识别 → 红 6 条；`_retry_after_seconds`
  恒返 None → 红 3 条；拿掉预算检查 → 红 3 条。`test_4001_retries_then_ok` 与
  「非限流码立即失败」在三次变异下都保持绿。

### 不成立的结论

- **没有真实 429 复现**。新路径只被离线替身压过，真实网关上「退避后重试成功」的样本 **= 0**。
- Retry-After 两种形态都只在替身上验过。
- 默认 300s **短于**实测窗口上沿，救的是瞬时限流，不保证救得了一次完整全局窗口。

## 后续要做的

1. 用户定 PR 落点：并入 #810，还是以 feat 为 base 开栈式 PR。
2. 盘后 18:30 之后在隔离库跑一轮全采集，取夜跑时段的限流证据。
3. #810 的独立 Spec/Quality 等 09-27 Codex 额度恢复；若并入，审查范围要覆盖本修复。

## 不要做的

- **不要把默认预算直接调到 600s 以上当作「修得更彻底」**——那是让夜跑静默阻塞十分钟的决定，
  要用户明确点头，并且最好同时有一条「阻塞多久」的可观测信号（当前模块**刻意没有日志**，
  为的是 key 卫生）。
- **不要把 429 退避当成编排层问题的解**。退避只降低触发概率；单请求失败中止整轮这个形状没变。
- **不要在 main 基线上改这块**——采集器只在 feat 上。
