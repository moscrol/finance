# 2026-08-16 中转全站中断 + GLM 失败转移（8792 生产线交接）

roadmap_ref: 另案（运行时可用性）。分诊报告见本文件 §6；账本 `docs/prediction-ledger.md` 第 9 轮。

> 本文件写在主 checkout（分支 `docs/dsh-absorption-spec`），**未提交**。
> 起因：用户 22:18 在 8792 问「国产算力处于发酵/共识/透支期」，拿到一句
> 「现有证据不足」。分诊结论：不是证据问题，是模型出口挂了。

---

## 1. 一句话状态（2026-08-16 23:10 更新）

**中转 `x.ailzd.com` 全站 502/503 且仍未恢复；8792 已切成「GLM 主 / 中转兜底」并重启（pid 90194），provider 层已修好——模型能跑、工具能调、证据能取。但原题仍交付不出来，阻塞点换成了 repair 窗口与 GLM 延迟错配（30s 硬顶 vs p90 34.4s）。详见 §6b。**

> §2 与 §4 是**事故当时**的冻结快照（8792 尚未切换），保留供溯源；现场当前状态以 §5 + §6b 为准。

## 2. 冻结事实（事故当时，都是实测不是推断）

| 项 | 值 | 取证方式 |
|---|---|---|
| 故障单 | `run_20260816_221823_213588`（user=`default`，8792） | 落盘 artifact |
| 症状指纹 | `outcome.status=failed` / `draft=""` / `tool_calls=0` / `llm_calls=16` / `stop_reason=repair_model_unavailable` | `continuous-episode.json` |
| 真成因 | `events[seq=2].error="LLM 调用 HTTP 503"`，4 次 provider attempt 全败，**6.1s 内**（`timeout_asked=69.88s`，故不是超时） | 同上 |
| 中转当前状态 | `GET /v1/models → 200`；`POST /v1/chat/completions` 对 `gpt-5.6-terra` / `gpt-5.6-sol` / `gpt-5.4` / `gpt-5.3-codex` **全部 502 `upstream_error`** | 分诊时点直接探测 |
| 鉴权/分组正常 | `gpt-5.6` 单独返 403「不在当前 group」——证明不是 key 失效、不是配额 429 | 同上 |
| 8792 当前指向 | `LLM_BASE_URL=https://x.ailzd.com/v1`、`LLM_MODEL=gpt-5.6-terra`、`AGENT_RUNTIME_BACKEND=continuous_glm` | `ps eww -p 87031` |
| **GLM 那条路是好的** | 8795 于 **22:23:43 重启**换成 `open.bigmodel.cn/api/coding/paas/v4` + `glm-5.2`，此后 11 单全部正常：draft 576–894 字、tools 3–6、3 单 `completed`、**零 5xx** | `users/r13-starve-0816/runs/` 逐单读数 |
| 8792 代码根 | `finance-workspace-runtime` → `finance-workspace-6cd0756e4a61`（`6cd0756e`） | symlink |

### 当日故障时间线

```
14:42–14:53  longtail-ab ×9   URLError      draft=0 tools=0 llm=16   ← 同形中断（另一段）
20:54        default          正常          draft=688 tools=12       ← 出口那时还活着
21:57        r13-starve ×4    HTTP 503      draft=0 tools=0 llm=16   ← 中转开始挂
22:18        default（本单）   HTTP 503/502  draft=0 tools=0 llm=16   ← 用户这一问
22:23:43     8795 重启 → GLM
22:24–22:47  r13-starve ×11   正常          draft 576–894            ← GLM 路正常
```

`draft=0 / tools=0 / llm=16` 是 provider 硬故障的稳定指纹（16 = 4 轮 × 4 attempt）。见到 16 先查出口，别查预算。

## 3. ⚠️ 前一份分诊报告的错误（必读，别沿用）

我在第一版分诊里把这次故障写成「唯一挡住答案的因素，只能等中转恢复」。**这是错的**，用户当场纠正：两条路本来就只是 provider 差异，GLM plan 可用。

具体错在三处：

