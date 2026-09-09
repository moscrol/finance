# 历史发现研究实施交接 · 2026-09-09

用户最新要求：“先 handoff，保留成果，然后剩下的我交给 agent 去处理执行。”本轮已停止新增实现，所有子 agent 停止。真实测试均已结束，测试服务 8809 已关闭；没有替换生产 8792、没有合 main、没有数据同步。

## 接手位置与成果

- 工作树 `/Users/a77/fwp-wt-historical-discovery`，分支 `codex/feat-historical-discovery`，基线 `gitea/main@f90af450b1be1fe80d5ad1515973503c646e15d0`。
- `e2f4173a`：批准 spec；`7d49c9d8`：历史计算/存储/领域接入；`b28d7331`：模型可见完整语义块；`5c980d79df79b7d227b0bdcc078b2b7c004a9770`：真实对话修复、草稿 patch、发布上限、恢复投影、独立审计 CLI。后续文档提交不改变代码。
- 主树 `/Users/a77/finance-workspace-private` 有其他 agent 工作，不要切它的分支、清理或覆盖。解释器固定 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，在本工作树运行。
- 先读 `docs/superpowers/specs/2026-09-09-historical-discovery-research-design.md`、同日 `plans/2026-09-09-historical-discovery.md`、本交接。不要重做设计采访。

用户要的是：事后强案例发现特征→提出假设→找其他历史同类、失败及无特征却走强样本→形成可修订的条件认识。发现阶段允许后验看完整路径，不要求先锁定强股、不强迫等待未来行情；行情量能不等于主动资金流。领域 harness 在既有 runtime 上选择研究行动，不另造 loop。

## 已实施的准确范围

1. `historical_research/query.py`：只读 canonical DuckDB，精确板块/个股代码；`inspect_history` 日轴/成员联立、`compute_history` 内置特征、`find_analogues` 召回、`compare_cases` 声明全集四格/缺失/未到期/重叠窗口。完整结果与预览分母分开；特征带定义版本与字段覆盖。严格双红是 pct>0、diff_ratio>10、amount>500 亿元；`amount_ratio` 是首末成交额比，不是量比。
2. `RunStore` 内容寻址、不可覆盖原件、同用户同会话引用、scope/截止/哈希核验、案例锁与 run 元数据并发保护。`HistorySession` 是接既有 writer 的领域绑定，没有第二份台账 writer。
3. 自然历史意图与明确对象/日期、跨轮继承、实际 Workbench 工具装配/能力授权。中文省略年/月的连接范围可解析；限定窗口不明要澄清。主题与短公司名冲突、明确新对象被旧会话覆盖等已修。
4. 原件数据以 <=240 字完整 JSON 语义块进入模型，定义/值/unknown 分块；案例读取为 <=900 字完整 JSON 假设分页。初次 `draft`，修订 `previous_result_ref + patch` 自动保留旧假设/来源/失败/反证/已暴露样本并增版，重复保存幂等。
5. 领域完成度上限在语义判官后仍生效；历史比较用途只有单案例/相似列表时公开未完成缺口。异常恢复保留原 E 编号，领域仅提供现有哈希优先序，runtime 保持 12 条帽与工具保底；省略计数明确不代表源缺失。
6. `scripts/audit_historical_research_artifacts.py` 为可重复使用的独立复算 CLI，只读原件，不调用原计算引擎/主库。支持的公式检查、跳过、不支持版本及错误分别报告，不能当统计认证。
7. `prepare_methodology_candidate` 仅纯函数桥接现有 Rule builder/validator/compiler 的 private candidate 草稿，不写入、不登记实验、不运行评价、不晋升。

所有输出仍 `research_only=true / decision_eligible=false / promotion_eligible=false`。严格 PIT、独立样本认证、新算子沙箱、S3 正式评价/S4 方法记忆闭环未在本轮交付。L2、晚间卖方、晨汇保持 pending_sync、未排期。已有路径看能力图谱，禁止以未实现本轮桥接断言全仓没有能力。

