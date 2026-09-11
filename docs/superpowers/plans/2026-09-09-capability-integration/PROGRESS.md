# 能力集成执行进度（PROGRESS）

> Spec：`docs/superpowers/specs/2026-09-09-capability-integration-and-live-research-design.md`
> 执行分支：`feat/capability-integration`（基于 `codex/docs-capability-integration-spec` a06deea7 = gitea/main b952439a + spec）
> 执行树：`/Users/a77/fwp-wt-capability-integration`。换会话先读本文件与 BLOCKED.md。
> 本文件由执行者维护；证据等级标注 [实测]/[推断]，未标注默认 [实测]（当次命令跑出）。

## 任务 0 开工回执（2026-09-09 21:55，22:15 补全后定稿）

1. 树/分支：执行树 `fwp-wt-capability-integration` @ `feat/capability-integration`；主检出（脏、detached b4a35fa2）留给原使用者，不动。
2. 远端：gitea/main=b952439a 已 fetch；生产 8792 healthy @ac013255（=#696 合入点，含 05/07/09 首刀），落后 main 12 提交；#697/#699 投影修复已合 main、未上生产。
3. 知识库：kb gitea/main=0f7ce1dfd（03 已合）；kb 主检出 af2f708 落后 5 且脏（保留原树）；全部既有 kb 树均不含 03 → 已新建干净运行树 `/Users/a77/kb-wt-cap03-runtime` @0f7ce1dfd。
4. live 端口→树：00→8813（**批次进行中** PID 30453，user=cb00-baseline，截 20:57 干净 6/30、tainted 1、待跑 23，编排/收尾 watcher 挂着，勿动）、02→8802@360ef6f0、04→8794@51ee71f8 与 8795@2ebbc04f、06→8811(base)/8812@de799ff8、08→8808@09c16461、09→8847@adcd4830（含 #697/#699）、10→8815(base)/8816@0d942702（第二轮批 pid 39647 在等 8080 探针放行）、生产→8792、launchd 能力 sidecar→8796@40fd5a84。
5. 模型/判官：网关 `http://127.0.0.1:8080/v1`，模型 `gpt-5.6-sol`；判官 grok 1.0.24（`~/.grok/bin/grok` 符号链接，生产启动器已带 `LLM_JUDGE_GROK_SANDBOX=off`）；生产 ASK_CONTINUOUS_RUNTIME=on、ASK_AGENT_LOOP=auto、ASK_EVIDENCE_JUDGE=auto。凭据不落本文件。
6. 用户/数据根：生产 users=`/Users/a77/.local/share/finance-workbench/users`，user=`linxiaoqi5111`；FINANCE_WS=`/Users/a77/finance-workspace-private`；主库 `db/market_feature_store.duckdb`（截至 2026-09-07；`fact_sector_daily` 缺 09-03/09-04，00 数据前提已冻结此口径）。
7. 日程：`daily-full-review-sync`/`-finalize`（20:40 → `~/.local/bin/nightly_full_review.sh`）今日 last-exit 均 =2 待查；包装脚本无 method_validation 接线；`launchctl list` 无 method-validation 项 → **07 blocked #3 属实，I5 未开工**；`checkpoint-recheck`(03:50) loaded exit 0。
8. 题库/规则指纹（冻结）：questions `d987df999f866873`、sealed-manifest `4ef1fd08f5db09cf`、capability_benchmark.py `6a04879c9924f07c`，均 @00 分支 `baseline/capability-benchmark-00` b044b61c；公开 20 题、密封 10 题（本体在仓外 `~/capability-benchmark-00-sealed-20260909/`，执行者不读）；判卷合同 `docs/verification/2026-09-09-capability-benchmark-00-scoring-rules.md`。
9. 代码地图：ready（n=22076 @b4a35fa），doors 查询正常返回。
10. 批次纪律：本轮新增 live 一律串行排队，调度责任人=本执行者；不停止、不复用他人进行中批次的用户域（cb00-baseline、10 的第二轮批都在跑/在等）。

## 冻结条件台账（§2.2-4）

