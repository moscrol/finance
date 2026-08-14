# Handoff: prior_recall 槽位 + runtime 修复链 + UA 根因

> 2026-08-08。接续 `2026-08-07-v2-correction-and-push.md`。
> 目标：让「我之前的判断还成立吗」这类问题里，模型主动调用 `memory_lookup`
> 拿到用户历史先验，并把它绑进契约里的 `prior_recall` 槽位。

---

## 本 session 落地的提交（8 个，全在 main）

```
9380b3b9  feat(prompt): 在 prior_recall 存在时注入 memory_lookup 的显式调用指引
d2bbca6d  fix(llm): 所有出站 LLM 请求加自报 User-Agent
14487cfd  test(episode): 断言 memory_lookup 真的出现在发给模型的 tools 列表里
e097a156  test(episode): 端到端锁住 memory_lookup → prior_recall 的整条链
39beabd2  fix(runtime): 把单 provider 的瞬时重试预算从 1 次升到 3 次
701d2f23  fix(runtime): 修复生产路径的 502 重试闸门
21bd0a61  fix(runtime): 把 HTTP 502/503 加进 transient error 重试白名单
f22e8cf8  feat(contract): 为用户历史先验开 prior_recall 槽位（user_premise，可选）
```

全量基线：`13 failed, 4326 passed, 3 skipped`（13 条为既有环境依赖失败，逐条一致）。

---

## 各提交做了什么 + 关键背景

### f22e8cf8 — prior_recall 槽位

`episode_factory.py` 新增条件性注入：

- **触发条件**：问题里引用了用户自己的历史看法（`_PRIOR_REFERENCE_RE`），**且**
  题型在 `_PRIOR_RECALL_QUESTION_TYPES = {stock_deep_dive, theme_analysis, theme_track}`
  （与 `_RUNTIME_CAPABILITY_FLOOR` 里 `memory_lookup` 的三条授权策略保持一致，
  避免「有槽位没工具」或反之）。
- **grounding_mode = user_premise**：先验不是市场事实，不能要求有市场证据支撑，
  也不能让它反过来去支撑别的结论。语义裁判已有对应契约。
- **required = False**：生产 24 个 user 台账全为空，设 True 会让每道题材问答
  都因绑不上这格而降级 partial——为一个增益特性引入全局回归。

顺带发现并钉住一个已知缺口：「跟我上次说的比，液冷变了什么」被路由成
`comparison_analog`，而该策略未授权 `memory_lookup`，所以不开槽——
有测试显式记录这个半截状态，避免下一位误判为漏了。

`task_fulfillment.py` 补了 `_MARKERS["prior_recall"]` 词表，否则
`output_marker_is_checkable` 恒为 False，覆盖度统计会把瞎仪表读成 0%。

### 21bd0a61 — 502 加入重试白名单

`_TRANSIENT_PROVIDER_ERRORS` 原来只有 TimeoutError / RemoteDisconnected / URLError，
`HTTP 502` 命中不了，不重试，直接 `model_unavailable`。

### 701d2f23 — 生产路径的重试闸门修复（最重要的单点 bug）

`app.py:226` 显式传 `providers=providers` 给 `GLMModelClient`，于是 `__init__`
走「providers is not None」分支，`_retry_single_real_provider` **恒为 False**——
即使 502 在白名单里，重试也不触发。四次决证 run 的 `provider_attempts` 全是 1，
就是这个闸门造成的。判据从「链是否注入」改成 `complete_fn is None`（区分
「注入真 provider 链」和「注入测试替身」）。

### 39beabd2 — 单 provider 重试上限 1→3

实测 cockpit gateway 10 次里约 3 次通，1 次重试不够；3 次上限远低于 LLM_TIMEOUT。

### e097a156 + 14487cfd — 端到端测试