## 现在先修这两处

### A. 应用回退工具响应没有对应调用声明

确定事实：真实 M3 `run_20260909_031431_477111` 的 `empty-pool-fallback-1` 以 `role=tool` 进入下一次请求，但前面没有 `assistant.tool_calls` 声明。第 3/4 轮都返回 HTTP 400。旧 M6 `run_20260909_023642_220318` 前四轮合法成功（最后 45,379 输入 token），第 5/6 轮首次出现同形孤儿 tool 消息后 400。因此不支持“30k 上下文长度墙”的解释。未取 provider 原错误 body；证据是非法 wire 与两次首次分叉一致，不声称已取得服务器直接归因。

- 最早变换：`intelligence/runtime/agent_episode.py::_maybe_execute_empty_pool_fallback` 直接 execute；accumulator.consume 无条件追加 tool_message。
- `intelligence/services/episode_messages.py` 的 `derive_messages`→`to_provider` 原样派生，`llm_refine.py` 发出。
- M3 durable 原件：外部根 `fixture/state/episodes/run_20260909_031431_477111_msg_fab3054fe8904e0aae228277454f172e-c86aaec9db95/events.jsonl`。event33 应用 tool_request、34 tool_result、36/41 是失败模型调用；实际派生 17/18 条消息，第16索引为孤儿响应。
- 建议而未实施：显式通用 `application_tool_call` durable 事件，同源派生成 assistant(tool_calls)，在应用发起的 execute 前记录。不能伪造 model_turn，不能只在发送边缘补假消息而让 durable/live 分叉。旧记录兼容、崩溃重放、一次执行与 E 编号要一起覆盖。
- 优先红测 `test_empty_pool_fallback.py`、`test_episode_messages.py`、`test_agent_episode.py` 的真实失败形状；普通模型工具轮保持不变。

此项只读诊断，**没有半成品代码**，没有额外模型重放。

### B. 终止校验误拒合法案例原件

真实 UI `run_20260909_031412_035721` 已保存 case v2。FINAL_JSON `history_research.result_refs` 同时引用合法 compare query 和刚保存的 case；`assess_history_finish` 的引用表只收四种 query 操作，把 case 误判 `history_unknown_result / integrity`，整篇有依据的回答变成缺口模板。新 M2/M4 也出现同一错误码，需逐条确认其引用。

接手建议（未实施）：

1. 经本轮成功 save 或 scope 校验 read 的 case 允许作为研究产物引用；read_case 增独立 `read_history_case` 元数据。
2. 引用合法性和计算资格分开：case 不算事实证据/历史计算；非 insufficient 仍须真实 query，historical_comparison 仍须 compare_cases。未知引用继续拒绝。
3. `feature_definitions` schema 明确只填定义 ID，例如 `amount_ratio@history-features-v1`，不能填公式文本。当前模型两次把公式当 ID 保存失败，之后自行修正成功；错误提示可把正确例子放在前160字符，不能放宽定义白名单。
4. 测真实跨轮 save/read case + query 的 finish，未知/只有 case/冒充比较均拒绝或保持 partial。

此项也**尚无代码修改**。不要通过删完整性门或把草稿升级为市场事实来“修好”。

## 真实验收与文件位置

外部原件根：`/Users/a77/.finance-runtime/historical-discovery-20260909`（下称 R）。不把其中数据库、用户数据、完整模型上下文提交到 Git。