| 项 | 值 | 来源 |
|---|---|---|
| 题库（20 公开） | sha256 前 16 位 `d987df999f866873` | `fwp-wt-capability-benchmark-00/intelligence/eval/fixtures/capability-benchmark-2026-09-09.questions.json` |
| 密封题清单（10 密封） | `4ef1fd08f5db09cf`（manifest 含 hidden_case_ids/rubrics 哈希/verify_cmd；执行者不读密封判分点） | 同目录 `.sealed-manifest.json`；本体 `~/capability-benchmark-00-sealed-20260909/` |
| 评分实现 | `6a04879c9924f07c` @ b044b61c | `intelligence/eval/capability_benchmark.py`（I1 允许改分类实现，改后此指纹按新提交重记，题面/密封判分点/权重/阈值不变） |
| 评分规则文档 | `docs/verification/2026-09-09-capability-benchmark-00-scoring-rules.md`（00 分支） | 主表 9 字段、双评 ≥20%、一致门 ≥0.8、decoy 反向验证 |
| 判官 | grok 1.0.24（`~/.grok/bin/grok` → `../downloads/grok-1.0.24-macos-aarch64`），SANDBOX=off | ls -la 实测；06 定根因（read-only 沙箱解析 docker.sock 失败拒启） |
| 模型 | `gpt-5.6-sol` @ `http://127.0.0.1:8080/v1` | 生产进程 env（ps eww，已脱敏） |
| 基线 live 占用 | cb00-baseline 批次进行中（PID 30453 → 8813@372d047c），截 20:57 干净 6/30 | ps + runs 目录 + progress/00.md |
| 00 数据前提 | DuckDB 主表截至 2026-09-07；`fact_sector_daily` 缺 09-03/09-04；`fact_mainline_sector_daily` 09-07 农林牧渔 NULL | progress/00.md 冻结段 |

## 环境与身份台账（§2.2-2）

