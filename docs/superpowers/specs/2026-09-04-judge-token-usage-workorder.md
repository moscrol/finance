# 2026-09-04 判官侧 token 用量记账 + 单次研究全口径成本报表 工单（P1，小单）

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
无前置单；与 `feat/methodology-backtest-p0`、`docs/finance-agent-bp` 互不依赖。预计半天到一天。

## 1. 背景与动机

- BP（`docs/bp/2026-09-finance-agent-bp.md` §7.3 / §13.3）承诺 6 个月内公开「单次研究全口径成本实测」。2026-09-04 实测只量到了**写手侧**：真人用户 356 个完成 run 的 `continuous-episode.json → outcome.usage.{input_tokens,output_tokens}`，中位 37,504 / 1,403，p90 79,988 / 2,930。**判官侧没有任何 token 记录**，全口径只能按「写手 + 三到五成」估。
- 病灶位置：判官经 `llm_refine.complete()` 调用，落到 `_post_chat()`（API 判官）或 `_complete_cli_judge() → grok_cli_judge.complete_grok_cli()`（grok CLI 判官，生产当前用的这条）。两条路径都只返回 `content` 字符串，`usage` 被丢弃：
  - `_post_chat` 直接 `return body["choices"][0]["message"]["content"]`，不读 `body["usage"]`（`_post_chat_message` 那条路径已经会把 usage 挂到 `message["_usage"]`，但判官不走它）。
  - `grok_cli_judge._extract_text` 只取 CLI JSON 里的 `text`，CLI 输出里是否带 usage 字段**尚未探明**。
- 已有的记账骨架：`llm_refine.LLMCallLedger` 按「provider 尝试」粒度记每次调用（`LLMCallRecord{caller, provider, model, status, elapsed_ms, reason}`），turn 级用 ContextVar 聚合，`continuous_turn_adapter._ledger_attempt_count()` 只取了 `call_count` 做 `metrics.provider_attempts`。**token 字段加在这本账上，不新开账本。**
- 为什么不改 `complete()` 的返回契约：它返回 `(content, provider, reason)` 三元组，调用方遍布 services；改签名是大动干戈，且台账本来就是为「一个 turn 的 LLM 花费」设计的。

## 2. 目标（每条可验收）

