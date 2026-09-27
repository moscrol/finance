# 2026-09-27 LLM 调用「越窗 38 分钟」定性为主机睡眠，只补可观测

代码提交 `cf09cae44`，分支 `fix/llm-host-suspend-observability`，基线 `gitea/main@85bcee6dc`。
未合 main / 未部署 / 未碰生产 8792。

## 背景

生产 8792（运行 `4f334a6da0af`），用户 `deploy-probe`，`run_20260927_211317_791596`：
`continuous-episode.json` 里 turn-3 的 `model_intent`（21:13:33，`timeout_asked=75.0`）与
`model_turn`（21:52:13，`error="LLM 调用失败（LLMDeadlineExceeded）"`，`provider_attempts=2`）
墙钟隔 2320 秒，`stream.jsonl` 同样静默 2320 秒；随后 `planning_model_unavailable` 进收尾，
交付降级的「证据不足」答案。GLM 网关前后都正常应答（1–6 秒）。

任务书的假设：一条连接卡死或滴流，传输层没在绝对截止切断；要查 connect / TLS / 首字节 /
流中读 / SSE 行读哪一步能活过截止，修成「到点关 socket 的看门狗」。**这个假设不成立。**

## 按发现顺序

1. **读传输层**（`llm_http_transport.py`，#868）。网络全在 `python -I` 子进程里做；父进程只
   `select` 等管道，超时取剩余时间，每轮 `_check()`，到点抛 `HTTPDeadlineExceeded` 并 SIGKILL
   子进程；子进程另有 `threading.Timer → os._exit(124)` 兜底。父侧没有「收到一个字节就重置」的
   空闲超时，DNS / connect / TLS / 首字节 / 流中 / SSE 行卡在哪一步都一样被切。
2. **对账 episode 自己的预算字段**。turn-3 入场 `remaining_seconds_at_entry=584.747`
   （21:13:33.285），turn-4 入场 `509.538`（21:52:13.271）：预算钟走了 75.209 秒，墙钟走了
   2319.986 秒，有 2244.8 秒预算钟没看见。**截止是准的——按它自己的钟。**
3. **`pmset -g log`**：21:14:20 `Entering Sleep state due to 'Clamshell Sleep'`（电池 23%）978s →
   21:30:38 DarkWake 2s → 睡 976s → 21:46:56 DarkWake 2s → 睡 299s → 21:51:57 `Wake`（开盖 / HID）。
   合计 2253 秒，与 2244.8 秒差 8 秒（进出睡眠的过渡里进程还在跑）。醒来 16 秒后截止触发。
4. **本机时钟**：`time.get_clock_info('monotonic')` 是 `mach_absolute_time()`，睡眠时停走；此刻
   `CLOCK_MONOTONIC_RAW − time.monotonic()` = 221657 秒 ≈ 61.6 小时，就是开机以来的累计睡眠。
5. **任务书第 2 步（离线停滞 / 滴流复现）**：#868 的 `test_llm_timeout_diagnostic` 已有真实本地端点
   8 个慢响应场景（`header_delay` `body_stall` `headers_then_body` `body_trickle`
   `tools_stream_trickle` `tools_stream_partial_line` `synthesis_stream_trickle`
   `synthesis_stream_partial_line`）外加判官迟到回包等，全文件 35 passed；生产 `4f334a6` 到基线之间
   `llm_http_transport.py` 零差异。没有再写一套重复的。
6. 定性后把语义问题交给用户（下表第一行），用户选「只补可观测」。

## 决策与被否方案

| 决策点 | 方案 | 评价 | 结果 |
|---|---|---|---|
| 截止计不计主机睡眠 | A 只补可观测：预算照旧「睡眠即暂停」，事件带 `host_suspended_seconds` | 零行为变化，下次一眼看出是睡眠 | **选**（用户 2026-09-27 拍板，依据是上面 2–4 的对账） |
| | B 仅传输层计睡眠（含睡眠钟 + ≤1 秒等待切片，醒来即截断） | 本次会在 21:30 的 2 秒 DarkWake 就截断转收尾，收尾调用又被下一次睡眠截断；短暂合盖（TCP 重传还能送达）也被迫降级——本次事件链里一次 `LLMDeadlineExceeded` 就直接 `planning_model_unavailable` 进收尾 | 否 |
| | C 全部预算计睡眠（传输 + 600 秒根预算） | 语义一致，但 `Deadline` / `ResearchDeadline.expires_at` 与大量裸 `time.monotonic()` 混用，两钟在本机差 61.6 小时，漏改一处 = 永不超时或立刻超时 | 否（范围与风险） |
| | D 可观测 + 醒后续跑（跨长睡眠的调用醒来即按可重试连接失败中止重发） | 体验最好；要设计重试计数，且 DarkWake 期间会白发请求 | 否，留作后续可选 |
| 含睡眠的钟 | macOS `CLOCK_MONOTONIC_RAW`、Linux `CLOCK_BOOTTIME`，减 `time.monotonic()` | RAW 与 `mach_absolute_time` 同为不受 NTP 调频的原始钟，差值只剩睡眠；macOS `CLOCK_MONOTONIC` 也含睡眠但受调频（21 天漂 5 秒） | 选 |
| | 墙钟 `started_at` / `completed_at` 相减 | NTP 或手改时间会跳 | 否 |
| 字段落点 | 三处 `model_turn`（主循环 / 修复轮 / 兜底合成）+ `LLMCallRecord`，同名 | 分诊看的就是 `model_turn`；调用记录与 `elapsed_ms` 并排；同名好 grep | 选 |
| | 传输层 observer 事件 | 生产没接 observer | 否 |
| | 公开 `report.json` / `gate_receipt` | `RECEIPT_KEYS` 被测试钉死（schema v1），可观测字段按惯例进私有块 | 否 |
| 单位与缺省 | 秒，3 位小数；平台量不到为 `None` | 与 `remaining_seconds_at_entry` 同单位；`None` 不冒充 `0.0`「确认没睡」 | 选 |