1. **「现在没法答」是错的**。说这话时 8795 上的 GLM 路已经正常跑了约 25 分钟。
2. **修复建议的形状错了**。原 `R-20260816-06` 提的是「熔断 + 快速失败 + 如实告知」——那只让失败更快更诚实，**不让它成功**。正确的一级修复是 **provider 失败转移**。
3. **把「模型轴已定 gpt-5.6」当成了技术约束**。那是 2026-08-05 的一个决定，不是代码限制；`continuous_glm` 壳是 provider-neutral 的。

`R-20260816-06` 已在账本中改写为失败转移口径，`07`（成因行）降为二级——它仍要做，但它是「转移也失败之后怎么说话」。

## 4. 修复方案：这是配置改动，不是代码改动

### 4.1 关键机制（实测）

`llm_refine.detect_providers()` 返回的是**有序 fallback 链**，`GLMModelClient` 吃的就是这条链（docstring：*"the adapter is provider-neutral: when callers inject `providers` it owns one explicit, ordered chain"*），`llm_refine.py:730/830` 遍历它。

两个 key 同时设置时的实测结果：

```
链长度 = 2
  [0] name=zhipu   model=glm-5.2       base=https://open.bigmodel.cn/api/coding/paas/v4
  [1] name=openai  model=gpt-5.6-terra base=https://x.ailzd.com/v1
```

**当前 8792 的链长度是 1**（启动器只设了 `OPENAI_API_KEY`+`LLM_BASE_URL`）。链长为 1 时会命中 `glm_agent_runtime.py:84` 的 `_retry_single_real_provider`，于是变成「在同一个死 provider 上重试 4 次」——这正是 `llm_calls=16` 的来源。**链上有第二个 provider 就不会这样。**

### 4.2 动作

在 `/Users/a77/.local/bin/start-finance-workbench` 里把 GLM 三件套加回来（key 从 Keychain 取，条目 `finance-workbench-glm` 已存在，**不落盘**）：

```zsh
export FORESIGHT_BUILTIN_LLM_API_KEY="$(security find-generic-password -s finance-workbench-glm -a a77 -w)"
export FORESIGHT_BUILTIN_LLM_BASE_URL="https://open.bigmodel.cn/api/coding/paas/v4"
export FORESIGHT_BUILTIN_LLM_MODEL="glm-5.2"
```

然后按蓝绿纪律重启（**属主是 launchd，不要手工 kill + nohup**）。

### 4.3 三条必须知道的副作用

1. **GLM 会变成 primary，不是 fallback**。`detect_providers` 先查 `FORESIGHT_BUILTIN_LLM_API_KEY`（`llm_refine.py:189`）再查 `OPENAI_API_KEY`，所以 GLM 排 `[0]`。要「中转优先、GLM 兜底」得改排序逻辑——那才是代码改动。**先确认用户想要哪种**。
2. **这会挡住将来切 `sdk_gpt`**。启动器里删 GLM 三件套是刻意的：`built_in_provider()`（`llm_settings.py:182`）见到该变量就把 `providers[0].name` 硬编成 `zhipu`，而 `api/app.py:251` 硬要求 `sdk_gpt` 的 `providers[0].name == "openai"`。**当前 backend 是 `continuous_glm`，它不检查 name，所以现在加回来是安全的**；只是壳轴 A/B 要切 SDK 那天得先处理排序。
3. **这动到了 2026-08-05 记录在案的「模型轴已定 gpt-5.6-sol、GLM 退役」决定**。用户 2026-08-16 已口头确认 GLM plan 可用；但账本/项目笔记里那条决定需要相应更新，别让下一个 agent 读到过期那份。

## 5. 现场状态（我改了什么、停了什么）

| 对象 | 状态 |
|---|---|
| cursor-agent **pid 17907** | **已 SIGTERM 停止**（20:49 起，闲置无子进程）。它就是在 `~/.finance-runtime/` 里找 trace 的那个——路径找错了，生产 run 在 `~/.local/share/finance-workbench/users/<user>/runs/`，且那单挂在 `default` 用户下不是 `linxiaoqi5111` |
| cursor-agent **pid 41109** | **未动，仍在运行**。它是 r13-starve 的属主（8795 是它的子进程）。**它没做错**：自己发现中转 5xx、22:19 生成 `start-sidecar-glm.generated.sh`、22:23 切 GLM、写了 `provider-window.json` 记录切换、`score.json` 只取切换后的 11 单（`n=11`），21:57 那 4 单污染读数已排除 |
| **8795** | 未动，GLM 正常服务 |
| **8792** | ~~未动~~ → **已切 GLM 主 / 中转兜底并重启（pid 90194）**，详见 §6b |
| `docs/prediction-ledger.md` | 已加第 9 轮回填表 + `R-20260816-06..10`；**06 已按 §3 改写**。未提交 |
| `docs/trace-profile.md` | 已加 7 条字段陷阱 + 3 条盲区。未提交 |
| skill `known-gaps.md` | 登记 G-002 / G-003 两条 taxonomy 缺口 |