1. `LLMCallRecord` 增加可选字段 `input_tokens: int | None`、`output_tokens: int | None`、`usage_source: str | None`（取值 `api` / `cli` / `estimated`）、`purpose: str | None`（取值 `judge` / `writer` / `synthesis` / `other`，缺省 None）。`LLMCallLedger.summary()` 增加 `input_tokens_total`、`output_tokens_total`、`tokens_by_purpose`、`estimated_share`（估算记录占比），`records[]` 逐条带上述字段（None 不输出）。
2. `_post_chat` 读取响应顶层 `usage`，兼容两套命名（`prompt_tokens/completion_tokens` 与 `input_tokens/output_tokens`；复用 `glm_agent_runtime._message_token_usage` 的取值逻辑或把它抽到 services 层的纯函数），记入台账，`usage_source=api`。
3. grok CLI 判官：**先探明**。用一次真实判官调用把 CLI 原始 stdout 落到 `~/.finance-runtime/judge-usage-probe-<date>/raw.json`；若 payload 含 usage 类字段（任何命名），解析并记 `usage_source=cli`；若不含，用估算：`input ≈ len(system + user) / K`、`output ≈ len(content) / K`，K 用中文占比加权的字符 / token 比（取值与依据写进模块 docstring，并用同一段文本对照 GLM API 返回的真实 usage 校准一次，误差写进收据），记 `usage_source=estimated`。**估算值永远带标记，不得与真实值混算成一个数而不注明。**
4. 判官调用打 `purpose=judge`：在 `episode_semantic_verifier` 发起判官请求的入口用 ContextVar 上下文管理器（例如 `llm_refine.call_purpose("judge")`）包住，`_record_llm_call` 读取该 ContextVar 写入 record；不改判官提示词、不改 `complete()` 签名。
5. `continuous_turn_adapter` 的 turn `metrics` 增加 `judge_usage: {calls, input_tokens, output_tokens, usage_source}`（只汇总本 turn 内 `purpose=judge` 的记录，沿用 `attempts_before` 的差分方式），落进 `continuous-episode.json`。**该字段必须有读者（第 6 条），否则字段契约门禁会拦。**
6. 新增读者 `intelligence/eval/research_cost.py`（形状照 `intelligence/eval/tool_hunger.py`：`--since`、`--runs-root`、`--out-dir`，输出 `intelligence/eval/measurements/research-cost-YYYY-MM-DD.{json,md}`）：遍历 run 目录，写手侧取 `outcome.usage`，判官侧取 `metrics.judge_usage`，按 `status=completed` 过滤；输出中位 / 均值 / p90 的 input / output tokens（写手、判官、合计三列），并按**价目表文件**折算元/次。价目表 `intelligence/eval/pricing/llm-prices.json`（进 git）：`{model_pattern, input_cny_per_m, output_cny_per_m, cache_hit_cny_per_m, source_url, checked_at}`，首版录智谱官方 2026-09-04 定价（GLM-5.2 / 5.3：8 / 28 / 2；GLM-5：4–6 / 18–22 / 1–1.5；来源 https://bigmodel.cn/pricing）。报表明写「估算记录占比」，占比 > 0 时成本列标「含估算」。
7. 台账地图 `docs/learning/ledger-map.md` 追加一行：`单次研究成本报表 | intelligence/eval/measurements/research-cost-<date>.{json,md} | JSON/md | python -m intelligence.eval.research_cost | 是 | 同名 .md`。
8. 测试：`intelligence/tests/test_llm_call_ledger_usage.py`（两套命名解析、CLI 有 / 无 usage 两种 payload、估算路径必带 `estimated` 标记、summary 合计与按 purpose 分组正确、`purpose` ContextVar 在嵌套调用中不串）；`intelligence/tests/test_research_cost.py`（合成 run 目录 → 报表数值、缺 `judge_usage` 的旧 run 不崩且计入「判官未记账」计数）；现有 `test_grok_cli_judge.py`、`test_episode_semantic_verifier.py`、`conformance_transport/` 全绿。
9. 真库读数：对生产用户 `linxiaoqi5111` 最近 ≥ 20 个新 run（改动上线后产生的）跑 `research_cost`，把「写手 / 判官 / 合计」三列与元/次写进交接与 BP §7.3 的 `【待填：Alpha 期含判官的全口径实测】`。
10. 在途交接 `docs/handoffs/inflight/feat-judge-token-usage.md`。

## 3. 非目标（写死认领）

- ❌ 改 `complete()` / `refine_or_reason()` 的返回契约。
- ❌ 改判官提示词、判官 JSON schema、修复轮逻辑（`episode_semantic_verifier` 只加一个上下文管理器包裹，不动判定逻辑）。
- ❌ 按 token 计费的配额（配额仍按 run 次数，`hosted-alpha-gate.md` §4.3 的已知边界另单）。
- ❌ 调价格 API、自动更新价目表——价目表是手工核对的 JSON，带 `checked_at`。
- ❌ 接提示词缓存、换判官模型、降本优化——本单只量不改；量出来的数进 BP，优化另单。
- ❌ 回填历史 run 的判官 token——旧 run 没有原始 stdout，报表把它们计入「判官未记账」，不估。
- ❌ 写 `docs/prediction-ledger.md` / 取 R-号。
- ❌ 改 `market_feature_store` 任何东西。

## 4. 证据路径表（先读这些，禁止臆测）

