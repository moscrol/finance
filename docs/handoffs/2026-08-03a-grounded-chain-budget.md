# Handoff — Grounded 合成链预算与可观测性（2026-08-03a）

**起点**：用户反馈「金融 agent 老出现输出降级」，用 `agent-run-triage` skill 做事后分诊。
**范围**：`intelligence/services/{llm_refine,ask_synthesis,ask_types}.py`、`intelligence/api/app.py`、
`intelligence/eval/`。生产 prompt 未改，架构未改。
**状态**：已合并进本地 `main`，**4 个 commit 未 push**；8801 服务在跑但代码已落后于 main。

---

## 0. 一句话现状

「输出降级」的根因**不是预算保留太小**（我最初的判断，已作废），而是**时间片从未被强制执行**——
`synthesize_messages` 在调用方传 `deadline` 时把 `timeout` 参数整个丢弃，导致 brief 一段吃掉
整条预算、composer 饿死。三个 commit 修好了强制执行与可观测性，但**修完暴露出更硬的约束**：
在实测 34.3 tok/s 下，三次串行调用需要 160~220 秒，而 turn 预算只有 120 秒——**装不下**。
下一步是架构取舍，不是继续调数字。

---

## 1. Git 与运行时

| 项 | 值 |
|---|---|
| 分支 | `main`（任务分支 `fix/grounded-chain-observability` 已合并并删除） |
| HEAD | `9878f489` |
| 已 push | 到 `6c16b73a` 为止 |
| **未 push** | `cd175a0e`、`8ed66020`、`bd845320`、`9878f489`（后两个互为撤销） |
| 全量测试 | 3642 passed / **13 failed（基线，改动前就红）** / 2 skipped |
| 基线红的是 | `test_subconscious`(7)、`test_userspace`(3)、`test_acceptance_board`(2)——都是 vault/env 路径类，与本次无关，已用 `git stash` 反复验证 |
| Ruff | 全过 |
| 服务 | 8801，`nohup` 起，日志 `/tmp/workbench-8801.log` |
| ⚠️ 服务代码 | 跑的是 `bd845320`，**已落后于 main**（撤销 commit 之后没重启）——继续工作前先重启 |

### 服务重启方式（关键，容易踩坑）

**必须从当前进程抄环境变量**，不要照文档示例写：

```bash
PID=$(lsof -nP -iTCP:8801 -sTCP:LISTEN -t)
DUMP=$(ps eww -p $PID | tr ' ' '\n')
pick() { echo "$DUMP" | grep "^$1=" | head -1 | cut -d= -f2-; }
K=$(pick FORESIGHT_BUILTIN_LLM_API_KEY); B=$(pick FORESIGHT_BUILTIN_LLM_BASE_URL)
M=$(pick FORESIGHT_BUILTIN_LLM_MODEL); U=$(pick FORESIGHT_USER); D=$(pick FORESIGHT_USERS_DIR)
kill $PID && sleep 3
nohup env FORESIGHT_BUILTIN_LLM_API_KEY="$K" FORESIGHT_BUILTIN_LLM_BASE_URL="$B" \
  FORESIGHT_BUILTIN_LLM_MODEL="$M" FORESIGHT_USER="$U" FORESIGHT_USERS_DIR="$D" \
  FINANCE_WS=/Users/a77/finance-workspace-private \
  .venv-workbench/bin/python -m uvicorn intelligence.api.app:app \
  --host 127.0.0.1 --port 8801 > /tmp/workbench-8801.log 2>&1 &
```

运行时配置：`gpt-5.6-sol` via **cockpit** 本地网关 `http://127.0.0.1:57244/v1`（进程名 `cockpit-c`）。
GLM 早已不在链路里，`continuous_glm` 只是 backend 常量名，模型无关。

---

## 2. 根因链（三层，逐层套）

### 第一层：时间片形同虚设 —— 已修 `cd175a0e`

```python
shared_deadline = deadline or Deadline.from_timeout(timeout)   # 传了 deadline → timeout 被丢弃
remaining = shared_deadline.require_remaining(1)               # 整条剩余当单次超时
```