- 金融仓：gitea/main=b952439a；生产 8792 加载指纹 `4e2acfe59bd26d9a…`（code_matches_repo=true，878 模块）@ `/Users/a77/.finance-runtime/finance-workspace-ac0132553aae`。
- 知识库仓：gitea/main=0f7ce1dfd（!146 = 03 research-map；!147=38adb7cca 门禁修）；干净运行目录 `/Users/a77/kb-wt-cap03-runtime`（detached @0f7ce1dfd，clean）。
- I2–I5 落点存在性 [实测]：main 已有 `scripts/method_validation.py`、`intelligence/services/method_validation/`、`research_project.py`、`followups.py`、`runtime/continuous_turn_adapter.py`、`market_feature_store/sync/sync_akshare_sw_l1_daily.py`；`services/data_requests.py` 仅在 08 分支；`derived_calculation*.py`/`sandbox_fincalc.py`/`ranking_contract.py` 仅在 04/10 分支；`capability_benchmark.py` 仅在 00 分支。
- 各单分支/提交：00=`baseline/capability-benchmark-00`@b044b61c、01=`fix/judge-recovery-01`@0c4a0bab(PR#693)、02=`feat/cap02-retrieval-deep-read`@63b7859a（未推远端）、04=`feat/calc-artifacts-04`@51ee71f8（叠在未合 #682 上）、06=`feat/adaptive-research-06`@de799ff8、08=`feat/demand-driven-data-requests`@3fdc1193、10=`feat/ranking-scenarios-10`@0380d812。

## 已被别人修好的缺口（§2.2-1，定稿）

- 03 已合知识库 main（!146→0f7ce1dfd）+ 门禁 !147；合并后干净检出四道等价 CI exit 0、519 passed。金融侧 `graph_lookup` 适配**未落**（main 无 `mode` 参数）。
- 09 投影缺陷 #697（subject 众数+as_of 回溯）/#699（子串归并）已合 main；生产未含。09 判卷点①-④全过（P1 六轮+P2/P3 各四轮）。B8（直答车道拿不到先验块）仍开，归 06/05。
- 05 已合 main（#696）且已切生产（8792=ac013255）；frame 级 11/12；材料内容「答案级」未验证；B05-1（turn_controller.py:1058 一行传 conversation_context）/B05-3/B05-4 未修 → 归 I2。
- 生产判官二进制被清已修（启动器 `LLM_JUDGE_GROK_BIN=~/.grok/bin/grok` + `SANDBOX=off`，备份在案）。
- 07 工程+默认入口+真实验收（带边界）+生产激活（register/history/probe）已完成（#692、#707）；**日程未装**（blocked #3）→ I5 只做「接夜跑日程 + 中断恢复实测」，不重建第二条写入链。
- 08 五子命令（build/check/fill/resume/status）+隔离全链验收完成（staging `77cb88d98b64`，1 请求 5 消费者）；sw_l1 writer 历史窗覆写缺陷（B2/B3）**未修**、引擎 A 库根只认 FINANCE_WS（B4）**未修** → 归 I4。
- I1 漏判**未修**：b044b61c 只改 watcher 闸门；`_MODEL_UNAVAILABLE_STOPS` 不含 `invalid_repair_finish` 形状（实测反例 run_20260909_205227_971715：修复收尾连续 502、carried_draft_chars=0、final_answer=None、终态名 invalid_repair_finish、未标污染）。

## 阶段计划：落点/依赖/测试/验收命令（§2.2-3）

### I1（先行）
- 修改文件：`intelligence/eval/capability_benchmark.py`（read_episode 补可用性信号、新分类函数、_load_resume_cases/build_review_pack 共用判据、summarize_artifact 可用性分母、新 `reclassify` 子命令）、`intelligence/tests/test_capability_benchmark.py`（四类反例红→绿）。
- 依赖提交：`baseline/capability-benchmark-00` b044b61c（题面/密封/权重/阈值不动）。
- 工作分支：`feat/i1-availability-attribution`（工作树 `/Users/a77/fwp-wt-i1-attribution`，不动 00 原树——其 sidecar 与批次在跑）。
- 定向测试：`.venv-workbench/bin/python -m pytest intelligence/tests/test_capability_benchmark.py -q`。
- 验收命令：`python -m intelligence.eval.capability_benchmark reclassify --artifact <旧基线件> --out <新分类报告>`（旧件保留）；真实反例：calc-01 漏判 run_20260909_205227_971715、恢复成功 feel 样本（evidence-20260909/cb00-feel-0[12]）、真实产品失败对照、判官不可用样本。
- 四类判据（spec §I1 表）：恢复有效答→接受留失败记录；终态仍上游失败无有效答→隔离（不被改名漏掉）；模型可用答错→接受判败不许重跑洗分；判官不可用/降级→按判卷合同明示。所有尝试计入可用性/耗时/费用分母。

### I5（与 I1 并行）
- 修改文件：`~/.local/bin/nightly_full_review.sh`（或其调用的编排落点，任务 0 已追到：finalize LaunchAgent 20:40 → 该脚本）+ 新 LaunchAgent plist（安装位置 `~/Library/LaunchAgents/`）；仓内脚本 `scripts/method_validation.py daily` 复用不改（除非验收暴露缺陷）。
- 依赖提交：main 已含 07 全部工程（#692/#707）。
- 验收：七类日收据（未到起点/数据落后/无信号/环境不适用/有信号/重复执行/到期缺结果）；两个中断恢复点实测（capture 落盘未登记→重跑唯一登记；到期缺数→08 补齐后同一观察再回检）；协议起点 2026-09-10，结算最早 09-17；隔离故障只作用测试域。
- 前置观察：今日 sync/finalize exit=2 待查（BLOCKED W1）。

### I2（I1 后）
- B05-1：`intelligence/services/turn_controller.py:1058` 传 `conversation_context=context`（05 已写好精确改法）；控制器全部实际入口核对。
- 材料身份找回：按身份从会话存储取原正文/版本（允许最小读取适配）；新增「长材料超窗追问」验收。
- 03 适配：`intelligence/services/agent_research.py::build_graph_tools::_graph_lookup` 加 `mode ∈ {entity,relation,theme}`（06 已写明落点），保留 known/computable/unknown 与原页指针；运行目录用 `/Users/a77/kb-wt-cap03-runtime`；研究查询只读（不调 package 写 access_log）。
- 02 送达：跨旧截断边界表格实例验证（先用现有分段机制：一段一条 ≤240 字白名单口径）；`web_fetch` 发布主体/文档类型消费者口径同步。
- 依赖提交：01@0c4a0bab、02@63b7859a、05（已在 main）、06@de799ff8；共享装配由本执行者串行整合。

### I3（I2 后）
- 收 04（51ee71f8，先理清与未合 #682 的叠置）与 10（0380d812）分支；09 产品侧消费（research_project/followups/ResearchProjectPanel）。
- 计算记录加载器绑定请求用户的 RunStore/产物域（不回落进程默认用户）；两次假设修改重算；排序消费数值证据。

### I4（修根因后接 I3）
- `market_feature_store/sync/sync_akshare_sw_l1_daily.py:283-299` 历史窗实时覆写修复（08 已定位）；`runtime/continuous_turn_adapter.py`→`services/episode_tools.py::_roots` 库根传递（08 B4）；收 08 分支接 build/check/fill/resume/status。
- 优先调查八个 `.TI` 双红空标签：881128/884059/886061/886064/886080/886081/886087/886093.TI，15/18 信号日出现（11 天恰好 8 个：2025-02-07/10/11/17、06-25/26、08-06/07/13/25、2026-01-07；4 天另缺 990167.FP：2026-01-05/06/09/12）。查 `fact_sector_daily_generation` 对应日期 `diff_ratio/amount` 缺值或 `_build_sector_labels` 处理；不放宽配对门。
- 隔离环境证明后才谈生产；生产事实仍只走 daily-full。

### J1/J2/J3 与 00 对照
- 按 spec §4/§5：先冻结输入/参考/日期/判卷点；00 对照在候选冻结后，`--decoy-case`/`--decoy-answer-file` 反向验证；两臂条件清单不可变。

## 执行状态表

| 项 | 状态 | 负责标签 | 提交 | 原件 | 下一命令 |
|---|---|---|---|---|---|
| 任务 0 | **完成**（本文件即回执+计划+冻结台账） | 集成执行者 | 见 git log 本目录 | 本文件 | — |
| I1 | **工程完成+真实重审完成**（22:15）：分支 `feat/i1-availability-attribution`@01de7e94（已推 gitea）；红→绿 6 新测试（旧代码全红）、23 全绿、ruff 绿；reclassify 重审 3 个真实原件（派生件在 `~/.finance-runtime/capability-integration/i1/`，旧件未动）——20:53 件「干净 6」实为 recovered 2（feel-01/02，中途 502 恢复出终稿）+ 漏判隔离 3（calc-01/material-01/material-02）+ 已标 1（calc-02）；16:04 废件 calc-01 同形漏标；判官不可用逐轮明示 | 00 | 01de7e94 | `~/.finance-runtime/capability-integration/i1/reclassify-*.json` | 批次收尾后由 00 用新码 --resume（不搬假干净题，按原条件重跑）；进 00 对照的候选清单 |
| I2 | 未开工 | 06/01/02 | — | blocked/05.md B05-1/3/4 | I1 后 |
| I3 | 未开工 | 06/09/04/10 | — | — | 依赖 I2 |
| I4 | 根因①完成（22:4x）@e1c08bfe：`sync_akshare_sw_l1_daily.py` 历史窗末日不再被实时行覆写——`end==date.today()` 才调 `_fetch_realtime`，历史末日缺行走 hist/板块代理仍缺则如实报错不造数；测试改「历史窗调 realtime 即断言失败」（原先允许 realtime 失败降级）。其余（08 接 data_requests 五子命令、`episode_tools::_roots` 库根传递、八个 `.TI` 双红空标签）未开工 | 08/06/09 | e1c08bfe | — | 修 `episode_tools::_roots`（B4）；收 08 分支接 build/check/fill/resume/status |
| I5 | **工程完成+生产接线验证**（22:36）@a2cec9ff：恢复点①（capture 落盘后中断→重跑补齐唯一 checkpoint，不改捕获时间）+ 恢复点②（data_insufficient 非终态，重建后沿同一观察重试）红→绿（旧实现 2 failed→15 passed）；`nightly_full_review.sh` 接 `run/skip_method_flywheel`（仅最终硬门通过后跑，失败夜写原因+下次机会），规范源+部署副本一致（旧件备份 .bak-pre-i5-20260909）；生产三元组手动 verify rc=0×2（rebuild 旁路库 09-07→09-09、capture skipped 起点未到、幂等）。夜跑 exit=2 根因=fact_theme_flow_daily 缺 09-09（其余表全到位）→ 归夜跑运维。注意：主检出（launchd 的 WORKSPACE）没有 method_validation.py，实际生效在本单合 main 后 | 07 | a2cec9ff | logs/method-validation-daily.log、docs/verification/…§I5 | 合 main 后夜跑自动生效；09-17 前后首个结算或 03:50 recheck；I4 补数后验②生产形状 |
| J1/J2/J3 | 未开工 | 集成执行者 | — | — | I2/I3/I4 就绪后 |
| 00 对照 | 未开工（baseline live 6/30 进行中，勿动） | 00 | — | ~/.finance-runtime/capability-benchmark-00/ | 候选冻结后 |