把整条链（注册→工具调用→证据落账→hash 补齐→validate_episode_finish 校验）
用真实 episode 循环跑通，只替换「模型的自由选择」（ScriptedEpisodeModel 直接
发 memory_lookup 调用）。验证了 5 件事：

1. memory_lookup 工具真的被执行
2. registry 自动补 content_hash（`research_tool_registry.py:533`）
3. 先验绑进 prior_recall，basis=user_premise
4. 台账路径不外泄进 draft
5. memory_lookup 真的出现在发给模型的 tools 列表（`model.calls[0]["tools"]`）

### d2bbca6d — User-Agent 修复（本 session 最隐蔽的 bug）

**症状**：同一把 key、同一个 URL、同一份 body，curl 手测恒通（200），
python urllib 恒 502（`Upstream access forbidden`）。

**定位过程**：排除了 key 错误（401 一次都没出现），排除了请求体（最小 body 也 502），
才用 2×2 判别实验隔离出 UA：

```
curl 默认 UA (curl/x.x)          → 200, 200
curl 伪装成 Python-urllib/3.12   → 502, 502
urllib 默认 UA                   → 502, 502
urllib 伪装成 curl               → 200, 200
```

中转上游按 UA 拦 `Python-urllib/3.12`。加了 `_LLM_USER_AGENT = "finance-workbench/1.0"`
并封装成 `_llm_request_headers()` helper，四处 `urllib.request.Request()` 统一接上。

### 9380b3b9 — prompt 补连接句

加了 `prior_recall_rule`（条件 f-string，prior_recall 存在时注入）：

```
本任务包含 prior_recall 槽位：研究开始时必须优先调用 memory_lookup 工具，
检索用户对该主体的历史判断与纠偏原则，把召回结果绑定到 prior_recall
（basis=user_premise）；若 memory_lookup 返回空命中，在 binding.gap 注明
「用户记忆无相关命中」，然后继续执行市场侧工具。
```

同步更新 `_CONTRACT_FINGERPRINT`：
`0bff83…` → `3bf11c056939b25beca044fbeee11a561315326727b7b9d5e11b7f2bf527d98f`

---

## 决证状态：✅ 已通过（`run_20260808_114635_724215`）

> ⚠️ **本节 2026-08-08 14:xx 重写。** 原文写的是「本 session 唯一未完成的格子」，
> 并给出「用 rev 9380b3b9 重跑一次决证即可」的下一步。**那是过期的**：决证在
> 本文档提交（`e5391b79`，11:57）之前 11 分钟就已经跑通，结论写在了 `e5391b79`
> 的 commit message 里，但正文没同步改。照原文做会去重跑一个已经通过的验证，
> 并沿着一条**已被同一个提交撤回的归因**排查。

**「模型会不会主动调 memory_lookup」——会。**［实测，2026-08-08 复核］

```
run_20260808_114635_724215   （tester 台账，rev 含身份穿透修复 c6a60342）
  tools : [memory_lookup, evidence_search, finance_query,
           finance_query, graph_lookup, news_search]
          ^ 无强制顺序指令，模型自主排在第一位
  prior_recall binding : basis=user_premise, gap="", evidence_hashes=['3bb2d0e9…']
  台账路径泄漏 : 无
```

`status=partial` 的原因在数据源侧（evidence_search 超时、finance_query 返
`request_error`、后两个工具撞批上限），**与 prior_recall 链路无关**——那条链是闭合的。

### 三条已撤回的归因（别再沿着它们排查）

原文把「模型没选 memory_lookup」解释成模型的选择问题。**实测该工具压根没注册**，
下面三条共同的前提（「工具在候选列表里」）不成立：

| 撤回的说法 | 实际 |
|---|---|
| 「模型有工具但没选」 | 工具没注册，模型看不见 |
| 「预算竞争把它挤掉了」 | 单批上限是 `MAX_BATCH_TOOL_CALLS=4`（`episode_tool_batch.py:34`），不是 standard tier 的 6 次 max_steps；两次 run 里第 5 个调用被拒都是撞这个上限 |
| 「required=False 给了跳过的理由」 | 被拒的是 `graph_lookup`，全程没有一次涉及 `memory_lookup` |