grounded 三段链（brief/composer/judge）**一直显式传 deadline**，所以 `_shadow_phase_timeout`
算出的 0.25/0.5/0.35 三个片从来没被读过，每段都能吃掉整条预算。

修法：`Deadline.call_timeout(timeout) = min(片, 剩余)`，非流式与流式两个调用点各替换一次。

### 第二层：重试各拿一份片 —— 已修 `8ed66020`

`_RETRY_MAX_ATTEMPTS=2`，22s 的片跑出 44.5s。片是「每次尝试」的预算而不是「这一段」的。
修法：进函数先折出 `phase_deadline = min(共享 deadline, now + 片)`，重试在其内部消耗。

### 第三层：模型速度与架构假设不匹配 —— **未解决，需决策**

```
cockpit 实测：极小请求 2.0s，吞吐 34.3 tok/s，reasoning_tokens≈0（不慢，就是这个速度）
brief     实测 2,324 tokens → 69.7s   （8 字段含 chain_mapping，长度合理）
composer  上限 7,200 tokens → 60~120s
judge     上限 3,600 tokens → ~30s
                        合计 160~220s
root turn 预算                    120s（ResearchExecutionPolicy.max_elapsed_seconds）
```

**在这个吞吐下 token 预算就是墙钟时间。** 分片修复只是让这件事从隐形变可见。

---

## 3. 本次落地的 commit

| SHA | 内容 |
|---|---|
| `60dee33c` | **phase 埋点**：brief/composer/judge 各记入口剩余预算/分片/实耗/失败归一码；没跑到的段不留记录（「judge 从未开始」靠记录不存在来判定）。API 与 eval 两层白名单同步放行 |
| `3ab5f271` | **judge 闸门 + 诊断分态**：`「截止时间」`拆出 `deadline_exhausted_local` 并移出瞬时故障白名单（自家预算耗尽不再冒充供应商故障）；新增 `released_unverified` 状态，`accepted` 不再涵盖「没人审但放行了」 |
| `6c16b73a` | **四态口径** `intelligence/eval/synthesis_health.py` + 准入检查（片塌到下限时不发注定失败的请求） |
| `cd175a0e` | 第一层修复（见上） |
| `8ed66020` | 第二层修复（见上） |
| `bd845320` → `9878f489` | brief token 上限砍到 1200，**已撤销**——前提是错的，见 §6 |

---

## 4. 实测产物（都在 `intelligence/eval/runs/`）

| 文件 | 配置 | elapsed | phase 结果 |
|---|---|---|---|
| `smoke-phase-check.json` | 修复前 | 92.5s | brief ok 69.7s（片 22s）→ composer failed 20.3s |
| `smoke-after-fix.json` | 片强制后 | 46.2s | brief failed 44.5s（22×2 重试） |
| `smoke-budget-300.json` | 总预算 300s | 32.2s | brief 入口 118.7s（被 root 120s 卡住）、片 29s、failed |
| `smoke-brief-fixed.json` | brief 砍到 1200 | 24.2s | brief failed 22.0s（正好用满片） |
| `20260803T062809Z.json` | ⚠️ **作废** | — | 误设 `ASK_CONTINUOUS_RUNTIME=on`，走了另一条路径，见 §6 |

四态口径读数（历史 8-02 那批，23 个 completed turn）：
**完整通过 1 (4%) / 放行未核验 6 (26%) / 模板降级 14 (61%) / 未进合成 1 / 未知 1**。
旧口径按 `state=accepted` 读出来是 7 个健康 —— **虚高 6 倍**。

查看命令：
```bash
.venv-workbench/bin/python -m intelligence.eval.synthesis_health intelligence/eval/runs/*.json
```

---

## 5. 待决策：A + D（我的推荐）

三段串行在 120s 里装不下。既然模型固定为 `gpt-5.6-sol`，剩下三个选项：

- **D：judge 移出关键路径**（异步后置）。依据是代码自己的注释：「judge 是**后台请求**，
  用户不在等它的结果」——但它现在占着同步预算 ~30s。移走后语义审仍做，只是事后标记。