- 冻结库 `R/fixture/db/market_feature_store.duckdb`，3,387,961,344 字节、只读，SHA256 `c384f071aa186f41c5ba70750a9c72799ac55ff640fd7fc2c39c601f66ac197d`。收据 `fixture-receipt.json`。未改生产库。
- 数据清点 `S0-data-audit.md`、`selected.json`、`engine-frozen-smoke.json`；最新日期 09-07。种植业只是农业代理，不能把其数值套到农业综合。2024-09 个股有19日、市场表0日，不能把相对收益缺失写成个股整月缺失。
- `frozen-migration-scenarios.json` 由独立 agent 在答案前冻结；题目不改写。`live-review.json` 只评过早期诊断版，不是最终通过报告。
- 最新全量目录索引 `handoff-run-index.json` 含每题 answer、structural/semantic/publication 状态、错误与终止原因。文件名 `verified-*` 只是本轮尝试标签，**不代表通过**。

| 场景 | 5c980d 真实 run | 实际断点 |
|---|---|---|
| UI 改1.2→1.5并保存 | 031412_035721 | case v2保留成功；history_unknown_result使公开回答未交付 |
| M1 农业 | 031431_482283 | model_finish、语义repaired/completed；尚未最终独立逐条评分 |
| M2 人形机器人 | 031431_479984 | 有13份历史原件；history_unknown_result、invalid_model_finish |
| M3 两股票/反例 | 031431_477111 | 自动回退孤儿消息400→恢复；发布上限partial生效，尚未完成条件全集比较 |
| M4 储能 | 031650_919631 | 有6份原件；history_unknown_result、invalid_model_finish |
| M5 2025股票比较 | 032003_690211 | HTTP429三次，finalization_recovery_failed |
| M6 2024股票比较 | 032019_634195 | HTTP429三次，finalization_recovery_failed |

上述短 run 均加前缀 `run_20260909_`。路径 `R/after-users/linxiaoqi5111/runs/<run>/` 下有 `continuous-episode.json`、`run.json`、answer、原件；durable events 在 `R/fixture/state/episodes/`。`run_status=completed` 只是后台运行结束，不能当研究验收通过。下一轮降低并发，避免把限流失败读作研究能力失败。

UI 连续会话为 `conv_f03500280f0e42669acb94002c4de76d`。旧版在 `run_20260909_015903_623271/history-case-0335235573bccebf1b47d6978c40bf958243266a1c030648834e30502e49a33d.json`；新版本在 `run_20260909_031412_035721/history-case-de6d99cfd20dfee91e6f3e5f36bfefd2660aae61cfc5603728563a97889d2784.json`。`verified-ui-revision-preservation.json` 独立逐字段确认 case 同一、1→2父链、全部旧假设和来源/失败/反证/暴露保留。保存成功与公开答案成功必须分别验。

同冻结库基线对照：baseline `f90af450` run `011045_123742`，实现早期 run `011045_123035`，自然问题同文。`baseline-live-workbench.json`/`after-live-workbench.json`；早期不带 live 的文件曾 mode=off，是无效对照。外部新闻和KB未全部冻结，且只有一对，不能据此宣称整体正确率/速度提升。

## 验证、取舍与沉淀

- 最终代码相关 **1101P**，收据 `/Users/a77/.finance-runtime/test-receipts/20260908T191227Z-b28d7331.json`。当时是 b28 加本轮受控变更，随后固定为5c980d；target 字段保存全部精确测试文件。Ruff、diff-check、层级/路径/字段/dataset/实际工具可达性等提交钩子通过。未运行全仓等价CI，不声称合并就绪。
- 恢复切片自测/独测167P；发布上限独测107P。句法回归不代替真实研究答案验收。
- 独立审计22份早期原件：2215检查、1198显式跳过、0错误；6 checked/13 partial/3 unsupported，收据 `historical-artifact-audit-final.json`。尚未对最新七轮原件全部独立复算，不能沿用这份数字。
- 否决任意SQL/新沙箱：当前用有类型受限算子，避免未控计算和第二套执行器；新算子按spec后续依赖处理。
- 否决全文长草稿重写：真实模型会漏旧记录，改为服务端保留并patch；仍要检查新增引用和真实父版本。
- 否决全局把semantic partial强压回去：既有deadline全槽完成有明确豁免，改用领域发布上限，不破普通任务。
- 否决只增加摘要长度：原件/模型/恢复/判官/公开答案每层必须保住语义；恢复依然有上限，不能声称全可见。
- 可复用审计已进 `scripts/`，实际 reachability 探针已接门禁。跨项目投影经验已追加 `/Users/a77/agent-memory/10_knowledge/verifier-projection-narrower-than-model-world.md`，提交 `83ddcf78`。传输配对问题未修，因用户此刻要求交接，不能写成已补门禁。