**代码与文档：未提交、未合并。** 分支 `docs/dsh-absorption-spec`（`d98a8a59`）。

⚠️ **但生产配置已改并已重启**：`/Users/a77/.local/bin/start-finance-workbench` 加了 GLM 三件套，8792 已按 launchd 重启（§6b）。该文件不在 git 里，回滚用备份 `start-finance-workbench.bak-20260816-glm`（sha256 前缀 `275b7c0e1f5bc775`），回滚后需再 `launchctl kickstart -k` 一次。

## 6. 分诊结论摘要（全文见 `/tmp/triage-run_20260816_221823.md`，`validate-report.sh` RC:0）

- **PRIMARY** `l0:HARNESS / l1:tool / l2:execution-error-category-service-errors` —— 上游中转 completions 全站不可用。
- **SECONDARY** `l1:stop` —— 降级出口把机械中断渲染成「现有证据不足」。`_gap_answer` 三档全失效；`degraded_fallback._STOP_REASON_CAUSES` 里本来就有 `repair_model_unavailable → "核验修复阶段模型服务不可用"` 这句真话，但挂在默认 off 的 `ASK_DEGRADED_FALLBACK` 后面（实测生效 env 中该变量不存在）。
- **TERTIARY** `l1:observe` —— 缺口模板自证：模板写「提供主要**反证**或竞争性解释」，而 `_MARKERS["counterpoint"]` 含子串「反证」，于是宣告缺失的那句话被判成已交付，与 `structural_verifier` 直接冲突。
- **独立缺陷** `l1:configure` —— `_OUTPUT_DESCRIPTIONS` 缺键静默回落成裸 `output_id`：`chain_mapping：chain_mapping`。实测 **18 个 question_type 中 10 个**受影响。与本次中断无关，健康 run 上天天生效。

## 6b. ✅ 已执行：GLM 主 / 中转兜底（2026-08-16 23:04，用户决策后落地）

§4 的方案**已实施并验证**，本节取代 §5 中「8792 未动」那一行。

- 启动器 `/Users/a77/.local/bin/start-finance-workbench` 已加回 GLM 三件套（key 走 Keychain `finance-workbench-glm`，fail-closed：取不到就 exit 1，拒绝以单链启动）。备份 `start-finance-workbench.bak-20260816-glm`。
- 08-05 那段「三件套必须删干净」的注释**保留但标注失效**，并写明为何该顾虑对当前 backend 不成立（`built_in_provider()` 不参与 `runtime_providers_for()` 那条链；name 检查只在 `sdk_gpt` 生效）。
- 按 launchd 属主重启：`launchctl kickstart -k gui/$UID/com.a77.finance-workbench`，pid 87031 → **90194**，health `status=healthy`、`source_revision=6cd0756e`、`dirty=false`。
- 生效链实测：`[0] zhipu/glm-5.2@bigmodel-coding` + `[1] openai/gpt-5.6-terra@x.ailzd`。

**验收读数**（原题复跑，`user=verify-glm-0816`，`run_20260816_230528_976709`）：

| 判据 | 中断时 | 转移后 | |
|---|---|---|---|
| provider / 5xx | openai，16 次全 5xx | **zhipu，零 5xx** | ✅ |
| tool_calls / evidence | 0 / 0 | **4 / 25** | ✅ |
| 模型产出 | 0 token | 72 + **1395** 字符（17266 in / 2547 out） | ✅ |
| `outcome.draft` 终值 | 0 | 0 | ❌ |
| required output fulfilled | 0/3 | 0/4 | ❌ |

**结论：provider 层修好了，交付层没有。阻塞点换人了。**