真正的修复是 `c6a60342`（把 user 身份穿透到 `memory_lookup` 的注册链）+ `23335c63`
（三条策略授权），不是 `9380b3b9` 那行 prompt 指引。

**这正是** [[info-not-delivered-bug-pattern]] **那个形状**：先问「它看没看到这份信息」，
再问「它为什么没用」。跳过第一问会得出三条自洽但全错的解释。

### 决证跑在哪条线上（重要限定）

［实测］这次决证走的是 **8788 冒烟实例**（进程起于 11:45:15，决证 run 11:46:35），
用 env 注入的中转 key。**不是生产 8792。** 生产走
`FORESIGHT_LLM_KEYCHAIN=1` → Keychain BYOK → cockpit `localhost:57244`，
而该网关活跃账号为 0（13 个凭证全是 `.bak`，`quota-pool-state.json` 是
`{"accounts": {}}`）。

所以准确表述是：**链路已验闭合，但只在 8788 那条线上验过**；生产线的同一验证
要等 cockpit 上游账号恢复。原文「8788 冒烟实例已关」也不准——实测仍在监听
（pid 79613，rev `9380b3b9`，落后 main 4 个提交，且不含 `45d51616` 的漂移检测字段）。

---

## Keychain BYOK 劫持问题（重要 footgun）

**8788 实例配置**必须不设 `FORESIGHT_LLM_KEYCHAIN=1`。

原因：`app.py:2214` 用 `runtime_providers_for(user_id)` 显式注入 provider 链，
优先级高于 env。`linxiaoqi5111` 的 Keychain BYOK 条目指向已死的 cockpit
（`base=http://localhost:57244/v1`），开关一开，env 里写了中转地址也没用——
请求整条被劫走，四次重试全 502。关掉开关后 `runtime_providers_for` 落回 env。

正确的冒烟脚本：`/tmp/smoke_8788_relay.sh`（内含注释解释此处）。

---

## Cockpit 上游账号池（非代码问题）

```
auth-dir : /Users/a77/.antigravity_cockpit/codex_local_access_sidecar/auths
活跃 (*.json)  : 0 个
归档 (*.json.bak) : 13 个
quota-pool-state.json : {"accounts": {}}
```

所有 13 个上游凭证被 cockpit 自己归档（额度耗尽），这是本 session 最大的外部阻塞。
**不要把 .bak 改回 .json**——需要你在 Cockpit Tools 里重新授权上游账号。

---

## 生产注意事项

> ⚠️ **本节 2026-08-08 14:xx 重写。** 原文描述的陷阱（health 版本号 ≠ 实际执行
> 代码）已由 `45d51616` + `b93e4a00` 修掉，且原文给的「手动同步这两个文件」配方
> **已被后者明确否定**——照它做会重现事故。原文保留在 git 历史里。

**曾经的陷阱（已修）**：`health.source_revision` 读的是 `code_root` 的 git HEAD，
而生产进程执行的是 `PYTHONPATH` 上的独立快照。两者是文件系统里两份拷贝，
没有任何 hook 同步它们。危险在于它**恰好在最可能出错的时刻前进**：git merge
会更新仓库因此更新这个字段，但绝不会更新快照。

**现在的机制（两层，职责不同）**：

| 层 | 做什么 | 失败时 |
|---|---|---|
| `45d51616` health 双指纹 | 同时算「实际加载的树」和「仓库树」的指纹再比对，暴露 `loaded_code_root` / `loaded_tree_fingerprint` / `repo_tree_fingerprint` / `code_matches_repo` | 只是报告，不阻断 |
| `b93e4a00` `scripts/deploy_workbench_runtime.sh` | 真闸门：rsync → 校验 → **只有一致才重启**，并等 health 真起来才宣布成功 | 「没部署成」，可回退可重试 |