- **A：root 预算 120s → 180s**。移走 judge 后需要 brief 68 + composer 90 ≈ 158s。
- C（三段并两段，brief 并进 composer）：更彻底，但要重写 prompt 架构、丢掉「先规划后成文」
  的分层。建议 A+D 验证过还不行再考虑。

单独 A 要到 240s（单轮 4 分钟，体验差）；单独 D 只省 30s，不够。**两个一起才装得下。**

---

## 6. 踩过的坑（下一个人必看）

1. **`ASK_CONTINUOUS_RUNTIME=on` 会整体切换回答路径。** 我重启时从 `docs/workbench/local-site.md`
   的示例里抄了这个变量，而生产进程**没有**它（默认 `off`）。结果整批 10 题走了 Continuous
   Episode runtime，**完全绕开 `ask_synthesis` 的 grounded 链**，埋点一条没出。
   识别特征：`trace_steps` 从 `understanding/planning/research×5/verification` 变成
   `understanding/research×12/finalizing/repair/verification`，降级文案也不同。
   **教训：重启服务要从运行中的进程抄环境，不要抄文档。**

2. **`acceptance run` 默认打 8799，真实服务在 8801。** 必须显式 `--base http://127.0.0.1:8801`。
   8799 上还有一个 7/31 起的僵尸进程（无 API key、preflight 过不了）。

3. **测试里手搓的 Deadline 替身会随 Deadline 增加方法而坏**，已经坏过两次
   （`call_timeout`、`expires_at`）。`test_stream_fallback_uses_only_remaining_deadline`
   已改用真 `Deadline`。别再造替身。

4. **`elapsed_s` 是 2 秒轮询的量化值**（`acceptance.py` 里 `time.sleep(2.0)` 轮询），
   不是精确耗时。做延迟对比时注意 ±2s 分辨率。

---

## 7. 本次分诊里我判断错的两处（记下来避免重复）

1. **「`synthesis_reserve` 20 秒太小、检索抢了预算」——错。** 实测 brief 进场时 118.7 秒
   全在，检索一秒没抢。这个结论当时是从代码算术推的，没有测量支撑。**代码推演是这类分析
   里最容易混进「看起来很对但其实错」的地方**，必须配一次测量才能升为结论。

2. **「brief 只是三字段小 JSON，3600 tokens 是浪费」——错。** 它有 8 个字段，还带
   `chain_mapping`（产业链公司清单），2,324 tokens 是合理长度。我是从测试 fixture 只用了
   3 个字段推的，**没读真实 prompt**（`_DECISION_BRIEF_SYSTEM_PROMPT`）。基于此的
   `bd845320` 已撤销。

---

## 8. 顺带完成的仓库收敛

- 远端分支 282 → 50（删掉 232 个已并入 `origin/main` 的，逐个校验过零独有 commit）
- 开着的 PR 4 → 0（#282 是空 PR；其余三个基线差近千个 commit，已关并说明）
- 本地分支 10 → 2（`main` + `fix/kb-rag-worker-attribution`）
- 归档 tag 4 个已推远端：`archive/workbench-query-retrieval-latency` 等，内容不会丢

**`fix/kb-rag-worker-attribution` 还没合**（5 个 commit，8-02）。它里面有两样值得看的东西：
`fix(kb-rag): worker 路径补齐 env 与异常归因`（很可能是 B/C 组「知识库检索失败（退出码 1）」
的解药）和 `chore(gitignore): 忽略工作流指标流水/市场快照/工具本地配置`（正好清理当前
工作区那几个未跟踪目录）。当时没合是因为跑批正在调用 kb-rag，中途改工作区会污染实验。

---

## 9. 下一步动作清单（按信息增益排序）

1. 重启 8801 到 `9878f489`（当前服务代码已过期）
2. 决定 A+D 还是别的方案；D 涉及改执行时序，改完先跑单题验证
3. 合 `fix/kb-rag-worker-attribution`（先跑全量测试确认干净）
4. push 那 4 个未推的 commit
5. 跑完整 A 组 10 题，用四态口径对比 8-02 的 1/23，确认修复是否兑现
6. 工作区 7 个未跟踪项待处理（`.codex/`、`.windsurf/`、`.tmp-opinion/`、`market_snapshot/` 等）