| 文件 | 看什么 |
|---|---|
| `intelligence/services/llm_refine.py` `:425–560` | `LLMCallRecord` / `LLMCallLedger` / `summary()`；ContextVar 聚合方式与跨线程传播注释 |
| `intelligence/services/llm_refine.py` `:683` `_record_llm_call` | 记账入口；token 字段从这里进 |
| `intelligence/services/llm_refine.py` `:742–788` | `_complete_cli_judge`（CLI 判官）与 `_post_chat`（API 判官）——两处都只返回 content |
| `intelligence/services/llm_refine.py` `:937–1107` | `_post_chat_message_stream` / `_post_chat_message` 已有的 `message["_usage"]` 逻辑与 `stream_options.include_usage`——复用命名与解析，不重写 |
| `intelligence/services/grok_cli_judge.py` `:109–146, :173–190, :193–242` | argv（`--output-format json`）、`_extract_text`（只取 `text`）、`complete_grok_cli`；探明 CLI payload 是否含 usage 就在这里落原始 stdout |
| `intelligence/runtime/glm_agent_runtime.py` `:641, :751` | `_message_token_usage` 与 `token_value("input_tokens", "prompt_tokens")` 双命名取值——**复用勿重写**（注意 services 不得 import runtime，需要就把纯函数下沉到 services） |
| `intelligence/services/episode_semantic_verifier.py` `:1071, :1286, :1427` | 三处 `_judge_request(...)` 之后发起判官调用的位置——`purpose=judge` 上下文包在这些调用外 |
| `intelligence/runtime/continuous_turn_adapter.py` `:477, :1430–1488` | `attempts_before` 差分与 `metrics` 构造；`judge_usage` 加在同一处 |
| `intelligence/eval/tool_hunger.py` | 报表脚本的形状（`--since` / `discover_run_dirs` / `write_*_report` / 输出到 `measurements/`）——**照抄形状** |
| `intelligence/eval/metric_field_contract.py` `:229–232` | 指标字段契约；新字段 `judge_usage` 按其规则登记（它已记录「token 是真正的缺口：input_tokens 仅 29/45」） |
| `intelligence/tests/conformance_transport/transports.py` | 传输层符合性套件含 grok 判官；改动后必须全绿 |
| `scripts/layer_audit.py` docstring | services 不得 import runtime 的门禁口径 |
| `docs/learning/ledger-map.md` | 台账登记表头 |
| `docs/bp/2026-09-finance-agent-bp.md` §7.3 | 写手侧实测数字与「每次 1 元」假设——本单的读数要回填到这里 |
| `~/.finance-runtime/` 现有探针目录 | 收据落地位置的惯例（`live-probe-*` 等） |

## 5. 步骤 + 验收

### 步骤

1. `git status --short && git branch --show-current && git worktree list`；从 `gitea/main` 新开树与分支 `feat/judge-token-usage`。解释器 `.venv-workbench/bin/python`。
2. **探明 CLI**：在现有判官配置下跑一次真实判官（可用 `scripts/` 下现有探针或最小脚本），落原始 stdout 到 `~/.finance-runtime/judge-usage-probe-<date>/raw.json`，记录 payload 顶层键名。有 usage → 走目标 3 的 `cli` 分支；没有 → 走 `estimated` 分支并做一次 K 值校准（同一段文本经 GLM API 拿真实 usage 对照，误差写进交接）。
3. 实现顺序：`LLMCallRecord` 字段 → `_post_chat` 解析 → `grok_cli_judge` 解析 / 估算 → `call_purpose` ContextVar 与 `_record_llm_call` 读取 → `episode_semantic_verifier` 三处包裹 → `continuous_turn_adapter.metrics.judge_usage` → `metric_field_contract` 登记 → `research_cost.py` + 价目表 → 测试 → 台账地图。每步一个提交，pathspec。
4. 变异测试至少一条：把 `_post_chat` 的 usage 解析删掉 → `test_llm_call_ledger_usage` 必须变红；恢复后绿。记进交接。
5. 门禁：`ruff`、`layer_audit.py`、全量 pytest（或至少 `-k "ledger or judge or semantic or transport or research_cost"`）。
6. 上线一次（切流按现有 cutover 流程，需用户确认）后积累 ≥ 20 个真实 run，跑 `python -m intelligence.eval.research_cost --since <上线日>`，读数回填 BP §7.3 与交接。

### 验收（机器可判或有明确观察面）