### 新阻塞：repair 窗口与 provider 延迟错配

时间账（`run_20260816_230528_976709`）：

```
 0.0s  task
14.9s  model_turn(zhipu)  ok, 72字 + 5 个 tool_call     ← 首轮 14.9s
26.3s  5 个工具返回（graph_lookup 撞 tool_budget_exhausted）
26.3s  finalization  reason=retrieval_deadline_closed
60.9s  model_turn(zhipu)  ok, 1395字                   ← 合成轮 ~34.6s
61.0s  finish  stop_reason=deadline_exhausted           ← 根预算在此耗尽
61.0s  repair_goal  remaining_seconds=30.0
91.2s  model_turn  TimeoutError                         ← 整 30.0s 超时
121.5s model_turn  TimeoutError                         ← 又一次整 30.0s
121.5s finish  stop_reason=repair_model_unavailable
```

根因不是 GLM 慢，是 **30s 的 repair 窗口卡在 GLM 的 p90 底下**：

> GLM `model_turn` 耗时（8795 已有 11 单，n=32 成功轮）：
> **min 6.2 / p50 17.3 / p90 34.4 / max 49.4 秒；6/32 超过 30s**

`repair_coordinator._REPAIR_SECONDS_CAP=30` 是按中转 terra（08-08 实测 9–15s）定的。换 provider 后这个常数没跟着换，于是 repair 轮结构性超时。已登记 `R-20260816-11`。

⚠️ **不要直接把 30 调大**——账本里 `R-20260816-02` 已预注册纪律：须附按 provider 分档的延迟实测、全路由影响面，非研究题对照不得变慢超 5pp。正确形状是「窗口取值随生效 provider 的实测 p90 走」，不是换一个新常数。

### 顺带确认了 SECONDARY 的分析

本次降级文案变成了：「…**本轮已取得 25 条证据，但未完成核验绑定，暂不能引用；可直接重试**。证据数据截至 2026-08-14」。

这正是 `_gap_answer` 的中间档（`elif verified.outcome.evidence`）。它在 22:18 那单没触发，只因当时 evidence=0——坐实 §6 SECONDARY 的判断：**那个修复没有覆盖它最该覆盖的那一档**。`R-20260816-07` 仍要做。

## 7. 下一个 agent 从这里接

1. **先探中转**：`POST /v1/chat/completions` 一次。仍 502 就别等了，直接走 §4。
2. **问清 §4.3 第 1 条**：GLM 做 primary 还是做 fallback？前者是改启动器（分钟级），后者要改 `detect_providers` 排序（要开分支 + 用户确认）。
3. 改完启动器按蓝绿重启 8792，然后**用原题复跑一次**：`国产算力当前处于发酵期、共识期还是透支期？…`。验收判据：`usage.tool_calls > 0` 且 `outcome.draft` 非空 且 至少 1/3 required output `fulfilled`。
4. 落 `R-20260816-07`（成因行拆出开关）——转移也失败时，用户要看到「模型服务不可用」而不是「证据不足」。
5. 落 `R-20260816-10`（补 `_OUTPUT_DESCRIPTIONS` 10 个缺项 + 静默回落改显式失败）——唯一一条与中断无关、可独立推进的。
6. `R-20260816-08/09`（三份 artifact status 统一、marker 自证短路）按账本口径排期。

## 8. 别再踩的坑

- **`/v1/models` 返 200 不代表出口可用**。目录端点和完成端点是两条路；全站故障时前者照样绿。任何基于 `/v1/models` 的 readiness 都会发假绿。
- **「现有证据不足」不等于检索失败**。先看 `report.json.llm.used` 和 `usage.tool_calls`；两个都是 0/false 时，一次检索都没发生。
- **别在 `~/.finance-runtime/` 找生产 run**，那是开发工作区/实验树。生产落盘由启动器的 `FORESIGHT_USERS_DIR` 决定。
- **读代码要用 `finance-workspace-runtime`**（8792 实际加载的快照 `6cd0756e`），不是 `finance-workspace-private`（当前在 `docs/dsh-absorption-spec` @ `d98a8a59`，另一份代码）。
- 取证时若 `ps eww` 打了生效 env，里面带中转 API key。若会话记录要外传，轮换 Keychain 条目 `finance-workbench-test-relay`。
