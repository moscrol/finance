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