## 恢复测试环境与下一步

生产8792未动。测试8809（PID39333）已正常停止；基线8810也已停止，无需杀其他进程。`5c980d-final-health.json` 记录启动时代码干净、loaded/repo fingerprint一致、continuous=on、gpt-5.6-sol；不要用CLI冒充Workbench。

重启只供接手验收（不要输出凭据）：用 `/bin/bash` 执行现有启动器的 export 行，`eval "$(rg '^export ' /Users/a77/.local/bin/start-finance-workbench)"`，随后覆写 `WORKBENCH_REPO_ROOT/PYTHONPATH` 为本工作树、`FINANCE_WS=R/fixture`、`FORESIGHT_USERS_DIR=R/after-users`、`FINANCE_DEPLOY_LEDGER=R/after-deploy.jsonl`、`FORESIGHT_USER=linxiaoqi5111`、`PORT=8809 UVICORN_PORT=8809`，以项目解释器启动 `uvicorn intelligence.api.app:app --host 127.0.0.1 --port 8809`。将R展开为绝对路径。`source <(rg ...)` 曾静默未生效，不复用。等实际startup/health就绪再跑。

建议技能：`agent-run-triage` 用于上述两份具体失败；`diagnosing-bugs` / `tdd` 或项目适用调试流程实现修复；`code-review` 验差分；`handoff` 完成后刷新本分支在途文档。用户当前只要求交接，原 agent 不继续执行这些建议。

给接手 agent 的启动 prompt：

> 在 `/Users/a77/fwp-wt-historical-discovery` 接续 `codex/feat-historical-discovery`。先读 AGENTS、session_facts、本交接、批准的历史发现spec与执行计划。成果到5c980d已保存，但真实端到端尚未验收通过。先用现成M3/M6 durable记录修应用回退孤儿tool消息，再修合法case引用误判integrity；不得放宽证据资格。复跑相关测试、以低并发重跑同六道冻结题和原UI会话，独立复算/评分后再判S1/S2是否完成。生产8792、主库和其他agent工作树保持原状；L2/晚间卖方/晨汇只占位；不直接合main。不要把completed后台状态、保存v2或1101P当成回答质量已通过。

---

## 2026-09-09 下午 · 接手进展（代码 `b24c43f3` → `f818e6cd`）

接手 agent 按上文「现在先修这两处」执行，另外发现并修了分支原有的门禁失败。生产 8792、主库、其他 agent 工作树未动；未合 main。

### 已修（四笔提交，均 pathspec）