单个指纹只能说明身份、说明不了漂移——看到一串 hash 无法判断它是否等于仓库那份，
所以必须同时算两个再比对。

⛔ **不要逐文件 `cp` 补快照**（原文教的就是这个）。`b93e4a00` 实测：先补 2 个
文件起不来（缺 `runtime/` 整包），补上还是起不来（缺 `tool_result_budget.py`），
`services/` 实际缺 14 个。**模块重组后「差哪些文件」无法靠读 diff 推断**，
而快照里的陈旧模块会被 import 到，留着比缺着更危险。所以是全量
`rsync --delete`，不做增量补丁。

⛔ **也不要在服务启动时硬失败**（曾考虑过的另一个方案）。launchd 实测
`KeepAlive=true` + `ThrottleInterval=10`，启动时 `sys.exit` 不会「拒绝启动」，
会变成每 10 秒重启一次的无限崩溃循环，生产彻底不可用且日志被刷爆。
**闸门必须放在部署一侧。**

正确做法：`scripts/deploy_workbench_runtime.sh`，一条命令。

［实测 2026-08-08 14:00 复核］`code_matches_repo: true`，两侧指纹同为
`532a954e…`，模块数 470/470，`/api/readiness` 的 `code_snapshot_matches_repo`
为 true。

---

## ASK_CONTINUOUS_RUNTIME 已写入启动器

```
/Users/a77/.local/bin/start-finance-workbench 第 44 行
export ASK_CONTINUOUS_RUNTIME="on"
备份 : start-finance-workbench.bak-20260807
```

生产 8792 已重启（launchd com.a77.finance-workbench，pid 37033 → 后续重启会换 pid），
`mode: on` 已生效，但快照代码未同步（见上）。

---

## 测试台账位置

```
tester 台账（484 条 judgments，含液冷）：
  /Users/a77/agent-memory/.foresight/tester/judgments.jsonl

linxiaoqi5111 台账（无 judgments.jsonl）：
  /Users/a77/agent-memory/.foresight/linxiaoqi5111/
```

决证必须以 `user=tester` 发请求，否则 memory_lookup 只会返回空命中。

---

## 下一个 session 最优路径

> ⚠️ **本节 2026-08-08 14:xx 重写。** 原步骤 1（逐文件 `cp` 同步快照）已被
> `b93e4a00` 否定，原步骤 4（重跑决证）在写下时已经通过。以下是当前有效路径。

1. **~~同步快照 + 重启~~ → 用部署闸门**（原步骤 1+2 合并，且不再手工 `cp`）：
   ```bash
   scripts/deploy_workbench_runtime.sh
   ```
   它自己做 rsync → 校验一致 → 重启 → 等 health 起来。**不一致就不重启**，
   失败只是「没部署成」。别再手工 `cp` 单个文件（原因见上节 ⛔）。

   ⚠️ 该脚本当前**有未提交改动**（见「遗留」一节），先确认工作区那版再跑。

2. ✅ **决证已完成** —— `run_20260808_114635_724215`，见上方「决证状态」节。
   原步骤 4/5 的命令保留在下面，仅用于**生产线（8792）复验**：cockpit 上游
   账号恢复后，同一组命令换 `localhost:8792` 再跑一次，才算生产线也验过。

3. **起 8788 冒烟实例**（需要可用的中转 key；实例当前仍在跑，pid 79613）：
   ```bash
   RELAY_KEY="<你的 key>" nohup /tmp/smoke_8788_relay.sh > /tmp/smoke_8788_relay.log 2>&1 &
   ```
   注：`smoke_8788_relay.sh` 里**不设** `FORESIGHT_LLM_KEYCHAIN`（Keychain 劫持问题）。

