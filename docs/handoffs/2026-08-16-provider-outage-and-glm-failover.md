# 2026-08-16 中转全站中断 + GLM 失败转移（8792 生产线）

roadmap_ref: 运行时可用性。账本新号 `R-20260816-16`..`21`（**不要用** dsh 草稿里的 06–11，那些号在 main 上已占用）。

> 第一份交接写在 `docs/dsh-absorption-spec` 工作区，未提交。本文件是落到
> `gitea/main` 的干净副本：事实保留，案号重编号，§7 接到当前现场。

---

## 1. 一句话状态

**中转 `x.ailzd.com` chat 仍 5xx；8792 已切 GLM 主 / 中转兜底（pid 90194）。**
provider 层修好了，交付层没有：原题复跑有工具、有模型字，repair 30s 卡在 GLM p90 底下。

## 2. 冻结事实

| 项 | 值 |
|---|---|
| 故障单 | `run_20260816_221823_213588`（user=`default`，8792） |
| 指纹 | `draft=""` / `tool_calls=0` / `llm_calls=16` / `stop_reason=repair_model_unavailable` |
| 真成因 | seq=2 `LLM 调用 HTTP 503`，4 attempt 全败，6.1s 内（`timeout_asked=69.88s`，不是超时） |
| 中转（23:02 复探） | `/v1/models`=200；terra chat **503**。`/models` 绿不代表 completions 可用 |
| 官方 GLM paas/v4 | 同 key **429** 余额不足 |
| GLM Coding Plan | chat **200**（Keychain `finance-workbench-glm`） |
| 8795 | 22:23 切 Coding Plan，11 单零 5xx。pid **73668** / `16f2cd47`。属主 cursor-agent **41109**，未停 |
| 8792 | launchd `com.a77.finance-workbench`。启动器已加 GLM 三件套。pid **90194** / `6cd0756e` dirty=false |
| 链 | `[0] zhipu/glm-5.2@coding/paas/v4` + `[1] openai/gpt-5.6-terra@x.ailzd.com` |
| 回滚 | `~/.local/bin/start-finance-workbench.bak-20260816-glm`（sha256 前缀 `275b7c0e1f5bc775`），再 `launchctl kickstart -k` |

时间线：20:54 default 正常 → 21:57 r13-starve×4 HTTP 503 → 22:18 本单 503 → 22:23 8795 切 GLM → 22:24–22:47 r13×11 正常 → 23:04 8792 kickstart → 23:05 原题复跑。

`draft=0 / tools=0 / llm=16` = 单链死 provider × 4 轮 × 4 attempt。见到 16 先查出口。

## 3. 前一份报告不要沿用的错

1. 「现在没法答」——说这话时 8795 GLM 已经在跑。
2. 一级修复不是「熔断 + 更快失败」，是 **provider 失败转移**。
3. 「模型轴已定 gpt-5.6」是 08-05 决定，不是代码限制；`continuous_glm` 不检查 name。

## 4. 配置（已落地，不是代码）

`detect_providers()` 有序链。只设中转时链长=1，命中 `_retry_single_real_provider`，同一死出口重试 16 次。加上 GLM 三件套后链长=2，GLM 排 `[0]`。

用户 23:02 拍板：**GLM 做 primary**。启动器已按此写。要「中转优先」才需要改排序代码。

副作用：挡住将来切 `sdk_gpt`（`providers[0].name` 必须是 openai）。当前 backend 是 `continuous_glm`，现在安全。

## 5. 进程

| 对象 | 状态 |
|---|---|
| cursor-agent **17907** | 已 SIGTERM。它在 `~/.finance-runtime/` 找 trace，路径错；生产 run 在 `FORESIGHT_USERS_DIR`，那单是 `default` 不是 `linxiaoqi5111` |
| cursor-agent **41109** | **未动**。r13-starve 属主，8795 是其子进程。22:19 写 GLM 启动器，21:57 四单污染已排除 |
| 8795 | 未动 |
| 8792 | 已 kickstart，87031 → **90194** |

## 6. 分诊摘要

- PRIMARY：上游 completions 全站不可用。
- SECONDARY：降级把机械中断写成「现有证据不足」。真话在 `_STOP_REASON_CAUSES`，挂在默认 off 的 `ASK_DEGRADED_FALLBACK` 后面。
- TERTIARY：缺口模板「反证」命中 `_MARKERS["counterpoint"]`，与 structural 冲突。
- 独立：`_OUTPUT_DESCRIPTIONS` 18 个题型里 10 个缺键，静默回落成裸 `output_id`。

## 6b. 原题复跑（`user=verify-glm-0816`）

`run_20260816_230528_976709`：zhipu、零 5xx、tools=4 / evidence=25、模型 72+1395 字。
**`outcome.draft` 终值仍 0，required fulfilled 0/4。** provider 层过了，交付层没有。

```
14.9s  首轮 model_turn ok（72字 + 5 tool）
26.3s  finalization retrieval_deadline_closed
60.9s  合成 1395字
61.0s  deadline_exhausted → repair 授予 30s
91.2s / 121.5s  两发 TimeoutError → repair_model_unavailable
```

8795 上 GLM 成功轮 n=32：p50=17.3 / p90=34.4；6/32 >30s。
`_REPAIR_SECONDS_CAP=30` 按 terra 9–15s 定的。**禁止直接调大 30**（`R-20260816-02` / `-07` 绊线）。正确形状是窗口随生效 provider 的实测 p90 走。

复跑降级文案走到 `_gap_answer` 中间档（有 25 条证据）。22:18 那单 evidence=0 没走到这档。

## 7. 下一个 agent 从这里接

§4–§6b 已做完。不要再探一次就重 kickstart，不要停 41109/8795。

1. **`R-20260816-17`**：成因行从 `ASK_DEGRADED_FALLBACK` 拆出。`llm.used=false` 或 `repair_model_unavailable` 时首句必须是「模型服务不可用」，不能是「现有证据不足」。
2. **`R-20260816-21`**：repair 窗随 provider p90，不把 30 调成新常数。须附分档延迟实测 + 全路由影响面；非研究题不得变慢超 5pp。
3. **`R-20260816-20`**：补 `_OUTPUT_DESCRIPTIONS` 10 个缺项，静默回落改启动期失败。与中断无关，可独立开 PR。
4. `R-18` / `R-19` 按账本排期。
5. `R-16` 部分验证：链长=2 且本复跑零 5xx，但 draft 终值 0，**不得写 confirmed**。

部署 8792 代码仍走 launchd + 快照软链，不要 `kill` + `nohup`。

## 8. 别再踩的坑

- `/v1/models` 200 ≠ completions 可用。
- 「现有证据不足」先看 `llm.used` 和 `tool_calls`；两个都是 0 时一次检索都没发生。
- 生产 run 不在 `~/.finance-runtime/`，在 `FORESIGHT_USERS_DIR/users/<user>/runs/`。
- 读 8792 代码用 `finance-workspace-runtime` → `6cd0756e`，不要用 `docs/dsh-absorption-spec` 那棵脏树。
- dsh 草稿把本事故写成 `R-06`..`11`：**那些号在 main 上已是 judge 窗 / 绊线 / 判断槽结案**。本文件用 16–21。
- `ps eww` 会带出中转 key。会话外传须轮换 `finance-workbench-test-relay`。