| 提交 | 内容 | 红/绿 |
|---|---|---|
| `a963002f` fix(history) | **B**：`assess_history_finish` 引用分两类——evidence（四种 history_query 算子）与 product（本轮成功 save、或经 scope 校验 read 的 case）；`result_refs ⊆` 并集，未知引用照旧 integrity；`history_missing_result` / `history_missing_comparison` 只看 evidence。`read_history_result` 读 case 落 `read_history_case` 元数据（此前提前 return）。`unsupported_definition` 报错前 160 字给出 `amount_ratio@history-features-v1` 形状，draft/patch schema 同步说明；白名单不放宽。 | `tests/test_history_product_refs.py` 在 5c980d 上 8 红 3 绿，修后 12 绿 |
| `7751ab81` fix(runtime) | **A**：新 durable kind `application_tool_call`（payload source/call_id/name/arguments）→ 派生 `assistant(content="", tool_calls=[…])`；`episode_messages.record_application_tool_call` 先落事件再进 messages，在 `tool_request` 之前调（声明 → 意图 → 效果），两条 loop 同一处调。不伪造 model_turn。恢复：声明落了意图没落 → `restore` 合成 tool_error{interrupted}；`fallback_already_attempted` 把声明算作已尝试。检查器 `undeclared_tool_call_ids`。事件车道、评测 L1 步表、`docs/runtime/events.md`、终态稿 §6.1(d)、空池 spec 同步。**这是 main 原有 runtime 缺陷**，本提交可独立 cherry-pick。 | `test_empty_pool_fallback` 两条 wire 断言在旧 runtime 上红（`['empty-pool-fallback-1']`）；M3/M6 真实 durable 原件复放：旧流可派生，检查器分别在 index 16 / 29 点出孤儿，插入声明后为空 |
| `b24c43f3` chore(history) | 历史三工具补 `episode_progress._TOOL_LABELS`；`docs/runtime/tools.md`、`harness-seams.md` 再生成（分支新增工具/协议后未生成，`test_runtime_catalog` 与 `test_tool_labels_cover_exactly_the_registered_tools` 原本红，不在 1101P 收据的 target 里） | — |
| `f818e6cd` fix(registry) | 全仓 CI 在 b24c43f3 上 7 红全在此：`_DEFAULT_TOOL_METADATA` 把历史三工具声明为共享 `finance_query`（批准 spec），但 `default_registry` 装配一律 `capability=name`，切换板缺三行，两条测试与一个审计脚本把工具名当 capability 传。修：装配读元数据声明（既有工具 name==capability 行为不变；探针确认无 history_intent 时不外泄历史工具）、T-7 登记 `SHARED_CAPABILITY_TOOLS`、切换板补三行、`switch_box_default_v1.json` / `tools.md` 再生成、三处改传 `DEFAULT_RESEARCH_CAPABILITIES`。 | 相关 229 项绿 |

全仓等价 CI：`b24c43f3` ruff 通过、pytest 8612P / 7F（全是上表第四行）；`f818e6cd` ruff 通过、pytest 8616P / 3F（`test_rag_worker::…first_timeout…`、`test_workbench_conversation_integration` 两条），三条均为时序敏感用例，机器负载 39–43（15 个用户、十余个 uvicorn）时抖动，单跑可过，只回退注册表改动对照也过——**不是回归，但也不能写成全绿**；负载低时再跑一遍取干净收据。收据：`test-receipts/20260909T054237Z-b24c43f3.json`、`20260909T071225Z-f818e6cd.json`（均 dirty=false）。前端 `pnpm lint/typecheck/test/build` 本轮未跑（分支未触 webapp）。

### 真实复验（8809，冻结库，代码 `b24c43f3`，并发 1）

**先修了两处环境问题才拿到可评分的回答**（详见 `.claude/lessons_learned.md` 2026-09-09 段）：
1. 启动脚本 `LLM_JUDGE_GROK_BIN=…/grok-1.0.5-…` 已不存在（grok CLI 11:18 自动升 1.0.24 删旧版），判官 `FileNotFoundError`，run 照常 completed 但公开回答全部降级成「复核服务不可用」（第一批 M1/M2 就是这样，不可评分）。改指 `~/.grok/bin/grok`。
2. 1.0.24 的 `--sandbox read-only` 在本机套不上（`/var/run/docker.sock` 是符号链接），判官 `GrokCliExit`。加 `LLM_JUDGE_GROK_SANDBOX=off`（判官本身已 `--disallowed-tools`、`--max-turns 1`）。直接调 `complete_grok_cli` 一条 2+2，9.4 秒回合法 JSON 后才发题。
**生产 8792 进程环境里仍是失效的 1.0.5 路径**（`ps eww` 实测）；生产最近一次 run 是 00:38（升级前，判官 passed），下一次生产 run 的判官会失败。需要用户改 `~/.local/bin/start-finance-workbench` 并重启 8792——本轮未动生产。