## 改了什么

- `llm_http_transport`：`host_suspended_total()` / `host_suspended_since(anchor)`；模块文档写明截止在
  主机睡眠时暂停。测试缝是 `_suspend_inclusive_clock`。
- `llm_refine`：`_new_call_attempt` 取锚点，`LLMCallRecord.host_suspended_seconds`；
  墙钟跨度 ≈ `elapsed_ms / 1000 + host_suspended_seconds`。
- `agent_episode`：三处 `model_turn` 都带 `host_suspended_seconds`，锚点与 `model_started` 同时取。

## 验证与收据

- 新测试 8 条（`test_host_suspend_clock` 5 条、`test_agent_episode` 3 条），时钟注入模拟调用中途合盖
  2245 秒：记录与 `model_turn` 如实报出，`elapsed_ms` 与根预算不扣睡眠。
- 变异 7 杀 0 存活：三处 `model_turn` 删字段、记录删字段、删尝试锚点、锚点改到结算时取（值变 0.0）、
  根预算改计睡眠（暂停语义的钉子）。初版「删锚点那一行」红在 `NameError`——红错原因，已换掉。
- 定向 1143 passed（`cf09cae4`，收据 `~/.finance-runtime/test-receipts/20260927T144209Z-cf09cae4-058efdc3e3ac.json`）。
  更早一轮 1445 条是边改注释边跑的混合读数，1 红 `test_shared_window_zero_rejection_is_not_a_third_request`：
  负载约 11、10 个 pytest 并跑，亚秒窗口下 worker spawn 赶不上（#868 记过的已知代价），单跑 5/5 绿，
  干净读数里也绿。
- ruff 全仓通过；pre-commit 13 道通过（含 unread-fields、layer-audit）。
- **不成立 / 没压到的**：测试不能让本机真睡，「所选时钟睡眠时继续走」只由本次 pmset 与 61.6 小时差值实测
  支撑——若有人把 darwin 的钟换成 `CLOCK_UPTIME_RAW`，全部测试照绿（醒着时两钟同速）。
  Linux `CLOCK_BOOTTIME` 分支本机没跑过。全量 pytest 与前端叶子本轮没跑（WIP PR，合入前补）。

## 后续要做的

- 部署后遇到下一次合盖，验收 `model_turn.host_suspended_seconds` ≈ pmset 的睡眠时长。
- 真要做 D（醒后续跑）或 C（墙钟预算），先读上表的否决理由；D 的前提是改掉「一次截止错误就进收尾」。
- 运维：8792 跑在笔记本上，电池供电合盖一定进 Clamshell Sleep，`caffeinate` 这类电源断言挡不住；
  长跑 probe 前接电或别合盖。

## 不要做的

- 别为这类空档改传输层的停滞 / 滴流逻辑：#868 场景下它按绝对截止切断，本次截止实际准时。
- 别把 `time.monotonic()` 全局换成含睡眠的钟：两钟在本机差 61.6 小时，与 `expires_at` 混比就是灾难。
- 别把 `host_suspended_seconds` 塞进公开 `gate_receipt`（schema v1 键钉死）。

## 可迁移知识点

- **monotonic 不等于墙钟。** macOS `time.monotonic()` 与 Linux `CLOCK_MONOTONIC` 都不计休眠；计不计是
  语义决定，关键是日志分得清两者。
- **分诊「超时越窗」先三方对账**：预算字段 vs 事件墙钟 vs 系统电源日志（macOS `pmset -g log`，
  Linux `journalctl | grep -i suspend`）。对不上任何一条预算边界，就是归因错层的信号。