4. **发决证请求**（用 `user=tester`；台账里有 judgments 的只有它，换别的用户
   `memory_lookup` 只会返回空命中，那时的「没召回」不是缺陷）：
   ```bash
   CID=$(curl -s -X POST localhost:8788/api/conversations \
     -H 'Content-Type: application/json' \
     -d '{"user":"tester","title":"decisive"}' \
     | python3 -c 'import sys,json;print(json.load(sys.stdin)["conversation_id"])')
   curl -s -X POST "localhost:8788/api/conversations/$CID/messages" \
     -H 'Content-Type: application/json' \
     -d '{"content":"液冷题材现在怎么看？我之前的判断还成立吗","skill_mode":"auto","user":"tester"}'
   ```

5. **读 continuous-episode.json**，确认 tool seq 里有 `memory_lookup`：
   ```bash
   RUN=run_20260808_xxxx   # 从上一步的响应里取
   EP=/Users/a77/agent-memory/.foresight/tester/runs/$RUN/continuous-episode.json
   python3 -c "
   import json,pathlib
   ep=json.loads(pathlib.Path('$EP').read_text())
   o=ep['outcome']
   seq=[c.get('name') for e in ep.get('events',[]) for c in (e.get('payload') or {}).get('tool_calls',[]) if c.get('name')]
   print('status:', o.get('status'))
   print('tool seq:', seq)
   print('memory_lookup called:', 'memory_lookup' in seq)
   print('prior_recall binding:', [b for b in o.get('bindings',[]) if b.get('output_id')=='prior_recall'])
   "
   ```

---

## 本 session 收获汇总

| 类型 | 内容 |
|---|---|
| 合法 bug fix（非 prior_recall 相关）| 生产路径 `_retry_single_real_provider` 恒为 False（701d2f23） |
| 合法 bug fix（非 prior_recall 相关）| urllib `Python-urllib/3.12` UA 被中转上游拦截（d2bbca6d） |
| 设计缺陷（外部，无法修复）| cockpit 账号池全归档，13 个凭证全 `.bak` |
| ~~陷阱（文档化）~~ → **已修** | health.source_revision ≠ 实际执行代码 → `45d51616` 双指纹 + `b93e4a00` 部署闸门 |
| 陷阱（文档化）| FORESIGHT_LLM_KEYCHAIN=1 + Keychain BYOK 劫持 env 里的中转地址 |
| 端到端测试链 | ScriptedEpisodeModel 验证 memory→prior_recall 整条链无需 LLM |
| ~~仍未验的一格~~ → **已验** | 模型在真实 run 里主动选了 `memory_lookup` 并排在第一位（`run_20260808_114635_724215`），限定：8788 线，非生产 8792 |

---

## 遗留（2026-08-08 14:xx 复核时发现，均未处理）

| # | 事项 | 证据 |
|---|---|---|
| 1 | `scripts/deploy_workbench_runtime.sh` **有未提交改动**，且改的是核心正确性：`python - <<PY` 从 stdin 读脚本时 `sys.path[0]` 是 `''`，优先级高于 `PYTHONPATH`，不 `cd` 到快照的话校验会退化成「仓库跟自己比」恒真 | `git diff scripts/deploy_workbench_runtime.sh` |
| 2 | 8788 是第二条在跑的代码线，rev `9380b3b9` 落后 main 4 个提交，health 无 `loaded_code_root` / `code_matches_repo`（那两个字段是 `45d51616` 才加的）——**它自身不具备漂移检测** | `curl localhost:8788/api/health` |
| 3 | 生产 8792 的 LLM 出口仍指向死网关：启动器第 19 行 `FORESIGHT_LLM_KEYCHAIN=1` → BYOK → cockpit `localhost:57244`，活跃账号 0 | `auths/` 0 个 `.json` / 13 个 `.bak` |
| 4 | `health.source_dirty: true` —— 工作区有未提交改动（含第 1 条） | `/api/health` |