- [ ] 新 run 的 `continuous-episode.json` 里 `metrics.judge_usage` 存在，`calls ≥ 1`，`usage_source ∈ {api, cli, estimated}`；`outcome.usage` 写手侧字段不变。
- [ ] `LLMCallLedger.summary()` 的 `input_tokens_total` = 各 record 之和；`tokens_by_purpose.judge` 只含判官调用（用一条写手 + 一条判官的合成序列断言）。
- [ ] API 判官夹具：`prompt_tokens/completion_tokens` 与 `input_tokens/output_tokens` 两种响应都能解析；缺 usage 的响应记 None 且不抛。
- [ ] CLI 判官夹具：含 usage 的 payload → `cli`；不含 → `estimated` 且 `estimated_share > 0`；`_extract_text` 行为不变（现有 `test_grok_cli_judge.py` 全绿）。
- [ ] `purpose` ContextVar：判官调用内部若再触发其他 LLM 调用（例如修复轮），不会把写手调用误标为 judge（嵌套测试）。
- [ ] `research_cost` 对合成的 5 个 run（3 个有 `judge_usage`、2 个旧格式）输出：写手 / 判官 / 合计三列的中位 / 均值 / p90，`judge_unrecorded_runs=2`，元/次按价目表算对（手算一组对照值）。
- [ ] 报表 md 顶部有成立条件块：价目表 `checked_at`、run 数、日期范围、估算记录占比、树 / 解释器 / revision。
- [ ] `metric_field_contract` 登记 `judge_usage`，其自检通过；字段契约门禁（unread-fields）不新增未读字段。
- [ ] `ledger-map.md` 新行在；`layer_audit.py` ERROR 0；`ruff` 0；`conformance_transport` 全绿；变异测试记录在交接。
- [ ] 真库读数（≥ 20 个新 run）写进交接与 BP §7.3；若 `estimated_share > 0`，BP 里的数字必须注明「判官侧为估算」。

## 6. 红线（抄 AGENTS.md，不新发明）

- 开工先 `git status --short && git branch --show-current && git worktree list`；主树有他人足迹**另开干净树**。
- 🚫 禁 `git add -A` / `git add .`；一律 `git commit -- <明确文件列表>`；不合 `main`、不强推、合并与切流等用户确认。
- 🚫 禁提交 `.env*` / 密钥 / `*.duckdb` / `*.db` / `.DS_Store` / 缓存与虚拟环境；探针原始 stdout 落 `~/.finance-runtime/`，不进仓。
- 解释器 `.venv-workbench/bin/python`；宿主 `python3` 缺依赖会给偏高失败数。
- `intelligence/services/` 不得 import `intelligence/runtime/`（`layer_audit.py` 门禁）——双命名取值函数若要复用，下沉到 services 而不是反向 import。
- 判官调用的 argv、提示词、超时、沙箱一律不动；本单只在返回值上加读取。
- 估算值必须带 `estimated` 标记进入每一层（record → summary → metrics → 报表），任何一层丢标记即为 bug。
- 用户纠偏必落 correction（`python3 -m intelligence.cli record-correction ...`）。

## 7. 成立条件

- 树：`/Users/a77/fwp-wt-finance-agent-bp` @ `docs/finance-agent-bp`（本单在此起草）；实施基线取派单时的 `gitea/main`。
- 行号：2026-09-04 读自 `docs/finance-agent-bp` 分支（基线 `gitea/main@2d8eaea5`），实施时以 `rg` 重定位。
- 写手侧实测数字来源：生产用户目录 `linxiaoqi5111/runs/*/continuous-episode.json`，356 个 completed run（2026-08-12→08-31）。
- 本文零运行时改动。

## 8. 可迁移知识点（教学备注）

- **记账加在已有的账本上，不新开账本。** 台账（ledger）的价值在于「一个 turn 的所有花费在一处」；为 token 单开一条通道，下次要对账就得 join 两本账。这和「单一真本源」是同一条原则。
- **估算值必须带标记走完全程。** 混算一个数最省事，但六个月后没人记得哪部分是估的。数据工程里叫 provenance（来源标记）；面试里常问「你怎么处理缺失值」，答案的关键词就是「标记而不是填平」。
- **先探明再设计分支。** CLI 输出里有没有 usage 是一个五分钟就能确认的事实，先落原始 stdout 再决定解析还是估算，比先写两套代码再删一套便宜。
- **新字段必须有读者。** 本仓的字段契约门禁会拦「写了没人读」的字段——这是把「可观测性不是打日志，是有人看」做成了机制。