| 场景 | 复跑 run | 运行结果 | 独立评分（C1–C5，各 20） | 与上一轮对比 |
|---|---|---|---|---|
| M1 农业 | `run_20260909_140558_100256` | model_finish；finish partial（模型自报 5 条缺口）；判官 repaired；发布 completed；2 份原件复算 0 错 | **90** PASS（C1=10：按名称命中「农业综合」作代理，未披露种植业 27.58% 更高；其余 20） | 上一轮未独评 |
| M2 人形机器人 | `run_20260909_141143_465966` | model_finish；finish completed 一次通过；判官 repaired；5 query + 4 read + 1 save；5 份原件 240 项复算 0 错 | **100** PASS | 上一轮 `history_unknown_result` / invalid_model_finish → **B 修复生效** |
| M3 两股票/反例 | `run_20260909_141613_811730` | model_finish；finish completed；判官 repaired；无 model_error；6 份原件 1466 项复算 0 错 | **80** PASS（恰在阈值；C3/C5=10：验证器删了一句反例口径成孤句、公开稿缺 evidence_boundary） | 上一轮 400 → 恢复 partial；本轮模型首批非空，空池回退未触发 |
| M4 储能 | `run_20260909_142229_257953` | model_finish；finish completed；判官 passed；7 份原件 209 项复算 0 错 | **80** PASS（恰在阈值；C4/C5=10：修订条件未经自己检验结果披露、成员联接缺口未交代） | 上一轮 `history_unknown_result` → **B 修复生效** |
| M5 2025 股票比较 | `run_20260909_142644_628756` | model_finish；finish completed；判官 repaired；**触发空池回退**：`application_tool_call` seq31 → 回退 `tool_request` seq32 → `tool_result` seq33，其后四轮模型调用全部成功、0 model_error、派生消息无孤儿；4 份原件 26 项复算 0 错 | **100** PASS | 上一轮 429×3 → 本轮 **A 修复现场证据** |
| M6 2024 覆盖边界 | `run_20260909_143059_999994` | 约第 100 个事件起 429×3（重试间隔 0.6s 无退避）→ finalization_recovery_failed，公开回答降级；冷却 2 分钟后单发 `run_20260909_144012_045830` 首次调用即 429 | 未评分 | 上一轮同为 429；网关 `model_cooldown`，两个模型所有凭据冷却，reset 4939s（约 16:05） |
| UI 追问（conv_f035…） | `run_20260909_143515_517406` | 15 秒内 429×2 → repair_model_unavailable | 未评分 | 待冷却后重发 |

评分由独立 agent 只读完成（不读参考值/rubric 之外的提示），每题写出回答原句 + 原件字段/值 + 硬伤逐条核对；原件用 `scripts/audit_historical_research_artifacts.py` 独立复算。全部材料落 `R/rerun-20260909-b24c43f3/`（`rerun-index-batch3.json`、`grades/*.md`、`audits/*.json`、两份 CI 日志与收据、网关 429 探针）。三批索引：batch1（判官 FileNotFound）、batch2（判官 sandbox）、batch3（可评分）。

评分员发现的两个**审计缺口**（不是本轮修复目标）：① M3 trace 里 seq73–84 有一轮 backfill 修复，正文更完整但未被采用，且该轮事件不在 `episode.events`（止于 seq72）；② runtime 对 429 无退避。

### 现在的位置与下一步
- M6 与 UI 追问等网关冷却后（≥16:05）串行重发（`/tmp/hd_rerun.py --skill-mode hybrid M6`，隔几分钟再 `UI`），评分、复算同上；只有它们也过了才勾计划 Task 6 第一项。
- 负载低时在最终 revision 上重跑全仓 CI 取干净收据；前端叶子未跑。
- 合 main、切生产、改生产启动脚本三件都要用户确认。A 修复（`7751ab81`）建议单独 cherry-pick 进 main。
