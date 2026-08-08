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

## 决证状态（本 session 唯一未完成的格子）

**「模型会不会主动调 memory_lookup」** —— 接近验通但卡在网关。

已经确认的：
- 契约里有 prior_recall 槽位（多次 run 均可见）
- allowed_capabilities 包含 memory_lookup（`True`）
- memory_lookup 出现在发给模型的 tools 列表里（`14487cfd` 断言锁住）
- User-Agent 修复后，模型确实有了响应（之前是 `provider_attempts=1` 502 不重试）
- 但模型在几次决证 run 里选择了 kb_search/graph_lookup 等工具，没选 memory_lookup

最后一次有参考价值的 run：`run_20260808_021916_234953`（tester 台账）：
- status=partial，stop_reason=repair_model_unavailable
- tools=[kb_search, graph_lookup, evidence_search, finance_query]
- memory_lookup: False
- 原因：prompt rule `9380b3b9` 刚提交，那次 run 用的还是 `rev d2bbca6d`，
  还没有「必须优先调用 memory_lookup」这行指引。

**下一步**：用 `rev 9380b3b9`（含 prior_recall_rule）重跑一次决证即可。
8788 冒烟实例已关。启动所需的中转 key 不写入本仓任何文件——存 macOS Keychain，
冒烟脚本按服务名读取（见下面「起 8788 冒烟实例」）。

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

**health 端点的 source_revision 和实际执行代码不一致**（已知陷阱）：

```
health.source_revision = git rev-parse HEAD（WORKBENCH_REPO_ROOT）
实际执行代码           = PYTHONPATH 指向的独立快照
                       = /Users/a77/.finance-runtime/finance-workspace-88b28ab4-standalone/
```

快照是旧版目录结构（`glm_agent_runtime.py` 在 `services/` 不在 `runtime/`）。
每次重启生产只重新加载快照，不自动拉最新代码。需要手动 rsync 关键文件。

上次同步的文件（8-8 00:xx）：
- `intelligence/services/glm_agent_runtime.py`（从 `runtime/` 同步过来）
- `intelligence/services/episode_factory.py`
- `intelligence/services/task_fulfillment.py`

**本 session 新增的、还未同步进快照的文件**：
- `intelligence/services/episode_protocol.py`（prior_recall_rule）
- `intelligence/services/llm_refine.py`（UA 修复）

重启生产前需要先同步这两个文件。

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

1. **同步快照**（2 个文件）：
   ```bash
   SNAP=/Users/a77/.finance-runtime/finance-workspace-88b28ab4-standalone
   cp /Users/a77/finance-workspace-private/intelligence/services/episode_protocol.py \
      $SNAP/intelligence/services/episode_protocol.py
   cp /Users/a77/finance-workspace-private/intelligence/services/llm_refine.py \
      $SNAP/intelligence/services/llm_refine.py
   find $SNAP/intelligence -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
   ```

2. **重启生产**：
   ```bash
   launchctl kickstart -k "gui/$(id -u)/com.a77.finance-workbench"
   ```

3. **起 8788 冒烟实例**（需要可用的中转 key）：
   ```bash
   RELAY_KEY="<你的 key>" nohup /tmp/smoke_8788_relay.sh > /tmp/smoke_8788_relay.log 2>&1 &
   ```
   注：`smoke_8788_relay.sh` 里**不设** `FORESIGHT_LLM_KEYCHAIN`（Keychain 劫持问题）。

4. **发决证请求**（用 `user=tester`，rev 必须是 `9380b3b9`）：
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
| 陷阱（文档化）| health.source_revision ≠ 实际执行代码 |
| 陷阱（文档化）| FORESIGHT_LLM_KEYCHAIN=1 + Keychain BYOK 劫持 env 里的中转地址 |
| 端到端测试链 | ScriptedEpisodeModel 验证 memory→prior_recall 整条链无需 LLM |
| 仍未验的一格 | 模型在真实 run 里会不会主动选 memory_lookup |
