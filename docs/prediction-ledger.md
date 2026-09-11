# Prediction Ledger: finance-workspace-private

- last_updated: 2026-08-29（**22:15 8792 已切 `5be00c4f563e`（29b）+ rejudge 积压清账**：用户令「切过去」。链切五步（bootout→软链→账本 switch --port 8792→3s 缓冲 bootstrap 一次过）；三项验证过：readiness 13/13（预热约 100s）、health 三读 `5be00c4f563e`/dirty=False/match=True、长电探针 `fact_stock_daily`×4、degraded=0、judge_unavailable=0、secret=0（收据 `20260829-post-5be00c4f-changdian.json`）。回滚锚 `cutover-20260829b-rollback-8792.txt`→`39c13d7caf13`；备份 post513。本批上产=白天全部合并：#509 冻结集修复（`R-20260829-01`）、#510/#512/#513 三张符合性套件（P1 收官，~372 契约断言）、#511 MARKET_DAILY 接门控（`R-20260829-02`，默认行为不变）、#507/#508 docs；批次门禁读数在各 PR（终门 7278P/0F @`5be00c4f` 收据 exit 0）。**rejudge 积压清账（21:4x–22:0x）**：97 行 →93 唯一 →44 可重放（其余 49 条 pending 行 run_id/artifact_path 双空且不存请求，工件已清理即永不可重放——占位单 `2026-08-29-rejudge-pending-replayability-workorder.md` INDEX #17）；判官=sol（Cursor 子代理×6 批，生产判官原版提示词+官方线格式渲染），收据经 `run_offline_rejudge` 落 `intelligence/eval/runs/*-rejudge.json`（44 份，已发布答案零改动，sha 断言看守）；读数 **2 confirm / 42 overturn（95.5%）**，抽查裁决可用（R4 题抓到生产判官宕机漏掉的真实内容瑕疵「逐日递减」与自引证据矛盾；休市披露句按提示词字面从严属可辩护）。**归因**：积压横跨 08-19..08-28 每日都有（峰 08-20/27/28 各 16-19 条）=判官不可用是慢性病；故障形状 GrokCliExit 18/RuntimeError 12/TimeoutError 4/旧行未记 63。**升格建议：判官备链**（grok CLI 失败回落 API 侧模型）——95.5% overturn 首次量化了判官宕机的内容代价，#513 传输套件已把两路契约钉住，接备链有现成合同面。汇总 `intelligence/eval/runs/20260829T140500Z-rejudge-drain-sol.json`。）（**16:10 用户裁决执行：8792 已切 `39c13d7caf13`（29a）+ #494 携带后关闭**：链切五步（bootout 后立刻 bootstrap 报 error 5，3s 重试即过；账本 switch 带 `--port 8792`）。三项验证过：readiness 13/13（预热约 80s）；health 三读 `39c13d7caf13` / dirty=False / match=True；长电探针 `run_20260829_160525_310737` caliber=`fact_stock_daily`×4、degraded=0、**judge_unavailable=0**（判官本轮在线）、secret_scan=0（收据 `~/.finance-runtime/live-probe-traceability/20260829-post-39c13d7c-changdian.json`）。回滚锚 `cutover-20260829a-rollback-8792.txt`→`7a8cefc16e17`。备份 `~/backups/gitea-20260829-post507.tar.gz`。**#494 处置**（用户令「合并」，但树对树=台账三行真冲突且直接合并会退掉 R-08 行与 28c 抬头，按 #464「内容由收口提交携带后关闭留指针」先例执行）：其独有增量由本行携带——第二次独立生产复评（2026-08-28 19:09–19:13，probe-r05close-0828，产物 `~/.finance-runtime/live-probe-r05-close-20260828/`）读数 R1/R2/R4 draft rate 1.0、均值 0.900、R5 0.5=判分器 REFUSAL_MARKERS 冻结词表字面未含「无法给出」（语义拒答成立、尺不改）、C1/C2 罐头保留，与 #493 的 18:23–18:31 复评互为佐证；#494 已关闭留指针（指向本行与 PR 批注）。）（**16:00 conformance 双套件验收合并（#504/#505）+ 批次门禁**：独立验收 session 执行（backlog INDEX #10/#11 收口）。两分支读数复算一致：运行时后端缝套件 43p/3s/1xf @`9b49ac0a`（INV-5 codex 阳性对照 strict-xfail 入棘轮，5 后端全参数表）、缝普查 7 够格（2 已覆盖+3 P1+2 P2）/14 不够格＋工具注册表套件 86p @`2064a50e`；merge-tree 干净、互不堆叠、零生产代码 diff。批次门禁 @`85e4b1fd`：ruff 绿 + webapp 四连（vitest 70，子树 `732c79b5` 与 08-28 生产绿读数同哈希）+ e2e 15P（8811+WORKBENCH_PYTHON）+ 全量 **7032P/1F/15S/1xf**（收据 `20260829T074556Z-85e4b1fd`，checker 八项 exit 0，干净树；对上次门禁 6902P@`572f1df9` 增量 +130P/+3S 与套件新增对账相符）。**1F 已归因非本批**：`test_frozen_thirty::test_thirty_set_dry_run_has_no_contract_gaps` A3「2026-07-23 立新能源怎么看」——隔离复跑 `c3514529`/`b77df25c` 同红（后者 28c 门禁 0F 同 rev），08-28 22:48 @`572f1df9` 尚绿，`wiki/entities/立新能源.md` 08-29 00:05 由 IMA 夜队列灌入 → 主体解析翻 company/stock_deep_dive → frame 输出换组，冻结验收清单按旧解析态标定 = **冻结集对 KB 解析态不封闭**，占位工单 `2026-08-29-frozen-thirty-kb-state-workorder.md` 已立。**8792 未切**（本批 tests+docs，较在产 `7a8cefc1` 运行时行为零变化；#471 先例切流零收益有中断成本）——**待裁决**。**#494 待裁决**：与 #493 平行收口同三行台账，树对树=outcome 已被抢先、独有第二次生产复评（19:09–19:13 `probe-r05close-0828`）佐证已留档，裁决批注在 PR 评论、验收方倾向关闭。验收树 `fwp-wt-qc-conformance`（webapp 依赖已装）接替已删的 `fwp-wt-167-merge` 供后续复用。同 PR 携带：第二轮长尾工单收口回写 `fb95aa03`（工单状态待认领→已收口，R-20260828-05/06/07/08 指针+根因订正入档）。）（**17:12 #490 合并+8792 切 `b77df25c7961`（28c）**：QC 收尾 session 执行。门禁 6885P/0F/12S 收据 `20260828T085034Z-b77df25c` exit 0；health 三读 / readiness 13/13；P0 `find_spec` 两模块生产非 None。长电复跑 `run_20260828_171124_251680`：`fact_stock_daily`×4、served 08-27=库 max、judge unavailable 噪声。回滚锚 `cutover-20260828c-rollback-8792.txt`→`e5d459338982`。`R-20260828-04` 仍 pending。）（**28日00:55 #471 验收合并+门禁收口**（独立验收 session，裁决全文在 PR #471 评论）：两份工单（工具差值 `R-20260827-14`/停更披露 `-13`）+ crosswalk 订正传播向上主干 @`85aeeeb1`。独立复核全过：分支尖全量 6837P/0F/12S 重跑一致、收据门八项 exit 0、工单 §3.0 四组数按伪码零沟通重算**全等**（747 份对齐：425/1193/698/572 + 八行工具表逐字）、§4.0 红线三消费者 `:327/:773/:1205` 逐字吻合、变异抽验 1/3 精确击杀、真仓订正实验复现。合并前置=解**当日第四例撞号**：分支 -12 与主干 dataset 单 -12 双占（双方各自避撞又撞上同号），merge-tree 实证按旧号合入 → crosswalk 重号 exit 2，故合并前改 `-14`、旧号（含短形式）引用清零；顺手修 `-13` 行「四条变异」→「五条」（旧稿残留，漏的恰是守 §4.0 红线那条变异）。批次门禁 @`85aeeeb1`（合并时点 tip；其后 #473–#475 的门禁归各自 session）：ruff 绿 + webapp 四连（vitest 70）+ e2e 15 全绿 + 全量两跑 6855P/0F/12S（收据 `20260827T162044Z-85aeeeb1`，dirty=e2e fixture state 残留、已清）与 6854P/1F（干净树）——**翻转已归因 flaky**：`test_executor_timeout_marks_pending_conversation_message_failed` 单跑 5 连 3 挂，恰是 `d0f0a681`（`R-20260827-11` 时序余量单）最后改的测试，主干存量、非 #471 引入（#471 零碰该文件且同 rev 有过全绿），**知会 -11 单 streak**。8792 未切：本批 docs+审计脚本零运行时改动，切流零收益有中断成本——待裁决。升格：①预注册号分配（分支取当日 max+1、落盘窗口并发）当日撞四例，建议立单改「先占号后施工」（与「配额在副作用前预占」同族）②crosswalk 订正词表实测漏认「已在本单修正」（隔字不匹配 `已修正`），约定依赖已发生非理论。22:00 预注册 `R-20260827-12`（原号 -11，与并发 #468 撞号改号，当日第三例）：dataset 豁免语义整改（工单 `2026-08-27-dataset-exemption-semantics-workorder.md`，P0 D6 附带发现①、用户裁决立单推进）——审计规则 3 类别白名单（`dedicated_path` 废除）+ 存量 4 张先量后判（sector_period_rank **转正**、L2 两张改判 stale_since 断更 20 天、mainline 改判 model_reachable_via），TDD 5 钉先红后绿。同时段 **8792 已切 `3da2c712`（27f，#465 controller 修复上生产）**：三项验证过（health 三读一致 / readiness 13/13 / 长电探针 `run_20260827_211959_285536` 口径 fact_stock_daily×4、degraded=0、judge_unavail=0、数据日 08-27=库 max、rev 自证），回滚锚 `41d9d8d2`（`cutover-20260827f-rollback-8792.txt`）、账本 switch 已带 --port 8792（#464 坑修）、备份 post467。21:20 `R-20260827-10` **live 已验 → confirmed（带成立条件）**：修复树 8822@`111af0f7` 复跑 D6——controller 地板生效（research+检索）、detail 留证破案（GLM 首答选对 `dated_market_review` 但只回三键被全等校验拒收=unparsable 真面目）、tool 步 0→4、答案引用 `limit_advance_daily` 与 12 行真值逐字吻合、**machine-truth rate 0.0→1.0**；顺带闭环 `-07a` 挂起项 **#454 检验通过**。21:35 批次合并（用户「最优路径」授权）：#466（registry 止血，并发 session 交付、hash 与本侧独立重扫逐字一致=交叉验证后代验收）→ #460（台账/工单）→ #465（本修复）→ main `e2242aed`；终态 registry 五道全绿、全量 pytest 见 handoff；#464 内容由 closeout 提交携带后关闭留指针。**8792 未切（仍 41d9d8d2，不含 #465）**，切流窗口开、等用户裁决。21:00 P0 复跑回填：`R-20260827-07` **改号 `-07a`**（预注册落分支期间 main 经 #462 落了 export 事故同号行，按 `-03a` 先例改号、工单引用同步）并 **→ refuted**——两臂+冻结原始三 run `ablation_activation_step=none`，但非预写形状：controller `unparsable_response` 一次失败即降级 chat 零检索，检索计划从未生成，#454 装没装上轮不到问；归因升格 controller 层，**不并入 `-09`**，修复+复验预注册 `R-20260827-10`（分支 `fix/turn-controller-unparsable-fallback`，重试一次+留首次原文+显式日期检索地板，TDD 6 钉先红后绿、变异 3/3）。发生面：8792 生产 39 run 中 4 个 unparsable 恰=全部 chat lane（B6/C8/D6/D9），D6 3/3 复现=题面相关。与 `-08` 同反模式（LLM 组件失败→粗标签留下、载荷丢弃、无重试），streak 关注。收据 `~/.finance-runtime/p0-d6-20260827/`。20:12 27e 收口（验收方独立复核后补记，原 PR #464，内容由本提交携带）：**含 #123 考卷（@`623334d3`）与 #461 export 修复在内、27d→27e 窗口 39 张合并已全部上生产，8792 已切 `41d9d8d2e60b`（27e）**；health 三读一致 + 20:04 独立第四读同（rev 自证/dirty=False/match=True）、readiness 13/13（20:05 活体，market_snapshot 与库两侧均 2026-08-27 且 consistent）、长电 grounded 探针 `run_20260827_195210_064576`（读数见 inflight/main.md 20:00 行）。`R-20260826-04` / `R-20260827-07` → confirmed（读数在行内；-07 明晚 18:30 launchd 自然复验顺带回读）。回滚锚 `40fd5a847c65`（锚文件 cutover-20260827e-rollback-8792.txt）、备份 post462（2.8GiB）。坑一枚：27d/27e 账本 switch 行 `port=None`（record 时没带 --port，infer_port 认不出不猜），按 port 过滤 switch 会漂回 03:06 的 `35e1b291`——SessionStart 事实的 8792 行因此显旧，下单补 --port。17:55 预注册 `R-20260827-07/-08/-09`：四臂对照（`~/.finance-runtime/four-arm-20260827/`，unseen 集 react 0.857 vs 8792 0.567）D6/D2/D5 三题差距收口，工单 `docs/superpowers/specs/2026-08-27-longtail-react-gap-remediation-workorder.md` 同批落地——发现此前全部留在 runtime 目录、docs/ 零字提及，正是「账本住址漂移则闭环静默断裂」的现场，本次补上。05:20 P1 收口：**#445（P1 三件）+ #447（证据页载荷修复）已合并，8792 已切 `40fd5a847c65`（27d）**，health 三读一致 / readiness 13/13 / 长电 grounded completed / 简报生产 run payload=dict·4 袋·数字⊆载荷。`R-20260827-01/-02` → confirmed（读数在行内）；`-03` pending（原生注册表四绿被他人在途 capability-switchboard 交接脏文件阻塞主树前移，CI 语义已 4/4×3 轮，不代解）。**live 首验逮到 P1b 真缺陷并当轮修复**（详见 -02 行）。今晚并发切流两起（03:06 #444→35e1b291、~03:45 #443→47cf855d），本 session 27c（67c88b27）被超越属正常并发，最终态 27d 含全部。备份 post441/post447 两份。教训两条：管道 `| tail` 吞 git 退出码曾让链切在 worktree add 失败后继续走（靠 launcher fail-closed + 补建目录恢复，服务中断约 2 分钟）；harness 壳一次楔死在 bootstrap `cat <&3`（35 分钟假等待，杀后重跑，读数无污染）。02:50 用户裁决切流：8792 已切 `67c88b27b75b`（27a），三项验证全过、回滚锚与备份在位，自选简报生产门冻结题过（读数见 inflight/main.md 02:50 行）；切流把 #427 首次送进夜跑运行时（`FINANCE_CODE_ROOT`=runtime 符号链，plist 实证），今晚 18:30 夜跑自此才是 `R-20260826-04` 的干净判据。01:55 验收收口：**#439 已合并 @`547653c4`**，`R-20260826-05/-06/-07` live 过 → 全部 confirmed（收据在各行内）；批次门禁四叶全绿 @`547653c4`：pytest 6654P/0F/12S + 前端四连 + e2e 15（8811 端口 + venv PATH）+ registry 4/4；**8792 未切**（spec §10 本单默认不切）待用户裁决；真画像 linxiaoqi5111 已钉（watchlist=飞书自选股表 13 只逐字，派生题材 10 个 n≥4，focus_themes 留空待手钉）。21:35 预注册 `R-20260826-05`…`07` 自选简报包（watchlist_digest）：原会话预注册号 -01…-03 与当日其他 session 撞号，实施分支 `feat/watchlist-digest-pack` 改号入表；离线 24 钉已绿、live 未跑、三行均 pending。20:05 追加 `R-20260826-04`：夜跑 sector-daily EMFILE——**归因更正**：非「上游数据未就绪」而是 fupanhui 直连 401 风暴下 HTTPError 持 socket 等 GC（与 -03 同族、同日第二例），修复 #427 已合；19:32 并行 session 手动补跑已换名进生产、readiness 13/13，但高 ulimit 壳成功不作 confirmed 依据，干净判据=明晚 launchd 夜跑，本行 pending。19:20 状态：#417/#418 已合并、8792 已切 `c0226f34`，`R-20260826-01/-02/-03` 全 confirmed（-02 带成立条件：sw_l1 映射缺口 119/403，回填工单 #429 已立）。实测目录 `~/.finance-runtime/trace-diff-spt-forward-20260826/`、`~/.finance-runtime/boundary-probe-20260826/`、`~/.finance-runtime/cutover-20260826f-8792/`。）
- 配套文件：[trace-profile.md](trace-profile.md)（同址、同为被审方资产）
- 消费方：`agent-run-triage` skill 的 `Prior prediction closure` 段
- 结构依据：skill `references/adapters/prediction-ledger-template.md`（四段结构与列名不自拟）

每条修复建议都带一条可证伪的 `verification_prediction`（「改完之后会看到什么」）。
**这些预测的唯一事实源是本文件**，报告里的 `Prior prediction closure` 段只是它的一次切片。

住址固定为 `<project>/docs/prediction-ledger.md`：本项目会被多个 harness
（Grok / Codex / Claude）共用同一份实体目录，若各 harness 把结论留在自己的报告里，
下一个 harness 去别处找 pending，**闭环会静默断裂且不报错**。

用法：分诊**开工第一步**先读 Open 表，用本次 trace 回填 `confirmed` / `refuted`，
再开始新归因。顺序不能反——否则新证据被本次结论污染。

### 记账规则（照抄，不要各自发明）

- `refuted` 是本账本**最有价值的输出，不要粉饰成 `pending`**。前者是「上次判错了层」的硬证据并驱动升格；后者只是「还没测」。把判错记成没测，长期命中率永远攒不出来。
- 同类 `fix_type` 连续 ≥3 次 `refuted` → 停止再堆同类修补，升格质疑 `HARNESS`/架构层。**streak 按本项目累计，不跨项目**。
- `fix_type` 只能取这 7 个值：`SYSTEM_PROMPT_FIX` / `TOOL_DESCRIPTION_FIX` / `ROUTING_FIX` / `DATA_CONTRACT_FIX` / `HARNESS_FIX` / `EVAL_ONLY` / `NO_SYSTEM_FIX`。**不要发明新值**（例如 `CONTROL_FLOW_FIX`）——fix_type 是冻结枚举，新增须走 skill 的 `known-gaps.md` 晋级线。
- 只记引用、hash 和最短摘录。用户题面、答案正文、持仓/股票池、凭据不进本文件（本文件进 git）。
- 条目来源不是标准四阶段分诊时（如代码审计、收口）**必须在溯源段写明**：这类条目只有 `fix_type` 与 `verification_prediction` 可用于 streak 统计，**不能当作已确认根因的 PRIMARY 引用**。

### Open（pending）

| ID | 来源 | fix_type | verification_prediction | 怎么验 | outcome |
|---|---|---|---|---|---|
| `R-20260908-05` | 用户 09-08 授权第一条方法验证闭环；`docs/superpowers/plans/2026-09-08-method-validation-loop.md`；号由 claim_ledger_id 原子领取 | `EVAL_ONLY` | 在主升/反弹阶段，连续至少三日严格双红组的后五日均值相对当日双红组、同日板块总体是否提供正的增量；不预先认定成立。沿用 seed v1 阈值，冻结 2024-12-20 至 2026-09-07 历史窗，前向自 2026-09-10 开始，日期等权，全部基准成员结果完整才比较 | 三组固定日配对；保留未到期、缺数据、非适用日与全部成员；历史结果仅描述性。真实收据由 method_validation CLI 落 `~/.finance-runtime/method-validation-first-cycle/`，同日观察只登记一次，回检不重新选样。严格 PIT 和统计认证依赖另一基础补强任务，当前禁止晋升 | `pending`（程序交付：e41ef60b、240P；历史416天仅2共同完整日，连续组相对当日组-0.5629pp，不判有效/无效；验证见 docs/verification/2026-09-08-method-validation-loop.md；真实前向观察尚未发生） |
| `R-20260908-01` | **溯源：非标准四阶段分诊**——2026-09-07 GLM-5.3-flash 能力天花板探针（收据 `~/.finance-runtime/glm-ceiling-20260907/RECEIPT.md` §1–§3）。现场：max 档 D5 思考臂两发 `judge=unavailable`，收据 `judge_attempt_index=1 / timeout_asked=0.0 / remaining_seconds_at_entry=415–469`，issue 却写 deadline exhausted。两层根因：①判官窗 `semantic_judge_window_seconds()` 不传 policy 时走 `policy_for_env()`，读的是 `ASK_RESEARCH_TIER`，生产设的是 `WORKBENCH_RESEARCH_TIER=max` → max 档判官按 standard 派生（50s 窗 + 50s 帽 = 只发得出一次）；②首发超时耗光整窗，第二发拿 0 秒，被记成根期限到点。真实载荷重放 grok-4.6 n=6：p50 52.0s / max 60.6s，4/6 超 50s | `HARNESS_FIX` | 分支 `fix/judge-window-follows-tier`：判官窗与单次帽从**合同档位**派生（`policy_for_contract`），max 档单次 75s / 窗 150s（= 两次完整尝试），quick/standard/deep 一字不变；「窗被前一发吃光」拆成 `WINDOW_EXHAUSTED_ISSUE`。预测：切流后 max 档 run 的判官收据 `timeout_configured=75.0`；大载荷（≥20 句）判官 unavailable 中「窗耗光型」（`attempt_index=1, asked=0.0, remaining>100`）归零；sol 主链 judge_unavailable_count 不升（帽只放宽不收紧）。失败形状①：切后仍见 `attempt_index=1 / asked=0.0 / remaining>100` → 窗没跟档位走，refuted；失败形状②：出现 issue=`WINDOW_EXHAUSTED_ISSUE` 但 `deadline.expired=True` → 判据反了，refuted；失败形状③：standard/deep 档收据 `timeout_configured≠50` → 越界改动，refuted | 离线：`test_stage_caps.py` + `test_episode_semantic_verifier.py` 4 条新钉先红后绿（关 max 分支的变异 3 红 1 绿）、邻域 23 模块 556P、pre-commit 10/10。**旁支 live 已验（修复分支 sidecar 8797/8798/8799，GLM-5.3-flash max 档，23:57–00:31）**：11 发跑完 episode 的 run 判官 11/11 passed/repaired、`asked=75 / configured=75 / attempt 0`；旧代码同臂 D5 三发 2 发 unavailable。生产（sol@8792）切流后按上述三条失败形状复核。**首读（2026-09-08 02:06，0908b 切流 `0060da5c1a08`，探针 `run_20260908_020235_111517`）**：判官收据 `timeout_asked=75.0 / timeout_configured=75.0 / attempt 0 / remaining 667`，judge passed——预测第一条命中，三条失败形状均未出现；「窗耗光型归零」与「sol judge_unavailable_count 不升」待自然样本（切前 09-03 基线：判官不可用把生产弃权率从 3% 抬到 25%） | `pending`（首读 ✓） |
| `R-20260830-02` | **溯源：非标准四阶段分诊**——勒死单 `docs/superpowers/specs/2026-08-30-engine-b-into-a-strangler-design.md` P0。现场：D10 早有 `as_of`，D8/D11 没有，所以 A 开口预取只能给这两块写 gap（`asof_prefetch._history_analog_items`），「有格子没供数」在同一批题上复发。根因不是接线漏了，是**取数函数缺 `as_of` 能力**，且解析器（`_resolve_stock` 钉 `max(trade_date)`、`resolve_query_themes` 扫全表）是**数据自派生的基准** | `HARNESS_FIX` | 算子命中的冻结题，A opening prefetch 出现 D8/D11 的块或显式 gap；且**同题跨两个 as_of 跑，块内最大日期随 as_of 变**。失败形状①：只截历史查询、漏截解析器 → 块头主体来自库尾那天的宇宙、窗口截到 as_of，两个日期不是同一天而整块自洽 → refuted；失败形状②：`as_of=None` 时 B 侧输出与改前不逐字节一致 → refuted | 离线：`intelligence/tests/test_analog_as_of_truncation.py`（10 条）+ 全量 7257P/0F @旁支；**五个变异逐条证伪**（D11 解析器不截 / D8 解析器不截 / 两块历史查询不截 / 预取漏传 as_of ×2）。live=8792 切流后冻结题复验。**未合 main 前保持 pending** | `pending` |
| `R-20260830-03` | **溯源：非标准四阶段分诊**——勒死单 P1。现场：双红口径在树里有**三份互不引用的实现**（`market_feature_store/signals.py` 写死字面量 / `theme_lifecycle_timeline` 自带 `DOUBLE_RED_PCT/DIFF/AMOUNT`、Engine A 的 `asof_prefetch` 走这份 / `market_regime_analogs._AUX_QUERIES` D10 里再写死一次），**数值恰好一致所以无人发现，且每一份自己都自洽**。分家线正好压在 A 侧与 B 侧之间；D10 同时供 A 预取与 B compose | `HARNESS_FIX` | 阈值只在 `signals.py` 三行，谓词串由它们生成且与手写版**逐字节一致**（B 侧既有 SQL 零改动）；生产代码除 `signals.py` 外不得出现写死的双红谓词（棘轮基线 `daily_review.py=4`，只许缩不许涨）。失败形状①：某处又写死回字面量而数值比对类断言仍全绿 → 说明尺子选错（数值比对在三份各自硬编码时也绿）；失败形状②：行字典版 `is_double_red` 自带比较逻辑 → 块与时间线可互相矛盾 → refuted | 离线：`intelligence/tests/test_double_red_single_source.py`（6 条，主门禁是**棘轮式源码扫描**不是数值比对）+ 全量 7257P/0F @旁支；三个变异逐条证伪。**未合 main 前保持 pending** | `pending` |
| `R-20260830-05` | **溯源：非标准四阶段分诊**——2026-08-30 会话拍板「优化后只留包椅与引擎 A；包=固定工作流（步骤/空态/数字格在代码里，不是提示词搬家）；研究题 A 整台拒收出声明缺口，不用旧 `answer_query` 循环托底（托底则 B 也得养，假兜底）」。设计稿 `docs/superpowers/specs/2026-08-30-optimized-orchestration-contract-design.md`。勒死单 T1 由本行收口为 (a)。实施仍归 `2026-08-30-engine-b-into-a-strangler-design.md` P2/P3，本行不代验 P0/P1 取数接线 | `HARNESS_FIX` | P2/P3 落地后三条同时成立：①包椅题公开稿数字 ⊆ 包 `render()`/快照，`compose=False`/`synthesize=False` 已锁，trace 无 `generic_research_owner` 阶段、无 `run_agent_loop` 调用（**包椅不许数 `ask_root`**：盘面/复盘/外盘绑包后落 `else` 进 `_run_answer_query_with_watchdog`，合法带该阶段，且 P3 目标态就要留在 `answer_query`；只有自选与披露在 orchestrator 内短路。拿它验包椅会把正确的目标态判红）；②研究题（含 `general_finance_qa`）主循环只有 episode，同上三锚点为 0（**不许数** `capability="agent_loop"`）；③研究题 A 未能开张 → 声明缺口稿且收据自述未进 episode，不得出现三锚点。失败形状①：研究拒收仍进 `_run_answer_query_with_watchdog` 且 `compose=True` → 本行 refuted；失败形状②：盘面/自选公开稿被模型改数 → 包椅破，本行 refuted | 离线腿随勒死单 P2/P3 实施 PR；live=8792 切流后冻结包椅题 + 一题研究题 + 一次强制 A 未开张。**未实施前保持 pending** | `pending` |
| `R-20260830-04` | **溯源：非标准四阶段分诊**——2026-08-30 会话裁决「工作台纠偏没接成环，只有判官 repair 是环」；设计稿 `docs/superpowers/specs/2026-08-30-workbench-correction-loop-design.md`。现场：Workbench UI/API/runtime 零处 `record_correction`；用户说「不对」只进 `ConversationContext`；`AGENTS.md` 义务只到编码会话。修复=P0 写侧：`workbench_correction_ingest` 精度门（须有上一轮 assistant + 「应为」载荷；评盘面/工程词表/探针身份不写；`default` **要写**）→ `corrections.record_correction`（`source=workbench_conversation`）fail-open；读侧开口必取归姊妹单 `2026-08-30-coverage-without-number-ownership-design.md`，本行不代验 | `HARNESS_FIX` | 离线：冻结对话 W-corr-1 写入且带 source；W-corr-2/3/5 零写入；W-corr-4（`user_id=default`）写入；写入抛错研究仍跑。live：生产身份 `default` 走一遍正例，`FORESIGHT_USERS_DIR` 下该用户 `corrections.jsonl` 尾行 `source=workbench_conversation`。失败形状①：`default` 被跳过（抄了 `_ingest_track_next_watch` 名单）→ 本行 refuted；失败形状②：「这波不对，应该是情绪退潮」也写入 → 精度门松，本行 refuted | 离线腿随实施 PR；live 腿=8792 切流后工作台正例。**未实施前保持 pending** | `pending` |
| `R-20260829-04` | 工单 `docs/superpowers/specs/2026-08-29-rejudge-pending-replayability-workorder.md`（INDEX #17，rejudge 清账产出）。现场：`append_pending_from_artifact` 落行时 run_id/artifact_path 双空（adapter 调用点不传、artifact 无 run_id 键），judge_request 不随行存——工件一被清理，积压行只剩 sha 指纹**永不可重放**（2026-08-29 清账实测 49/93 唯一 sha 即此形状）。修复=①行内内联 `judge_request`+`published_answer`（**行即夹具**，独立于工件生命周期；`has_judge_request` 语义收紧为「行内自带」）；②`episode_task_id` 从 artifact 自带的 contract.task_id 免费取（adapter 调用点零改动）；③新 `replayable_pending_rows()` 把行分（可重放, stale）两组**不改写索引**（旧行如实归 stale，不硬清不假装）；④CLI 加 `--export-fixtures`：可重放行导出夹具文件供外部判官批量裁决（本次 sol 清账 prepare 步的固化），stale 行拒绝导出 | `HARNESS_FIX` | 离线：(a) 新行内联三件且 episode_task_id 就位；(b) **行即夹具**：删工件后 `run_offline_rejudge(row)` 直接重放出裁决；(c) 新旧行分类如实（旧式 has_judge_request=True 但行内无请求 → stale）；(d) CLI 导出只含可重放行。live：下一次 judge_unavailable 发生后，索引新行带内联请求（工件无关可重放）；下一次积压清账 0 条「因工件丢失不可重放」（基线：本次 49/93） | 离线 **[已过，实施与本行同 PR]**：3 新钉先红后绿 + 既有 5 钉零回退（8P）；adapter 邻域 88P；ruff 绿 | `pending`（live 腿=下一次 judge_unavailable 自然发生 + 下一轮清账读数） |
| `R-20260829-03` | 工单 `docs/superpowers/specs/2026-08-29-judge-fallback-chain-workorder.md`（rejudge 清账归因升格：判官宕机慢性病 08-19..28 每日都有、95.5% overturn 量化内容代价；08-28 grok 402 靠手工改 env 切 sol 救场且注释明言临时）。现场：判官解析「二选一」单点（grok-cli 优先于 API key），无备链，主判官断供=整段 judge_unavailable。修复=①`judge_provider_chain()`：主判官解析一字不动 + 显式备胎（**新词表** `LLM_JUDGE_FALLBACK_API_KEY/_BASE_URL/_MODEL`——不复用 `LLM_JUDGE_MODEL`，CLI 主历史部署用它命名 grok 模型会互踩）；同端点去重；只配备不配主=未接线空链；**永不自动追加合成主链**（「不静默退回相关自审」在案红线不破例）。②verifier 槽位轮转：attempt 0 主、1+ 备（`MAX_SEMANTIC_JUDGE_ATTEMPTS=3` 不加槽）；主放弃且下一槽换人且窗口未烧穿→放行换人重试；释放安全账跨人如实累计。观测=既有调用台账逐 attempt 记 provider 名（`judge-fallback` 可查），零 schema 新增。激活手册在工单（grok 回归时取消注释三行+现 sol 三行改名 FALLBACK；当前 sol 单主不改也照跑=链退化单主行为不变） | `HARNESS_FIX` | 离线：(a) 救场钉——主判官 `LLM 调用 HTTP 402`（生产真实断供形状，分类不可重试）→ 备胎接管，observed=[主,备]、judge_status=passed、correlated=False；(b) 主健康→备胎零触碰；(c) 链耗尽→仍如实 unavailable；(d) 链构造五钉：链头与 `judge_provider()` 全等/单主/只备不接线/同端点去重/合成 provider 永不自动入链；(e) 变异「枯死换人判定」→救场钉必红。live：激活（用户改 env）后 30 天窗口，主判官断供不再产生整段 judge_unavailable，备胎接管在调用台账留 `judge-fallback` 记录。失败形状①：主判官可重试瞬时故障被换人抢跑（主只得一枪）→ 轮转策略过激，收窄为「仅不可重试时换人」，本行 refuted；失败形状②：链上出现合成主链 provider → 红线破，本行 refuted | 离线 **[已过，实施与本行同 PR]**：救场/零触碰/耗尽 3 钉 + 链构造 5 钉先红后绿；变异精确杀（枯死判定→救场钉红 1F/还原 174P）；存量判官测试 171 条零回退（合计 174P）；ruff 绿 | `pending`（live 腿=激活待 grok 额度恢复后用户改 env；当前 sol 单主继续跑不受影响） |
| `R-20260829-02` | 工单 `docs/superpowers/specs/2026-08-29-market-daily-gating-workorder.md`（INDEX #16，datablock 套件（#510）装配对账首跑产出）。缺陷：`MARKET_DAILY` 注册进 evidence_registry（检索计划可选词表；`PERSPECTIVE_MANDATORY` 含它、planner 注释明言「走 owner 侧预取」），但执行点（ask.py `_generic_market_data` mainline_current 档 owner 预取）**从未接** `provider_enabled`——`without_providers("MARKET_DAILY")`/LLM 检索计划裁剪对它无效，「仪表可配置、实际不接线」，与 MOC「授予的额度必须真的传到最下游执行者」同族。修复=mainline_current 分支前置门控；被裁剪=**诚实缺席**：零下游取数、trace `skipped`+`market_daily_pruned_by_enabled_providers`、空证据经既有 prefetch/完成层自动投影成 required-output 缺口（公开词面「同日市场总览」尚缺），**不回落**周窗口等替代口径（2026-06-22 静默换口径同族禁忌）。默认 `enabled_providers=None` 行为逐字节不变 | `HARNESS_FIX` | 离线：①TDD 新钉（裁剪→零下游[哨兵 raise 证零触碰]、skipped 痕、mainline_context 不连坐、答案缺口含「同日市场总览」）先红后绿；②datablock 套件棘轮闭环：修后 `DB-6:MARKET_DAILY` strict xfail 转 **XPASS(strict) 逼清账**（棘轮闭环首次真实运转），该块转声明旁路、baseline 回空、套件 194P；③邻域（owner 54P + registry/capabilities）+ ruff 绿。live：生产默认 None 不触发本门——自然观察窗=后续 `ASK_PLANNER_MODE=llm` 灰度或视角计划真裁剪该块的 run，trace 应见 skipped 而非取数。失败形状①：裁剪后仍见 `_daily_market_overview_block_for_llm` 调用 → 门没接到位，本行 refuted；失败形状②：mainline_current 默认路径（未裁剪）行为变化 → 越界，本行 refuted | 离线 **[已过，实施与本行同 PR]**：红→绿全链（首红=哨兵抓到裁剪后仍触下游）；XPASS 清账实录在 baseline.py 头注；298P 邻域 + 分支尖全量见 PR | `pending`（live 腿=灰度/视角计划自然观察窗） |
| `R-20260829-01` | 工单 `docs/superpowers/specs/2026-08-29-frozen-thirty-kb-state-workorder.md`（conformance 验收批次门禁 1F 归因产出）。根因两层（比工单初判多出第二层）：①**冻结集两本锚定词典只密封了一本**——conftest 封证券名单（`ENTITY_ANCHOR_SECURITIES_DB=0`），wiki `entity_exposures` 读活库；08-29 00:05 IMA 夜批灌入「立新能源」实体页后，A3 解析翻 company/stock_deep_dive，代码零变化由绿转红（08-28 22:48 @`572f1df9` 门禁同代码尚绿）。②**benchmark 缺口计算做字面比较**，缺生产侧 `_LEGACY_OUTPUT_ALIASES` 归一——同义覆盖（direct_answer→direct_assessment、evidence_boundary→counterpoint）被误报成缺口；旧解析态是字面碰巧相等才一直绿。且双向敏感：wiki 变空则 B4/C9 的题材主体（电网设备，来自实体概念词典）反向出缺口。修复=①测试密封：`KB_VAULT` 钉到 `intelligence/eval/fixtures/frozen-thirty-wiki`（最小词典：瑞华泰/立新能源/万控智造[电网设备]+**哨兵实体**，哨兵解析落空即红并点名「密封未生效」，防 env 接缝静默失效退回活库）；②尺子：`_acceptance_contract_gaps` 经别名表归一后再比（延迟 import conversation_orchestrator 唯一事实源，禁抄第二份）。冻结题面/真值文件零改动，生产代码零改动 | `HARNESS_FIX` | 离线：(a) 外部 KB 三态（空 wiki/未设变量/指活库）下测试同结果；(b) 变异 1 撤归一化→必红且缺口点名 A3；(c) 变异 2 夹具路径失效→哨兵断言红并带「密封未生效」信息；(d) A3 在夹具下钉住 subject=立新能源、question_type=stock_deep_dive。live：30 天窗口内批次门禁不再出现该测试因 KB ingest 翻转（基线：08-29 首例） | 离线 **[已过，实施与本行同 PR]**：TDD 红→绿（夹具先使红确定化：字面缺口在钉住的解析态下必现；归一化落地转绿，7/7）；变异 2/2 精确杀（撤归一红、破密封哨兵红带信息）；三态判据 3/3 过；邻域 216P（frozen_thirty/entity_anchor/query_understanding/tool_produces_satisfiability 127 + benchmark 直接消费者 89）+ ruff 绿 | `pending`（live 腿=30 天窗口自然观察） |
| `R-20260828-08` | 审架构（2026-08-28 晚，harness-architecture-review 对 #489/#490 三家族收口后的路由层复审）发现项 1：以 question_type 为键的手写名单 ≥5 张分布 3 文件（`DETERMINISTIC_OWNER_TYPES`/`CONTINUOUS_FAST_PATH_TYPES`/`_FAST_PATH_TYPES`/`DO_NOT_LENGTHEN`/`_COMPANY_SUBJECT`），组合矛盾无门禁——F1 正是三表各自「对」、组合成死路。且有活漂移：F1 把 quick_fact 移出拒接名单后，评测分臂 `_FAST_PATH_TYPES` 仍含 quick_fact，A/B 会把它跑成 runner「尚未接入」空壳臂；`CONTINUOUS_FAST_PATH_TYPES` 与 runner 内硬编码 `!= "market_technical"` 同一语义写两遍。修复=①runner 支持集提常量 `FAST_PATH_RUNNER_SUPPORTED_TYPES`，adapter 名单直接引用（单一真本源）；②`_FAST_PATH_TYPES` 移出 quick_fact（评测臂跟上生产路由）；③新 `test_route_composition_gate.py`：名单成员合法性（7 张，分母=route_table ∪ `QUESTION_GENERAL`）、拒接∩快路径=∅、评测臂⊆非 episode 集、快路径名单==runner 支持集、路由题型 evidence_policy 映射完整、episode 合同标配 `finance_query`/`evidence_search`（F1 生效机制防回退）。生产答题路径零行为变化（adapter 名单值仍 ={market_technical}，runner 判断等价）；评测侧 quick_fact 回 episode 臂是语义修正 | `HARNESS_FIX` | 离线：突变「quick_fact 加回 `_FAST_PATH_TYPES`」→ `test_eval_arm_roster_is_subset_of_non_episode_types` 红且报错点名漂移题型；还原后 12P；受影响面（episode_tools/adapter/residual_budget/watchlist_pack/agent_episode/seam_ladder）全绿。失败形状①：门禁把合法表外题型（legacy 兜底 `general_finance_qa`）误判红 → 分母口径错，本行 refuted；失败形状②：新增 question_type 名单不登记 `_ROSTERS` 即无覆盖 → 门禁范围虚标，需回写测试 docstring | 离线 **[已过，实施与本行同 PR]**：突变实测红（`评测确定性臂包含生产会进 episode 的题型：['quick_fact']`）、还原绿；新门禁 12P + 受影响面 338P + ruff 绿。已知偏差如实入档：market_watch/watchlist_digest/disclosure_scan 生产拒接走 legacy 而评测仍按 episode 臂跑（测生产不走的路），收敛会动 benchmark 基线读数，留待基线换代，本门禁用 ⊆ 单向断言不掩盖它 | `confirmed`（离线判据；成立条件：门禁只覆盖登记进 `_ROSTERS` 的名单；评测臂已知偏差三类在案未收敛） |
| `R-20260828-07` | 工单 `docs/superpowers/specs/2026-08-28-longtail-round2-quickfact-gap-workorder.md` R5 残余（F1 路由已过：3×`finance_query[sector_daily]`，但空结果只说「结构化查询无结果」，模型把「航空发动机」放宽成「航空」近邻替代）。修复=定点空结果且带 filters 时探针最后一次出现：问句日数据集有别的行、该筛选停在更早 → `_exited_universe_result`（构成要素退出，非数据陈旧）。从未出现仍走空结果。C1/C2/stale 红线不动 | `DATA_CONTRACT_FIX` | 离线：夹具「航空发动机」07-24 末行、08-19 仅「航空/芯片」→ observation 含「构成要素退出」与 07-24，不含「结构化查询无结果」、不含近邻成交额 261.26。live（sidecar 会话路）：R5 首跳 `finance_query` observation 含退出事实，答案不得把「航空」数字当「航空发动机」。失败形状①：observation 仍是无结果 → 探针没接到空路径，本行 refuted；失败形状②：把从未出现的名字也说成退出 → 过触发，本行 refuted | 离线 **[已过，实施与本行同 PR]**：钉先红（observation=`结构化查询无结果`）后绿；邻域 stale/historical/exited_universe/F2 flush 20P + ruff。**live 已验（2026-08-28 15:38 sidecar 8797@`95fa4100` 会话路，run `run_20260828_153826_624785`）**：首跳 `contains 航空发动机` 空结果 → observation=「最后一次出现是 2026-07-24；数据集已更新到 2026-08-19，其后未再出现（构成要素退出，非数据陈旧）」+07-24 行；模型未放宽到「航空」，私有稿明确「无法给出当日取值：口径缺口」，无近邻 261.26。近邻替代消失。判官复核服务不可用扣公开稿（外部容量，与当晚 Grok 402 同源），工具面判据不受影响。**生产 live 已验（2026-08-28 18:23–18:31，8792@`b77df25c` 会话路，run `run_20260828_182719_909896`）**：首跳 observation=「最后一次出现是 2026-07-24…（构成要素退出，非数据陈旧）」+07-24 行，不是「结构化查询无结果」。次跳才查「航空/航空装备」；私有稿列 261.26 作最近似口径，但写明「取值不能等同于航空发动机板块本身」。失败形状①②未发生。machine-truth 私有稿 0.5=拒答词表未覆盖「无数据行/证据缺口」，不是把近邻当主体。公开稿仍被 `judge_unavailable` 扣下（容量桶）。产物 `~/.finance-runtime/live-probe-8792-round2-post489/` | `confirmed`（成立条件：生产会话路；工具面看首跳 observation；合成层允许列近邻但必须声明不可等同） |
| `R-20260828-06` | 工单同上 F2（独立复核钉：R6 首轮 `model_turn.tool_calls` 已发出正确 `finance_query[sector_stock_daily] order_by=return_5d_pct`，随后无 `tool_request`，`stop_reason=deadline_exhausted`、`carried_draft_chars=0`；修轮 `remaining_calls=0`/`reopen_tools=false`。不是「知道缺、不去补」，是邮箱里的查询被 consume 失败丢掉）。修复=`_consume_root_seconds` 失败且本轮已有 `tool_calls` 时 flush 再停：不发明稿、不开下一轮模型。取消路径仍不跑工具。原则与 `_settle_batch_calls` 同源——已经发生的工作不能 fail-closed 扔掉 | `HARNESS_FIX` | 离线：工具轮 consume 失败 → runner 被调用 1 次、`tool_result` 在 events、`draft==""`、`stop_reason=deadline_exhausted`、`carried_draft_chars=0`；合法 FINAL_JSON 仍交卷；取消仍 0 次工具。live：R6 冻结题 sidecar 复跑，trace 出现已派发的 `finance_query` 且 `order_by=return_5d_pct`（不再是 model_turn 有调用、无 tool_request）。失败形状①：仍 0 次 tool_request → flush 没接到 consume-fail，本行 refuted；失败形状②：consume 失败却发明稿 → 回归 R-20260817-01，本行 refuted | 离线 **[已过，实施与本行同 PR]**：旧钉「不得再跑工具」先红后改成 flush-then-stop 绿；finalize 交卷与取消路径回归绿。**live 已验（2026-08-28 15:39 同 sidecar，run `run_20260828_153908_887609`）**：首轮 `return_5d_pct is-not-null` 写法 tool_error（重试提示接住），次轮 `order_by=return_5d_pct desc, limit=15, 08-26` **tool_result 命中 15 行**——R6 首轮被 deadline 丢掉的补查形态这次真正派发并返回；后续 graph/kb/news 跟进，私有稿判 耐科装备 +15.9%（与冻结真值一致），并指出预取成交额 top12 无人进 5 日涨幅前五。判官外部容量不可用扣公开稿，rate 待切流后复评。**生产 live 已验（2026-08-28 18:28，8792@`b77df25c`，run `run_20260828_182816_607781`）**：首跳即派发 `finance_query[sector_stock_daily] order_by=return_5d_pct desc`、`sector_name eq 半导体`、08-26，`tool_result` 命中耐科装备 +15.9（私有稿 rate **1.0**）。`stop_reason=model_finish`——本轮没打到 consume-fail flush（与 sidecar 同：dispatch 判据过，flush 仍靠离线钉）。失败形状①②未发生。不改 prefetch。 | `confirmed`（派发 `return_5d_pct` 已在生产 tool_request；flush 本轮未触发） |
| `R-20260828-05` | 工单 `docs/superpowers/specs/2026-08-28-longtail-round2-quickfact-gap-workorder.md` F1+F3（第二轮 react vs 8792 对照：quick_fact 排名/成员冠军/退清单 0 次 finance_query；区间终点周六被 `calendar_disclosure` 整题 canned。独立复核钉 F3 不是 needs_retrieval 误判，是日历罐头过触发；F2 预取锚定本行**不修**——首轮已发出正确 `return_5d_pct` 补查被 deadline 丢掉）。修复=①区间题且含可检索交易日时 `deterministic_lane_answer` 不 canned（休市句仍注入假设、检索后前置）；②`quick_fact` 移出 `DETERMINISTIC_OWNER_TYPES`，结构化取值进 episode（合同含 `finance_query`，单日问句 cutoff=requested）。C1/C2 单日休市罐头保留 | `ROUTING_FIX` | 离线：区间终点周六题 `deterministic_lane_answer is None` 且 C1/C2 仍 canned；排名 quick_fact `handle` 走到 `context_factory`（不再 decline）；合同 `finance_query` 授权且 cutoff 为问句日。live（切流后）：R1/R2/R4/R5 冻结题复跑，trace 出现 `finance_query`（R4 须走出 generate-only），R1/R2 rate>0，R5 须披露无数据不得编造，C1/C2 单日休市仍 0 LLM。失败形状①：进了 episode 仍 0 次 finance_query → 升格检索计划/合成层，本行 refuted；失败形状②：单日休市不再 canned → 回归 C1/C2，本行 refuted | 离线 **[已过，实施与本行同 PR]**：F3/F1 钉先红后绿（区间 canned→None；adapter 入口 `context` 被调用；C1/C2/退役表罐头回归绿）；邻域 `test_honesty_gates`/`test_trading_calendar`/`test_quick_fact_routing`/`test_forecast_residual_budget` 等 67P。**sidecar live 已验（2026-08-28 12:05–12:10，8797@`09aefe81` dirty=false；8792 全程 `e5d45933` 未切）**：门=Workbench 会话 `POST /api/conversations/{id}/messages`（`live_probe ask`=/api/runs 是 Engine B，本单修的是会话路，那条门作废）。C1/C2：`llm.used=false`、`generate=lane_direct_answer`、正文休市罐头。R1 `finance_query[sector_daily]` 08-19 数据中心 6671.51 rate 1.0；R2 `finance_query[sector_stock_daily]` 寒武纪 125.89/+4.28 rate 1.0；R4 `finance_query[market_daily]` 08-18..22 **非 generate-only** 08-19/25108.68 rate 1.0；R5 3×`finance_query[sector_daily]` 路由过，但近邻替代「航空板块」数字——残余（react 臂是 07-24 退出清单）。失败形状①②均未发生。产物 `~/.finance-runtime/live-probe-r05-quickfact/`。**生产 live 已验（2026-08-28 18:23–18:31，8792@`b77df25c` 会话路，专用用户 `fsr2-*` 串行）**：C1 `run_20260828_182328_276573` / C2 `run_20260828_182336_996066`——`llm.used=false`、`lane_direct_answer`、休市罐头一字未漂。R1 `182345_960428` `finance_query[sector_daily]` 数据中心 6671.51；R2 `182503_258570` `sector_stock_daily` 寒武纪 125.89/+4.28；R4 `182609_628397` `market_daily` 08-18..22 **非 generate-only** 08-19/25108.68（公开稿前置周六休市句，F3 预期形态）；R5 `182719_909896` 2×`sector_daily` 路由过且首跳已是退出事实。七道研究题公开稿均 `judge_unavailable`（容量桶），私有稿 R1/R2/R4 rate **1.0**。失败形状①②均未发生。产物 `~/.finance-runtime/live-probe-8792-round2-post489/`。正文 `docs/handoffs/2026-08-28-489-live-reeval.md` | `confirmed`（8792@`b77df25c` 会话路；成立条件：judge_unavailable 扣公开稿，内容看私有稿/工具面） |
| `R-20260828-04` | **溯源：非标准四阶段分诊——用户要求对 08-27/08-28 两日 30 个已合 PR 做独立质检，本行为代码审计条目**（按本文件纪律，只有 `fix_type` 与 `verification_prediction` 可用于 streak，不得当作已确认根因的 PRIMARY 引用）。工单 `docs/superpowers/specs/2026-08-28-orphan-module-and-theme-gap-workorder.md`。两处实测缺陷：**P0** 08-20 `a41e86df` 的「零引用」判据只认静态 import，不认 `-m "scripts.X"` 字符串形式模块引用——`sync_akshare_market_snapshot`（AkShare 兜底 provider，生产 code_root 实测 `find_spec -> None`）与 `forecast_learning_loop`（launchd 工作日 09:10 双盲链的 lessons/rules 注入）**已死 8 天且静默**；同一 sweep 的第三轮残留（前两轮 #453/#472 修的是实例、判据没动）。修复=两模块 `git mv` 移回 + `tests/test_scripts_module_references.py` 判据测试（`-m` 正则 + import 经 AST，AST 避开合成夹具字符串误报）。**P1** #484 `_theme_sector_snapshot_items` 的缺口声明挂在 `elif items:` 上，板块行缺失或 `exclude_sector` 命中时连缺口都不声明、返回空元组（与该函数自述的 fail-closed 契约相反）；修复=缺口按「板块行」「成员行」两维各自独立声明 | `HARNESS_FIX` | ①判据测试对未来任何一次归档 sweep 一律生效：把任一模块挪回 archive/ 必红且点名引用点；②`sector` 解析成功时 `_theme_sector_snapshot_items` **永不返回空元组**（要么给数、要么给缺口）；③30 天内不再出现第四轮「归档孤儿仍被引用」事件（基线：08-20 起三轮） | 离线 **[已过，实施与本行同 PR]**：判据测试 3 条全绿，变异（两模块挪回 archive/）**精确杀** `test_dash_m_module_references_resolve` 并点名三处引用点——其中 `scripts/run_akshare_snapshot.sh` 是人工反查漏掉、由判据扫出的（判据优于清单的现场实证）；反向锁测试钉住 AST 不误报 `test_rag_worker.py` 的合成夹具字符串。P1 两条新钉先复现（Case A 板块诞生前日期 / Case B `exclude_sector`+无成员行，均 `0 items`）后转绿，变异 1（恢复 `elif items:`）与变异 2（删板块行缺口块）各**精确杀**其目标测试 1F/6P，既有 5 条逐字节保绿。live：2026-08-28 17:12 8792 已切 `b77df25c7961`（#490），生产 code_root `find_spec` 两模块均非 None（工单 §1.6 验收 1 达成）。AkShare 腿仍看下一次 `run_market_snapshot.sh` 的 `akshare_exact` 档能否 published；双盲 plist 未装，09:10 腿不会自然发生——先装 plist 并把解释器升到 3.10+ 再验 `LEARNING_CONTEXT` | `pending` |
| `R-20260828-03` | 工单 `docs/superpowers/specs/2026-08-27-longtail-react-gap-remediation-workorder.md` §5 点名的判分侧缺口（四臂 D9 三臂全 None：case 只有 `forbid_future_data`（advisory 不进分母）+ `require_falsifiable`（判分器未实现）→ 硬格数 0 → rate=None，判分器对该题失明）。修复=实验判分器 `score_machine_truth.py` v2（**EVAL_ONLY，不动生产**）：①`require_falsifiable` 落地硬格（推翻/证伪/失效/跌破等标记词表）；②`forbid_future_data` 增「未来日期 ±40 字窗内携带行情词+数字」硬格，前瞻条件词与否定/披露词豁免（「显式请求 07-23 数据被系统拒绝」是诚实披露不是泄漏——react 真实答案的误伤现场，变异 C 抓的）；原「任意未来日期提及」保持 advisory；历史 machine-truth-*.json 不重写，重判分落 `analysis/d9-rescore-v2.json` | `EVAL_ONLY` | 判分器自身先过变异（尺子纪律）：泄漏注入必翻红、剥可证伪标记必翻红、合法前瞻条件不误伤、advisory 不进分母——4/4；随后 D9 四臂可判（rate ≠ None） | **已验（2026-08-28 03:15，`d9_mutation_check.py` 4/4 过）**：重判分 react **1.0**、8792/8796/component 各 **0.5**（四臂均无未来数据泄漏；产品臂输在无可证伪条件——8792 那份是 unparsable chat-lane 时代答案，该病 `R-20260827-10` 已治，live 复测归下轮题组）。误伤修复过程本身即变异测试价值的现场：首版把 react 的泄漏防线披露句判成泄漏 | `confirmed`（EVAL_ONLY 无 live 腿；成立条件：对 v2 判分器与 20260827 四臂存档答案成立） |
| `R-20260828-02` | 工单 `docs/superpowers/specs/2026-08-27-longtail-react-gap-remediation-workorder.md` §P2-D5 接力（`R-20260827-09` refuted 升格：H2 送达不充分——送达 wiring 五环 live 证明成立但 D5×3 全 0.0；r3 解剖钉出模型自选查询全程不用精确板块名「可控核聚变」，`contains "核"` 撒网/成交额 top8，react 臂精确名直查命中 0.41/1134.9；判官当晚 3/5 unavailable 噪声在案）。修复=theme_analysis 确定性预取 `asof_prefetch._theme_sector_snapshot_items`（分支 `fix/theme-sector-prefetch`）：`resolve_prefetch_sector`（问句内精确长名>subject>既有别名梯，与发酵分支同一把尺）→ ≤as_of 最近日 `fact_sector_daily` 行 + 同日 `fact_sector_stock_daily` 成员 top12（带 StructuredObservation），解析不到 fail-closed 提示项不臆配；发酵时间轴同板块时板块行让位、成员表仍交付 | `HARNESS_FIX` | 8823 临时臂消融（D5 冻结题 ×3，同 machine-truth 判分器）：(a) **activation**=run 证据里出现「{板块} 板块日行情」与「成员当日表现」两项 L4_structured 预取（读 episode 证据面，判官无关）；(b) D5 rate 0.0→**≥2/3**（判官 unavailable 整篇扣稿的 run 不计入分母，须至少 2 个可判 run，剔除口径预先声明）。失败形状①：预取两项在证据里但答案数值/实体仍缺 → 升格合成/绑定层，本行 refuted 另立；失败形状②：解析不到（fail-closed 项出现）→ 解析梯覆盖案另议，不加宽松轮 | 五钉离线先红后绿（精确名胜过拓宽主体 / fail-closed / 发酵让位 / 分发门控 theme_analysis-only / ≤as_of 同日对齐）；消融绿后走 PR + 批次门禁 + 切流，live 同判据复跑。**已验（2026-08-28 01:55–02:31）**：①消融（8823@`f31ca44d`，D5×3）**全绿超线**——activation 3/3（两项预取均在证据面）、rate **1.0/1.0/1.0**（判据 ≥2/3）、judge repaired×3 零剔除、graph_lookup 3/3 自发出现（预取供数后模型转向图谱补充）。②#484 合并 → 批次门禁独立树 `fwp-wt-qc-prefetch` @`e5d45933` 全量 **6870P+6P/12S/0F** + ruff + registry-check 绿。③切流遭遇并发碰撞：另一 session 的 28a 切流（→`d98fd637`，PR #485 收口 R-20260827-15）与本次重叠，软链被两度改写；等其收口后重切 `e5d459338982`（三读干净/readiness 13/13/账本 ledger_rev==health_rev，回滚锚 `cutover-20260828b-rollback-8792.txt` 回 `d98fd637`）。④live 腿（run_20260828_023000_124171）：activation 两项 ✓、judge=repaired、verified=completed、rate **0.667=判据线 2/3**（sector_pct_chg ✓、entity_recall 2/4 ✓、sector_amount ✗——预取已交付 1134.9 但答案未引用精确数）。**残余（非 refuted 形状，rate 已达线）**：数值从证据到答案的携带率是合成/绑定层老问题，若后续同形状复发累积，另立单不改本行 | `confirmed`（消融 3/3=1.0 + live 0.667≥2/3；成立条件：判官 unavailable 轮不计分母的剔除口径本次未用到——live 一发即判） |
| `R-20260828-01` | 工单 `docs/superpowers/specs/2026-08-28-ledger-id-claim-workorder.md`（2026-08-27 单日四例撞号后用户裁决立单：预注册号分配是 check-then-act——分支上「读当日 max」与「落盘占号」不原子，双向避撞不收敛（-12 例：两 session 各自让路让到同一号上）。修法=本机 claims 登记簿 + flock 预占（`~/.finance-runtime/ledger-id-claims.jsonl`，仓外只追加、号不回收），与 MOC「配额在副作用前预占」同族；方案对比与成立边界（单机）见工单 §2） | `HARNESS_FIX` | P0 落地后：① 并发 ≥8 进程 claim 两两不同且连续；② 取号自述四项（主干 rev/台账 max/登记簿 max/取到号）；③ 台账与登记簿双源参与 max；④ 登记簿损坏 fail-closed 不发号；落地后 30 天主干**零新增撞号改号事件**（基线：08-27 单日四例） | 离线 **[已过，实施与本行同 PR]**：8 专项测试全绿；8 进程并发压测两两不同且连续（-03…-10）；变异 1（去 flock）/3（坏行跳过）**精确杀**各自目标测试（1F/7P），变异 2（无视登记簿）杀 3 条（目标在内，多杀两条同依赖登记簿仲裁=防线冗余，如实记）；live：30 天窗口自然观察（基线：08-27 单日四例），成立条件=仅对走脚本取号的 session（约定依赖已在工单 §3 声明，手工残余窗口不算 refuted） | `pending` |
| `R-20260827-17` | 全量门禁 flaky 收敛 2026-08-28 00:55（#471 验收批次门禁同 rev 一绿一红：6855P/0F 与 6854P/1F 翻转，单跑 5 连 3 挂定位 `test_executor_timeout_marks_pending_conversation_message_failed`；`d0f0a681`（`R-20260827-11`）治了 slow_turn 追平、留了**第二竞态**：executor 仲裁顺序 `claim_failed_run`（run 先可见）→ `terminal_handler`（后标消息），run 终态后立读 messages 撞 pending 窗口。修复=测试侧显式等待最终一致（`_wait_last_message_settled`），同型第二处 executor_failure 路径（`_forget` done-callback 同两步）一并修；**仲裁顺序不能倒**——claim 赢了才有资格动消息，倒序会在与正常完成的并发里错标，故不动生产代码） | `HARNESS_FIX` | 修复后三条同时成立：① 该测试与 exception 同型测试单跑 20 连 0 失败（修前 5 连 3 挂）；② 后续任意 session 全量门禁若再见此测试红，失败点必不再是 `messages[-1]==pending`（该窗已由等待关闭），再红即新问题另立案不并入本行；③「loser 保持 pending」负向测试不受影响仍绿（时点断言未动） | 离线：20 连绿读数随修复 PR；live：后续全量门禁自然复验，`R-20260827-11` streak 至此有收敛点 | `pending` |
| `R-20260827-16` | 2026-08-27 harness 六层审查「两个用户大脑」P0 的独立复核（复核实测为**三个根**且找到持续分叉机制：`~/.zshenv` 与 `~/.zshrc` 双设 `FORESIGHT_USERS_DIR`——`.zshenv` 指 08-16 已退役的 `agent-memory/.foresight`（其 `RETIRED.md` 明示新根=finance-workbench 且「不再作为活跃根」），zsh 非交互壳只读 `.zshenv` → 退役根当晚 20:46 仍新增 correction；交互壳与两个 launchd plist（checkpoint-recheck / daily-full-review-finalize）均指新根 → 双根同晚都在长（20:46 / 20:55）。第三根=仓内 `intelligence/users/` 默认回落，27 条 corrections 停 07-30、其中 **12 条不在两活根**、16 卡 ⊋ A 根 14 卡） | `HARNESS_FIX` | **已执行（2026-08-27 21:48）**：`~/.zshenv` 该行改指 `/Users/a77/.local/share/finance-workbench/users`，对齐 08-16 退役决定（回滚=改回 `/Users/a77/agent-memory/.foresight`，一行）。预测：自改行起 48h 内退役根 `linxiaoqi5111/` 的 corrections/interactions/answer_scores **零新增**（改前最后一条 ts=2026-08-27T12:46:33Z）；若仍新增→存在绕过 env 的写入者（已知显式钉旧根的仅 `dual_blind_auto.sh`/`dual_blind_flows.sh` 两个评测夹具，不在日常路径，不改） | 48h 后回读退役根三文件尾行 ts 与 mtime，B 根应持续增长作对照；执行记录与回滚锚见 `docs/handoffs/inflight/docs-foresight-root-and-span-io.md`。**成立条件**：只治本机 env 分叉、不含数据合并——A 独有 12 corrections/21 answer_scores/14 卡 + C 根独有 12 corrections/2 卡的幂等合并**另立工单（未立）**，落地前这些记录对 8792 消费者不可见 | `pending`（48h 回读） |
| `R-20260827-15` | 工单 `docs/superpowers/specs/2026-08-27-tool-call-correlation-workorder.md`（2026-08-27 harness 六层审查 L6 缺口 + 独立复核实测：episode 事件 `tool_request` 4/4 带 `call_id`、`tool_result` 0/4 连字段都没有、`tool_error` 代码同形——`agent_episode.py` :502/:541 两处 `ledger.add` 展开缺该键，而 `call.call_id` 就在作用域、模型消息 :513/:545 早已带 `tool_call_id`；本行为工单预注册，与工单同提交） | `HARNESS_FIX` | P0（两处展开补 `"call_id": call.call_id`）落地后：① 新 run 每个 `tool_result`/`tool_error` payload 带非空 `call_id` 且与同 episode 恰一个 `tool_request` 配对（单射）；② 同名工具重复调用两对各自闭合（配对靠 id 不靠 name/顺序）；③ 模型可见字节零改动（同夹具 `messages` 逐字节相等——`call_id` 只进 ledger 展开，不得进 `public_observation`/模型 `payload`，那两个 dict 同时是喂模型的底稿）；④ 历史产物无 `call_id` 读取容缺不炸。失败形状：字节变了→写进了模型视图底稿；同名重复配不上→拿 `name` 当配对键；旧 run 统计炸→消费侧硬取键 | 工单 §4 五条验收（第 5 条=pytest 收据）全过 + §5 四条变异逐个精确击杀；**离线绿≠confirmed**，须一次 live run 回读 events 配对。**已实施**（分支 `fix/tool-call-id-correlation`，实施与本读数同分支）：判据 1/2 两钉先红（2F 实录）后绿，整文件 109P；变异 4/4 各自只红对应钉（M1→判据1、M2→判据1+2、M3→红线钉、M4→容缺钉），复原后 4P；全量以分支尖收据为准（`check_test_receipt.py --expect-revision <tip>` exit 0 方可合并；首轮全量 6858P/1F，红者为 `executor_timeout` 挂钟家族（R-20260827-11 三态签名：单跑绿 0.94s、失败文件不在本单改动面、同晚兄弟树两轮全量均绿），复跑求全绿收据）。顺带发现：`openai_agents_runtime`（sdk 后端）tool 事件双侧均无 call_id，同病另批，见分支交接。**live 已回读（2026-08-28 02:18，28a 切流后首个 grounded 探针 `run_20260828_021841_211122`，8792@`d98fd637`）**：`tool_request`×2（finance_query/kb_search 各带 call_id）→ `tool_result`×1（finance_query）配对精确命中 + `tool_error`×1（kb_search 超时）配对同样命中——**成功与异常两条发射路径一发全验**；口径 `fact_stock_daily`×4、degraded=0。合并批次全量收据 `20260827T180940Z-d98fd637`（6871P/0F/12S 干净树，`--expect-revision` exit 0） | `confirmed`（成立条件：单 run 双路径各 n=1，配对判据=result/error 的 `call_id` 非空且 ∈ 同 episode request 集；批量复核可由 `R-20260827-14` 差值审计脚本落地后顺带承载） |
| `R-20260827-14` | 工单 `docs/superpowers/specs/2026-08-27-tool-usage-differential-workorder.md`（harness 回程边审查建议 2：工具面只装了「要了没有」一侧传感器，「有了没要」零遥测；本行为工单预注册，与工单同提交） | `EVAL_ONLY` | P0 离线差值脚本落地后，对同一样本（`$FORESIGHT_USERS_DIR/*/runs/*/continuous-episode.json`，747 份，2026-08-08→2026-08-27）重算，四组数与工单 §3 **逐个相等**：output 实例级差值 **425**、`suspicious` **1193**、可算差值 run **698**、至少一处差值的 run **572**；且输出头部自述样本份数/日期跨度/revision 跨度/探针占比四项。失败形状：数对不上→**先核对是否同口径**（本单基线的原始脚本未留存，口径分歧是第一嫌疑，判据以工单 §3.0 钉死的伪码为准），再查分母定义（⚠ 归一由 runtime **写入侧**注入、产物存原始 `output_id`，离线脚本**不带也不应带**归一——见工单 §3.0）；`--since` 过滤后分母不变→过滤是恒等没生效。⚠ 425 受双向污染（§4.1 低估：空 produces 进不了分子；§4.1b 高估：没检查那格最后是否真填上），**是「值得看一眼」的信号，不是可下结论的度量** | 本轮已用一次性脚本在 `gitea/main@fea0633e` 上实测出上述四数（见工单 §3，含八行工具表与分母）；正式判据=脚本化后复算相等 + 四条变异（工单 §9）逐个精确击杀。**离线绿≠confirmed**，须待脚本入库并由领单方独立复算 | `pending` |
| `R-20260827-13` | 工单 `docs/superpowers/specs/2026-08-27-staleness-disclosure-workorder.md`（产品面审查「夜跑失败那天用户看得见数据停更吗」→ 四层走查确认交付层零披露；根因下推为「全系统只有『从数据自身派生』一个日期参照系，缺少外部日历参照的第二信号」，与 `R-20260826-01` **同形状但非同因果**——该行 outcome 已 `confirmed`，其预登记的「min() 之外还有第二处钳制」条件失败**从未发生**，不得读成本单兑现了它） | `HARNESS_FIX` | P0 落地后四条同时成立：① 非交易日问隐式盘面题**不得**出现落后披露（量纲=交易日，防每周末误报）；② 库停在 T-2、问句日 T（皆交易日）时公开稿出现落后披露且量纲为交易日；③ 库为最新交易日时无披露；④ 停更场景 `should_stop` 仍为 `False`、四袋正常出（= 未复用带副作用的 `calendar_disclosure` 字段）。失败形状：周末误报→用了自然日；停更仍不报→新增信号的参照系还挂在数据自身；包变「该日无行情」→ 复用了 `calendar_disclosure`；`_structured_as_of`/历史窗口授权回归→ 违反 §4.0 红线动了 `_structured_freshness_floor`（该函数三方承重，**不是本单目标**） | 四条验收 + 五条变异（工单 §8）逐个精确击杀；历史实锤在 `R-20260826-01`（snapshot 停 08-24 两天、08-25 在 episode 出现 0 次、零告警、靠双臂对照才发现，当时只补数据未动结构）。**离线绿≠confirmed**，须 live 回读一次真实停更日或构造停更夹具 | `pending` |
| `R-20260827-12` | 工单 `docs/superpowers/specs/2026-08-27-dataset-exemption-semantics-workorder.md`（P0 D6 附带发现①→用户裁决「立工单推进执行」；实证：`dedicated_path` 豁免前缀把「代码消费得到」当「模型够得着」，#454 与 sector_period_rank 两次翻案同它遮蔽；实施与台账同提交，分支 `fix/dataset-exemption-semantics`。**原预注册号 `-11`**：与并发 #468（owner_timeout 时序余量）撞号，#468 先落 main，本行按先例改号——当日第三例，撞号根因=预注册号在分支上取当日 max+1、落盘窗口并发） | `HARNESS_FIX` | 审计规则 3：豁免理由须以白名单类别前缀开头（no_writer/internal/stale_materialized/stale_since/candidate/kb_side/overlap/model_reachable_via），`dedicated_path` 与未知前缀 → `invalid_exemptions` 点名到表、exit 非 0。存量 4 张先量后判清理：`fact_sector_period_rank_daily` **转正** `sector_period_rank_daily`（实测 05-06~08-27 活、四档 top10；coverage 带「榜单非全量」防分母坑 + sector_daily 回指）；`feature_l2_*` 两张改判 `stale_since`（06-15~08-07 断更 20 天，注册停更表=喂旧数据，复活条件=恢复日更）；`fact_mainline_stock_daily` 改判 `model_reachable_via:mainline_context`（模型已可达，再开 dataset 双口径）。live 预测：切流后 sector_period_rank 类问题（近5日榜/连续在榜）episode trace 出现 `dataset=sector_period_rank_daily` | 离线：TDD 5 钉先红（3 审计 + 2 dataset，收据 `20260827T132842Z-3da2c712` 区间）后绿（`20260827T133043Z-3da2c712`，84P）；变异：删规则 3 → 白名单证伪钉红；`dedicated_path` 塞回清单 → audit 红点名。live：切流后按预测回读，结论携带 revision 条件 | `pending` |
| `R-20260827-11` | 合并门禁抓存量红 2026-08-27 20:23（#464 验收 session：干净树 @`e4276e00` 全量 2F/6821P，owner_timeout 在 623334d3/41d9d8d2/fea0633e/e4276e00 四 revision 单跑一致红；同晚实证 623334d3 干净树 registry check rc=1——「批次门禁 registry 五道绿 @623334d3」读数与树内容矛盾，源头 #123 合流解冲突 `f8169980` 未重跑 scan，#466 已回填。实施与台账同提交，分支 `fix/owner-timeout-test-isolation`） | `HARNESS_FIX` | 根因两只（都是测试拿挂钟赌调度，非生产缺陷）：① owner_timeout 给统一研究预算仅 0.1s，orchestrator 调 skill 前编排链（configure→controller→plan→route→retrieve）冷态实测 ~0.4s——预算在 skill 启动前烧完 → `invoked=()`、正文「专项研究达到统一截止时间」；被同文件第 33 个测试（long_tail e2e）暖场后开销缩到几十 ms 才够用（文件内二分锁定 primer 且单 primer 足够；三态签名：单跑红/整文件绿/全量随负载）。初始怀疑「全局状态翻转 skill 路由」证伪——冷态 `selected=('stock-deep-dive',)` 路由正确，烧的是预算。② executor_timeout 的 slow_turn 兜底 1s 在全量负载下被 50ms 看门狗追平——runner 先正常返回 → run completed → 断言红（`-10` 行当晚两读独立佐证：唯一红即它、单跑绿、同刻并行树同红同条）。修法只动测试不动生产 deadline 语义：三不等式放余量（预算 2.0s ≈ 冷态开销 5×；sleep 3.0s > 预算；skill 自身 timeout 30s > 预算，保证掐断者是统一截止）+ 兜底 1s→30s + `release.set()` 移入 finally（失败路径不拖 30s）。预测：单跑/整文件/全量三态皆绿、与执行序解耦（primer 不再必要） | 修后四级定向：owner_timeout 单跑 1P（修前同命令 1F）、原失败对 2P、executor_timeout 单跑 1P、编排器整文件 103P；干净树全量 **6830P/0F/12S**（10m18s，ruff 过；run 于本 docs 行写入前的同分支树，代码差异为零）。注：`41d9d8d2` 生产快照带此测试红出门，定性测试脆弱非生产缺陷（当晚 readiness 13/13 + 长电探针过） | `confirmed`（对本机三态读数成立；跨机以 5× 冷态余量为设计依据，若 CI 机再现同形状红先查该机开销再放余量） |
| `R-20260827-10` | P0 D6 复跑分诊 2026-08-27（`-07a` refuted 的归因升格：controller `_parse_llm_decision` 一次解析失败即 `_safe_fallback(chat, needs_retrieval=false, detail="")`，`_enforce_task_frame_route` 因关键词分支漏「高标股/晋级/空档」不生效——8792 生产 39 run 中 4 个 unparsable 恰=全部 chat lane（B6/C8/D6/D9），D6 3/3 复现=题面相关；收据 `~/.finance-runtime/p0-d6-20260827/`。实施分支 `fix/turn-controller-unparsable-fallback` @ `111af0f7`，与 `-08` 同反模式的 controller 侧修复） | `HARNESS_FIX` | 三道修法后：① 解析失败重试恰一次（坏输出贴回+纠错指令，provider 挂不重试）；② unparsable 的 `llm_failure_detail` 留首次原文（声明式截断 200 字）——下一个 unparsable 的 run 可验尸；③ `task_frame_requires_retrieval` 显式日期地板（timeframe/题面含完整日历日期即需检索，月份粒度不触发、model_reasoning 豁免优先）。live 预测：修复树复跑 D6 frozen 题面，controller 步不再落 `chat+needs_retrieval=false`（重试成功路由检索车道，或 fallback 被地板拦成 research），trace 出现 tool 步；届时按 `-07a` 原判据检验 #454（finance_query 出现 `dataset=limit_advance_daily`）。失败形状 ①：地板拦住（needs_retrieval=true）但检索计划仍不选连板表 → 回到「装了没用」，升格检索计划层与 `-09` 合并归因；失败形状 ②：controller 出牌正常但 D6 rate 仍 0 → 合成/判分层，另立 | 离线：TDD 6 钉先红（收据 `20260827T121838Z-fea0633e`）后绿（`20260827T122000Z-fea0633e`，135P）；变异 3/3 精确击杀（删日期地板→恰 3 钉红；删重试→恰 2 钉红；detail 置空→恰 2 钉红，变异前提交 `111af0f7`）。live：修复树起临时服务复跑 D6，对照 `-07a` 读数（三 run 一字不差的 unparsable-chat）做单变量自对照（变量=本修复），结论携带 revision 条件。**live 已验（2026-08-27 20:34，8822@`111af0f7` dirty=false，run `run_20260827_203359_346648`，PR #465）**：controller `lane=research / needs_retrieval=true`、reason 尾「TaskFrame 证据政策禁止零检索执行」=地板生效；**detail 留证当场破案**——GLM 首答实际选对路由（`dated_market_review`, 0.82）但只回 route_id/confidence/reason **三键**，键集全等校验拒收，重试仍三键 → fallback 被地板拦住（unparsable 真面目=模型少键，D6 题面系统性诱发，解释 3/3 复现）；tool 步 0→4 次，答案引用 `limit_advance_daily`（07-22，与库 12 行真值逐字吻合：5板立新 1/1、4板华银 1/1、3板美利云 1/3、2板 9 只、无断层，证据边界诚实）；**D6 machine-truth 复打 rate 0.0→1.0**（entity_recall 3/3 + must_mention，判据 ≥0.5）；两条失败形状均未现（检索计划选中了连板表=非「装了没用」；rate 满分=非合成/判分层）。**顺带闭环 `-07a` 的挂起项：#454 检验通过**（`ablation_activation_step` 激活）。全量 6829P/1F ×2 读，唯一红 executor_timeout 单跑绿且同刻并行树 `e4276e00`（不含本改动）同红同条=负载抖动。修复树全量收据 `20260827T123752Z-111af0f7`；复跑收据 `~/.finance-runtime/p0-d6-20260827/fix8822/` | `confirmed`（成立条件：live 读数为修复树 8822 自对照 n=1；**#465 已合 main `e2242aed`（2026-08-27 21:35），8792 未切流仍 `41d9d8d2`**——生产面「4 unparsable=4 chat lane」的收敛待切流后下一个等宽窗口回读；若三键缺失形状在生产仍高频，追加 prompt/schema 收紧另立行） |
| `R-20260827-09` | 工单 `docs/superpowers/specs/2026-08-27-longtail-react-gap-remediation-workorder.md` §P2-D5（四臂对照 D5 三产品臂 0.0 vs react 1.0；react 首跳 `graph_lookup` 实体解析 [实测 session.json 5 跳序列]，8792 侧仅见 6 次粗粒度 `research`、载荷未取证；main 无对应改动。**预注册非四阶段分诊**，归因假设待 M2，只供 streak） | `HARNESS_FIX`（暂定；本行预测的是归因走向，M2 定层后如改判 ROUTING_FIX 须更新本行并留档） | 跨臂 M2（按工单 §P1 映射表对齐 8792 `run_20260827_134712_662543` 的 continuous-episode research 载荷 vs react calls）将把 8792 的缺口定位在 retrieve/tool 前缀——**从未发出实体解析类查询**，而非 synthesize/判官段。失败形状 ①：8792 实际发过 graph_lookup 但结果空/被丢 → DATA_CONTRACT 层，本行 refuted 重立；失败形状 ②：D5 同样被判官扣留（judge_status=unavailable）→ 并入 `-08` 族，本行 refuted | M2 报告 `validate-report.sh` RC:0 且 residual_uncertainty 含 plan/observe 两条损耗（映射表门槛 2/3 的显式声明）；确认后修检索计划层再自对照复跑，D5 按 machine-truth 该 case checks 复打 ≥2/3。⚠ D6 复跑教训（`-07a`）：controller unparsable 降级会让「从未发出某类查询」在 plan 之前就成立——M2 定层前先查 controller 步 `llm_failure_reason`，排除同因。**M2 已取证（2026-08-28，报告 `~/.finance-runtime/react-gap-m2-20260828/m2-d5.md` RC:0；§P1 映射表同批落 `docs/trace-profile.md` §6，D2 侧验收报告同目录 RC:0）**：定位预测兑现——四臂 run 全调用窗 6 次调用参数逐条在案，**0 次 graph_lookup / 0 次 sector_daily / 0 次 sector_stock_daily**；controller 干净（`llm_failure_reason=""`，排除 D6 同因）、judge=repaired（形状②排除）、0 次调用（形状①排除）。**定层收窄至两候选待消融**：B 自己的 research_plan 列了 chain_stages/company_mapping 而 episode task 载荷（687 字符全文检索）不含任何阶段字段（送达层 H2=HARNESS）vs contract 已授权 graph_lookup、task_frame 已要求 chain_mapping 产出而模型不选（选择层 H3=REASONING）；消融=仅把 retrieval_stages 注入 task 载荷后同题复跑，activation 判据=实体类调用 ≥1。SECONDARY 实证：kb_search 申请 30s 只授 13.9s（episode 剩余 73s）超时，react 臂同类查询 30.2s 成功。**不变性复跑（8792@`33026dc1ef1a`，run_20260828_010136_666196）**：graph_lookup 仍 0 次（缺跳复现，#473 不触及本案）；但该次模型自选 sector_daily×3（四臂 run 为 0 次——工具选择随机性大），最终 rate 仍 0/3 由 `missing_required_output`→核验不过→按缺口话术发布造成——**D5 失败面是复合的（缺跳 + 产出结构），复跑判据 ≥2/3 保留不降**。**H2 送达消融已执行（2026-08-28 01:30–01:40，8823 临时臂 @`87fb61d5`=PR #482，D5 冻结题 ×3）**：①送达全链 live 证明五环绿（plan→control→context→prompt 渲染 7 阶段+rule 行，不经 LLM 的 wiring 证明 + 服务指纹 match）——「没装上」排除；②activation 形式达标（r2 `graph_lookup`×1、r3 `sector_daily`×2、r1 首跳变 evidence_search 产业链概念股）但**归因不成立**：无注入的生产对照同晚也出现 sector_daily×3，工具选择方差 >> 注入效应；③**rate 判据 refuted：3 run 全 0.0**（判据线 ≥2/3）。r3 解剖钉出下一层：首查 time_range 越 cutoff 被弹回；重试 `contains "核"` 撒网/按成交额 top8，**全程未用精确板块名「可控核聚变」查 sector_daily**（react 臂即精确名直查命中 0.41/1134.9）；判官当晚 3/5 次 unavailable（噪声已声明，r3 为带声明发稿仍内容 miss，排除「全由扣稿造成」）。**归因升格：主体拓宽（核电与→）+ 精确板块名解析缺失**——与 `2026-08-25-step-trajectory-qualification-design.md` 的「科技臆配量子科技→subject 解析梯 fail closed」同形状；下一步候选=确定性预取（theme subject→精确 sector_daily/sector_stock_daily 行），新行待预注册（用 #481 取号器）。送达分支挂 PR #482 等裁决（必要不充分：是后续 stage-aware 修复的前置，零回归） | `refuted`（H2 送达层不充分；M2 定位段已兑现留档；归因升格精确板块名解析层，新行另立） |
| `R-20260827-08` | 工单同上 §P2-D2（[实测] 8792 probe `run_20260827_152937_309324`：`judge_status=unavailable` + `semantic judge provider error` + `verified_status=partial` + `terminal_phase=evidence_gap_fallback`；生产同形 8/38=21%；main 现状 `_stable_semantic_judge_error` 瞬时档仅认 `empty_model_response`，grok CLI **类名**串被 invalid 分支抢走判永久；修复 `b614daf0` 在 `fix/range-cutoff-and-judge-fallback` 未合。**预注册非四阶段分诊**，先验假设=掉在判官层非作答层，M2 拿到 trace 才能定，只供 streak） | `HARNESS_FIX` | `b614daf0` 合并+切流后同题复跑：`judge_status ≠ unavailable`、`verified_status=verified`、D2 rate 0.25→≥0.75；生产下一个 38-run 等宽窗口 `judge_unavailable ≤ 3/38`。搭车判据（同 commit 修缺陷 D-1）：区间题 `requested_information_cutoff` 取终点、D10 复跑 rate>0（当前三臂 0.0）。失败形状：retryable=True 但三连重试仍失败 → 判官容量/超时层而非分类层，本行 refuted 另立；若跨臂 M2 发现 8792 在 retrieve/tool 前缀已分叉 → 先验假设翻车，本行 refuted 重立 | 跨臂 M2 只做假设生成（模型/引擎双混杂声明在工单 §1），确认走自对照：合并前后同题复跑单变量=`b614daf0`；合并走正常 PR（CI 绿才可合），红线「未经复核的草稿不出稿」不动。**live 已验（2026-08-28 00:19–00:26，8792@`33026dc1ef1a`）**：`b614daf0` rebase 后以 `4db7ed1b` 经 PR #473 合入（姊妹修复 #472=theme_radar_quality_rules 移回先行；批次门禁独立树 `fwp-wt-qc-batch-33026dc1` 全量 6842P+6P/12S/**0F** + ruff + registry-check 绿，收据 `20260827T160920Z-33026dc1.json`）→ 蓝绿切流（三读 `33026dc1ef1a`/dirty=false/`code_matches_repo=true`、readiness 13/13、`audit_deploy_ledger check` ok、回滚锚 `cutover-20260827n-rollback-8792.txt` 回 `3da2c712278b`；冷启 ~6.5min 属 RAG 预热）→ 同题自对照复跑（单变量=#473，user `p2rerun0827-8792`，收据 `~/.finance-runtime/p2-d2d10-rerun-20260827/rerun-report.json`）：D2 `run_20260828_001919_707518` rate **0.25→1.0（4/4）**、`judge_status=repaired`（≠unavailable）、`judge_unavailable_count=0`、`terminal_phase=validated_synthesis`（修前 `evidence_gap_fallback`）；搭车 D10 `run_20260828_002209_616295` rate **0.0→0.8（4/5）**，07-21/07-22 两日成交额+涨停数四格数字全过=区间终点数据可达，唯一 miss=`must_mention 反弹阶段` 措辞格（非 D-1 缺陷面）。两种预写失败形状均未出现。勘误：预测里 `verified_status=verified` 不在该字段词表（实际健康值=`completed`），按「判官跑完且未整篇扣稿」语义判达标 | `confirmed`（判官层假设成立；成立条件：38-run 等宽窗口 `judge_unavailable ≤ 3/38` 属生产遥测，观察窗未满，留待下一个 38-run 回读） |
| `R-20260827-07a` | 工单同上 §P0（四臂对照 D6 三产品臂 0.0 vs react 1.0；根因**已证**=连板晋级全集表未接入工具层，`~/.finance-runtime/four-arm-20260827/analysis/defects-found.md` 缺陷 D-4；#454 `3816b297` 已合 main（≥`470e43a3`）**从未 live 复跑**，⚠ 预注册时生产 8792 `40fd5a847c65` 不含该提交。**预注册非四阶段分诊**，只供 streak。**原号 `-07`**：预注册落在分支 #460 期间，main 经 #462 落了 export-increment 事故同号行，按 `-03a` 先例改号留档，工单引用已同步） | `HARNESS_FIX` | 含 `3816b297` 的树复跑 D6 frozen 题面：修后 trace 的 finance_query 出现 `dataset=limit_advance_daily`（或 `theme_limit_stock_daily`），即 `ablation_activation_step` 非 none（「装上了」）；D6 按 machine-truth 该 case checks 复打 rate 0.0→≥0.5。失败形状（一等结论，m2-differential 第 25 条）：`expected_divergence_step=tool` + `observed: none` —— dataset 已注册但检索计划不选它（「装了没用」），升格检索计划层并与 `-09` 合并归因 | 对照修前 run `run_20260827_153157_271373`（trace 8.7KB+stream 19.7KB 在 fourarm0827-8792 用户目录）做 M2 自对照，单变量=#454；报告 RC:0；结论携带 revision 条件（对哪棵树成立）。**已验 → refuted（2026-08-27 P0 复跑，收据 `~/.finance-runtime/p0-d6-20260827/`）**：8820@`31809161`（pre-#454）/ 8821@`3816b297`（post-#454）+ 冻结原始三 run——`ablation_activation_step=none observed`，两臂 finance_query 均 0 次，步骤序列逐字相同（configure→controller→plan→generate(lane_direct_answer)，无 tool 步）。但**不是预写的两种形状**：三 run 的 controller 输出一字不差 `lane=chat / needs_retrieval=false / llm_failure_reason=unparsable_response / llm_failure_detail=""`——`_parse_llm_decision` 一次解析失败即 `_safe_fallback`（turn_controller.py），`_enforce_task_frame_route` 因 `task_frame_requires_retrieval` 关键词分支漏「高标股/晋级/空档」不生效，**检索计划从未生成**，#454 装没装上轮不到问。预写形状①命中一半（observed none 对、层错）：归因在 controller 层非检索计划层，**不并入 `-09`**。同 trace 的 task_frame 完全正确（user_goal/assumptions 点名连板梯队数据依赖）——「知道该怎么答，把答案扔了」。发生面：8792 生产 39 run 中 4 个 unparsable **恰构成全部 chat lane**（B6/C8/D6/D9）；D6 3/3 复现（基础率 10%，三连 0.1%）= 题面相关非随机。与 `-08` 同反模式：LLM 组件失败 → 粗标签留下、诊断载荷丢弃（detail="" vs `_stable_failure_reason` 压扁类名）、无重试。环境复刻成立：旁路臂与冻结原始步骤序列、controller 决策逐字一致。修复+复验预注册 `R-20260827-10`（分支 `fix/turn-controller-unparsable-fallback`）；#454 检验挂起待 `-10` 落地后复跑 | `refuted`（归因升格 controller 层 → `R-20260827-10`；#454 待 `-10` 后复检） |
| `R-20260827-07` | 夜跑 export-increment 连坐事故分诊 2026-08-27 18:42（`logs/daily-full-review.out.log`；实施与台账同提交 #461） | `HARNESS_FIX` | 根因双层：① `export_increment.py` 不吃 `MARKET_FEATURE_STORE_DB`，staging 架构下读默认生产库路径——换名前生产库必然无当日行 → 「无数据」`sys.exit(msg)`=rc1；② `run_release_steps` 把备份步算进全绿判定 → wrapper 不换名 → 生产库停 08-26、readiness `market_data_consistency` 红。修法 A+B（#461）：export 传 `--db` 指 staging（备份「即将上生产」的数据，语义更正）+ fail 降告警级不阻塞换名（26g 人工「告警级」裁决固化）；质量双门仍 fail-closed。预测：修复版重跑 export status=ok 且真导出增量、换名完成、readiness 回 13/13 | TDD 4 钉先红（2红2绿精确）后绿；变异 2/2（连坐判定改回→钉1红；去 --db→钉3红，变异前提交 `7baf5e48`）；#290 邻域 21 钉回归。**live 已验（2026-08-27 19:20 手动重跑修复版全链，wrapper 吃主树代码）**：export-increment **status=ok** 且首次真导出（29 表/120587 行 → iCloud increments，此前读生产库即使不 fail 也永远导空——本次顺带治好备份空转）；staging 校验过（表 51>=51、覆盖 08-27）、原子换名 0.167s（run_id `9b5e43b7b831`）、readiness **13/13**。成立条件：手动壳跑的是与 launchd 同一 wrapper+主树代码；launchd 自然验证=明晚 18:30 夜跑 export ok + 换名 ok | `confirmed`（launchd 自然复验明晚顺带回读） |
| `R-20260827-06` | 工单 `docs/superpowers/specs/2026-08-27-qc-gate-and-ledger-integrity-workorder.md` §P1-b（实测：`R-20260824-25…-29` 五号 spec 写明判据、实施 #359 已合，台账零行——不是 pending 是不存在；`R-20260821-03` 一号两行状态互斥） | `HARNESS_FIX` | `audit_ledger_spec_crosswalk.py`（挂 registry-check 同档）：正向 specs/** 每个 `R-` 引用台账有且仅有一行（缺行红、点名哪份 spec 第几行）；Open 主表同号多行直接红（历史回填段复行是过程记录不算）；反向（行回指 spec/handoff/verification）warning 档、存量清完升 error 时在调用处注明生效 revision | 离线 TDD 7 钉先红后绿。真仓先红：缺号 7（工单点名 5 + 新逮 `R-20260822-03/-05`）+ 重号 1（`R-20260821-03`）→ 存量清理（-25…-29 判据从两 spec 逐条抄回、-03 逐字抄 spec 预留行、-05 占位指 spec §9、重号预注册行改号 `-03a` 留档双向指针、sector-disclosure spec 状态行回写 v1.5）→ 后绿 exit 0（工单验收 1/2 ✅）。变异 2/2：删台账 -25 行 → 红点名（查引用→行非总量）；塞孤儿号+升 error → exit 2、还原 exit 0（验收 3 ✅） | `pending` |
| `R-20260827-05` | 工单 `docs/superpowers/specs/2026-08-27-qc-gate-and-ledger-integrity-workorder.md` §P1-a（#444 实证：分支尖收据 6579P 真、基座落后 main 27 张，合并后 tip 无收据零报警；「收据树 SHA == main tip」只是规程文字）| `HARNESS_FIX` | `check_test_receipt.py --expect-revision` 全等比较（rev-parse 展开，防 startswith 削弱）不等即非 0 且差额（落后几张合并）进错误正文；`--base-drift-max N` 基座落后主干 > N 张合并即拒绝、主干引用解析不了 fail-closed；acceptance-workflow §3 完成判据改为该命令 exit 0 并注明对哪个 revision 成立 | 离线 TDD：7 新钉先红（AttributeError）后绿（+既有收据钉 5 = 12P）。真实收据实测：`ebca3c6b` 收据 + 期望 `35e1b291` → exit 1、正文「落后期望 29 张合并」（工单验收 1 ✅）；`20260826T192253Z-35e1b291.json` + `35e1b291` 在 35e1b291 树上 → exit 0（验收 2 ✅）。变异已击杀：比较削成 `startswith(want[:4])` → `same_prefix_is_not_enough` 钉红、其余 6 绿（验收 3 ✅，变异前先提交）。验收 4 = workflow §3 改写随本 PR。边界：本门只治「收据对不对得上树」，不治「该不该 rebase」的裁决本身（工单原文） | `pending` |
| `R-20260827-04` | 工单 `docs/superpowers/specs/2026-08-27-qc-gate-and-ledger-integrity-workorder.md` §P0（QC 实证：`application/vnd.api+json` 落在中间件子串匹配与 FastAPI JSON 口径的差集里，body 自报 `user` 直达端点=身份门 fail-open 绕过；号随实施 PR 同提交现取） | `HARNESS_FIX` | 中间件 body 改写口径 ⊇ FastAPI 解析口径（`_is_json_content_type` 与 `routing.get_request_handler` 同源：`application` 主类型 + `json`/`*+json` 子类型）；无 Content-Type 的 body 本模块自己尝试改写，不再把安全面押在 FastAPI `strict_content_type` 默认值上；七格参数化（json / json;charset / vnd.api+json / hal+json / 大小写 / 缺 CT / text-plain）凡 FastAPI 会解析成 JSON 的格 `user_id` 必须 == token 身份；query 侧 `_force_user_param` 既有钉不回退 | 离线 TDD：新 7 用例先红（`vnd.api+json` / `hal+json` 两格 200+`user_id=bob-beta` 复现绕过，收据 `20260827T0757*-*.json` 区间）后绿（26 passed 含既有 24 条零改动）。变异（工单验收 2）**已击杀**：`_is_json_content_type` 换回 `"application/json" in raw.lower()` → 恰 `vnd.api+json`/`hal+json` 两格红、其余 24 绿（2026-08-27 实测，变异前先提交 `538f65b2`）。live 面：`WORKBENCH_AUTH_MODE` 默认 off、生产 8792 未开身份门，无 live 判据；本行是 Hosted Alpha 开门的前置，开门当天须复核本行 outcome | `pending` |
| `R-20260827-01` | spec `docs/superpowers/specs/2026-08-26-watchlist-digest-pack-design.md` §3.3 P1a（发酵摘要；同 session 实施预注册，落表时 gitea/main 无 R-20260827 占用） | `HARNESS_FIX` | 发酵摘要仅在 theme 项命中主线或严格双红时出现（个股项/仅热度命中不挂）；轨迹判定一次批量委托 `theme_fermentation`（逐日复用 `_query_dual_red`/`_query_limit_heat` 袋口径，主体数不放大查询数）；摘要数字 ⊆ 快照 `fermentations`；停机路径（empty/locked_db/休市）fermentations 为空；措辞为「在袋/在榜」（袋有 LIMIT 截断） | **离线已绿**（2026-08-27，分支 `feat/watchlist-digest-p1`）：`test_theme_fermentation.py` 7 钉先红（ImportError 收据 `20260826T184918Z-990c1c86`）后绿——计数/连红/峰值、零命中零摘要、窗口按日历截断、口径棘轮（源码禁 `fact_sector_daily`/`fact_theme_limit_heat_daily`/`DOUBLE_RED`/`diff_ratio`）、逐日单查（2 主体 5 日 = 恰 5+5 次袋查询）；pack 侧 3 新钉：触发面（AI 主线挂、储能仅热度不挂、个股不挂）、单次批量委托（monkeypatch 计数=1）、停机路径为空。live：切流后真画像一发，若当日清单无 theme×主线/双红命中，以「无发酵行 + 快照 fermentations=[]」为正确读数记录。**live 已验（2026-08-27 05:09，8792@`40fd5a847c65`，run `run_20260827_050931_922012`）**：真画像清单当日仅命中涨停热度袋（人工智能/工业互联）→ 正文无发酵行、payload `fermentations=[]`、瘦收据 `fermentation_rows=0`——触发面按 spec 收窄成立；正向路径由合并前真库冒烟证实（临时画像「黄金概念」：双红在袋 3 天/热度在榜 2 天，与袋截断语义直查逐字一致；谓词口径 4/6 的差=LIMIT 截断，佐证「在袋/在榜」措辞必要） | `confirmed`（成立条件：live 正向发酵行待某日真画像题材命中主线/双红时顺带回读） |
| `R-20260827-02` | 同上 §3.3 P1b（Workbench 快照证据页） | `DATA_CONTRACT_FIX` | 含 `watchlist_digest_snapshot` 的 run 在对话里出现可点的「证据快照」页；只读渲染（页内零 button/input/textarea）；三档前缀与包渲染同源、不新开 marker 方言；无快照的 run 不显示该页 | **离线已绿**（同上分支）：`components.test.tsx` 2 新钉（快照页可点+只读+冻结内容逐项可见；无快照不渲染），前端 69 过 + lint + typecheck 绿。live：切流后生产 run 的 report 含快照载荷且 UI 构建产物已随分支入库。**live 首验逮到真缺陷（2026-08-27 03:55，生产 47cf855d）**：P0 的 `watchlist_digest_snapshot` 键实际是 `str(write_snapshot(...))` 且落盘即被脱敏成占位句——字符串真值会让证据页把非对象当快照渲染（`bags.map` 抛错）。修复 `fix/digest-snapshot-payload`：报表新增 `watchlist_digest_snapshot_payload`（整袋 dict，无路径免脱敏）+ UI 换键 + 形状护栏 fail-closed（bags/rows 非数组不渲染）+ 双端回归钉（py 源码钉 + 前端 legacy-string 钉）。**live 复验已过（2026-08-27 05:09，#447 已合并、8792@`40fd5a847c65`，run `run_20260827_050931_922012`）**：payload 类型=dict、4 袋、`standing_date=2026-08-26`==各袋 served、正文全部小数 ⊆ payload、买卖词 0；UI 构建产物（`index-3ryUyqDG.js`）随 #447 入库并已部署。教训已入交接：跨端合同夹具至少一条须来自真实产线序列化产物 | `confirmed` |
| `R-20260827-03` | 同上 §3.3 P1c（Claude Code skill 软链） | `HARNESS_FIX` | `skills/watchlist-digest/SKILL.md` 只作入口指针（正门=CLI digest + 问答门冻结题），不复述接合/主张档口径（防第二份漂移）；`.claude/skills/watchlist-digest` 是相对软链非物理拷贝；注册表四检查全绿 | **离线已绿**（同上分支）：CI 语义（REPOS_DIR 打补丁指向本分支树）scan 后 `check-parseability`/`check`/`backfill-tables --check`/`generate-views --check` rc=0×4，注册表 59→60 仅本条新增；CLAUDE.md 生成块自动补行。live：合并后原生环境（主检出树 pull 至含本单的 main）四检查绿。**进展（2026-08-27 05:15）**：CI 语义四检查已 4/4×3 轮（P1 分支 / c7d06930 / 40fd5a84）；原生跑 3/4 过、唯一 FAIL=`check`（主树 skills/ 缺新 skill 的**预期陈旧漂移**）；主树 `git pull --ff-only` 被他人在途文件 `docs/handoffs/inflight/feat-capability-switchboard.md` 阻塞——按并发纪律不代解，主树前移后本行自动可结 | `pending` |
| `R-20260826-05` | spec `docs/superpowers/specs/2026-08-26-watchlist-digest-pack-design.md`（会话收口预注册，非标准四阶段分诊；**原预注册号 -01…-03 与当日其他 session 撞号，2026-08-26 实施时改号 -05…-07**，先例 `R-20260824-31`） | `ROUTING_FIX` | 冻结题「按我的自选出今天的简报」在信封 / plan / `decide_turn(llm=boom)` 三层都是 `watchlist_digest`；Engine A `handled=False`；§5 负样本（今天市场怎么样 / 今日看点 / 指定日复盘 / 止损 / 展望 / 题材阶段）题型不变 | **离线已绿**（2026-08-26，分支 `feat/watchlist-digest-pack`）：`intelligence/tests/test_watchlist_digest_pack.py` 24 钉先红（ImportError 收据）后绿——正样本四句三层（信封/plan/decide boom）全 `watchlist_digest`；负样本六句按干净树实测现状钉死（「复盘7月16日」信封层=general_finance_qa + `is_dated_market_review`=True、「止损」decide 层=trade_advice）；`DETERMINISTIC_OWNER_TYPES` 加入 `watchlist_digest` 且既有 declined 参数化用例同步扩展；信封阶梯/头部意图两处「自选先于 market_watch」有源码顺序钉。全量二读（提交后 @`4101e214`）6624 passed / 0 failed / 12 skipped，收据 `~/.finance-runtime/test-receipts/20260826T135533Z-4101e214.json`（一读的 1 红 `test_agent_review_worker` 进程组关停未复现，单跑绿=负载抖动，与本单无交集）。live 由验收方跑，执行方不得自行 confirmed。**live 已验（2026-08-27 验收方，main@`547653c4`，8999 临时实例=生产 env 形状、8792/8796/8802 未动）**：Workbench 冻结题 run `run_20260827_013659_654081`（真画像 linxiaoqi5111）controller 决策 / research_plan / legacy 信封三处 `question_type=watchlist_digest`、lane=workflow、置信 0.98；回合 2.4s 完成且无 LLM 草稿阶段（`smoke_workbench_self_use` 协议探针 draft_seen=False 反证确定性路径，见该探针适配缺口备注）；负样本六句与 Engine A `handled=False` 以离线钉为准（live trace 无 declined 观测字段，成立条件） | `confirmed` |
| `R-20260826-06` | 同上 | `DATA_CONTRACT_FIX` | 开口前 `WatchlistDigestPack` 收据在；公开稿数字 ⊆ 快照 rows；显式日 `trade_date = ?` 无邻日回落；清单空走缺口句、不落到 `market_watch` | **离线已绿**（同上分支）：夹具 DuckDB 正反成对——fact 行数字（3.1/12.0/600.0）逐字可在 `to_snapshot()["bags"]` 找到；显式缺日（07-25）只出无行情句、邻日（07-23）数字 0 泄漏；清单空 → `status=empty` 缺口句、公开稿无「指定日盘面组件包」标题；库缺失 → `locked_db` 不冒充「该日无行情」。编排器在 owner 分叉前 bind（源码顺序钉），瘦收据进 `report["watchlist_digest_pack"]`、整袋快照落 `report["watchlist_digest_snapshot"]`。live：真画像用户 CLI `digest --write` + Workbench 冻结题各一发，对账 `~/.finance-runtime/watchlist-digest/<user>/<date>/` 快照 `standing_date` 与袋 `served_date` 一致、公开稿数字 ⊆ 快照。**live 已验（同 -05 环境）**：CLI `digest --user linxiaoqi5111 --write` 落 `snapshot-20260826T173302563313Z.json`，Workbench QA 路径自动写 `snapshot-20260826T173701714850Z.json`（同目录 `~/.finance-runtime/watchlist-digest/linxiaoqi5111/2026-08-26/`）；两份 `standing_date=2026-08-26` == 四袋 `served_date`，公开稿全部小数数字 ⊆ 快照 rows（两路各验）；瘦收据 `report["watchlist_digest_pack"]`（13 股+10 题材 / 3 fact / 0 inference / 20 gap / 四袋全 hit）与整袋 `watchlist_digest_snapshot` 都在 run 工件；验收方另用临时画像复算黄金概念 1.74/17.11/990.42 与直查 `fact_sector_daily` 逐字一致 | `confirmed` |
| `R-20260826-07` | 同上 | `HARNESS_FIX` | 四袋只委托一次 `run_market_watch_pack`；公开稿无买卖词面；主张档三档可见 | **离线已绿**（同上分支）：变异两杀——monkeypatch 计数断言委托恰好 1 次（私有 SQL 替身必红）；模块源码机械核查（禁 `select` 词面 / 四张 fact 表名 / duckdb.connect，第二套口径进不来）。公开稿正则 `买入\|卖出\|加仓\|减仓\|现在做多\|现在做空` 三种站立日场景 0 命中；（事实）/（推断）/（缺口）三前缀 + 图例收尾有钉。**live 已验（同 -05 环境）**：CLI 与 Workbench 两路公开稿买卖词面正则 0 命中；三档 live 可见——3 条（事实）题材行〔储能 涨停12家/23.08、数据中心 7家/13.46、新能源车 6家/11.54〕+ 20 条（缺口）+ 全市场袋 1 行 + 图例收尾；委托唯一性不在 live 重复变异，以离线两杀为准（成立条件） | `confirmed` |
| `R-20260826-04` | 夜跑 sector-daily 事故分诊 2026-08-26 18:45（`logs/daily-full-review.out.log` same-day gate rc=2 段 + err.log EMFILE traceback；生产事故根因+修复预注册，非标准四阶段分诊） | `HARNESS_FIX` | 根因链：fupanhui 08-24 起匿名直连 401（实测 kline 端点回「未授权，请先登录」）→ `get_sector_klines_batch` 直连臂 403 板块逐个抛 `HTTPError`——该异常对象本身 file-like、持有响应 socket → `_direct_batch` 把异常收进 failures 列表且异常→traceback→frame→列表成引用环 → fd 只能等周期 GC → CDP 兜底抓数成功但进程 fd 已爆 → `duckdb.connect(staging)` EMFILE「Too many open files」→ same-day gate rc=2、`fact_sector_daily` 停 08-25，连坐 features/period_rank 与 readiness `market_data_consistency`。与 `R-20260826-03` 同族（fd 生命周期交给 GC），同日第二例。预测：`_direct_api_get` 对 HTTPError 先 `e.close()` 再原样重抛后，批量 401 fd 增长 ≤3；修复生效后的下一次 sector-daily（夜跑或手动补跑）status=ok、same-day gate 全绿、readiness 回 13/13。失败形状：修后仍 EMFILE（=还有第二处持 fd 的异常/响应，查 stocks 批与 cdp_eval 路径） | **离线已绿**（分支 `fix/fupanhui-direct-fd-leak`）：`tests/test_fupanhui_direct_fd_hygiene.py` 2 钉——泄漏钉先红（50 次 401 泄 50 fd，1:1）后绿（≤3）；语义钉锁 HTTPError 照旧逃逸供 api_get 回退 CDP。fupanhui 邻近 19 绿。stocks 批今晚幸存只因每子进程 60 板块未及 256 顶，同一修复覆盖。live 待合并后 sector-daily 实跑回读，单测绿 ≠ confirmed。**回读一（2026-08-26 20:05）**：#427 已合（`215df878`），批次门禁 `93db6ea6` 全绿（pytest 6599/0、前端四连、e2e 15、registry 4/4）。19:32 并行 session 手动重跑整段 sync 成功（sector-daily 61s ok、same-day/cross-day 双门 ok、19:35 换名进生产、readiness 回 13/13）——但该轮在**合并前**运行且交互壳 ulimit 远高于 launchd 256，高限额下泄漏不触顶，**其成功不归因本修复、不作 confirmed 依据**。干净判据 = 2026-08-27 18:30 launchd 夜跑（256 软上限环境）sector-daily status=ok + same-day gate 绿。**2026-08-27 18:42 launchd 夜跑读数（干净判据达成）**：sector-daily ok（覆盖 406 交易日至 08-27）、same-day gate ok(5.1s)、cross-day gate ok(3.2s)、全程零 EMFILE（out/err 双日志 rg 无命中）——fd 修复在低 ulimit 壳下成立。注：当晚换名被 export-increment 连坐阻塞（独立事故，另立 `R-20260827-07` 当轮修复），数据止血后 readiness 13/13；该阻塞不影响本行判据（sector-daily/gate/EMFILE 均达标） | `confirmed` |
| `R-20260826-01` | 双臂对照 2026-08-26（`~/.finance-runtime/trace-diff-spt-forward-20260826/one-page-report.md`；非标准四阶段分诊，为修复预注册） | `DATA_CONTRACT_FIX` | 根因链：`market_snapshot/latest.json` 停 08-24（08-25 16:20 生成时库内无当日行，fallback served=08-24；08-26 00:16 的 0825 修复补了 DuckDB/复盘产物但漏了本产物）→ `_runtime_market_reference_date`=`min(snapshot, db)` 钳到 08-24 → 修复前同题 run 全部 as_of=08-24、08-25 在 episode 出现 0 次。预测：补跑 `scripts/sync_market_snapshot.py --date 2026-08-25`（已跑，provider=duckdb_exact/complete/fresh）后，无显式日期盘面题站立日=库内最新交易日。失败形状：postfix run 仍站 08-24（= min() 之外还有第二处钳制）。防复发：daily-full 修复类操作的完成判据须含 market_snapshot 产物（工单 `docs/superpowers/specs/2026-08-26-width-resonance-bag-workorder.md` §P0） | postfix 正对照 run（同题同画像同端口 8792）episode 的 `as_of`/量能台阶右端=2026-08-25；收据 `~/.finance-runtime/trace-diff-spt-forward-20260826/workbench-8792-postfix/`。**回读（2026-08-26 15:44，run_20260826_154242_107356 completed）**：episode `as_of=2026-08-25`×12、台阶右端推进到 08-25（修复前 08-25 出现 0 次、as_of=08-24×36）；公开稿站立日改为 08-25 且实质结论变化（前一顺位板块因 08-25 缩量回落被降级为分歧观察）——站立日钳制是结论级分叉源，判据成立。防复发条款仍开放（工单 §P0 待 daily-full skill 认领），不阻塞本行 | `confirmed` |
| `R-20260826-03` | 边界探针电池 2026-08-26（`~/.finance-runtime/boundary-probe-20260826/one-page-report.md`；生产事故根因+修复预注册，非标准四阶段分诊） | `HARNESS_FIX` | 根因链：`WorkbenchDB` 全部操作用裸 `with sqlite3.connect(...)`（只管事务不关连接）→ 连接被环持有仅周期 GC 可收（隔离复现 50 次 RunStore 泄 93 fd、`gc.collect()` 归零）→ API 层每请求新建 store + 轮询负载 → fd 顶 launchd 软上限 256 → EMFILE 以 `unable to open database file` 间歇 500（15:43 起 `/api/runs`、16:07 起 conversations/messages；重启后电池轮询 20 分钟内再次灌顶=机制正对照）。预测：`_connect` 改「事务+finally close」contextmanager 后，gc.disable 下 61 次连接 fd 增长 ≤3；live 轮询 10 分钟 fd 曲线持平、电池零 500。失败形状：修后 fd 仍随请求增长（=还有第二处裸连接，查 conversation 侧） | **离线已绿**（分支 `fix/workbench-db-fd-leak`）：`test_workbench_db_fd_hygiene.py` 2 钉先红（增长 93/60+）后绿（≤3）；存储层邻近 151 绿。live 待合并+cutover 后正对照（fd 基线 14 起测），单测绿 ≠ confirmed。**回读（2026-08-26 19:00，验收方独立复算）**：红侧在 `ef2d8427` 基线树复现 2 failed（30 次实例化泄 61 fd）；#417 合入、8792 切 `c0226f34` 后 live 正对照——fd 基线 11，240 次轮询（`/api/runs`+`/api/conversations`，10 分钟）20 个采样点全程 11、增长 0（≤3）、非 200=0；自然对照：切换前旧码（`fbdbbfd2`）被 UI 轮询 2h16m 从 14 灌回 225/256。预注册失败形状「还有第二处裸连接」已排除（仓内非测试代码仅此一处 `sqlite3.connect`）。收据 `~/.finance-runtime/cutover-20260826f-8792/fd-curve.log` | `confirmed` |
| `R-20260826-02` | 同上双臂对照（react 臂多做「概念×申万一级宽度共振」交叉验证并因反证降级结论，产品臂引用画像判据未验证；为组件预注册，非标准四阶段分诊） | `HARNESS_FIX` | 给 market_watch 预取加「宽度共振袋」（概念板块当日 pct/diff × 对应 `sw_l1` 当日 pct，DuckDB 只读、与其余袋同 served_date）后：视角/板块题在「概念涨、行业负」形状的交易日，公开稿不再把概念级放量升格为主线扩散级结论。袋只交付事实对照行，判语留给画像解读（§0.2 纪律：不加 prompt、不内嵌 ReAct）。失败形状：加袋后模型忽略袋内容仍给主线级结论（=问题在解读层不在供数层，停止供数侧加料） | 先离线：袋渲染单测 + served_date 一致性断言红→绿；后 live 同题双态（有/无该袋）；开关板登记原子行（seam+close_via+positive_control，走 switchboard 交接第 0-1 步纪律）。工单同上 §P1。**回读（2026-08-26 19:00，run_20260826_185712_417484 completed，8792@`c0226f34`）**：袋 live 交付——episode 含标题+免责声明，站立日 08-25×12 与其余袋同源，渲染 6 行与 DuckDB 原表逐位一致；模型消费袋（公开稿引用 E6）并按画像降权：「光纤光缆/海洋经济…但无申万一级共振对照，按『无宽度夺价确认的单一概念异动』降权，仅作轮动观察，不升级为新主线」；无袋臂（`workbench-8792-postfix`@`fbdbbfd2`，同题同画像）对该 +4.89% 异动零提及=双态分叉成立；失败形状（忽略袋内容硬给主线结论）未现。**成立条件**：站立日 top6 概念 sw_l1 映射全空（`fact_sector_daily` 08-25 仅 119/403 有映射，`dim_sector` 同空），「概念涨×行业负」精确形状 live 未观测；解读侧读数 n=1。映射回填列数据侧候选工单，开关板行 `positive_control` 待补即引用本回读。收据 `~/.finance-runtime/trace-diff-spt-forward-20260826/workbench-8792-widthbag/` | `confirmed` |
| `R-20260824-20` | V8 addendum `docs/superpowers/specs/2026-08-24-optional-forward-slots-addendum.md`（上游 V8 spec `2026-08-22-v8-semantic-deletion-rights-design.md`；来源非标准四阶段分诊，为设计收口预注册） | `HARNESS_FIX` | 部署后：① 前瞻信号（`_OUTLOOK_JUDGMENT_RE`）命中且契约原无前瞻槽的 run，契约含 `scenario_paths` / `continuation_conditions` / `invalidation_conditions` 三槽（`required=False` + `grounding_mode=model_reasoning` + `evidence_types=()`），模型不绑不影响 completed；② 该类 run 公开稿中的条件阈值句（若/跌破/站稳 + 具体数值）不再被 `numeric_unsupported` 机械删除；③ 该类 run 的 `basis_mismatch` 拒次数为 0（**归因已更正 2026-08-24**：`grounding_mode` 本就在逐回合载荷 `build_episode_input` 里，非动态提示规则之功；本条只作为「挂槽没引入新的绑定错误」的回归观察）；④ `market_forecast` / `event_forecast` 契约逐字段不变，`market_technical` 的 `invalidation_conditions` 保持 evidence 签约，`test_numeric_unsupported_sentence_is_still_deleted` 原断言绿。预测失败形状：挂槽后阈值句仍被机械删（豁免未贯通 = 设计 §3.1 坑复现）、挂槽后模型绑三槽被 `basis_mismatch` 拒（提示词未带 grounding_mode = §3.2 坑复现）、market_forecast 必选槽被降级、或无前瞻槽契约的无据阈值句留在公开稿 | **离线已绿**（2026-08-24，分支 `feat/optional-forward-slots`）：新文件 `intelligence/tests/test_optional_forward_slots.py` 18 钉先红后绿，覆盖设计 §8.1 ①–⑫；变异 §8.2 六条 **6/6 击杀**，含两条必杀（恢复 `item.required and` → 钉 6 红；删动态提示规则 → 钉 11 红）。`intelligence/tests` 全量 5699 passed / 11 skipped / 0 failed，V8 与 W1 锚钉零改动全绿。**live 首轮已跑（2026-08-25，8792@`468226108fef`，探针 `probe-fwd-0825`，5 个 run，详见 `docs/verification/2026-08-25-optional-forward-slots-live.md`）**：主目标达成——`stock_deep_dive`+「怎么看」挂 3/3 槽、模型全绑 `basis=model_reasoning`、公开稿保住无据阈值句（`跌破 860 元`/`跌破 800 元`，两数在证据字段中出现 0 次）、全稿无「以盘面为准」自保话术、`numeric_unsupported`/`basis_mismatch` 均 0。**但未结案**：误触发样本 D 出现 2 次 `basis_mismatch`（槽是 `counterpoint` 不是本单三槽，与 2026-08-18 同形）并 degraded，其无信号孪生对照 E 干净；同题型样本 B 却为 0——n=1 vs n=1，污染假说既未证实也未排除。结案前需补 3–5 个「theme_analysis+误触发」同形样本。原验收要求：验收方用 `probe-fwd-<mmdd>`，≥2 个挂槽样本 + 无前瞻槽对照 1 个 + **误触发样本 1 个**（设计 §8.3 对照三：语义上不问前瞻但命中正则的题，记录模型是否为填格硬凑情景）+ `basis_mismatch` 拒次数。执行方不得自行标 confirmed；单发不得结案 | `pending` |
| `R-20260824-12` | knevo28 P0-A（收口预注册，非标准四阶段分诊） | `HARNESS_FIX` | B2 形：`invalid_repair_finish` + 证据非空 → 开口不是「现有证据不足」；已兑现槽公开句保留；未兑现槽用户语言 unknown；无 `【结构缺口】` | **离线已绿**（2026-08-24）：`test_publication_view_deepen.py` n=3 + `test_gap_answer_middle_tier.py` 新成因。live/矿重放未跑，单测绿 ≠ confirmed | `pending` |
| `R-20260824-13` | knevo28 P0-A（收口预注册，非标准四阶段分诊） | `HARNESS_FIX` | 28 题重放 QC marker=0（靠不拼接，不靠禁语表）。judge unavailable 同 SHA 仍走已有两成因之一，不新开第三扇门 | 离线重放 knevo28 矿。禁止用本行重开 D1。adapter 缝合已拆，矿重放未跑 | `pending` |
| `R-20260824-14` | knevo28 P0-A（收口预注册，非标准四阶段分诊） | `HARNESS_FIX` | false capability 10/11→0：capability 来自 typed tool receipt 投影，不再 dataset 字符串启发 | **离线已绿**：`plan_capabilities_from_receipt(tool=finance_query)` 含 `market_data`；`verify_episode_outcome` 不再因工具名≠计划能力误报。矿 10/11→0 重放未跑，不得 confirmed | `pending` |
| `R-20260824-15` | knevo28 P0-B（收口预注册，非标准四阶段分诊） | `HARNESS_FIX` | A4/C6/B5 改写 100% 注册定义+`.TI` universe | 封存改写组。P0-B 接线已写（`feat/research-program-compiler`）；离线编译/pack/prefetch 绿 ≠ confirmed | `pending` |
| `R-20260824-16` | knevo28 P0-B（收口预注册，非标准四阶段分诊） | `HARNESS_FIX` | A10 走 aggregate；C8 走 catalog 快路 | 封存改写组 + latency。接线已写，改写组未跑 | `pending` |
| `R-20260824-17` | knevo28 P1（收口预注册，非标准四阶段分诊） | `HARNESS_FIX` | B1–B3 单槽缺不丢整篇；stale≠no-hit | P1；绑定 `ThemeResearchSpec` | `pending` |
| `R-20260824-18` | knevo28 P1（收口预注册，非标准四阶段分诊） | `HARNESS_FIX` | 有证据零公开=0；ReAct 空稿 `draft_source` 必填。reserve 在租用循环工具缝执行，不新加 schema 字段 | 重放 A3/B1/B3/B4/B8 | `pending` |
| `R-20260824-19` | knevo28 P2（收口预注册，非标准四阶段分诊） | `EVAL_ONLY` | 2×2 四格按预注册判读出结论；Both 不以盲评追平组件臂为门 | 消融批；盲评可附观察 | `pending` |
| `R-20260824-01` | spec 2026-08-24 盘面包（收口预注册，非标准四阶段分诊） | `HARNESS_FIX` | `market_watch` 进 ContinuousTurnAdapter 得 `handled=False`；A1 第一动作不再是 `deadline_exhausted` | §7.1 #1 单测绿；live A1 双态（run_20260824_034205 / run_20260824_035503）首动作 turn_assembly、非 `deadline_exhausted`，答案 14s 内交付；收据 ~/.finance-runtime/mwcf-live-20260823/receipts/probe-a1*.{log,json} | `confirmed` |
| `R-20260824-02` | 同上 | `HARNESS_FIX` | 显式站立日 `trade_date = ?`；问 07-25 不得吃 07-24 行；`_resolve_market_data_context` 无该日行不得回显问句日 | §7.2 #4/#5a/#6 单测绿；live A1 显式站立日=2026-07-23、四袋 served_date 一致；live P0（07-25 周六）公开稿只有休市句、无 07-24 行回显；收据 ~/.finance-runtime/mwcf-live-20260823/receipts/probe-p0.log | `confirmed` |
| `R-20260824-03` | 同上 | `HARNESS_FIX` | A1 冻结日开口前四袋齐；公开稿含锁字段、双红名、热度名；`served_date=2026-07-23` | §7.3 夹具绿；live A1 公开稿四袋齐：总量 21949.97 亿、主线 5 方向、严格双红 7 个（名单在稿）、涨停热度 20 题材，全部 served_date=2026-07-23；收据 ~/.finance-runtime/mwcf-live-20260823/receipts/probe-a1*.{log,json} | `confirmed` |
| `R-20260824-04` | 同上 P1 | `HARNESS_FIX` | 残差稿含 `MA20`/`110–120%`/「旗型蓄能」时公开稿删句，不留质检条 | §7.4 #10。**离线红→绿**（2026-08-25，分支 `fix/unregistered-threshold-gate`）：`apply_market_watch_delivery_gate` 只对 `market_watch` 生效，注册与否以本轮网格（包渲染/证据）为准；编排器双合并点前置删句 + Engine A 回退防线（若 `market_watch` 被移出拒收名单仍不上桌）；删句以 `market_watch_delivery_gate` degrade 入账不进正文。`test_market_watch_delivery_gate.py` 5 例（含 owner 正文接线 + 探针行不误删）。live/自然样本未回读，不得 confirmed | `pending` |
| `R-20260824-05` | 同上 | `HARNESS_FIX` | 有 `2026-07-23-daily-review.md`、daily-review own 时包仍跑、锁格进公开稿，不被 md 顶掉 | §7.1 #2a/#2b 编排器夹具绿；live 双态过洞 1：无 md 时 daily-review 降级、包仍上桌（run_20260824_034205）；有 md 时 daily-review own、正文含同名数字（21949.97）仍未顶掉锁格（run_20260824_035503）；收据 ~/.finance-runtime/mwcf-live-20260823/receipts/probe-a1-owner.json | `confirmed` |
| `R-20260824-06` | 同上 | `HARNESS_FIX` | `2026-07-25 今天市场怎么样` 公开稿休市句、总量袋 empty、无 07-24 成交额 | §7.2 #5a 绿；live P0『2026-07-25 今天市场怎么样』公开稿=休市句、无 07-24 成交额（live 走 lane_generation 短路，包 should_stop 为二道防线由单测覆盖）；C1 原题旁路一致未改路由；收据 ~/.finance-runtime/mwcf-live-20260823/receipts/probe-p0.log、probe-c1.log | `confirmed` |
| `R-20260824-09` | spec 2026-08-24 开关板收口（非标准四阶段分诊） | `HARNESS_FIX` | 用户明示后 8792 与 8796 的 `source_revision` 同一 12 位前缀、皆 `dirty=false` / `code_matches_repo=true` | 用户 2026-08-24 纠偏：8792=main，8796=解耦树，合 main ≠ 两港同 SHA。误切 8796→`af71f048` 已拨回 `76ee1e89`（三读 dirty=false / match=true）。同 SHA 预测不成立 | `refuted` |
| `R-20260824-11` | spec 2026-08-24 D4 第 1 步（收口预注册，非标准四阶段分诊） | `HARNESS_FIX` | 从今日 `gitea/main` 开 `feat/capability-switchboard`：只加盘点 §1.B 新文件 + 在 `asof_prefetch.dual_red_counts` 重贴最小 `faces()` 接线。生产 `intelligence/{services,runtime,adapters,api}` 除登记表自身外不含 `capability_switchboard`。`predicate.reading-baseline` 为 `pending-other-branch`，本底无 `reading_baseline.py`。默认 `faces()` 下双红预取与改前一致；`using({predicate.double-red})` 时 `dual_red_counts` 返回 `{}`。`query_understanding` / `foresight` / `ask_blocks` 仍不读 `predicate_faces`。 | 离线：`intelligence/tests/test_capability_switchboard.py` + 既有 `test_asof_prefetch_dual_red.py`。禁止 `git checkout 76ee1e89 --` 已漂路径。同 SHA / 合 main / 切 8796 不在本行，见 `R-20260824-09`。live 不得 confirmed | `pending` |
| `R-20260824-31` | spec 2026-08-24 outlook v2（收口预注册，非标准四阶段分诊。原误占 `-20`，该号已归 optional-forward-slots） | `HARNESS_FIX` | 句尾「写一下本周行情的展望」信封/plan/decide_turn 三链皆 `market_forecast`；`FORECAST_REQUIRED_OUTPUTS` 入契约。「分析有色金属板块后续走势」仍 `theme_analysis` | **离线已绿**（句尾表 + #9b）。sidecar live `run_20260824_225210_077131` 座位 `market_forecast`。生产 8792=`a7a8ba9f` 未再跑冻结展望，不得 confirmed | `pending` |
| `R-20260824-21` | 同上 | `HARNESS_FIX` | `bind_live_weekly` 的 `date=max(article.date)`；问句 BM25 / `memory_lookup` 纠偏不得标 `live_weekly`；更旧文号未标 analog 则公开稿删句 | **离线已绿**。sidecar live 同 run 活周报 `2026.34`/`2026-08-17` + hash 入账。生产冻结展望未再跑，不得 confirmed | `pending` |
| `R-20260824-22` | 同上 | `HARNESS_FIX` | `run_weekly_watch_pack(end=库尖, window=5)` 每日四袋 + 双红 COUNT；`collect_prefetch_items(question_type=market_forecast)` 开口含周四主线袋。`general_finance_qa` 不进该支 | **离线已绿**。sidecar live 同 run 五日包 08-18…08-24。生产未再跑，不得 confirmed | `pending` |
| `R-20260824-23` | 同上 | `HARNESS_FIX` | 包进 Engine A `_opening_prefetch_evidence` / `_seed_opening_prefetch`，不挂 compose。缺周四主线袋 = 包没跑完 | **离线已绿**。sidecar live 包在 opening evidence。compose 未挂。生产未再跑，不得 confirmed | `pending` |
| `R-20260824-24` | 同上 P1 / 可用稿 | `HARNESS_FIX` | 隔板新闻不得写「已验证」；无格阈值删句；路由加严后公开稿仍可用（非空、有判断或一条情景） | 隔板闸 + `locked` 已绿。#22 无格 `110–120%` 离线闸已接线。sidecar live 可用稿 1613 字。生产冻结展望未再跑，不得 confirmed | `pending` |
| `R-20260824-25` | spec `docs/superpowers/specs/2026-08-24-personalized-join-kernel-design.md` §8/§10 P0 洞 1（实施 #359 已于 08-24 合并 `ada882c6`；台账行 2026-08-27 由 crosswalk 存量清理补（工单 §P1-b：spec 引号台账无行，实施已合 live 状态无处可查）） | `HARNESS_FIX` | StancePack 挂上 compose 后 `trade_advice` 不再在 Engine A 早退——包不再是死代码，持仓/止损题 live 出包 | 判据文本以 spec §8 为准；#359 已合但 live 未回读，按工单不得因「PR 早合了」写 confirmed | `pending` |
| `R-20260824-26` | spec `docs/superpowers/specs/2026-08-24-personalized-join-kernel-design.md` §8/§10 P0 洞 2（同上，台账行 2026-08-27 由 crosswalk 存量清理补（工单 §P1-b：spec 引号台账无行，实施已合 live 状态无处可查）） | `HARNESS_FIX` | StancePack 与 V 块不再双写「你上次」——单一来源，两份清单不再必漂 | 判据文本以 spec §8 为准；live 未回读 | `pending` |
| `R-20260824-27` | spec `docs/superpowers/specs/2026-08-24-personalized-join-kernel-design.md` §8/§10 P0 洞 3（同上，台账行 2026-08-27 由 crosswalk 存量清理补（工单 §P1-b：spec 引号台账无行，实施已合 live 状态无处可查）） | `HARNESS_FIX` | 持仓/止损题 lane 钉死，chat 路径不再误跑或漏跑包 | 判据文本以 spec §8 为准；live 未回读 | `pending` |
| `R-20260824-28` | spec `docs/superpowers/specs/2026-08-24-workbench-quality-residual-ux-design.md` §10 P0-a（台账行 2026-08-27 由 crosswalk 存量清理补（工单 §P1-b：spec 引号台账无行，实施已合 live 状态无处可查）） | `HARNESS_FIX` | 活周报条目带非空 `content_hash` 进公开账本（有 E 号）；冻结原题+`sptfei` **同一次** live：`question_type=market_forecast`、活周报 `source_date=max(date)`、五日包在（或该袋 empty/locked）、可用稿——两次 run 拼证据=假齐不算过 | spec §9.1 #1/#2 逐字；变异：去掉 hash → 账本无「活周报」、有 E 号的盘面袋仍在 | `pending` |
| `R-20260824-29` | spec `docs/superpowers/specs/2026-08-24-workbench-quality-residual-ux-design.md` §10 P0 诚实（台账行 2026-08-27 由 crosswalk 存量清理补（工单 §P1-b：spec 引号台账无行，实施已合 live 状态无处可查）） | `HARNESS_FIX` | 主库写锁时收据有第三态 `locked`（与 `empty` 并列），公开稿能说「复盘写入中，请稍后」；**禁止**把锁写成「该日无数据」或静默 `except: pass` 成「包没跑」——DuckDB 单写者模型下与「没数据」不可区分是撒谎 | spec §9.1 #5 逐字；P1（状态栏/banner/重试/写入让位）不在本行 | `pending` |
| `R-20260824-30` | spec 2026-08-24 品质残差 v1.1（审查 PASS-WITH-NITS；非标准四阶段分诊） | `HARNESS_FIX` | `market_forecast` 仅在开口五日包已齐时升 `ResearchPolicy.for_tier("deep")`（12×240s）。`DETERMINISTIC_OWNER_TYPES` 与 `quick` 档字节不变。深档连打同问句 → `forecast_residual_duplicate_spin` 停机。禁止用全局 `WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS` 当主杠杆 | **离线已绿**（`test_forecast_residual_budget.py`）。live 未跑，不得 confirmed | `pending` |
| `R-20260824-36` | spec 2026-08-24 品质残差 v1.1 P2（审查 PASS-WITH-NITS；非标准四阶段分诊） | `HARNESS_FIX` | 首轮 `market_forecast` 公开稿含未核验格用户语言（无 `【质检`）；「把续走条件写具体」或 gap-mirror 追问继承 `market_forecast` 座位；`collect_prefetch_items` 不重跑五日包，只留沿用收据。复用已有 followup，不新造第三条链 | 离线：`intelligence/tests/test_forecast_residual_followup.py`。live 未跑，不得 confirmed | `pending` |
| `R-20260825-01` | spec 2026-08-25 替补观察探针（收口预注册，非标准四阶段分诊；源自五臂 live-toolkit 医药替补决策） | `HARNESS_FIX` | 主线题材当日无严格双红匹配且盘面题开启探针时，包渲染在缺口句之后出现替补池：带「出清/分歧观察」标签、带个股代码、`served_date=站立日`；触发复用缺口句文本包含对齐；只读 `fact_sector_daily`/`fact_sector_stock_daily`，无 KB/检索参与，`<=` 邻日回落被变异测试锁死 | 离线绿（`test_market_watch_substitute_probe.py` 10 例 + 变异 `<=` 必红实测）。live 只读真实库：2026-08-24 主线医药无双红 → 医药医疗（1556.85 亿）药明康德/沃森生物，`served_date=2026-08-24`；收据 `~/.finance-runtime/substitute-probe-live-20260825/`。生产 8792 未切，不得 confirmed | `pending` |
| `R-20260825-02` | 同上 | `HARNESS_FIX` | 替补行标签先于名单渲染（`[出清/分歧观察]` 在个股名之前），块标题带「非机会」；`strip_outlook_violations` 不误删探针行 | 离线绿（label-first 断言 + outlook gate 对照测试）。live render 同形 | `pending` |
| `R-20260825-07` | 前瞻观点词形（接下来/后续×怎么看/怎么走）题材题信封 `subject=None`、0.4 兜底；检索种子退化整句、stance pack 无主语（2026-08-25 生产 live 两发 + `0325d829` 离线实测；spec 预注册，未实施） | `HARNESS_FIX` | 单题材后缀窗口新路 + `_joint_board_subject` 门放宽后：冻结句 `subject=科技、医药`、「医药板块接下来的走势怎么看」`subject=医药`；cue 路（「分析下有色金属…」→ theme_analysis）与市场级（「接下来大盘怎么走」「今天市场怎么样」）回归锁不动；变异「新路插到 forecast 判定前」必红 | **离线红→绿**（2026-08-25，分支 `fix/theme-envelope-subject`）：单题材后缀窗口路（`_forward_opinion_board_subject`，matched_by=`suffix_window`，conf 0.74）+ `_joint_board_subject` 词形门放宽（scenario_tree 算子门 ∨ 前瞻观点词形）。§7 全表 + 变异锁（真命中 forecast 的「展望后市，科技板块…」不被抢；勘误：spec 原拟的「接下来大盘怎么走」本就不命中 `is_market_forecast_query`，其保护实际来自无板块后缀）。信封文件 76 过（72 存量 + 4 新）+ 消费方周边 82 过。**live 旁证已到**（#383 合并、8792 切 `e577430d` 后同冻结句生产复跑 `run_20260825_113_*`，post-envelope 探针）：契约 `task_frame.subject='科技、医药'`/`kind=theme`（切前两发为 None）；收据 `~/.finance-runtime/substitute-probe-live-20260825/post-envelope-e577430dd70c/`。同发模型绑定 `verification_timepoints`（bindings 在场），为 `R-20260825-06` 兑现率添首个正样本 | `confirmed` |
| `R-20260825-08` | harness 自审（2026-08-25）发现：market_watch 删句闸只在 dropped>0 时落 degrade，「闸跑了零删」与「闸没跑」在 telemetry 不可区分（「仪表全绿但值是空壳」同族） | `HARNESS_FIX` | 闸 applied 即落 trace 步 `market_watch_delivery_gate`（payload {applied, dropped}），零删不占 degrade 通道；orchestrator 双消费点（owner/合成路径 + Engine A 回退防线）皆有活性事件 | 离线红→绿（分支 `fix/watch-gate-liveness-signal`）：零删 owner 轮 trace 在场且 degrades 无此项、删句轮 trace dropped≥3 且 degrade 在场（owner 渲染复现 summary 多处，锁下限不锁精确值）。全量 6430P/0F。live 随下一次盘面题自然样本回读 | `pending` |
| `R-20260825-09` | spec 2026-08-25 台阶轨迹+资格判断（收口预注册，非标准四阶段分诊；源自 live ReAct 对照：同题 workbench `run_20260825_113538` 预取仅 1 件，「放量反弹失败→台阶回落」形状对模型不可见） | `HARNESS_FIX` | 题材前瞻/观察题（非 market_watch 路由）开口预取含题目相关板块近 5 日量能台阶：subject 解析梯 ∪ 近 20 交易日主线池（cap 6，subject 命中优先，发酵锚定板块让位），逐板块复用 `format_sector_timeline` 5 日窗 + 观察值注册；板块窗口无行如实声明不放宽 | 离线红→绿（`test_step_trajectory_qualification_prefetch.py` §7 #4–#8 全绿，36 测 + 全量 6446P/0F）。**live 一发过**（2026-08-25 sidecar 8820=worktree 脏码 `be67eb27+`，冻结题 `run_20260825_143634_143023`）：开口预取 7 件，台阶 4 件（医药/医药医疗/有色/半导体，E3–E6）全 `source_date=2026-08-24`=站立日，公开稿引用台阶形状（医药医疗 08-20 双红后连两日放量下跌、半导体缩量阴跌）；收据 `~/.finance-runtime/step-trajectory-live-20260825/`。生产未切、自然样本未回读，不得 confirmed | `pending` |
| `R-20260825-10` | 同上（SPT 第一判据「总量 vs 20 日均额」无供数，残差引用比值面临未注册误杀） | `HARNESS_FIX` | 同类题开口预取含大盘量能资格盘：站立日总量 + 20 日均额（窗口=截至站立日最近 20 交易日**含当日**，§3 #2 实测冻结）+ 比值一位小数，N=20 才注册三观察值、N<20 如实标注不冒 20 日口径；渲染用中文「20 日均额」不写 MA20；残差引用比值不被语义验证器判编造 | 离线红→绿（§7 #1–#3 + #11 判官对照；**变异 A 实测必红**：窗口改「不含当日」→ `test_qualification_uses_inclusive_20d_window` 红，真库两值 23110.8 vs 23145.4 可区分）。live 同 run：资格盘 E2 在桌，公开稿引用「大盘 08-24 成交 20072 亿，仅为 20 日均额 23111 亿的 86.9%」，与库内值逐位一致、无 MA20 拉丁词面。生产未切，不得 confirmed | `pending` |
| `R-20260825-11` | 同上（家族词 subject 经 `resolve_query_themes` 锚定宽松轮臆配词面近邻板块：「科技」→「量子科技」，错数据自信上桌；§3 #4 代码级推断已升实测） | `HARNESS_FIX` | 解析梯 fail closed：token 只到精确板块名与近 20 日主线登记题材为止，**禁止宽松轮**；解析不到输出如实未锚定声明；主线池把语义家族原料（AI算力/半导体等登记题材）端上桌，「X 属于科技系」归类留给模型 | 离线红→绿（§7 #5；**变异 B 实测必红**：梯子接入无条件包含解析 → `test_family_word_fails_closed_not_quantum_tech` 红，量子科技确实上桌）。live 同 run：无量子科技台阶，「科技」未锚定声明（E7）在桌，公开稿以主线池半导体作科技代表、全稿无量子科技。生产未切，不得 confirmed | `pending` |
| `R-20260825-12` | spec 2026-08-25 读向闸（收口预注册，非标准四阶段分诊；源自 glm-5.2/5.3 A/B：数字全对、放量/缩量贴反，语义验证器不响） | `HARNESS_FIX` | 能唯一锚定的陈述性读向断言对照注册 `diff_ratio` 符号；P0 影子只记账不改稿；门控=本轮含 `metric=diff_ratio`，不看 `question_type`；live 复放 5.2 原文期望 mismatch=1（聚合句 skip） | 离线红→绿（`test_reading_direction_gate.py` §7 #1–#14）。#391 已合 `gitea/main@2fea78a8`。**5.2 离线孪生 mismatch=1**（`founding-offline.json`）；**同题 live** `run_20260825_182254_867397` 步在场、checked=2/skipped=12/mismatch=0（稿形未复现 5.2 错句，对稿通过）。收据 `~/.finance-runtime/reading-direction-gate-live-20260825/`。生产未切，影子分母未满，不得 confirmed | `pending` |
| `R-20260825-13` | 同上（影子闸只记账；执法方式未定） | `HARNESS_FIX` | §6 #12 停规满足（checked≥50 + mismatch 人工二分）后，P1-a 在确定性换词 / revise-once / 仍只记账三选一，不默认修订 | 影子期未满，预注册 | `pending` |
| `R-20260825-05` | SPT 有色题（theme_analysis「后续的走势」）不入前瞻闸，推翻条件/验证时点整组缺席（2026-08-25 生产契约冻结实测） | `HARNESS_FIX` | `_OUTLOOK_JUDGMENT_RE` 补「后续的?走势\|后市」后，有色原题契约挂 opt/model_reasoning 前瞻槽组；事实题（涨停家数）不误挂 | 离线红→绿（`test_verification_timepoint_slot.py` A 刀两测）。live 自然样本未回读 | `pending` |
| `R-20260825-06` | 全题型缺「验证时点」格：判断句无 verify_by（指标×时间窗），进不了回检闭环（Knevo 结论元素④对标缺口） | `HARNESS_FIX` | `verification_timepoints` 进 FORWARD_HYPOTHESIS_OUTPUT_IDS 且五处登记齐（描述/marker/提示词/挂载/豁免）；前瞻信号题挂 opt/model_reasoning/evidence_types=()；marker 可判不瞎 | 离线红→绿（B 刀五测 + 钉 6 参数化自动覆盖）。模型 live 兑现率随自然样本回读 | `pending` |
| `R-20260825-04` | P1-b 引入的生产回归：`substitute_observation` FactSlot 未在 episode_factory 三处登记，三词族题 `build_episode_context` 抛 ValueError 整题炸（8792=`20858faf` 暴露，夜间发现无用户流量） | `HARNESS_FIX` | fact slot 进契约三处登记（描述/advisory/evidence_types）补齐后，SPT 两题建契约成功且 `substitute_observation` 为 advisory 格、工具映射收窄 market_data/finance_query；结构不变量测试锁「每个 `_SLOT_BY_OPERATOR` slot 三处齐」 | 离线红→绿（炸点原样复现）；52 探针族 + 78 契约筛选过。**切后 live 复跑已完成**（2026-08-25 10:15/10:23，走生产 HTTP 通道同题两发）：8792=`83ef1bcc` `run_20260825_101512_555399` 与 8792=`6a01f96f`（#377 切后） `run_20260825_102340_250817` 均 completed、trace 无 ValueError、`substitute_observation` 在契约 `required_outputs[4]`（advisory）；收据 `~/.finance-runtime/substitute-probe-live-20260825/{pre,post}-377-*/`。#377 切后 `verification_timepoints` 同题入契约 `required_outputs[11]`，advisory 未绑不影响 completed | `confirmed` |
| `R-20260825-03` | 同上 P1 | `HARNESS_FIX` | `run_market_watch_pack` 默认 `substitute_probes=False`，weekly 五日包与一般题路径行为逐字节不变；两路径接探针须各自带验收（weekly 走开口预取账本纪律，一般题走 `research_contract` 新 operator） | **两半都已落**。P1-b（一般题）：`SIGNAL_SUBSTITUTE_OBSERVATION` 三词族 + market_watch 门控 → `market.substitute_observation` → `collect_prefetch_items` 消费（落点修正见 spec §8.1）；as_of 截断已锁；#372 已合已切 8792=`eb034c7f`。P1-a（weekly）：`run_weekly_watch_pack` 仅最新交易日袋开探针，`_render_day` 标签先行尾接；历史日逐字节不变（3 新测锁）；真实库五日窗 live：仅 08-24 出探针（药明康德/沃森生物），历史日全空。生产自然样本未回读 | `pending` |
| `R-20260815-03` | 标准 M1 分诊 F-003 | `DATA_CONTRACT_FIX` | `answer_coverage` 与 `structural_verifier` 对同一 `output_id` 改用同一判据函数后，本轮 9 个 run 中的 6 处冲突全部消失或转为显式 warning；B8 的 `evidence_boundary` 不再同时是 present 与 missing | 用本轮冲突的 6 个 run 作回归夹具，断言无静默分歧 | `pending` |
| `R-20260815-04` | 标准 M1 分诊 F-001 | `HARNESS_FIX` | `outcome` 落盘补 `draft_source ∈ {model_returned_empty, truncated_by_budget, provider_error}` 与合成入口 `remaining_ms` 后，下一次空 draft 的 turn 其 `draft_source` 非空，可据以在 REASONING 与 HARNESS 之间定夺 F-001 的 L0 | 字段存在性单测；**单次读数不得结案**，需 ≥3 个同形样本 | `pending` |
| `R-20260804-10` | L7 finalization T3 | `HARNESS_FIX` | deadline-aligned per-tool handoff 能让超出安全窗口的 deterministic slow tool 在生效阈值返回一条可配对的 `research_stage_closed + instruction`；正常成功路径同 id 恰好一个 `tool_result`，handoff 路径同 id 恰好一个预期执行层 `tool_error` 且无迟到 `tool_result`；只发一次 finalization，归一化后 `unpaired_tool_requests=0`；finalization reason 与 budget payload 同时看见 root-ledger 耗尽，handoff window 来自 profile / 生效预算而非隐藏的 `initial×0.20` reserve | **主门只用离线** slow-tool fake clock/隔离测试，并另测 `policy calls>0、root ledger calls=0` 与 `floor_ratio=0`；按 request id 分开断言正常 `tool_result`、handoff 执行层 `tool_error` 和 late-result 不入账，`tool=mailbox,error=response_path_conflict` 作为独立 transport 诊断不计入执行终态基数；再断言配对计数、finalization 次数/余量与落盘生效值。全部通过后才跑一次瑞华泰 canary，单次 live 不能独立结案 | `pending` |
| `R-20260815-24` | 轨道 A Round 5 M1 F-001（E-007） | `DATA_CONTRACT_FIX` | marker-loss 删除某 required output 并写入 `gap_output_ids` 时，同步收缩/清空该格绑定或标 structural missing 后：同形 case（hashed fulfilled + 对这些 ID 做 marker-loss）不得再同时出现「结构 fulfilled + `gap_output_ids` 含这些 ID + `citations=0`」。要么剩余 fulfilled 格仍被引用且 `evidence_bound>0`，要么被删格不再 fulfilled。再出现 B3#2 分道即 **reproduces → refuted**。不给已删正文发引用 | **离线已绿**（2026-08-15）：`_shrink_verified_for_marker_loss` 在 `_marker_loss_partial_public` 两条返回路径上收缩 `semantic.verified`（lost 格 `missing`、绑定清空并补 gap）。夹具 `test_marker_loss_shrinks_b3_hashed_cells_and_clears_bindings`、`test_marker_loss_keeps_remaining_hashed_cell_on_partial_c6_shape`、`test_marker_loss_ignores_output_ids_absent_from_contract`。确认口径是 `semantic_verifier.verified.completion`，不是 `episode_fulfilled_hashed`（该仪器仍读 `structural_verifier` + 顶层 `outcome.bindings`，本轮不改 `acceptance.py`）。**部署窗已开**（2026-08-16）：8792=`437cd5e9aa1a` / `source_dirty=false` / `code_matches_repo=true` / 加载树含 `_shrink_verified_for_marker_loss`。live 臂仍等下一批同形 case；**切窗本身不得写 confirmed** | `pending` |
| `R-20260815-25` | 轨道 A Round 5 F-003 | `HARNESS_FIX` | 本修复部署后：新的 `tool_error` 且 `error=tool_exception` 的事件 `detail` 非空，形如 `ClassName: first line`，且不含 `/Users/` 或 `/home/`。再出现 `detail=""` 即 **reproduces → refuted**。不要求数据层已修；A 组仍可抛 `tool_exception` | **离线已绿**：`test_tool_exception_is_traced_and_model_can_finish_same_episode`、`test_tool_exception_detail_strips_home_path_and_stays_nonempty`、`test_public_tool_exception_detail_keeps_class_and_first_line`；timeout 夹具仍禁止 raw sentinel。live 臂等部署后下一批 | `pending` |
| `R-20260815-26` | S10 Phase A 标准 M1 F-001 | `EVAL_ONLY` | 冻结谓词与 N=5 题写入 `intelligence/eval/cases/s10_branch_eligible_tasks.json` 后：Phase B / S1 A/B 必须引用该夹具，不得改用 08-14「三次现场零调用」当基线。夹具 `frozen_at` 与五题原文保持不变；生产 prompt / 路由 / `episode_semantic_verifier.py` 本行不改 | 夹具存在且五题与报告 Freeze 表逐字相同；S10 报告 `validate-report.sh` RC=0。Phase B 若开，另用 `R-20260815-27` / `-28` 候选行，不把本行当 ROUTING 已确认 | `pending` |
| `R-20260816-01` | outlook 预算回归 M1 F-001 | `HARNESS_FIX` | 下一次空 draft 超时 run 的首轮 finalize `model_turn` payload 含 `timeout_asked`（及入口剩余秒 / input tokens），能直接比较 asked 与墙钟 | 字段存在性单测已随 #84 绿；用下一份同形 live run 读 seq=首轮合成 `model_turn`，缺字段不得结案。长尾窗收口前不占 8792 | `pending` |
| `R-20260816-02` | outlook 预算回归 M1 F-002 | `HARNESS_FIX` | 若动预算：同题重放要么首轮合成成功，要么 repair 的 `timeout_asked` 不再小于该 run 已观测的首轮合成墙钟；须附 2026-08-08 式延迟实测与全路由影响面 | 禁止只把 T 或 30 调大当修复；非观点题对照不得变慢超 5pp | `pending` |
| `R-20260816-03` | outlook 预算回归 M1 F-001 | `EVAL_ONLY` | 同题三臂（只 #72 / 只第 4 次查询 / 四层全开）能单独证实或证伪「#72 提示变重」与「stock_high_daily 扩容」 | 45 槽已否证二者作**窗口充分条件**；L01 r1 必要性仍要单变量。8795 只跑 identity。3-tool/#72-off 须另开 hook 树，不停泊 `21dbf6c1` | `pending` |
| `R-20260816-10` | 2026-08-16 judge transient R-06 T3 F-001 | `HARNESS_FIX` | 处置落地后，下一份 draft>0 的 8795 同形重放：judge 首轮 `timeout_asked` ≥20；H9 形 TimeoutError 率相对 `docs/verification/2026-08-16-judge-transient-r06.md` 11/11 下降 | 只验 standard 窗地板 50（08-20 起首轮=50，不再锁 25）；工具批仍 70、synthesis reserve 仍 20、deep 窗仍 50。PR 若含 T/`_REPAIR_SECONDS_CAP`/档位上调且无 08-08 式实测 → 改记 R-07 refuted | `pending` |
| `R-20260816-07` | 2026-08-16 有稿 judge 案豁免 | `NO_SYSTEM_FIX` | 本窗关闭后下一份自称「outlook 预算回归修复」的 PR diff **不含** T / `_REPAIR_SECONDS_CAP` / 生产档位上调 | 出现上调且无 08-08 式延迟实测 + 全路由影响面 → refuted | `pending` |
| `R-20260816-08` | 2026-08-16 有稿 judge 案 F-003 | `EVAL_ONLY` | 若把 G01–G05 degraded 写入长尾开关账，必须先有同题 off 臂；在此之前收据只写「heading 缺席 + 路由仍 theme-research」 | 无 off 基准却写开关因果 → 本预测 refuted | `pending` |
| `R-20260816-09` | 2026-08-16 有稿 judge 案 F-004 | `HARNESS_FIX` | 若动 `_BALANCED_SYNTHESIS_RESERVE` / 非 finalize `stage_timeout`：改完后非 finalize `timeout_asked` 不再系统等于 `remaining−60`；须附 2026-08-08 式延迟实测 + 全路由影响面 | 只调 T/30 当修复 → 本预测不兑现（T 不改 `min(90,T−40)`）。观点题对照不得变慢超 5pp | `pending` |
| `R-20260816-13` | 宽题取证饿死 M1（`run_20260816_205439_732198`，2026-08-16 20:54 生产首发实测） | `EVAL_ONLY` | 8795 含工具批埋点 tip 重放：每发 `tool_request` 带 `batch_grant_asked`/`stage_timeout_granted`/`episode_remaining_at_dispatch`/`remaining_slots_at_dispatch`/`turn_elapsed_at_dispatch`。**deep 自然完成值合计 > standard 总窗 → H-a**（架构支，不调参）；**evidence_search 自然时长 ≤10s 且失败仅与 dispatch 授予≤0 / slot 耗尽相关 → H-c**（顺序/信号）。缺字段不得结案。工具批读数对 `R-20260816-11` 冻结样本是**移交证据**（其独立 PRIMARY 候选之一），eb 结案权在 R-11，本行不代结 | 判定不得混入 R-10 判据（同侧车不同读数）；`tool_timeout`（时间闸：`_result` 给 timeout 项盖 `stage_timeout_granted_detail`，含授权额≤0 未派发与 `_dispatch` 未完成 future / `except TimeoutError`）与 `tool_budget_exhausted`（次数闸：`error="tool_budget_exhausted"` 落选分支）分开计 | `pending` |
| `R-20260816-14` | 宽题取证饿死案绊线 | `NO_SYSTEM_FIX` | 下一份自称修「宽题取证饿死」的 PR diff **不含** `ASK_TOOL_BATCH_TIMEOUT` / `tool_batch_seconds` / T / slot 上限 / 档位上调 | 出现上调且无 08-08 式延迟实测 + 全路由影响面 → refuted | `pending` |
| `R-20260816-15` | 2026-08-16 十题窗判断槽 0-hash M2 F-001 | `DATA_CONTRACT_FIX` | 用冻结三对离线重算：`_bindings_rate` 把 `grounding_mode=model_reasoning` 槽移出分母（或另报 `judgment_hash_rate`）后，`post:L01:r3` / `L03:r2` / `L05:r2` 的 evidence 槽 eb=1.00，窗级 `evidence_bound_pp` 回到 ±5pp 内；生产 episode / #72 / T / 30 / 档位不变 | 夹具=三对 `continuous-episode.json`；单测钉「判断槽 0-hash + 旁槽 hashed → 分层 eb=1.0、旧口径=0.5」。出现 T/30/档位 diff → 改记 R-07 refuted | `pending` |
| `R-20260818-01` | 2026-08-18 KC 验收 M1 F-001 | `EVAL_ONLY` | `_extract_numbers` 后补中文数量级归一（万亿/亿/万 → 同量纲候选，只加候选不改原值）；用**同一份** `20260818T051630Z.json` 重跑 board 后，B7 两条 fact 由 FAIL 转 PASS，且 A1（原生「亿」表述）保持 PASS | 单测钉「2.96万亿 命中 29569.03±1%」与「2.96亿 不得命中 29569.03」；08-15 / 08-18 两份 artifact 各跑一次，除 B7 外真值列逐题不变 | **`confirmed`** |
| `R-20260818-02` | 2026-08-18 KC 验收 M1 F-002 | `EVAL_ONLY` | 给 9 道无日期锚题补日期（拼进 query 或 runner 显式下达 `date`，两种都不改产品）后重跑：至少 A3 的 `close=12.11` 出现在答案（A6 已证同数据可得） | 冻结题面 sha256，改动前后逐字 diff 入台账；带日期的 19 题真值不得变差 | **`partially_confirmed`** |
| `R-20260818-03` | 2026-08-18 KC 验收 M1 F-003 | `HARNESS_FIX` | `episode_tool_batch` 的 `tool_result` 落盘增加 `payload_field_names`（非空字符串数组）与 `payload_sha256`，不落正文；补后可对每条 fact 失败判定期望字段名是否出现在工具返回字段集 | 断言字段名列表非空且不含正文、无 `/Users/`；artifact 体积增幅 <5% | **`partially_confirmed`** |
| `R-20260818-04` | 2026-08-18 KC 验收 M1 F-001 绊线 | `NO_SYSTEM_FIX` | 在 `R-20260818-01` 落地前，下一份自称修「B7 回归」的 PR diff **不含**产品侧（`ask*.py` / `episode*.py`）改动 | 出现产品侧改动且无新证据 → refuted | **`held`** |
| `R-20260816-16` | 中转全站中断 M1（`run_20260816_221823_213588`） | `HARNESS_FIX` | 8792 provider 链长度 ≥2（GLM Coding Plan + 中转）后：中转 5xx 时同题重跑 `usage.tool_calls>0`、可见 `[0]→[1]` 或直接走健康 `[0]`，且不再出现同一死 provider 重试满 16 次 | 启动器含 `FORESIGHT_BUILTIN_*` 三件套；live 单次不独立结案。draft 终值仍 0 不得写 confirmed | `pending` |
| `R-20260816-17` | 同上 F-002 | `DATA_CONTRACT_FIX` | 成因行从 `ASK_DEGRADED_FALLBACK` 拆出后：`repair_model_unavailable` 或 `llm.used=false` 的重渲染首句含「模型服务不可用」且不含「现有证据不足」 | 单测钉三零形状；开关 off 时其余文案逐字节不变 | `pending` |
| `R-20260816-18` | 同上 | `DATA_CONTRACT_FIX` | 三份 artifact status 同一投影后，不存在 `outcome=failed ∧ run.json=completed` | 用 2026-08-16 当日 run 目录作离线夹具 | `pending` |
| `R-20260816-19` | 同上 F-003 | `EVAL_ONLY` | `evaluate_marker_coverage` 对缺口模板整体 `uncheckable` 后，与 `structural_verifier` 不再因「反证」子串冲突 | 并入 `R-20260815-03` 夹具；正常 counterpoint 反向不变 | `pending` |
| `R-20260816-20` | 同上 F-004 | `DATA_CONTRACT_FIX` | 补齐 `_OUTPUT_DESCRIPTIONS` 10 个缺项，`.get(output_id, output_id)` 改启动期校验：`chain_mapping` 不再同义反复 | 18 个 `question_type` × required outputs 无缺键；删任一键须转红 | `pending` |
| `R-20260816-21` | 原题 GLM 复跑 `run_20260816_230528_976709` | `HARNESS_FIX` | repair 窗随生效 provider 实测 p90，不再用对 terra 的 30s 常数卡 GLM；同题重跑不再两发整窗 `TimeoutError`。**禁止只把 30 调大** | 须附分档延迟实测 + 全路由影响面；触 `R-20260816-02`/`-07` 绊线即改记那些行 | `pending` |
| `R-20260816-22` | 工具层追查（`run_20260817_002958_135258`）+ **2026-08-17 用户口径裁定** | `DATA_CONTRACT_FIX` | **按数据类分档，不是放宽门槛**：① DuckDB 硬事实（行情/成交/涨停等）新鲜度**照旧从严**；② 知识库/图谱（`kb_search`/`graph_lookup`）本就不过该门，保持；③ **新增第三种情形**——数据集整体已到 floor、但**被筛子集**停在更早（`fact_mainline_sector_daily` 有到 08-14 的行，而「AI算力」最后一天是 08-07），这不是 stale 而是**该主体退出了集合**，属行业生命周期观察，必须交付而非整批作废。预测：修复后同题重跑，`mainline_sector_daily` 不再返回零证据，答案含「算力于 2026-08-07 后退出主线、其后 N 个交易日未再出现」这一可核验事实；而真正的管道陈旧（数据集整体 max < floor）仍被拒 | 判别变量是**数据集 max 与被筛子集 max 的关系**，不是放宽 floor。离线双夹具：`dataset_max ≥ floor ∧ filtered_max < floor` → 交付退出事实；`dataset_max < floor` → 仍 stale（此条必须保持红线，它是该门禁的原始设计意图）。**变异**：把两个夹具的判据合并成一个即须转红。**实现归工具层执行方**；本行只占号，A 方不改 `_structured_provider_is_stale` | `pending` |
| `R-20260816-23` | 工具层追查（同上） | `TOOL_DESCRIPTION_FIX` | 模型三次写出不存在的维度名（`strength` / `index_return_pct` / `rank`）。`dataset_field_hint()` **已存在**但未进模型可见面——按本仓「事实投递 > 提醒」模式接进 `finance_query` 工具描述后，同题 3 样本的 `FinanceQueryValidationError`(`invalid_query`) 计数降到 0 | 离线断言工具描述含各 dataset 的合法字段清单；live 用同题 3 样本对照 `invalid_query` 计数。**不得靠加 prompt 训话**——字段表是事实投递不是提醒。**实现归工具层执行方**；本行只占号 | `pending` |
| `R-20260817-01` | 同题两发 M2（`run_20260817_014724_245782` / `run_20260817_015340_618752`） | `HARNESS_FIX` | `complete()` 已返回 FINAL_JSON 后，即使 `_consume_root_seconds` 失败，first finish `carried_draft_chars>0` 或 `outcome.draft` 含阶段判断；不得再把刚写出的稿当「从没生成过」。**禁止调 T / `_REPAIR_SECONDS_CAP` / 档位** | **离线已绿**（2026-08-17）：`test_deadline_after_successful_finalize_keeps_the_just_written_draft`；`test_deadline_after_tool_turn_does_not_invent_a_draft`。**#124 已合切** 8792=`31ee58ce`。live `run_20260817_022655_519631` 首轮是 PLAN+工具调用后 `deadline_exhausted`，没有写出答案（content 无 draft），`carried_draft_chars=0` 是工具轮空稿（夹具 2 的形状），**不是** M2 有稿未结转，不得写成 refuted。第二发 `run_20260817_093755_447794` 走到 finalization，`model_turn` TimeoutError，content 空，仍无写出答案。要结案仍须同形：finalize 已返回可取出 draft 的 content（`wrote_answer`，生效解析器 `parse_finish_json`，**不是** `json.loads`）后 first finish `carried_draft_chars>0`。`legal_json` 另计。单次 live 不得 confirmed。**第三发 `run_20260817_094617_943922` 首次同形**：seq14 `model_turn.content` 1404 字符 `wrote_answer` 与 `legal_json` 双绿、`draft` 732 字符，紧随 first finish `carried_draft_chars=732` / `rejection_code=none`，公开答卷 1901 字节含阶段判断。**这是本预测的正面证据，但单次 live 不得 confirmed**；结案须再有约定次数的同形 hit 且用户另拍 | `pending` |
| `R-20260817-02` | T-D 立案（`run_20260817_094617_943922` 工具批实测）+ T-E 形状对照 | `HARNESS_FIX` | **检索档位改为按剩余预算选**（形状挂 `tools/pre-execute`）后：同批多工具场景下，剩余窗口不足时 `kb_search` 降到 BM25 档**返回部分结果**，而不是整批 `tool_timeout` + `tool_budget_exhausted` 收场；`finalization reason` 不再是 `retrieval_deadline_closed`。**判别变量是「剩余时间 → 档位」这条新链路**，不是把窗口调大 | 离线夹具：造「剩余 4s / 剩余 20s」两种预算态，断言前者走 BM25 档有结果、后者走 hybrid；**变异**——把档位选择固定成常量即须转红。⛔ **本窗禁止动手**：触 `R-20260816-07` 绊线（`WORKBENCH_CONTINUOUS_TURN_TIMEOUT_SECONDS` / `_REPAIR_SECONDS_CAP` / 档位 / `ASK_TOOL_BATCH_TIMEOUT` / `MAX_GLOBAL_TOOL_WORKERS` / `MAX_BATCH_TOOL_CALLS` 一律不许调），且 `R-20260816-21` 已点名禁止「只把数字调大」。动手需用户另拍 | `pending` |
| `R-20260820-01` | 液冷同题 M2（`run_20260820_032014_595378`，2026-08-20 凌晨生产实测）→ 本轮已实现 | `HARNESS_FIX` | `resume()` 的截止路径不得再丢掉修复轮**刚写出**的合法 FINAL_JSON。同形液冷重放（首轮空稿 + 修复轮写出可过 `validate_episode_finish` 的稿 + 预算随即耗尽）：last finish `carried_draft_chars>0` 且 `outcome.draft` 非空；公开 `gate_receipt` 不再四格全 `missing_required_output`，`judge_status != unavailable`（有稿才测得到独立判官，`correlated_judge` 应为 `false`）。**禁止调 T / `_REPAIR_SECONDS_CAP` / 档位**（`R-20260816-07` 绊线） | **离线已绿**（2026-08-20）：`intelligence/tests/test_repair_carry_just_written_finish.py` 三条——夹具自洽（seq23 的稿在自己的 33 条证据下过校验器，draft=814、四格 bindings 全绑）、截止路径结转刚写出的稿、修复轮没写出合法稿时不许顶掉上一轮的稿。**变异**：把 `_carry_repair_finish` 的偏好改回 `previous.draft` 即转红（实测 `assert 0 == 814`）。夹具冻在 `intelligence/eval/fixtures/repair-carry-seq23-*`，**必须连 33 条证据一起冻**——缺证据集 seq23 的 `E1…E32` 序数会 `forged_hash` 被拒，测试会绿在错的分支上。**live 臂已跑一发但未同形，不计入验证**（2026-08-20，sidecar 8798 钉本分支 `f029b58a` / `dirty=false` / `code_matches_repo=true`，`run_20260820_103042_376640`，同题面）：首轮合成写出 1231 字、`carried_draft_chars=650`，**根本没进修复轮**（零 `repair_*` 事件），走的是 `run()` 侧 R-20260817-01 那条路径，本行改的两处未被执行。该发只证明两件事：① 改动不伤正常路径；② **有稿 ⇒ 公开 `correlated_judge=false`**（此发 `false`，与液冷 `null` 对照成立，佐证液冷那次是跳过路径而非判官挂了）。live 臂仍等下一批同形 case；**单次 live 不得 confirmed** | `pending` |
| `R-20260820-02` | grok 独立判官尾巴（压 prompt 后 N=5：18.9/23.4/23.6/26.2/46.7s） | `HARNESS_FIX` | 部署后下一份 draft>0 的 grok 独立判官：首轮 `timeout_asked`=50（=窗），不再是 25。窗地板仍 50；T / `_REPAIR_SECONDS_CAP` / 档位 / 工具批 / synthesis reserve **不变**。R-07 豁免证据就是该 N=5，不是再调 T | 离线：`complete_judge_attempt_seconds(DEFAULT)==50` 且 `leftover(49, DEFAULT)` 拒发、`leftover(50, DEFAULT)` 放行。live 读 `semantic_verifier.timeout_asked` 首轮；未部署不得写 confirmed。缺字段不得结案 | `pending` |
| `R-20260820-03` | 2026-08-20 五题分诊 R-1 / F-001 现象（`run_20260820_130200_500233` 等；**不是** 08-15 Open 表里的 F-001） | `DATA_CONTRACT_FIX` | 判官 registry 的 `evidence_id` 与 `evidence_ordinal_table()` 同一空间；bound 新闻卡的 `title` 进入 payload（许继/12.45 等正文不再只活在 title 里而判官看不见）。修好后 `projection_ordinal_mismatch_count=0` 且 `projection_dropped_field_chars=0` | 离线：`intelligence/tests/test_judge_evidence_projection.py`（A3 E9=07-13 非未绑定 E4；B1 容大在 E11；B4 E31 title；未绑定在前时 registry≠E1）。§6 第 7 例：冻 B4 的 evidence+bindings+draft，读**第一发** `rejected_sentence_indexes`（不是落盘 `rejected_claim_indexes`，也不是 `grounded_replay.py`），由 10 降至 ≤4 且句 16/17/22 从 issues 消失。无独立判官凭证则 `not_run`，单测绿 ≠ 本行 confirmed | `pending` |
| `R-20260820-04` | 2026-08-20 五题分诊 R-2 / F-002 传播（同上 B4；**不是** 08-15 的 F-002） | `HARNESS_FIX` | 语义 repair 若会清空全部 evidence-grounded required output，则保留修前 draft，`repair_withheld=True`，`judge_status` 仍为 `repaired`，不再三格 `missing` + 只剩「供研究参考」 | 离线已绿：`test_repair_refuses_to_wipe_every_required_output`；四处 marker-loss（含 terminal）走 `_marker_loss_or_withhold`。live 同形：B4 重放公开答案仍含判断/产业链/反证，`gap_output_ids` 不是三格全缺。未部署不得 confirmed | `pending` |
| `R-20260820-05` | 2026-08-20 五题分诊 R-3 / F-003 热度错绑（B3 `run_20260820_131823_131041`；**不是** 08-15 的 F-003） | `TOOL_DESCRIPTION_FIX` | 固态电池热度查询带题材过滤后，registry 不再混入他题材热度当本题材证据 | **本次不实施**，只占号。禁止把 `R-20260815-03` 标 refuted 来「关」本现象 | `pending` |
| `R-20260820-06` | 质量稿 P0 T1（锂矿现场 + 代码审计；非本轮标准 M1） | `HARNESS_FIX` | 模型自设 `limit=applied_limit=row_count=25` 时 observation **仍**含截断提示与实际覆盖区间；窗口 `ORDER BY` 时间维升序 + LIMIT 不得丢掉锚定日；`trace.requested_time_range.end` 等于问句日且不等于 `requested_date` | **离线已绿**：`intelligence/tests/test_finance_query_truncation.py` §7.1–7.4。T1b 选定「时间维 asc 时倒序取数、返回前翻回升序」，不是端点保底。~~live §7.15 无 sidecar 记 `not_run`~~ → **2026-08-21 live 已跑**（`run_20260821_012059_353272`，sidecar :8796 @ `b318881e`）：稿含「锂矿990382当日+4.4%/628.5亿」，`asked_date_coverage=covered`（**不是** `truncated`，锚定日已不在被截一侧），「未取到」0 次。单跑 n=1 未过方差门，**仍 `pending`** | `pending` |
| `R-20260820-07` | 质量稿 P0 T2（电网/铝资讯 as_of 全滤；路由稿前置） | `HARNESS_FIX` | as_of=问句日、源只回晚于问句日的标题时，不得静默 0 条；observation 可区分「源里没有」与「被时点门滤掉」；trace.status 仍为 `future_of_cutoff` | **离线已绿**：`test_news_cutoff_disclosure.py`。选定 **T2-a**（标注后交付越界条），不选 T2-c 放开 as_of。~~live §7.17 无 sidecar 记 `not_run`~~ → **2026-08-21 live 已跑**：首跑 `run_20260821_012745_516002` 模型未调资讯（traces 仅 `market_data`），未复现；补跑 `run_20260821_013054_035436` 复现，traces 含 **`directional_news` / `future_of_cutoff`** 且非静默 0 条。单跑 n=1 未过方差门，**仍 `pending`**。本行是路由稿合入前置 | `pending` |
| `R-20260820-08` | 质量稿 P0 T3（铝案单位；代码审计） | `DATA_CONTRACT_FIX` | `amount` 度量对外 label 带「亿」；模型写「226.41 亿」不再被判成「数字扩写」删句 | **离线已绿**：`test_amount_metric_labels_carry_unit`。`dragon_tiger_daily` / `core_stock_daily` 已是「成交额亿」，不得改成「亿亿」。~~live §7.16 无 sidecar 记 `not_run`~~ → **2026-08-21 live 已跑**（`run_20260821_012508_762073`）：稿含「成交额226.41亿」且**未**被判官当「数字扩写」删句。单跑 n=1 未过方差门，**仍 `pending`** | `pending` |
| `R-20260820-09` | 质量稿 P1 Q1（缺口声称对账） | `HARNESS_FIX` | 有 `directional_news` / 截断 `finance_query` 收据时，draft 写「未返回」不得改口；traces 完全没有资讯 capability 时才改口。判据用 capability 不是工具名 | **离线已绿**：`intelligence/tests/test_episode_answer_hygiene.py` §7.7–7.10。电网/锂矿形 `unattempted_claim_count=0`；无资讯 trace 才改口「本次未查询 directional_news」。变异：判据换成工具名 `news_search` → §7.7 会从 0 变成命中。~~live §7.15–7.17 未跑~~ → **2026-08-21 live 四跑已跑，只证了一半**：`unattempted_claim_count` 四跑全 `0`，含电网 `directional_news/future_of_cutoff` 收据那跑（`run_20260821_013054_035436`）与锂矿 `covered` 那跑——**「有收据不改口」live 成立，且生产 traces 确实发 capability `directional_news`（不是工具名），判据选型得到现场印证**。但**改口路径一次都没触发**（四跑无一稿含未尝试缺口声称），§7.9 那形仍只有离线证据。**不得 `confirmed`** | `pending` |
| `R-20260820-10` | 质量稿 P1 Q3（铝残稿回退） | `HARNESS_FIX` | repair 塌成残句则 withhold；回退是「修前稿减去判官点名句」，不是整篇 `view(before)` | **离线已绿**：同文件 §7.11–7.14。闸门 type 含 `market_cause`；合入闸不冻 `general_finance_qa` 的 384→43 整包。减完 ≥2 句且 ≥80 字 → `minus_flagged_sentences`，否则 `whole_pre_repair`。C3 必填格全灭仍走整篇修前稿，不和 Q3 减句混用。~~live §7.16 未跑~~ → **2026-08-21 live 已跑，但机制未被触发**：铝题 `run_20260821_012508_762073` 公开稿 720 字/8 句（原 43 字），`repair_withheld=false` / `repair_collapsed_to_stub=false` / `repair_rollback_mode=null` —— §7.16 那三条判据是**靠稿子本来就健康**满足的，**不是靠 Q3 回退生效**。减句回退与 `whole_pre_repair` 兜底仍只有离线证据。**不得 `confirmed`** | `pending` |
| `R-20260820-11` | 质量稿 P2 Q2（锚定日补枪兜底） | `HARNESS_FIX` | 若 P0-T1 后 live 锂矿稿已含问句日盘面，本行记 `deferred` 不撤号；否则合成前补一枪 | **本次未实施**。~~live §7.15 未跑~~ → **2026-08-21 live 锂矿稿已含问句日盘面**（07-23 +4.4% / 628.5 亿，`asked_date_coverage=covered`），**触发本行自带的 deferral 判据「本行记 `deferred` 不撤号」**，故按其原文改记 `deferred`；号不撤，P0-T1 一旦回退需重开。注意这是 Q2 **未实施**下的自愈观察，不是把 T1 单测绿写成 Q2 已自愈 | `deferred` |
| `R-20260820-12` | 问句日预取日历（asof-prefetch 第 1 刀；非本轮标准 M1） | `HARNESS_FIX` | 「锂矿…发酵到 2026-07-23」的 `information_cutoff` 为 `requested` 7/23，不是 `runtime_default` 今天；「1日至5日」区间题仍不得把起点当 cutoff | 离线：`test_asof_prefetch_dual_red.py` / `test_honesty_gates.py`。live 对照 Cursor SQL，不拿新旧店互比 | `pending` |
| `R-20260820-13` | forecast 双红个数序列（asof-prefetch 第 2 刀） | `HARNESS_FIX` | `market_forecast` 预取含问句日及前两个有数据交易日的双红个数；当日板块表 0 行写 `缺数`，不得写成 0 | 离线假库 2/1/0。live：8.19 题预取含 75→21→0 形 | `pending` |
| `R-20260820-14` | 发酵精确名+双红戳（asof-prefetch 第 3 刀） | `HARNESS_FIX` | 触发词命中且能锚定板块时，预取 `sector_name` 精确名时间轴且行上 `双红=是\|否`；禁止 `contains` 近义名；「固态电池有什么新进展」不强制窗口 | 离线：锂矿 7/23 的 4.4/628.5/11.73 → 双红=是，同日锂电池不进。live 对照 Cursor | `pending` |
| `R-20260821-03a`（原重号 `R-20260821-03`，2026-08-27 判定改号留档：后继实施行保留原号，见下方 confirmed 行） | 成功路径稿 子单 C（预取行拿不到引用把手；Gate 1 创新药现场）·预注册原始行 | `HARNESS_FIX` | 开场预取消息每条带 `[E<n>]`，且该号 == 终局 `evidence_ordinal_table` 解析到同一 `content_hash`；模型引用后判官不再判「无 evidence_id / 发明历史行情」；认不出 hash 的条目不发号 | **离线已绿**：`test_prefetch_evidence_ordinal.py` 5 条（TDD 修前 3F/2P → 修后 5P）；宽集 381 passed，收据 `~/.finance-runtime/test-receipts/20260820T181642Z-dfc25221.json`。变异「发号顺序反转」→ 3F。live `run_20260821_021724_077535`：公开稿 894→1027 字，四段发酵弧保住，`E1` 引用 117 次（修前 0 次且模型自陈「无证据序号」），6-29/7-15/8-3/8-7 四组数与分析师侧逐位对齐。**只改呈现层，判官「数字要有出处」那条未动**。n=1 未过方差门，不得 `confirmed`。详见 `docs/verification/2026-08-21-gate1-prefetch-evidence-id.md` | `pending` |
| `R-20260820-15` | 预取满足必填能力（asof-prefetch 第 4 刀） | `HARNESS_FIX` | outcome 里未绑定、未被 strip 的预取 tool 满足 `mandatory_capabilities`；`test_stripped_evidence_cannot_satisfy_mandatory_capability` 仍红 | 离线 verifier。stripped 哈希不得记账 | `pending` |
| `R-20260821-02` | 子单 B 槽位填数（spec §6.2） | `DATA_CONTRACT_FIX` | 必填格的数字与日期改由预取行/带收据的工具行填入、模型只写格间句子后：公开稿问句日的涨幅/成交额/双红个数能在预取观察值或 traces 里**精确对上**；对不上时输出结构缺口，不得用散文圆过去。Gate 1 PCB概念题的 08-07 由 `8.71%/1295亿`（主线短名）转为 `4.74%/3432.59亿`（E1 长口径） | 离线：定向 pytest 先红后绿；变异——把槽改回自由作文必须转红。live：新题（非本 spec 正文题）走 `POST /api/conversations/{id}/messages`，比对公开稿数字 ⊆ 桌上的行 ∪ 有收据的工具行。**已跑 n=2（生产 8792@`6320b3bc` clean，2026-08-21 部署后）**：`run_20260821_164659_624916`（CXO 同题 B 臂）31/31 实质数字有出处、抽验 17 值逐位对库真；`run_20260821_165210_889002`（减肥药新题）16/16 有出处、七节点含环比逐位对库真且缺口显式声明（「缺公告级证据」）未用散文圆。两 run 判官零删句。审计脚本正负号/尾零归一化盲区已排除（-3.9/-0.23/-3.25 均在带收据行上）。详见 `docs/verification/2026-08-21-tracediff-cxo-ceiling.md` 收口章 | `confirmed` |
| `R-20260821-03` | 子单 C 预取行带 E 号 + 问句精确名优先（#288 `fix/prefetch-evidence-id`） | `DATA_CONTRACT_FIX` | ① 开场预取行带 `[E<n>]`，真话不再被判成发明历史行情；② 问句里出现且表中存在的 `sector_name` 长名优先于被 `decide_turn` 收短的 subject——预取标题与数字跟问句口径走 | 离线**已绿**：`test_prefetch_evidence_ordinal.py` 5P + `test_asof_prefetch_dual_red.py`，合计 13 passed；变异（候选改回 subject 优先）转红。live 预取层**已过**（`run_20260821_031715_726466`，sidecar `33b4ca95` dirty=true）：预取标题 `PCB概念 双红时间轴`、E1 08-07=`4.74/3432.59` 单轨。**公开稿未过**（仍 `8.71/1295`），掉在工具旁路/写稿/判官三层——那是 `R-20260821-02` 与 `-04` 的范围，本行不代结。dirty 树的 live 不得写 `confirmed`。**2026-08-21 部署后补齐 clean 树 live n=2**（8792@`6320b3bc`）：`run_20260821_164659_624916` 预取观察值 subject=`CXO概念` 精确名（decide_turn 收短被覆盖）、公开稿预取事实 08-03=262.33 对库真、E 引用全部可解析、判官零「引用不存在/发明历史行情」类 issue；`run_20260821_165210_889002` 同形（`减肥药` 08-19=-3.25 上桌）。①②两判据在干净生产树上成立，公开稿闭环同时绿（见 `-02`） | `confirmed`（重号已解 2026-08-27：预注册原始行改号 `-03a` 留档于上方） |
| `R-20260821-04` | Gate 1 三筛：判官整段删（`docs/verification/2026-08-21-gate1-pcb-exact-name.md` §Live 第 3 层） | `HARNESS_FIX` | 三筛判该约束为「拦输出 → 封上限」，据此预测：**模型能力越强，被判官整段删连坐的真话越多**。落地 `R-20260821-02` 的槽位后，判官对槽内数字**无删除权**，同形 run 不再出现「整段含真数字被删、活下来的是错口径句」；`judge_status=repaired` 的稿件里，预取行数字留存率上升 | **已集齐 3 个同形样本**（均生产 8792@`6320b3bc` clean、判官 `repaired`、稿内含预取行数字）：① `run_20260821_164659_624916`（CXO B 臂）零删句、31/31 数字有出处；② `run_20260821_165210_889002`（减肥药）零删句、16/16 有出处；③ `run_20260821_171744_929436`（钙钛矿换形探针）**首个「删除与槽保护共存」样本**——判官删了 6 处真违规（合成区间/引未绑卡/无据链路角色/发明阈值），但**零槽值被删**：5 个预取槽值经【预取事实】块送达、13 个工具行槽值（第 10 刀）散文原样幸存。反向证伪未触发：三样本均无槽内数字被删。原判据「模型能力越强、被连坐的真话越多」的机制在样本 ③ 中被正面拆解：连坐止步于槽边界。散文侧引未绑定卡仍会被删（样本 ③ 的 E4 两句），那是残余①的范围，不属本行——本行只押「判官对槽内数字无删除权」。审查侧判据见 `harness-reference/PLAYBOOK.md` §约束三筛 与 `harness-architecture-review` C2。详见 `docs/verification/2026-08-21-tracediff-cxo-ceiling.md` §反过拟合换形探针 | `confirmed` |
| `R-20260821-05` | 反过拟合个股探针（`docs/verification/2026-08-21-tracediff-cxo-ceiling.md` §换形探针；`run_20260821_171744_955225`） | `HARNESS_FIX`（候） | 个股形状 contract-预算失配：`company_multi_layer_evidence` 把 `market_data`+`mainline_context` 定为 mandatory，但 90s 档个股题无预取覆盖、工具轮次耗尽后 `repair_goal.unreachable_without_tools` 且 `reopen_tools=False` → 预测同档个股题将持续 `missing_mandatory_capability=market_data,mainline_context`。修复方向二选一：个股预取补这两路，或契约按预算档把 mandatory 降为 best-effort | 修复落地前：再采 ≥2 个 90s 档个股题应复现该 issue（可证伪——若不复现，说明是本题偶发路径而非契约失配）。落地后：同形 run 该 issue 归零，且 direct_assessment 不再因此路径缺失。**2026-08-21 18:52 复现完成 n=3（生产 8792@`6320b3bc` clean，同形题换股名，烧题检查 gitea/main 0 命中）**：太辰光 `run_20260821_185226_491046` 缺 `mainline_context`（market_data 在修复轮被 mandatory 压着调了——返回**市场总览快照**，市场级数字混进个股公开稿 + marker_loss 横幅，194 字残稿，**满足契约反而污染答案**）；莲花控股 `run_20260821_185229_591768` 缺 `market_data,mainline_context` 与原案全同（且**无 repair_goal**、`model_finish` 直接收稿仍记 issue——记账点在结构核验层，修复路径非必要条件）。`mainline_context` 三 run 0 调用。**偶发假设排除，归因成立：mandatory 清单与个股题形真实取证路径不匹配**。修复方向证据倾向「契约按题形降 mandatory / 单独清单」（预取补路会重演背景当正文）。正文 `docs/verification/2026-08-21-r05-stock-contract-mismatch-repro.md`。**2026-08-21 19:38 修复落地并 live 达标（#296 `00336f0d`）**：`resolve_evidence_plan` 给公司主体题形（stock_deep_dive/valuation_estimate/financial_analysis）降级 `company_current_backdrop` 计划——market_data/mainline_context 降 optional，能力经 planned 并集保留；市场主体题形由 seam ladder `ROUTED_FACTS` 钉住不动。门禁 5882P/0F + 变异×2 击杀；8792 rsync 部署（生效指纹 `16595e41ba72`=00336f0d 树；health `source_revision` 标签滞后于快照名 `6320b3bc`，以指纹为准）。同题重放太辰光/莲花控股（daily-full 未跑、数据态与 before 全同、成对照）：**issue 2/2 归零**；A 臂 before 丢失的转折日数值 after 全数在稿，市场数字转为显式「市场背景」块服务反证②（背景放大器正确用法）；B 臂满稿逐日 E 引用 + 数据异常主动声明。A 臂修复轮 1 次 market_data 调用来自 W5 issue-backfill（`NUMERIC_UNSUPPORTED→market_data` 映射，`episode_issues.py`），与 mandatory 无关——「个股数值缺证回填市场总览」是形状错配，候选观察不立案。已知边界：quick_fact 题形分不出主体（茅台多少钱 vs 涨停家数多少），未动。收据 `~/.finance-runtime/live-probe-traceability/20260821-r05-fix-verify/summary.json` | `confirmed` |
| `R-20260821-06` | 残余①散文引未绑卡（`docs/verification/2026-08-21-tracediff-cxo-ceiling.md` §换形探针发现 1；投影 spec §8 后续项「写手 binding 缺口」；E4 案 `run_20260821_171744_929436`） | `HARNESS_FIX` | 写手散文引用注册表**真有**的 E 号（E4=财联社「反式钙钛矿电池实现产业化验证」）、只是漏写 bindings 数组 → 投影只送绑定子集，判官按「引用不存在」删两句真因果。预测：凡散文引用可反解而未绑定，该引用句必被误删——删的是记账缺陷不是证据缺陷 | **2026-08-21 20:21 修复落地（#298 `59ec4294`）**：投影选集改「绑定 ∪ 正文可反解引用」（`_project_semantic_evidence` + 协议层新 `cited_evidence_ordinals()`，语法与 `_EVIDENCE_ORDINAL_RE` 同源、左界排除 PE10/1.5E8 形似 token）。纪律论证：引用即答案对依赖的显式声明，比记账数组更直接——「only answer-bound」的本意是"判官只能用答案真依赖的证据"，补送**被引用**的卡不放宽它；未引用未绑定仍不送、表外引用照旧 fail-closed。否决替代：接收时改写 bindings（draft 无结构分段、归属不可机械判定、harness 代模型伪造声明）；全部未绑定卡送判官（投影 spec C2 已否决）。D2 哨兵收在绑定子集对账，新增 `projection_cited_unbound_count` 落盘。TDD 6 钉先红后绿 + 变异×2 击杀 + 全仓 5888P/0F；冻结夹具 `pv-perovskite-e4.json`。**机制证明=原始工件重放**：E4 案 before registry 19 行无 E4 / after 20 行 E4 入表（标题原文送达判官）、cited_unbound=1、哨兵 0。8792 部署指纹 `56270d7329b69c34`=59ec4294 树。live 探针×2：钙钛矿同形（passed、新字段=0 读数正确）；莲花控股 R-05 同题（14 处 E 引用全绑定、仅删 1 句无据数值条件、无横幅——R-05 形态未回归）。诚实边界：「引了忘绑」无法按需强触发，live 未采到自然样本；前瞻观测=后续 run 若 `projection_cited_unbound_count>0`，注册表须含该卡且不得再现「引用不存在」类删句。收据 `~/.finance-runtime/live-probe-traceability/20260821-r06-prose-cited-verify/summary.json` | `confirmed` |
| `R-20260821-07` | 残余②子问题1 / spec W1（`docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md` §W1；个股案 `run_20260821_171744_955225`、R-05 A 臂 `run_20260821_185226_491046`） | `HARNESS_FIX` | post-repair 判官对必需输出块只有降级权（missing+gap+标注+批评进质检段），删除权收窄到机械硬违规白名单；部分降级不挂道歉横幅，横幅只归全灭闸。预测：修复落地后，全量 run 中 marker_loss 记账与道歉横幅解耦——marker_loss>0 的 run 公开稿仍交付降级块正文；重放两案 after 残块保留。 | 离线：`test_ceiling_required_block_degrade.py` ①–⑤ + 两案重放夹具。变异：把降级改回删整格 / 去掉块级标注 → 至少一钉红。机制证明=原始工件重放（沿 #298），live 不可按需强触发。部署后自然样本（marker_loss>0 的 run）验收才可 confirmed。详见 `docs/verification/2026-08-21-w1-required-block-degrade.md`。**2026-08-22 00:23 live 探针**（`probe-w1-verify-0822`，`run_20260822_002309_013198`，23:18 URLError 批重发）：真 episode，3/3 必需块 present（direct_assessment/supporting_evidence/counterpoint）、无 marker_loss、无道歉横幅、公开稿 540 字带反证与缺口声明交付；但 semantic judge deadline exhausted（`judge_status=unavailable`，判官入场余量 ~90s/60s）——删除权收窄路径本发未被激发，marker_loss>0 自然样本仍欠，不得 confirmed | `pending` |
| `R-20260821-08` | 封上限形状 B / spec W2（`docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md`；残余②子问题2 + R-05 枚举地基） | `HARNESS_FIX` | mandatory 可满足性两级对账：contract 下发时按 KB 链路证据在场性降级 chain_mapping；运行时 unreachable_without_tools && !reopen_tools 一律降级为缺口声明。预测：结构性不可满足的必填格不再显影为 marker_loss/道歉横幅/错口径污染，显影为显式缺口声明。 | 离线 TDD：`intelligence/tests/test_mandatory_satisfiability.py`（空库题材 chain_mapping optional + 预置缺口；有暴露仍 mandatory；`unreachable && !reopen` 降缺口且 `lost_required_output_substance` 不再含该格；#296 `company_current_backdrop` / `ROUTED_FACTS` 回归；钙钛矿 run `run_20260821_171744_929436` 动态形状重放）。变异钉两条写在同文件。live：部署后同形题（KB 无链路证据的新题材，或 `unreachable && !reopen` 的修复轮）`missing_mandatory_capability` 与 chain_mapping 类 marker_loss 归零，缺口声明出现在公开稿。单次 live 不得 confirmed。**2026-08-22 00:23 live 探针**（`probe-w2-verify-0822` / `run_20260822_002310_733136`，KB 真无题材减肥药重发）：judge_status=repaired 且 `rejected_claim_indexes=[]`、`gap_output_ids=[]`、无横幅——判官 2 条批评以「输出质检」段呈现，零删句；公开稿含显式证据边界与缺口声明（「未核验具体公司的产业链订单、产能或量产事实」）。归零读数成立，但本题被路由为 `general_finance_qa` 契约（required=direct_answer+evidence_boundary），chain_mapping mandatory 路径未被激发——强测试半空；发酵题落非题材契约这一路由观察移交 R2 V1（题形×通道映射）作输入 | `pending` |
| `R-20260821-09` | spec #300 W3 / 形状 D；升级 R-05「个股数值缺证回填市场总览」候选观察 | `HARNESS_FIX` | NUMERIC_UNSUPPORTED 回填目标由静态映射改锚定主体反推，解析不出 fail closed。预测：个股题修复轮不再出现市场总览数字污染。 | **离线已绿**（2026-08-21）：`plan_issue_backfill` 三钉——个股→`finance_query`、市场→`market_data`、无主体不回填；adapter 消费点同步。冻结夹具 `intelligence/tests/fixtures/w3-r05-a-numeric-backfill.json` 重放 A 臂 `run_20260821_185226_491046` 的 `subject_kind=company`，after 计划不含 `market_data`。**变异**：个股分支改回静态 `market_data` → ① 与重放钉、adapter 个股钉三红（`01c5f783` 上改已提交态，`git checkout` 后复绿）。正文 `docs/verification/2026-08-21-w3-numeric-anchor-backfill.md`。全量 5894P/0F，收据 `~/.finance-runtime/test-receipts/20260821T135845Z-a6c682e1.json`（dirty=false）。live 未部署，单测绿 ≠ confirmed。**2026-08-22 00:23 live 验证探针**（`probe-w3-verify-0822` / `run_20260822_002312_957440`）：judge deadline exhausted、修复轮未触发，NUMERIC_UNSUPPORTED 回填路径本发无读数（公开稿中的市场总览数字来自主稿盘面背景块，属计划内上下文，非回填污染）；另记 `marker_coverage=incomplete`：direct_assessment 块标记 absent（正文有评估内容但未落块标记），待自然样本再验 | `pending` |
| `R-20260821-10` | deadline_exhausted 主稿归零路径（收口 R1 spec §W4 观测单；起点=换形双探针「预算观察」，`docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md`） | `HARNESS_FIX`（候，修法另行立项） | 主稿多轮归零（`carried_draft_chars=0`）、全稿一发成于修复窗的路径可复现 n≥3；归因二选一（可证伪）：provider 暂态（超时聚集特定时段）vs 结构性预算失配（任何时段必现），判据=时段分层复现率 | **2026-08-21 22:00 复现+归因完成（观测单，零代码改动）**：近 8 日 410 run 全量扫描，`deadline_exhausted` **323/410=79%**（`model_finish` 仅 17%）；其中 `carried=0` **276 个（全部 run 的 67%）且全部走 `repair_reentry`**——「全稿成于修复窗」是常规路径非探针偶发。时段分层：按天 69–100%、按小时 0–23 全覆盖无聚集无豁免 → **暂态否证，结构性成立**。机制链：共享 deadline 下成稿轮无保留量，工具轮吃剩的残值 median 13.0s / 82%<20s（有埋点 n=39），修复窗独立新授 30–40s 反成事实主生成窗。诚实边界：对照组 `model_finish` 末轮 12–26s 也有成功——归因指「预算分配结构把成稿轮系统性压到临界之下」，非「小窗必死」；末轮输出长度未逐 run 拆。修法三候选（成稿轮 reserve／carried 门槛／修复窗正名二段生成）**须实验组对照后另行立项**，受 R-20260816-07「无实测不得抬 T」约束；R-20260816-09 的 60s reserve 讨论在案，本读数是它等的实测证据之半。正文 `docs/verification/2026-08-21-deadline-exhausted-repro.md`（含字段路径与复算命令，W5 传感器可直接复用） | `confirmed`（归因结论；修复未做不在本行） |
| `R-20260821-11` | 输入侧形状 I+II：KB 检索暗资产（取证计划选择性盲区）+ 缺口声明无取证义务（`docs/verification/2026-08-21-inputside-kb-dark-asset.md`；对应收口 R1 spec §W2 验收方修订新拆的 W2b） | `HARNESS_FIX`（候，W2b 未派） | 形状 I：发酵/复盘题形的 `evidence_plan.requirements` 只列盘面+新闻，`kb_search`/`evidence_search` 授权但不引导 → 模型顺计划零调用，KB 沉淀（概念图谱/链路角色/L1-L3 证据）对这些题形贡献为零；chain_mapping 死格真因=通道不通非库无（钙钛矿 KB 实有奥特维/捷佳伟创/京山轻机带 role/strength）。形状 II：「缺公告级证据」类负面断言在零 KB 查证下做出（减肥药 run 实证——本次真缺撞对，KB 覆盖好的题材同一行为=假缺）。预测：① 打通计划引导（W2b）后，KB 有证据题材的 chain_mapping 类格有据可写、kb_search 出现在同题形 traces；② 缺口文案区分「库无」与「未查」后，零查证的断言性缺口声明归零 | **2026-08-21 22:10 立案读数**：5/5 案例 run（减肥药/CXO A/B 臂/钙钛矿/皇氏集团）KB授权=✅ 计划含KB=❌ 实调=❌；全局近 5 日 94 run 中 KB 调用 24（26%），集中个股深挖/估值题形——盲区是题形×计划选择性的。钙钛矿 KB 在场性与减肥药 KB 真无均已复算（命令在验证文档 §5）。修法前置：先量 KB 检索耗时分布（W4 已证预算紧张常态；在途 plan retrieval-tier 会在 <15s 降 BM25，通道打通必须带预算账）。W2a 重放案例已按此改判（钙钛矿→减肥药，spec §W2 验收方修订）。**2026-08-22 04:12/04:15 live（V1b+V2 部署后，验收方回填）**：预测①成立——钙钛矿 `theme_analysis` 探针 plan 含 KB、实调 `kb_search`、产业链段引 KB 公司（读数在 `-13` 行）；预测②成立——两发探针零「零查证断言」（读数在 `-14` 行） | `confirmed` |
| `R-20260821-12` | 输入侧形状 III+IV+V：KB 送达窗瘦管道/词频绑架选段/同族挤占（`docs/verification/2026-08-21-inputside-delivery-window.md`；与 -11 同属输入侧系列——-11 是调用层，本行是送达层） | `HARNESS_FIX`（候，修法三支互独可分批：粗管道接入/索引排除工件页/同族折叠） | 形状 III：agent loop 唯一 KB 文本入口 `_kb_search` 送达 5×160=800 字符（`hits[:5]`+`excerpt[:160]` 双硬编码），同栈 `llm_evidence` 粗管道（8000 字符预算）已被 evidence_search/主链消费而 kb_search 未接，且无深读通道。形状 IV：excerpt=命中 chunk=query 词最密段——来源清单/wikilink 堆/路径行，长电案 6 命中 4 条零信息、最载荷页送达半个 URL。形状 V：液冷案 top-5 被 4 个 theme-radar 验收工件页（v5-v7）挤满，测试产物在知识索引里。预测：① kb_search 接粗管道后同题送达信息量数量级提升、答案 KB 引用密度上升；② 索引排除工件页后同族挤占消失；③ 若只修 III 不修 IV，送达变大但仍是词频段——两者须分别验收 | **2026-08-21 22:20 立案读数**：31 条 kb/evidence tool_result 扫描（kb_search 恒 5 条、observation 300-500 字符 vs evidence_search 12 条 3635 字符）；长电 query 重放 hybrid ok 6 命中逐条判读；口径链行号与复算命令在验证文档 §5。遥测缺口：kb tool_result 的 telemetry 落盘空 dict，送达率不可回读——W5 传感器建议补 kb_search 送达字符数/条数计数。修法预算账前置同 -11（W4 已证预算紧张常态） | `pending` |
| `R-20260821-13` | 收口 R2 spec §V1 KB 通道计划引导（调用层，形状 I；`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md`） | `HARNESS_FIX` | TDD：发酵题形夹具 → `resolve_evidence_plan` 输出含 KB requirement，先红后绿。重放：R-11 验证文档 §5 的 5 案例，钙钛矿题形 plan 含 KB requirement。变异：删掉题形→KB 映射 → 夹具红。live（部署后）：同题形探针 trace 出现 `kb_search`/`evidence_search` 调用；KB 有证据题材（如钙钛矿）的 chain_mapping 格有据可写（R-11 预测①逐字）。 | 离线：`intelligence/tests/test_kb_plan_mapping.py` 先红后绿；映射恒空（`should_guide_kb_channel` 恒 False）须红。`theme_analysis`/`theme_track`/`stock_deep_dive`/`market_cause`/`valuation_estimate` 整题 optional `kb_search`；`dated_market_review`+别名 `market_review` 共用 `has_sector_theme_attribution_intent`（层名词∧归因动词）。不另建预算降档。live 等 V6 分臂结束由验收方回填，执行方不得自行标 confirmed。正文 `docs/verification/2026-08-22-v1b-kb-plan-mapping.md`。**2026-08-22 04:12 live 回填（验收方）**：钙钛矿探针（`probe-r2-live-0822` / `run_20260822_041251_127897`，8792）`question_type=theme_analysis`，plan 含 optional `kb_search` ✅；trace 实调 `kb_search`（hit_count=6）✅；答案产业链段有据可写——曼恩斯特 GW 级涂布订单（L2）/捷佳伟创量产客户验证/大胜达 1401 万公告/杭州柯林百兆瓦产线，全部来自送达 source_pages（R-11 预测①逐字成立）。已知边界：减肥药同发探针仍路由 `general_finance_qa` 空计划（路由债在案，模型自主调了 KB），不属映射缺陷 | `confirmed` |
| `R-20260821-14` | 收口 R2 spec §V2 缺口声明取证义务（调用层，形状 II；`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md`） | `HARNESS_FIX` | TDD：合成 trace（零 kb 调用 + 缺口声明）→ 文案带「未查证」限定；有查证未命中 → 允许「库无」。先红后绿。变异：二分判据删掉（全部当库无）→ 红。live：零查证的断言性缺口声明归零（R-11 预测②逐字）。 | 离线：`intelligence/tests/test_kb_gap_proof.py`（先红后绿）+ 实现提交 `15e4d8ec` 后把 `kb_gap_claim_kind` 恒返回「库无」须红。called 口径与 V7 钉一致（`provider=agent:kb_search|agent:evidence_search`，不按 capability）。live 由验收方部署后回填，执行方不得自行标 confirmed。正文 `docs/verification/2026-08-22-v2-gap-proof-v1a-kb-plan.md`。**2026-08-22 04:15 live 回填（验收方）**：减肥药探针（`run_20260822_041501_636838`）先调 `kb_search`（6 命中）后才作缺口声明（「缺一手公告确认」），未查通道带限定语（「未取得板块行情结构化数据（未查）」）；钙钛矿探针亦零违例。n=2 零违例 + 改写器在 hygiene 主链离线 8 钉证成——机制性归零由代码路径保证，非仅样本外推 | `confirmed` |
| `R-20260821-15` | 收口 R2 spec §V3 kb_search 送达粗管道（送达层，形状 III；`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md`） | `HARNESS_FIX` | TDD：同 query 送达字符数断言（夹具对比新旧规格，先红后绿）。重放：长电案 6 命中重放，送达含正文级信息（不再是半个 URL / 纯路径行）。变异：管道退回 160 截断 → 红。live：与 V7 的送达计数读数联动（送达字符数数量级提升；答案 KB 引用密度上升，R-12 预测①逐字）。 | 离线：`intelligence/tests/test_kb_search_coarse_pipe.py`（先红后绿）+ 长电夹具 `intelligence/tests/fixtures/v3-kbsearch-jcet-hits.json`；变异在已提交树上把管道退回 160 截断须红。live 由验收方部署后回填，执行方不得自行标 confirmed。本单与 V5 分开验收，不主张选段/答案质量。**2026-08-22 04:12 live 回填（验收方，不改判）**：钙钛矿探针 kb_search 送达 `evidence[].detail` 为正文级——曼恩斯特条目约 370 字（baseline 暴露+年报锚点）、大胜达条目约 600 字（证据链表），答案引用了其中事实（1401 万公告/GW 级订单/收入确认需验收），「送达含正文级信息」live 成立。但预注册「送达字符数数量级提升（与 V7 读数联动）」不可由现传感器证成：V7 `delivered_chars=len(observation)`（`agent_research.py:375`）量的是 observation 摘要串（本发 580 字/6 命中 ≈97 字/条，`display_excerpt` 兜底形状），V3 拓宽的是 `evidence[].detail` 通道——测量缝，不是管道失效。跟进：V7 传感器补 `evidence[].detail` 字符计数后再回填数量级读数。**2026-08-22 05:00 传感器落地后 live 读数**（`run_20260822_045215_303977`，钙钛矿同题）：`delivered_chars=565 / detail_chars=2279 / hit_count=6`——evidence 通道均值 380 字/条 > 旧 160 截断上限（截断确已拆除），总送达为 observation 串 4 倍、旧 800 上限 2.8 倍；同题冻结夹具（长电）800→4800（6 倍）。答案 KB 引用密度可见提升（捷佳伟创整线中试/曼恩斯特 GW 涂布订单/阿石创靶材过协鑫验证，均带证据层标注，R-12 预测①两半成立）。诚实边界：live 严格 10 倍未主张——live 绝对量受上游选段长度限制（frontmatter 噪声头，V5 范围）。另记部署事故：04:35 一次未带 `WORKBENCH_REPO_ROOT` 的部署把主树旧分支盖上生产（04:36/04:41 两发探针空计划即此，该窗口读数作废），04:47 用正确源恢复并复验；防呆闸随本行落地（deploy 脚本 cwd 所在树 ≠ 部署源且未显式指源即 fail closed） | `confirmed` |
| `R-20260821-16` | 索引卫生（索引层，形状 V）（`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md` §V4；`docs/verification/2026-08-21-inputside-index-hygiene.md`） | `HARNESS_FIX` | 重放：液冷 query 重放，top-5 无工件页。索引审计：工件页在索引条目中为 0（给出审计命令）。变异：排除规则删掉 → 重放红。TDD：索引构建入口对工件路径的排除钉，先红后绿。 | 离线：`intelligence/tests/test_kb_index_hygiene.py`（索引构建入口排除钉 + 液冷冻结夹具 + retrieve 接线）。索引审计命令与液冷重放命令见验证文档。变异：删 `_path_is_artifact` 排除规则 → 夹具重放红。执行方不得自行标 confirmed；live 由验收方复算。**2026-08-22 10:18 live 复算（验收方，生产指纹 `1816421c`）**：部署树 `~/.finance-runtime/finance-workspace-6320b3bcbf82`（health `loaded_tree_fingerprint`==`repo_tree_fingerprint`==`1816421c…`，快照标签滞后按指纹为准）的 `kb_index_hygiene.py`/`kb_rag.py` 与 gitea/main 逐字节一致；用部署树代码对生产索引跑 `audit_served_index`：physical_pages=10478 / physical_artifact_pages=24（按设计保留，本单不改物理索引）/ served_pages=10454 / **served_artifact_pages=0**；液冷 query（`液冷服务器 产业链 拆解`, k=5）经部署树 `kb_rag.retrieve` 重放：top-5=产业报告/英维克/申菱环境/工业富联/联创股份，artifact 0/5，与验证文档 §4 after 表逐行一致。重放+审计两腿判据均成立。注意「生产索引是否重建」是伪问题——V4 是消费侧过滤（§3 方案 A），物理索引按设计不重建 | `confirmed` |
| `R-20260821-17` | 收口 R2 spec §V5 选段质量（送达层，形状 IV；`docs/superpowers/specs/2026-08-21-inputside-closeout-r2-design.md`） | `HARNESS_FIX` | 长电案重放，4 条零信息 excerpt 变正文段；结构噪声段命中率读数下降（V7 供数）。TDD：合成页（正文+来源清单）选段落正文，先红后绿。 | 离线：`intelligence/tests/test_kb_selection_noise_filter.py`（先红后绿）+ 长电夹具 `v3-kbsearch-jcet-hits.json` + 钙钛矿冻结夹具 `v5-kbsearch-perovskite-hits.json`。变异：`filter_structural_noise` 恒等放行 → 红。过滤 fail-open，不加长度上限，不接 rerank。本单只主张选段质量，不主张送达量与答案质量（与 V3 分开验收，R-12 预测③逐字）。正文 `docs/verification/2026-08-22-inputside-selection-quality.md`。live 由验收方部署后回填，执行方不得自行标 confirmed。**2026-08-22 05:15 live 回填（验收方，部署 `d6755248` 后）**：钙钛矿同题探针（`probe-r17-live-0822` / `run_20260822_051501_196056`）kb_search 6 命中，observation 头全部正文前置（「最新市场逻辑…钙钛矿光伏组件」「证据与来源链｜纤纳光电 7683 万订单」），`tags:/section:` 标签汤头 **6/6→0/6**（对照 04:12 run1 同题同 `[:80]` 窗），遥测联动 `delivered=572/detail=1718/hit=6`——「结构噪声段命中率下降」腿 live 成立。**保持 pending 的原因**：判据另一腿「长电 4 条零信息 excerpt 变正文段」未兑现（执行方如实边界：那些检索窗内无正文可换，fail-open 保留），需「换 chunk / rerank」后续单收口，不是再加过滤规则。**2026-08-22 11:50 第二腿 live 兑现（验收方，V9a `R-20260822-01` 部署指纹 `160db3fa` 后，`probe-v9a-0822` / `run_20260822_115041_135880`，同题「长电科技怎么看」）**：原 4 条零信息 excerpt（长电逻辑跟踪/颀中/华天/莱宝）`reexcerpted=[T,·,·,T,T,T]` 全部换为各页正文段（#1 头=「长电科技作为国内封测龙头…」，不再是原始资料链接清单），cninfo baseline 指针页 `pointer_dropped=1` 由 `先进封装` 页回补。两腿均 live 成立 | `confirmed` |
| `R-20260821-18` | 收口 R2 spec §V6 实验单（R-10 下游；三候选谁优是可证伪命题） | `EVAL_ONLY` | 候选臂 model_finish 率较对照 +15pp 以上且答案长度不降 → 该候选进实施立项；否则记「未达标」并留读数。 | 每臂 n≥50（基线 79%，检出 15pp 变化的最小可用量）。分臂：对照（现状）+ 至少候选①成稿轮 reserve。影子配置分臂，实验期不得改生产默认参数。探针用户 `probe-v6-0821`（字段是 `user` 不是 `user_id`）。指标：model_finish 率、carried>0 率、修复窗依赖率、答案长度、judge_status 分布。正文 `docs/verification/2026-08-21-deadline-budget-ab.md`。受 `R-20260816-07` 约束：结论未出不得标 confirmed，不得抬 T。**2026-08-22 04:00 采满 50/50（题池 10×5 同题配对，分段交替）**：model_finish 44%→90%（+46.0pp ✅ 远超门槛），但答案中位长度 752.5→705.5（−6.2% ❌ 长度守门触发）——合取判据第二支不成立，按预注册记未达标，候选①不进实施立项，生产参数未动。副读数：修复窗依赖 64%→42%，judge passed 4→13，carried 案例 28→5。事后探索（不参与判定）：配对中位差 −55 字、6/10 题变短，变短最狠的题恰是对照完稿率最低的题，提示对照长答案部分来自修复窗改写膨胀；若要分辨水分/内容需按判官通过率加权的新判据=新预注册另立行。执行事故与修复（sidecar 健康窗 90→300s，`60eb4bbd`）见正文 §5 | `未达标` |
| `R-20260821-19` | 收口 R2 spec §V8；设计 `docs/superpowers/specs/2026-08-22-v8-semantic-deletion-rights-design.md` | `HARNESS_FIX` | 部署后：① 必需块内仅被 LLM 语义质量否决的句子留在公开稿并带 harness 存疑标，批评在「输出质检」，不得再被 `_repair` 整句删除；② `numeric_unsupported` 与表外 E 号（确定性闸）句仍被删除；③ `test_episode_semantic_verifier` 里 monotonic rejudge / 调用次数钉在机械扳机下保持原断言绿。预测失败形状：语义句从公开稿消失，或机械假数 / 表外引用留在公开稿，或再审次数钉在未改 `_repair` 的前提下变红。 | 离线 TDD：新文件（建议 `intelligence/tests/test_v8_semantic_deletion_rights.py`）先红后绿，覆盖设计 §7.1 ①–⑥。变异 §7.2 三条，击杀数写入交付。C 簇夹具改为机械扳机后跑原断言。W1 `test_ceiling_required_block_degrade.py` 回归。禁止改 `episode_semantic_verifier._repair` 函数体（diff 门或审查清单）。live：验收方用 `probe-v8-<mmdd>`，`judge_status=repaired` 的语义样本公开稿含原句 + 存疑标；机械对照句不在稿内。执行方不得自行标 confirmed。单发不得结案。**2026-08-22 11:50 live 首样本（验收方，部署指纹 `160db3fa`，`probe-v8-0822` / `run_20260822_115024_661457`，题「液冷服务器产业链怎么看」）**：`judge_status=repaired`，3 条语义 issue（因果无据/发明环节/外部原因偷渡）对应句 **3/3 留稿并带【质检存疑】**，批评在「输出质检」节，`repair_collapsed_to_stub=false`、`repair_withheld=false`；本轮无机械违规自然样本，「机械对照句不在稿内」半腿待样本。按行内「单发不得结案」保持 pending，续采自然样本 | `pending` |
| `R-20260822-01` | 本 spec §7.1 V9a 本仓换窗（形状 IV 同页错段 / 指针页） | `HARNESS_FIX` | 长电冻结夹具（页侧车，不重跑 live RAG）重放：#1 `长电科技_最新逻辑跟踪` 的 excerpt/llm_evidence 头为同页正文（一句话或市场逻辑），不再是 `原始资料链接` 清单；#3 baseline pointer 被丢弃或不再以 `raw/cninfo-baseline/` 路径行当头；#4–6 不再是纯 wikilink 堆（允许改为各该页自己的正文，不主张长电相关性）。TDD 先红后绿。变异：重摘录恒等 → #1 红。live：验收方探针抽样目标页为正文段；V7 `delivered_chars`/`detail_chars`/`hit_count` 只作联动读数，不得单独结案。p95 重摘录增量 <100ms，且 remaining<15s 时 `effective_mode` 仍为 bm25。 | 离线：新夹具 + `test_kb_search_coarse_pipe` / V5 过滤钉不回退。live：`probe-v9a-<mmdd>`，执行方不得 confirmed。与 V9b 分开验收。**2026-08-22 11:50 live（验收方，部署指纹 `160db3fa`，634 模块，ready 全绿）**：探针 `probe-v9a-0822` / `run_20260822_115041_135880`，同题「长电科技怎么看」。四条判据逐条：①目标页换正文段——#1 excerpt 头=「长电科技作为国内封测龙头，正站在AI算力驱动的先进封装爆发周期起点…」，颀中/华天/莱宝各为本页「一句话」正文（不主张长电相关性）；②指针页——`pointer_dropped=1`，`先进封装` 页回补进 6 命中；③遥测——`reexcerpted=[T,F,F,T,T,T]`（#2/#3 本就是正文，如实 False），非 KB 证据字段 None，联动读数 `delivered=554/detail=2713/hit=6`；④p95 与降档不变量**离线腿**成立（读 6 页 0.44ms + 重摘录 1.06ms ≪ 100ms；`test_remaining_under_15s_stays_bm25` 钉住 + `select_mode_for_remaining` 零改动经验收方 diff 复算），live 未逐调用计时。正文与逐条表见 `docs/verification/2026-08-22-v9a-kb-window-reexcerpt.md` §live 回填 | `confirmed` |
| `R-20260822-02` | 本 spec §7.2 V9b 排序（形状 IV 邻页链接堆占槽） | `HARNESS_FIX` | 长电同 query 的最终 top-k 中，`via_neighbor` 且代表段为「相关实体/相关概念」的颀中/华天/莱宝不再占 3 个槽（降至 ≤1 或 0）。不主张 #1 窗变成正文（那是 `-01`）。若开启 `mode=rerank`：remaining 4s 与 11.955s 零次 cross-encoder 调用，20s 才允许；不得新增第二套降档函数。变异：rerank 移出 `_DENSE_MODES` 或 4s 仍打 rerank → 红。 | 离线：冻结候选页列表。live：`probe-v9b-<mmdd>` 对页集合，与 `-01` 的窗内容分表记录。**2026-08-22 离线（V9b 执行方，不改 outcome）**：启发式 B5（不开 rerank）。夹具 `intelligence/tests/fixtures/v9b-jcet-candidates.json` 10 候选 → 最终 k=6 中结构邻页 3→0；`allocate_topk_slots` 0.0020ms。红 `20260822T042901Z-d5cb4e2f`（恒等桩 7 failed）；变异击杀 2/2（恒等排序器 `20260822T042954Z` / 门控清空 `20260822T043037Z`，映射见验证文档 §4）。正文 `docs/verification/2026-08-22-v9b-topk-rerank.md`。live 由验收方 `probe-v9b-<mmdd>` 回填，执行方不得 confirmed。**2026-08-22 13:30 live（验收方，生产指纹 `fb7a0d5d`）**：检索层重放（部署树 `kb_rag.retrieve` × 生产索引，冻结 query，k=6，同 R-16 法）：via_neighbor∧结构代表段∧颀中/华天/莱宝占槽 **0**（允许 ≤1 或 0）；`structural_neighbor_demoted=1` 机制开火；`pointer_dropped=1`，6 槽全正文窗。入径注记：三页本轮为**直接命中**（V9a 丢指针页改变候选组成），正是验证文档 §7 边界 #3 预登记情形，度量对象计数为 0、失败形状（链接堆占槽）live 不存在。episode 探针 `probe-v9b-0822`/`run_20260822_132015_150481` 本轮 LLM 计划未调 kb_search，只留档不作证据。详见验证文档 §10 | `confirmed` |
| `R-20260822-04` | R3 spec §B2 换题泛化电池（黑名单覆盖审计 + held-out 探针电池） | `EVAL_ONLY` | 审计腿（可证伪预测）：全库节标题审计将发现至少 1 个出现 ≥20 页、语义上属结构节、但不在 `STRUCTURAL_SECTIONS` 的节标题变体；若未发现，记 refuted 并说明黑名单当前覆盖充分。电池腿：首轮为基线采集，held-out 题池的 reexcerpted 率/正文头率/指针丢弃分布落入报告，不预设阈值不判 pass/fail。 | 离线：审计脚本冻结语料夹具单测；电池脚本 mock HTTP 单测、禁打 8792。真跑：审计读数执行方可离线产出（写验证文档）；电池首轮归验收方（`probe-battery-<mmdd>`）。盲区清单若非空 → 黑名单扩展另立后续单，届时电池做前后对照。执行方不得自行标 confirmed/refuted。**2026-08-22 13:49 live（验收方，生产指纹 `fb7a0d5d`）**：审计腿——验收方独立复算盲区 **13 条** ≥20 页（来源 378 居首，Top 与执行方读数逐条一致），预测「至少 1 个」实测 13 → 成立。电池腿——`probe-battery-0822` 9/9 completed：`body_header_rate=1.0`（8/8 可判题，换题零结构头）、`reexcerpted_rate=0.267`、`pointer_dropped` 全 0、KB 参与 5/9 题（episode 工具选择随机）、h7 无可判 KB 证据如实记 None。基线落 `docs/verification/2026-08-22-v10-generalization-battery.md` §8。黑名单扩展后续单用同题池前后对照 | `confirmed` |
| `R-20260822-03` | 本 spec §5.1 / §7.3 物理重切（跨仓，需用户裁决；spec 预留号自带完整行，台账行 2026-08-27 由 crosswalk 存量清理补（工单 §P1-b：spec 引号台账无行，实施已合 live 状态无处可查）） | `DATA_CONTRACT_FIX` | 用户批准并重建后：hybrid 重放长电 query，六页 best_chunk 的 `section` 不再落入 `原始资料链接` / `相关实体` / `Raw / Manifest Trace`；`chunk_profile` 变更导致旧索引 stale（fail-closed 提示重建，不静默混用）。未裁决前本行不得开工、不得用消费侧绿测冒充本行。 | KB 仓重建收据 + 本仓夹具重放（spec `docs/superpowers/specs/2026-08-22-kb-chunk-rerank-design.md` §7.3 逐字）。无用户裁决 → 保持 pending。 | `pending` |
| `R-20260822-05` | spec `docs/superpowers/specs/2026-08-22-v11-judge-guided-retrieval-design.md`（V11 判官引导检索；spec 约定「实施时才立案」，本行为 crosswalk 占位，判据以 spec §9 那行为准，实施时逐字替换本行；台账行 2026-08-27 由 crosswalk 存量清理补（工单 §P1-b：spec 引号台账无行，实施已合 live 状态无处可查）） | `HARNESS_FIX` | 未实施：spec §9 给出可逐字抄的判据行，实施 PR 落地时替换本占位行 | 实施前不验；本行存在只为「spec 引号可追溯」，不代表已开工 | `pending` |
| `R-20260824-08` | harness-ceiling D3 / 空池 fallback（`docs/superpowers/specs/2026-08-24-harness-ceiling-and-8796-decouple-followup.md` §7；来源非标准四阶段分诊） | `HARNESS_FIX` | 某个 `required_output` 观察池预取空表且首轮 `finance_query` `sector_daily` 0 行时，Episode 内恰好一次换同窗成交额前排；`tool_request` 带 `fallback_query=true` + 原查询 + `as_of`。历史题 `time_range.end` = 问句日，不得打到库尖。与 `plan_issue_backfill` / 修复轮互斥。第二次仍空则停，诚实报缺。公开稿不因做过 fallback 变严（本单不改发布门 / `_gap_answer`）。`market_watch` 不触发。 | 离线：`intelligence/tests/test_empty_pool_fallback.py`。正控一次、负控零次、as-of 钳制。互斥两头都验：`propose` 见到 backfill 计划则不 fallback；`plan_issue_backfill(..., events=outcome.events)` 见到 `fallback_query` 则不再派 `finance_query`/`market_data`（`financial_data` 保留）。装配钉：`_issue_backfill_plan` 吃 `outcome.events`，调用点含 `events=outcome.events`。本单不主张 Engine B C3 闸已罩住 episode 成交额前排。live 单发不得 confirmed | `pending` |

> `R-20260821-02` / `-04` 的 **live 臂 2026-08-21 尝试过，记 `not_run`**（不是 `refuted`）：
> 手搭 worktree sidecar 与生产环境不等价，同一道反过拟合题（钙钛矿电池→2026-08-18）
> 在**代码等于 `gitea/main` 的隔离臂**上同样失败于 `scenario_tree` 预检，故失败不可归因于本单四刀。
> 四臂对照与环境爬坑记录见 `docs/verification/2026-08-21-slot-fill-live-attempt.md`。
> 离线侧有效读数：`observation_value` 对 08-18 直接给出 `0.15 / 775.76`，与分析师第一刀逐字一致。
>
> **基线侧样本 +1（2026-08-21 午后，生产 8792@`dfc25221`，非本单代码）**：
> `run_20260821_152044_472523`（CXO概念发酵题，Cursor 直调组件对照臂 + trace diff 全程见主检出树
> `docs/verification/2026-08-21-tracediff-cxo-ceiling.md`）——judge `repaired` 把 1259 字草稿删至 437，
> 被删数字（**工具行**来源，非预取行）逐条对库全真。该 run 同时证明投影 C1–C4（`82a9fac6`）已在 main live
> （`projection_ordinal_mismatch_count=0`），残余机制为投影 spec §4/§8 留下的 A3 写手 binding 缺口
> （`evidence_alias_offset=29`，未绑卡不送判官→真引用被判不存在）。对 `-04` 记 **adjacent shape**，
> 不冒充 exact（exact 口径=预取行数字）；族内 n=2，不结案。`-02` 验收口径的「有收据的工具行」半边
> 由第 10 刀 `f0ad6cfb` 落地（离线绿；live 臂依旧待能进 episode 的 sidecar）。
>
> **`-04` 修后侧样本 +2（2026-08-21 17:00，生产 8792@`6320b3bc`，#288+#289 已合已部署）**：
> `run_20260821_164659_624916`（CXO 同题 B 臂）与 `run_20260821_165210_889002`（减肥药新题）——
> 两 run 判官均 `repaired` 且 `rejected_claim_indexes=[]`（**零删句**），槽内/工具行数字全量存活；
> 判官产出转向措辞级真实批评（「持续缩量」越界、覆盖起点 7-22 vs 注册表 7-27），以质检段呈现。
> 预测形状「槽位落地后判官对槽内数字无删除权、真数字留存率上升」成立中；
> 修后同形样本 2/3，**仍差 1 个才可 `confirmed`**，反向证伪条件未触发（无槽内数字被删案例）。
| `R-20260823-SPTTECH-04` | 2026-08-23 SPT 科技三臂 M2 R-004 | `EVAL_ONLY` | 同 revision 只 toggle `predicate.reading-baseline`，冻结 tool returns 各回放至少 10 次；组件开启时多日科技/MA20 query 命中率稳定提高，若 timeout 率无显著差异，不得把单次 timeout 归组件 | 保存 active component hash、query args、model latency、timeout grant 与业务状态；每臂 n≥10 并报告置信区间 | `pending` |

`outcome` 只能是 `pending` / `confirmed` / `refuted`。**部分验证不要写 `confirmed`。**

> `R-20260820-01` 与 `R-20260817-01` 是**同一失败家族的两条分支，不要合并计数**：
> 后者限定 `run()` 的 `complete()` 已返回 FINAL_JSON 后 `_consume_root_seconds` 失败
> （已由 `_carry_just_written_finish` 修掉）；前者是 `resume()` 一侧的对称洞——
> 修复轮七条停机路径当时一律结转 `previous.draft`，从不调那个函数。
> `R-20260817-01` 仍 `pending`，本行不代它结案。

### 2026-08-16 off 45 槽分型 + judge 全窗案：开工回填

此表冻结在本轮 M1 归因之前。材料 = 长尾 off 45 + G01–G05；对齐键 `slot`+`run_id`。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-05` | 三元组已分型：空稿跳过 judge 10 槽；有稿+transient 22 槽；judge 完成 3；无 episode 9。L01 空稿与 L05 候选草稿不再用 151–159s 合并 | `confirmed` | 从 Open 移到 Closed |
| `R-20260816-01` | 773b3d7e 窗内产物仍无首轮 `timeout_asked`。8795=`21dbf6c1` 已起，identity 未收齐 | `pending` | 保持 Open |

### 2026-08-16 identity 臂收齐：回填

8795 `21dbf6c1`；user `outlook-r03-0816`；L01×3 + L03×1。不占 8792。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-01` | 四槽合成/修复 `timeout_asked` 均在。空稿超时是 L01 r2 非 finalize asked=8.49，不是预测要的 finalize 空稿。68s finalize 空稿 0/3 | `pending` | 保持 Open。字段在 ≠ 形状结案 |
| `R-20260816-06` | L01 r3 / L03 已是 draft>0 + transient；`semantic_verifier` 仍无 judge `timeout_asked` / `exc_class` | `pending` | 保持 Open。#84 覆盖不够，须先补 judge 埋点 |
| `R-20260816-02` | 仍未动 T/30 | `pending` | 保持 Open |
| `R-20260816-03` | identity 不是单变量三臂 | `pending` | 保持 Open |
| `R-20260816-02` | 本轮书面豁免调 T/30，条件句「若动预算」未触发 | `pending` | 保持 Open；不写 confirmed/refuted |
| `R-20260816-03` | 45 槽否证 H2/H3 作充分条件；单变量三臂未跑 | `pending` | 保持 Open |
| `R-20260815-04` / `R-20260804-10` | 字段/headless 路径未触及 | `pending` | 保持 Open |

### 2026-08-16 outlook 核验预算回归：开工回填

此表冻结在本轮 M1 归因之前。被审 runtime = 8792 `773b3d7e`；主样本 `run_20260816_131941_597875`。#84 合入后代码在 `gitea/main` `21dbf6c1`，**尚未切 8792**。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-04` | 又一份空 draft：`outcome.draft=""`，`draft_source` 仍为 `None`。区分信号在 `gaps=['LLM 调用失败（TimeoutError）']` 与 `stop_reason=repair_model_unavailable` | `pending` | 保持 Open。字段未落地，不得因「这次能从 gaps 看出来」写 confirmed |
| `R-20260815-24` / `25` / `26` | 本 run 不是 marker-loss / tool_exception / S10 夹具样本 | `pending` | 保持 Open；本 run 不能回填 |
| `R-20260804-10` | 本轮是 workbench continuous episode，不是 headless handoff | `pending` | 保持 Open |
| `R-20260816-04` | L01 `answer.md` 原文过 `evaluate_marker_coverage` → `warnings=[]`、`marker_coverage=complete`。单测 `test_l01_gap_template_does_not_trigger_uncheckable_judgment_empty` 随 #84 合入 | `confirmed` | 从 Open 移到 Closed。改探测器另开观测台 |
| `R-20260816-01` | #84 离线单测绿；8792 仍是 `773b3d7e`，没有带 `timeout_asked` 的同形 live run | `pending` | 保持 Open。代码落地 ≠ 预测兑现 |

### 2026-08-15 Round 6 批 #3 回填

此表冻结在本轮新归因之前。8792 health `runtime.source_revision=fdb231148c0e91cd56f7f5d48b5252df80dfafb9`，`source_dirty=false`，`code_matches_repo=true`，`loaded_code_root=.../finance-workspace-fdb231148c0e/intelligence`，pid 70403。批 #3 `20260815T1005Z-r5-clean-baseline-3.json` `sha256=e475f3c889946b2ef87507ca303effa5bf9a1ca153821009f60e6b4edaf1ebf0`。本轨不写 A 的 R-23/R-24/R-25 outcome。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-10` | B 组 N=3（只 `evidence_bound>0`）：B1 2/3、B2 3/3、B3 2/3、B4 2/3、B5 2/3、B6 0/3（三批澄清）、B7 2/3、B8 2/3。三批 sha256=`b712bd2e…d8d350` / `51e61710…304ef4` / `e475f3c8…f1ebf0`。并行 efh 不结案。B4 产物 timeout/eb=0，仓外 episode 已交付——不改口径 | `confirmed` | 从 Open 移到 Closed。单批失败名单仍可打回 |
| `R-20260815-09` | 21/21 验收挂上的 episode 末条 finish 有 `rejection_code`/`rejection_reason`；20 题 `none`/空。B8 末条 `invalid_repair_finish` `rejection_code=no_substantive_answer` `rejection_reason=required output lacks substantive answer: scenario_range`。本轮 handoff 判据=字段在场性 + 有拒收时非空 | `confirmed` | 从 Open 移到 Closed。不定 B8 的 L0 |
| `R-20260815-12` | live：`preflight_detail` 含 `data_probe: finance_query=ok`，`data_probe_ok=true`，`window_contamination=null`（成功不盖戳） | `confirmed` | 已在 Closed；live 臂保持，不重开 |
| `R-20260815-23` | 本轨道只出数：15 条修复路径、14 条验收 eb>0；`invalid_action` 零条 unknown/truncated evidence hash。B8 是 `no_substantive_answer` | `pending` | 执行方正确不写 A 行。检阅方独立复核后收口，见下表 |
| `R-20260815-25` | 17 条 `tool_error` 均为 timeout/budget；零 `tool_exception`。数据层健康 | `pending` | 保持 Open；unobserved，不改口、不改 A 的行 |
| `R-20260815-24` | 13 题 `efh ≠ eb`；B3 本批 gap=`['direct_assessment']` 但 eb=10，不是 B3#2 零交付 | `pending` | 保持 Open；未实现，不开 L0 |
| `R-20260804-10` / `R-20260815-03` / `-04` | 本轮无新证据 | `pending` | 保持 Open |

### 2026-08-15 Round 6 检阅方回填 R-23

检阅方独立重扫批 #3 全部验收 run_id + B4 仓外 episode，不改执行方报告正文。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-23` | 3 条 `invalid_action` 均不含 unknown/truncated evidence hash（A5/B7=`bad_status`，B8=`no_substantive_answer`）。验收挂上的修复路径 14/15 eb>0。B8 是另一拒收码，不构成誊抄拒收再现。同形窗口存在，不是 unobserved | `confirmed` | 从 Open 移到 Closed。live 臂在 `fdb23114` / 批 #3 `sha256=e475f3c8…f1ebf0` |

### 2026-08-15 Round 5 收口回填

此表冻结在 Round 5 新归因之前。8792 health `runtime.source_revision=cb09f895734a65a38ae23f04d940f18ece2959fd`，`source_dirty=false`，`code_matches_repo=true`，`loaded_code_root=.../finance-workspace-cb09f895734a/intelligence`。无 `/tmp/finance-8792-live.lock`。无批 #3。批 #2 仍是 R-23 的 before。轨道 A 不写 B 轨行 / R-10。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-23` | 8792 仍 `cb09f895`；无 `*baseline-3*` / 本轮 r5 批。批 #2 before：B5#2 `run_20260815_112319_467917` seq 23、C7#2 `run_20260815_113732_480025` seq 17，`invalid_action.reason` 均为 truncated evidence hash；两题 `retrieved_unsynthesized` eb=0 | `pending` | 保持 Open。不得因 before 证据加长而写 confirmed / refuted。收口等用户部署 + 批 #3；若 A 组仍被数据层污染，只看 B5/C7 同形 |
| `R-20260815-21` / `-22` | 本轮无新 canary / slips 证据 | `confirmed` | 已在 Closed；不重开 |
| `R-20260804-10` | 本轮无 headless handoff 新证据 | `pending` | 保持 Open；本轨道不写该行 |
| `R-20260815-09` / `-10` / `-03` / `-04` | 本轮不取 B 缝证据 | `pending` | 保持 Open；本轨道不写这些行 |

### 2026-08-15 Round 4 收口回填

此表冻结在 Round 4 新归因之前。干净基线批在 B 分支 `fix/b-group-gap-shape-split`，
`sha256=b712bd2ee10fb431dba937416fb5882c6984ac65bb5421b5472f71c7ead8d350`，
`generated_at=20260814T200212Z`，`preflight_detail=revision=cb09f895`。
轨道 A 独立重扫 run 目录，不改 B 轨行 / R-10。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-21` | 预注册 C1 零违反：`caveat_slips>0` 恰 9 题（A6=2 / A8=2 / A10=1 / B2=3 / B3=3 / B4=2 / B5=1 / C7=1 / C9=1），有哈希格全部 `fulfilled` 且 eb>0。C2 零违反：6 个真缺口格（A4 `evidence_boundary`；C6 `direct_answer`+`evidence_boundary`；C9 `chain_mapping`；C10-t3 `direct_answer`+`evidence_boundary`）全部 `missing`。C3 不适用（有命中）。混合形正样本 C9：slips=1 与真缺口 missing 同 turn。条件靶收窄谓词（曾 `draft_chars>0` 其后 `carried_draft_chars=0`）0 命中，不开 M1 | `confirmed` | 从 Open 移到 Closed。预注册原文一字未改；收口见 `docs/verification/2026-08-15-trka-r3-r21-canary.md` §Post-batch closure。C10-t3 为 `bound_but_dropped`（两格 no_hash 真缺口），不移动 C1/C2 |
| `R-20260804-10` | 本轮无 headless handoff 新证据 | `pending` | 保持 Open；本轨道不写该行 |
| `R-20260815-07` / `-03` / `-04` | 本轮不取 B 缝证据 | `pending` | 保持 Open；本轨道不写这些行 |

### 2026-08-15 Round 1 开工前回填

此表冻结在 Round 1 新归因之前。归一化器代码 revision `cd47d257`，
`intelligence/eval/normalize_harness_trace.py` 自 `5b456532` 以来未被改动。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260804-02` | **首次拿到真 Codex rollout JSONL 并实跑归一化器**：输入 `~/.codex/archived_sessions/rollout-2026-08-03T20-18-55-019fc790….jsonl`（session_meta 的 cwd 为本仓，`sha256=62385ee5…b316a7`，264 条记录）。`--kind codex-rollout`、`--kind auto`（自动判定结果亦为 `codex-rollout`）、`--kind codex-exec` 三种传法**结果一致：264/264 `unmapped`，step 分布 `{'unmapped': 264}`，零个 `observe`、零个 `tool`**。预测要求的「真 rollout 中 `function_call_output` 归入 `observe`」在真产物上不成立 | `refuted` | 从 Open 移到 Closed。**根因是形状不匹配，不是格式漂移**：`_codex_mapping`（`normalize_harness_trace.py:279-298`）只读顶层 `type` 与 `record["item"]["type"]`，而真 rollout 的语义类型在 `record["payload"]["type"]`，顶层 `type` 恒为信封名（`response_item`/`event_msg`/`turn_context`/`world_state`/`session_meta`）。抽查 2026-06-02 / 07-16 / 08-03 / 08-14 四份真 rollout，**`item` 键出现次数均为 0**（跨 2.5 个月无一例），故该 mapper 从未在真产物上工作过；08-04c 那次「synthetic 已证明」用的夹具是 `{"type":"item.completed","item":{…}}`（`test_normalize_harness_trace.py:180`）与类型在顶层的 `{"type":"function_call_output"}`（同文件:350）两种形状，**均非真产物形状**。**比较层护栏确实生效**（不是静默发绿）：与 `a-control.json` 双输入比较返回 `unmapped_counts.left=264`、`pre_divergence_equivalence=not_established`、三条 `interpretation_caveats`（含「one side has no mapped semantic events: no comparison is possible」），故影响面是**跨 harness 比较拿不到信号**，不是拿到错信号。另注：单输入产物同时报 `unpaired_tool_requests=0`，正是 [trace-profile.md](trace-profile.md) §2 警告过的「健康零」——此处 0 的成因是没有任何事件进入配对词表 |
| `R-20260804-10` | 本轮无新证据。08-04 之后唯一触及 `intelligence/runtime/headless_tool_gateway.py` 的提交是 `b6900f47`（15 个 loop 模块搬进 `intelligence/runtime/` 的纯位移），故现存 `handoff_window`（gateway:588）属 Task 1/2 存量，非本轮进展。Task 3-6 四项在生产代码中穷尽搜索均为空：`intelligence/{runtime,services}/` 下 `derived_context`/`派生`、`late_result`/`迟到`/`stale_result`、`slow_tool` 零命中；`watchdog` 仅命中 `conversation_orchestrator` 的 `workbench-ask-watchdog`（Ask 根看门狗，与 R-10 的 headless watchdog 非同一物）。`docs/verification/` 中 08-05 起仅新增 08-09 的 seam-ladder / market-routing 三份，均非 R-10 主题 | `pending` | 保持 Open。预注册条件（离线主门全过 **且** 一次瑞华泰 canary）二者仍都未做到，**不得因 Task 1/2 已完成而写 `confirmed`**。口径校正：`docs/handoffs/2026-08-04d-worklist-freeze-r10-then-tool-surface.md` §0 原文写的是 Task 3-6「**取消**」，本账本此前记作「冻结」；两种记法指向同一事实（未执行），恢复条件以 08-04d §0 为准 |

### 2026-08-04d R-10 冻结（Task 3-6 未执行）

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260804-10` | Task 1/2 已完成，另补两个收尾洞：秒数结算的 check-then-act race 下沉到 ledger 锁内（新增 `settle_seconds()`），`root_budget_overdraft` 接进 `normalize_harness_trace` 映射表（`observe`/`control`）。离线读数：gateway 34 passed、research_contract 2 passed、normalize 30 passed、codex_runtime 28 passed+1 skipped、ruff pass；两条新测试均通过变异测试 | `pending` | **已冻结，Task 3-6 未执行**：未做 watchdog / 派生 context / 迟到隔离，未跑离线全量 gate，未跑 live canary。预注册条件要求离线主门全过**且**一次瑞华泰 canary，二者都没做到，因此不得写 `confirmed`。冻结原因与恢复条件见 `docs/handoffs/2026-08-04d-worklist-freeze-r10-then-tool-surface.md` §0；主线已切到工具面盘点 |

### 2026-08-04c R-10 观测前置补齐

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260804-02` | synthetic Codex rollout 已证明 `function_call_output` 进入 `observe` 且悬空调用计数为 1；仍没有该预测要求的真 rollout JSONL | `pending` | 保持 Open；synthetic 只锁 normalizer 行为，不替代真实产物结案 |
| `R-20260804-10` | gateway 的 request/result/error 已共享 32-hex request id；normalized artifact 保留独立 `correlation_id`，mismatched id 不再互相消费，Workbench N/A 显式为 `null` | `pending` | 只确认离线主门所需仪器已具备；尚未实现或运行 slow-tool handoff，不提前确认根因 |

### 2026-08-04b L7 finalization：T3 回填

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260804-02` | 本轮仍只有 `runtime-benchmark`，没有真 Codex rollout JSONL | `pending` | 保持 Open |
| `R-20260804-09` | T3 瑞华泰为事件级 `headless_protocol_rejected` / 135.555s，5 个 tool request 只有 4 个 mailbox exchange，`finalization=0`；最后一个 `evidence_search` 没有 result/error，随后为 `headless_command_failed` | `refuted` | 从 Open 移到 Closed；PRIMARY 前移到 in-flight tool 阻塞交接，另开 `R-20260804-10`，不调预算 |

> T2 的 instruction 传输与事件顺序已由真实 wrapper seam 单测证明，但 live 的失败路径
> 到不了 result/rejection activation point。按预注册规则，这不是“部分成功”或 pending。

### 2026-08-04b L7 finalization：开工前回填

此表在新增 finalization 仪器、修改 headless 运行路径或启动新 live run **之前**冻结。

| ID | 开工前新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260804-02` | 本轮仍无真 Codex rollout JSONL；预算 artifact 是 `runtime-benchmark`，不能替代 `function_call_output` 的原生投影证据 | `pending` | 保持 Open，不用近似事件结案 |
| `R-20260804-09` | 尚无带 `finalization` 与事件时间戳的新 rollout；冻结的 `c_long_capped` 瑞华泰事件序列停在 `tool_request(evidence_search)`，没有 `research_stage_closed` / `tool_budget_exhausted` rejection | `pending` | 先做 T1 仪器并复跑同一 profile；T2 必须以真实 activation path 为准，不能把 rejection-only 误写成已验证修复 |

> 开工前额外约束：`c_long_capped` 的 `gateway_floor_ratio=0.0`，瑞华泰只消耗
> 5/6 次工具额度且最后一次调用没有返回。仅给 rejection 增加 instruction 在该 case
> 上不会激活；这是 T2 的设计门，不是 R-09 的提前结案。

### 2026-08-04 预算标定：开工前回填

此表冻结在本轮新 live run 与新归因之前，防止后续结论倒灌成“开工前已知”。

| ID | 开工前新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260804-02` | 本轮暂无新的真 rollout JSONL | `pending` | 保持 Open；只有真 `function_call_output` 被归一化为 `observe` 才结案 |
| `R-20260804-04` | 本轮暂无新的真 Codex headless run；仍只有既有单元实测、合成端到端实测与中间跳的 code reading | `pending` | 先跑 `a_control` 五题，再按 runtime issues 与 protocol issues 的实际值结案 |
| `R-20260804-07` | 本轮尚未产出新的标准四阶段 triage 报告 | `pending` | 完成预算 M2 分诊后再检查 `first_bad_step` 是否与本仓 L1 空间直接对齐 |

> **`R-20260804-04` 已结案。** `b_floor_ablation` 的真 Codex headless run 自然产生
> 两个 `headless_timeout`；两题的 `runtime_result.payload.issues` 均为
> `["headless_timeout"]`，而 `protocol_issues` 均为 `[]`。此前缺失的 runtime stdout
> → usage → benchmark projection 中间跳已有实测，不再只靠 code reading。

### 2026-08-15 Round 5 轨道 B 回填

此表冻结在 Round 5 新归因之前。不改 R-23 / R-21。R-10 仍要 N=3 live 批才结案。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260815-12` | 离线：探针失败 preflight 仍 True 且 `preflight_detail` 含 `data_probe: finance_query=tool_exception`；`cmd_run` 产物顶层 `window_contamination=finance_query`、`data_probe_ok=false`；未探测不得盖污染戳。B3@批#2 夹具 `episode_fulfilled_hashed=2` 与冻结 `evidence_bound=0` 并存且不相等 | `confirmed` | 从 Open 移到 Closed。失败处置写死 `DATA_PROBE_ON_FAILURE=run_and_flag`。live 批 #3 若探针失败而无顶层标注，按原文 refuted |
| `R-20260815-10` | 本轮仪器已齐；N 仍为 2（缺批 #3） | `pending` | 保持 Open；不改判据 |
| `R-20260815-09` | 本轮不读未部署的 finish 拒收字段 | `pending` | 保持 Open；等新快照批 #3 |
| `R-20260815-23` | 本轨道只出数、不写该行 | `pending` | 保持 Open；不改 A 的行 |
| `R-20260804-10` / `R-20260804-02` / `-03` / `-04` | 本轮无新证据 | `pending` | 保持 Open |

### 2026-08-16 R-06 T2/T3 回填

8795 `02fa203e`；user `judge-r06-0816`；分层 12 槽。不占 8792。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-06` | 11 槽 draft>0 transient 带 `timeout_asked=5.208` + `exc_class=TimeoutError` + remaining 170–254；0 槽 asked≥20 / 5xx。asked≤12 且墙钟≈asked → H9 | `confirmed` | 从 Open 移到 Closed。收据 `docs/verification/2026-08-16-judge-transient-r06.md` |
| `R-20260816-02` | 未动 T/30 | `pending` | 保持 Open |
| `R-20260816-07` | 处置 PR 只地板 standard judge 窗，不含 T/30/档位上调 | `pending` | 保持 Open（绊线，合入后看 diff） |
| `R-20260816-08` / `-09` / `-01` | G 组只作旁证；未动 reserve；非空稿 finalize | `pending` | 保持 Open |

### 2026-08-16 十题窗 #94 合入：回填

8792=`6cd0756e`；修前臂 8794=`437cd5e9`（已停）。收据 `docs/verification/2026-08-16-outlook-ten-question-ab.md`。F01 勘误后护栏 PARTIAL 3/4。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-11` | 开行。post 臂 eb 0.947→0.772（−17.5pp）；L01 3 槽 −33.3pp。判断槽 hashes=0、旁槽仍 bound。不复用 R-06 | `pending` | 新开 Open。分诊交接 `docs/handoffs/2026-08-16-outlook-eb-judgment-slot.md` |
| `R-20260816-10` | 本窗 post 唯一 transient asked=12.5（重试半档），不是 8795 同形 12 槽重放；无首轮 asked 独立戳 | `pending` | 保持 Open。不得用 L01 r2 偷结 |
| `R-20260816-06` | 已 Closed。本窗 H9 残留不重开 | `confirmed` | 不回写 |
| `R-20260816-07` | #94 无 T/30/档位 | `pending` | 保持 Open（绊线仍看自称预算修复的 PR） |

### 2026-08-16 R-11 M2 回填

此表冻结在判断槽 0-hash M2 归因之后。材料 = 冻结三对 + 官方 compare caveat。对齐键 `slot`+`run_id`。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-11` | PRIMARY=`HARNESS/configure/task-instruction-category-non-compliance`：#72 判断槽 `model_reasoning` × `_bindings_rate` 全槽要哈希。H1（并进 R-06 / 窗地板）REJECTED：三对 judge 已跑完，L03=`passed`，asked/exc 皆 null | `confirmed` | 从 Open 移到 Closed。报告 `docs/verification/2026-08-16-outlook-eb-judgment-slot.md`。预测原文未改 |
| `R-20260816-15` | 开行。分层 eb / 把 `model_reasoning` 移出分母 | `pending` | 新开 Open。不改 #72 / T / 30 / 档位 |
| `R-20260816-10` | 仍不是 8795 同形 12 槽；L01 r2 旁证不得偷结 | `pending` | 保持 Open |
| `R-20260816-07` | 本 PR 无 T/30/档位 | `pending` | 保持 Open |
| `R-20260816-13` / `-14` | 三对工具已返回；0-hash 在 FINAL_JSON。不代结饿死案 | `pending` | 保持 Open |
| `R-20260816-01` | 见到合成 `asked=16.11` TimeoutError，但 repair 有正文，不是空稿终态 | `pending` | 保持 Open |

### 2026-08-16 R-13 T1 合入 / T2 受阻：回填

8795=`16f2cd47` dirty=false（pid 53843，`--port 8795`）；8792 全程 `6cd0756e` 未切。
收据 `docs/verification/2026-08-16-evidence-starvation-r13.md`。T2 四槽（W01×3 + 孤儿 W04）均
`LLM 调用 HTTP 503`，零 `tool_request`。本机直探中转 chat 仍 5xx。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-13` | T1 字段离线单测绿；live 四槽无工具批，五元组未落盘。相邻 5 次成功 `evidence_search` 墙钟 32.3–58.9s（0 次 ≤10s）只作 serial-phase 旁证，不是预注册重放 | `pending` | 保持 Open。缺字段不得结案，不得用旁证写 H-a/H-c |
| `R-20260816-14` | #100 diff 无 `ASK_TOOL_BATCH_TIMEOUT` / `tool_batch_seconds` / T / slot / 档位上调 | `pending` | 绊线常在；本 PR 未触线 |
| `R-20260816-10` | 同侧车但本窗 0 次 judge 调用（首轮 503）。不得用本窗偷结 | `pending` | 保持 Open。判据不与 R-13 互混 |
| `R-20260816-15` | 未改 #72 / eb 量具 | `pending` | 保持 Open。R-11 已结，不回写 |

### 2026-08-16 R-15 离线分层重算：回填

材料 = 冻结三对 episode + 冻结 `score.json`（mtime 2026-08-16 20:19:27，未覆写）+
`intelligence/tests/test_episode_bindings_rate.py`（6 passed）。
对齐键 `slot`+`run_id`。未改 #72 / 生产 episode / T / 30 / 档位。预测原文未改。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-15` | 三对 post 分层 eb=1.00；旧口径 main42 −17.5pp → 分层 +5.3pp。±5 带未入（差 0.3pp）。「修后不降」成立。单测钉 0-hash 判断槽 → 旧 0.5 / 分层 1.0 | `pending` | 保持 Open。部分验证不得写 confirmed。收据 `docs/verification/2026-08-16-outlook-eb-r15-rescore.md` |
| `R-20260816-07` | 本 PR 只动 eval/docs，无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 保持 Open（绊线仍看自称预算修复的 PR） |
| `R-20260816-10` / `-13` / `-14` | 未触及 8795 同形重放 / 工具批五元组 / 批窗旋钮 | `pending` | 保持 Open。本行不代结 |

### 2026-08-16 R-13 T2 GLM 窗：回填

8795=`16f2cd47` dirty=false（pid 73668，GLM-5.2 Coding Plan）；8792 全程 `6cd0756e` 未切。
收据 `docs/verification/2026-08-16-evidence-starvation-r13.md`。11 槽五元组齐。
中转 503 窗已作废。未动 T / 批窗 / slot / 档位。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-13` | 11/11 五元组落盘。0 次 `evidence_search`。D01 合同档 standard（「深挖」未升档）。H-a 缺 deep 四段合计；H-c 缺该工具自然值。`asked=30` 来自 reserve=60，不是本窗调参 | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-14` | 本窗无 PR 上调 `ASK_TOOL_BATCH_TIMEOUT` / `tool_batch_seconds` / T / slot / 档位 | `pending` | 绊线常在；未触线 |
| `R-20260816-10` | 本窗 0 次 judge。不得偷结 | `pending` | 保持 Open。判据不与 R-13 互混 |
| `R-20260816-15` | 未改 #72 / eb 量具 | `pending` | 保持 Open。不并案 |

### 2026-08-16 中转中断 / GLM 转移：开行

交接 `docs/handoffs/2026-08-16-provider-outage-and-glm-failover.md`。
8792 pid **90194** 链长=2；原题复跑 `run_20260816_230528_976709` 零 5xx、tools=4，draft 终值 0。
dsh 草稿曾占用 `R-06`..`11`——**那些号在 main 上已有含义，本表作废那份编号**。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-16` | 开行。启动器已加 GLM 三件套；复跑走 zhipu、llm_calls 不再是 16×5xx。draft 终值 0 / fulfilled 0/4 | `pending` | 新开 Open。部分验证不得写 confirmed |
| `R-20260816-17` / `-18` / `-19` / `-20` / `-21` | 开行。21 是 repair 窗随 p90，不是把 30 调大 | `pending` | 新开 Open。R-02/R-07 绊线仍看自称预算修复的 PR |
| `R-20260816-06` | Closed 的 judge 窗案。本事故不回写、不改原文 | `confirmed` | 不回写 |
| `R-20260816-11` | Closed 的判断槽 0-hash。本事故不占用此号 | `confirmed` | 不回写 |
| `R-20260816-07` / `-10` / `-13` / `-14` / `-15` | 未把 30 / T / 档位当本事故修复 | `pending` | 保持 Open |

### 2026-08-16 R-17 成因行：离线回填

夹具在 `intelligence/tests/test_degraded_fallback.py`。#106 已合 `main`。未部署 8792，未重渲染 22:18 / 23:05 生产 run。未动 T / 30 / 档位。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-17` | 离线：`repair_model_unavailable` 与三零（`llm_calls=0` / evidence=0 / bindings=0）首句含「模型服务不可用」且不含「现有证据不足」；开关 off 时模型正常结束的中间档逐字节不变 | `pending` | 保持 Open。部分验证不得写 confirmed。live 重渲染未做 |
| `R-20260816-07` | 本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 绊线未触 |
| `R-20260816-16` / `-18` / `-19` / `-20` / `-21` | 未做链长结案 / status 投影 / 反证夹具 / 描述表 / p90 窗 | `pending` | 保持 Open |

### 2026-08-16 R-21 repair 窗随 p90：离线回填

分档延迟：8795 GLM 成功轮 n=32，p50=17.3 / **p90=34.4** / max=49.4；6/32 >30s。
中转 terra 2026-08-08 P50≈28s，08-13 收据 30s 窗 5/5。取值：openai=30，zhipu=40（p90+余量），未知=30。
`_REPAIR_SECONDS_CAP` **仍是 30.0**。#109 已合 `main`。未部署 8792。

全路由影响面：非研究题不走 `admit_repair`（0pp）；中转研究题取值不变；仅 GLM 研究题的 repair / transient retry 单笔上限 30→40。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-21` | 离线：`repair_seconds_cap_for("zhipu")>34.4` 且 `!= openai`；不传 cap 的授予仍 30；transient retry 也吃注入帽。未做同题 live 重跑 | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-07` | diff **不含** `_REPAIR_SECONDS_CAP` 上调（常数仍 30.0） | `pending` | 绊线未触。窗随 p90 不是把 30 调大 |
| `R-20260816-02` | 动了 repair 授予公式的注入帽，不是 T。live 臂未跑 | `pending` | 保持 Open。条件句「若动预算」部分触发，不得写 confirmed |
| `R-20260816-16` / `-18` / `-19` / `-20` | 本 PR 不改 status 投影 / 描述表。R-17 已由 #106 合入 | `pending` | 保持 Open |

### 2026-08-16 R-20 描述表：离线回填

18 个 `QUESTION_TYPES` 默认槽位补齐后人话描述；`chain_mapping` 不再同义反复。
`.get(id, id)` 改为 `_require_output_description`，缺键在 `build_episode_context` 失败。
删 `chain_mapping` 键的夹具转红。未部署 8792。未动 T / 30 / 档位。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-20` | 离线：18 题型无缺键/同义反复；`test_missing_description_key_fails_at_build` 转红。未做 live 契约抽检 | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-07` | 本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 绊线未触 |
| `R-20260816-16` / `-18` / `-19` | 未做链长结案 / status / 反证。R-17/#106、R-21/#109 已合 | `pending` | 保持 Open |

### 2026-08-16 R-18 status 投影：离线回填

`run.json` / `report.json` / `continuous-episode.json` 走同一函数
`status_projection.project_artifact_statuses`。合流规则：`outcome.status=failed`
压过 delivery 的 `degraded`——有缺口文案也不能把 run 写成 completed（22:18 形）。
真 degraded（artifact 无 failed outcome）仍是 transport complete / business partial。
夹具是当日两份 run 的 status 切片，不含题面/正文。未动 T / 30 / 档位。未做 live 重跑。

8792 在本 PR 之前已切到 `0df86612`（#106/#109/#110）；本行代码尚未上 8792。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-18` | 离线：22:18 切片投影后 `run=failed` / `report=blocked`；23:05 `partial` 仍可 `run=completed`；orchestrator 夹具钉 `failed∧completed` 消失。未做 live 重跑 | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-07` | 本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 绊线未触 |
| `R-20260816-16` / `-17` / `-19` / `-20` / `-21` | 本 PR 不改链长 / 成因行 / 反证 / 描述表 / p90 窗 | `pending` | 保持 Open |

### 2026-08-16 R-19 缺口模板整篇 uncheckable：离线回填

`evaluate_marker_coverage` 认出 `_gap_answer` 整篇后，全部 required output 进
`uncheckable`，`present=[]`。22:18 形「提供主要反证」不再把 `counterpoint`
标成 present，与 `structural_verifier` missing 不再静默冲突。
真反证正文（「主要反证是…」）仍 present。未并完 R-15-03 的 6-run 同判据。
未动 T / 30 / 档位。未做 live 重跑。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-19` | 离线：22:18 形 `counterpoint` 进 uncheckable 不进 present；真反证反向仍 present；L01 缺口模板不再报 `marker_coverage=complete`，且仍不响 `uncheckable_judgment_empty`。未做 live | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260815-03` | 本 PR 只收缺口模板这一类冲突，未改成同一判据函数，6-run 夹具未齐 | `pending` | 保持 Open。不得把本行当 R-03 结案 |
| `R-20260816-07` | 本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 绊线未触 |
| `R-20260816-16` / `-17` / `-18` / `-20` / `-21` | 本 PR 不改链长 / 成因行 / status 投影 / 描述表 / p90 窗 | `pending` | 保持 Open |

### 2026-08-17 同题 live（8792=`1b678ee9`）

`run_20260817_002238_100737` / user `verify-r1621-0817`。墙钟约 110s。
主路径模型轮成功（timeout_asked 69.5 / 60.0）。repair 两发仍整窗 30.0 TimeoutError。
未动 T / `_REPAIR_SECONDS_CAP` / 档位。单次 live 不得写 confirmed。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-16` | zhipu、tools=4、llm_calls=4、evidence=15；不是 16×5xx。**draft_len=0**、fulfilled 0/4 | `pending` | 保持 Open。draft 终值 0 不得写 confirmed |
| `R-20260816-17` | 首句「模型服务不可用，暂不能可靠回答」；无「现有证据不足」 | `pending` | 保持 Open。单次命中 ≠ 结案 |
| `R-20260816-18` | outcome=`partial`（stop=`repair_model_unavailable`），run=`completed`。禁止对 `failed∧completed` 未出现 | `pending` | 保持 Open。允许对出现，不是结案 |
| `R-20260816-19` | present=[]；required 四格（含 counterpoint）全部 uncheckable | `pending` | 保持 Open。单次命中 ≠ 结案。R-15-03 6-run 未做 |
| `R-20260816-20` | 本 run 未做描述表契约抽检 | `pending` | 保持 Open |
| `R-20260816-21` | **MISS**：`repair_goal.remaining_seconds=30.0`，两发 `granted_seconds=30.0` / `seconds_granted=30.0`。代码在 8792，帽没挂上组合根 | `pending` | 保持 Open。预测「不再两发整窗 TimeoutError」未兑现 |
| `R-20260816-07` | 本 live 未上调 T / `_REPAIR_SECONDS_CAP` / 档位 | `pending` | 绊线未触 |

### 2026-08-17 R-21 帽挂上 GLM 组合根：离线回填

生产装配是 `GLMModelClient → GLMAgentRuntime → ContinuousTurnAdapter`。
`GLMAgentRuntime` 没有 `_providers` / `model_client` / `_client` / `_model`，
`provider_name_from(runtime)` 返回 None → `repair_seconds_cap_for(None)=30.0`。
`provider_name_from` 改为沿 `_episode` / `client` / `_model` 走（带环检测）；
`app.py` 组合根同时按链首名注入 `repair_seconds_cap`。
`_REPAIR_SECONDS_CAP` **仍是 30.0**。#113 已合 `main`。二次 live 见下节。

首笔 grant 仍可能是 30：standard 90 − synthesis reserve 60 的剩余。那是另一件事，
本行不把 30 调大。接线后 **retry** 应吃到 zhipu 帽 40；两发整 30 TimeoutError 仍算 miss。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-21` | 离线：`provider_name_from` 能从 GLM runtime→episode→client 读到 zhipu；组合根 adapter 帽=`repair_seconds_cap_for("zhipu")`。二次 live 见下节 | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-07` | diff **不含** `_REPAIR_SECONDS_CAP` 上调（常数仍 30.0） | `pending` | 绊线未触 |
| `R-20260816-02` | 仍只修帽的挂载，不是 T | `pending` | 保持 Open |
| `R-20260816-16` / `-17` / `-18` / `-19` / `-20` | 本 PR 不改链长 / 成因行 / status / 反证 / 描述表 | `pending` | 保持 Open |

### 2026-08-17 接线后同题 live（8792=`1594394c`）

`run_20260817_003329_048038` / user `verify-r21-wire-0817`。墙钟约 137s。
#113 已切：`source_revision=1594394cfbc2` / `source_dirty=false` / `code_matches_repo=true`。
未动 T / `_REPAIR_SECONDS_CAP` / 档位。单次 live 不得写 confirmed。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-21` | `repair_goal.remaining_seconds=40.0`，`repair_reentry.granted_seconds=40.0` / `timeout_asked≈39.95`。repair 轮 zhipu 成功（约 15s 墙钟），无 30.0 授予，无两发整窗 TimeoutError。stop=`repair_model_stop` | `pending` | 保持 Open。接线命中，单次 ≠ 结案 |
| `R-20260816-16` | zhipu、tools=4、llm_calls=3、evidence=39、**draft_len=675**；不是 16×5xx | `pending` | 保持 Open。draft>0 仍不得写 confirmed |
| `R-20260816-17` | 本 run 不是 `repair_model_unavailable` 形。首句是 judge 瞬时不可用的候选草稿提示，不是「模型服务不可用」缺口模板 | `pending` | 保持 Open。形状未再命中，不回写 |
| `R-20260816-18` | outcome=`partial`（stop=`repair_model_stop`），run=`completed`。禁止对 `failed∧completed` 未出现 | `pending` | 保持 Open |
| `R-20260816-19` | 本 run 不是缺口模板。`counterpoint` structural fulfilled；`chain_mapping` missing（kb_search `tool_timeout`） | `pending` | 保持 Open。缺口模板形未再命中。R-15-03 未做 |
| `R-20260816-20` | 本 run 未做描述表契约抽检 | `pending` | 保持 Open |
| `R-20260816-10` | judge `timeout_asked=12.5` / `exc_class=TimeoutError` / remaining≈171。预测要的首轮 ≥20 未兑现 | `pending` | 保持 Open。旁记，本窗不修 judge 窗 |
| `R-20260816-07` | 本 live 未上调 T / `_REPAIR_SECONDS_CAP` / 档位 | `pending` | 绊线未触 |

### 2026-08-17 contains 上线 + R-22/R-23 占号

#115 已合 `520fc0f8`，8792 已切同 SHA。`contains` ESCAPE 两字符根因在生产生效。
handoff：`docs/handoffs/2026-08-17-two-agent-collision-and-contains-escape.md`。
对方原 `-12`/`-13` 按 handoff §4 改号为本表 `-22`/`-23`，避免与宽题取证饿死的 `-13` 撞号。
实现（`_structured_provider_is_stale` 分档、`dataset_field_hint` 接模型可见面）归工具层执行方；A 方不改这两处。
18 条 `test_continuous_turn_adapter` 红：**漏改夹具**（判断槽 `basis=model_reasoning` + 强制 `market_data`），不是 R-18 投影语义。已另开 `fix/adapter-success-fixtures`：默认问句去掉「怎么看」，不再误踩判断槽。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-22` | 用户已裁定分档口径；Open 表已占号。离线实现见下节 | `pending` | 保持 Open |
| `R-20260816-23` | 原「hint 未进可见面」机制已否证，见下节 | `pending` | 保持 Open。机制更正，不得写 confirmed |
| `R-20260816-07` | #115 / 本次切窗未上调 T / `_REPAIR_SECONDS_CAP` / 档位 | `pending` | 绊线未触 |
| `R-20260816-16` / `-17` / `-18` / `-19` / `-20` / `-21` | 本窗不改链长 / 成因行 / status / 反证 / 描述表 / p90 窗 | `pending` | 保持 Open |

### 2026-08-17 R-22 主体退出 vs 管道陈旧：离线回填

`_subject_exited_universe`：`dataset_max ≥ floor ∧ served < dataset_max` → 退出并交付证据；
`dataset_max < floor` 或读数缺失 → 仍 stale。探针只在即将判 stale 且有 filter 时发。
未放宽 floor。未动 T / 30 / 档位。未做 live 重跑。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-22` | 离线：`test_subject_exited_universe.py` 双夹具 + 变异（同 served、不同 dataset_max 必须相反）+ fail-closed。未做同题 live | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-23` | 本 PR 不接 `dataset_field_hint` | `pending` | 保持 Open。实现仍归工具层 |
| `R-20260816-07` | 本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 绊线未触 |

### 2026-08-17 R-23 诊断更正：metric 抄进 dimensions

原预测「`dataset_field_hint()` 未进模型可见面」**机制否证**：hint 已在
`episode_tools` 的 finance_query 描述里，列全 13 个 dataset。4/4 生产报错请求
字段全部合法，只是模型把 metric 又抄进 dimensions（当「要返回的列」）。
靠 retry hint 纠正已试过且无效（repairwin-8 连错两次）。

修复：`normalize_spec` 把「已在 metrics 声明的字段」从 dimensions 去掉。
字段只在 dimensions、未在 metrics 声明时**不动**（意图不可判定）。
夹具逐字取自四个真实报错请求。未做 live。未动 T / 30 / 档位。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-23` | 离线：`test_metric_dimension_dedupe.py` 四组 live 夹具 + 真分组键保留 + 未声明 metric 不动（含 metrics 非空变异）+ 干净 spec 无副作用。原 hint 机制否证。未做同题 live | `pending` | 保持 Open。部分验证不得写 confirmed。Open 表原预测作机制更正，不另开号 |
| `R-20260816-22` | 本 PR 不改退出/陈旧分档 | `pending` | 保持 Open |
| `R-20260816-07` | 本 PR 无 T / `_REPAIR_SECONDS_CAP` / 档位上调 | `pending` | 绊线未触 |

### 2026-08-17 R-22/R-23 同题 live（#119 已切）

8792=`dd28e4d8` / dirty=false / match=true。user=`verify-r22-r23-0817`。
`run_20260817_014724_245782` ≈136s。run=`completed`，outcome=`partial`，
stop=`repair_model_unavailable`。tools=4 / llm=4。未动 T / 30 / 档位。
**单次 live 不得写 confirmed。**

工具层：

- R-22 hit：`finance_query` `mainline_theme_daily` + `contains` 算力 →
  trace `status=ok` `detail=dataset=mainline_theme_daily; subject_exited_universe`；
  served=`2026-08-07`，dataset_max=`2026-08-14`，rows=14。不是 stale / 零证据。
- R-23 hit：同请求 `dimensions` 含 metric `rank`/`sector_count`（亦在 `metrics`）。
  无 `not a dimension` / `invalid_query`；查询返回行。第一发 `market_daily` 干净
  spec（`index_return_pct` 只在 metrics）亦成功 20 行。
- contains ESCAPE 仍通（#115）。

交付层 miss（本窗不修）：

- repair grant=40 后 transient retry=20，两发 `TimeoutError`；draft=0。
- 答案走「模型服务不可用」缺口模板，40 条证据未绑定（R-17 形命中，不结案）。
- `kb_search` `tool_timeout`（已知 leftover）。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260816-22` | live：`subject_exited_universe` + 14 行退出前证据。答案层未写出退出事实（repair 死） | `pending` | 保持 Open。工具命中 ≠ 结案 |
| `R-20260816-23` | live：`rank`/`sector_count` 双边同名未炸 `invalid_query`。原 hint 机制仍否证 | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-17` | 本 run 是 `repair_model_unavailable` + 缺口模板「模型服务不可用」。形命中，不结案 | `pending` | 保持 Open |
| `R-20260816-16` | zhipu 路径 tools=4，不是 16×5xx。draft=0 | `pending` | 保持 Open。draft 终值 0 不得写 confirmed |
| `R-20260816-18` | outcome=`partial`，run=`completed`。禁止对 `failed∧completed` 未出现 | `pending` | 保持 Open |
| `R-20260816-21` | repair 首授 40（帽仍在）。其后 20s retry 仍 TimeoutError。不是两发整窗 30 | `pending` | 保持 Open。帽接线 ≠ 模型按时返回 |
| `R-20260816-10` | 本 run 未进 judge（repair 先死） | `pending` | 保持 Open。旁记 kb `tool_timeout`，本窗不修 |
| `R-20260816-07` | 本 live 未上调 T / `_REPAIR_SECONDS_CAP` / 档位 | `pending` | 绊线未触 |

### 2026-08-17 同题两发 M2：有稿未结转

报告：`docs/verification/2026-08-17-r22-r23-same-question-m2.md`（`validate-report.sh` RC:0）。
A=`run_20260817_014724_245782` B=`run_20260817_015340_618752`。8792=`dd28e4d8`。
未改生产、未切窗、未动 T / 30 / 档位。

PRIMARY：首轮 `model_turn` 已有可解析 FINAL_JSON（A draft_len=897 / B=738），
同毫秒 `finish.carried_draft_chars=0`、`rejection_code=none`。
工具层分叉（theme 退出 vs sector 空行）不能预测共享空稿。
repair 两发 TimeoutError 是传播。R-22/R-23 保持 pending。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-01` | 离线：finalize 后 consume 抛 ValueError，draft 仍在。未 live | `pending` | 保持 Open。部分验证不得写 confirmed |
| `R-20260816-22` | 第二发 `mainline_sector_daily`+`sector_name` 0 行；退出探针无 served 不触发。不是 stale 回归 | `pending` | 保持 Open。不得写成 refuted |
| `R-20260816-23` | 两发均无 `invalid_query` | `pending` | 保持 Open |
| `R-20260815-04` | 本形是「模型已返回 draft、outcome 仍 0」。`draft_source` 仍缺席 | `pending` | 保持 Open |
| `R-20260816-07` | 本分诊无 T / 30 / 档位 diff | `pending` | 绊线未触 |

### 2026-08-17 R-20260817-01 离线结转

`run()` 在 `complete()` 已返回后若 `_consume_root_seconds` 失败，先
`validate_episode_finish` 再停机：合法 FINAL_JSON 结转 draft/bindings；
工具轮 / 无效稿仍空。未调 T / `_REPAIR_SECONDS_CAP` / 档位。
**#124 已合切** 8792=`31ee58ce` / dirty=false / match=true。
R-22/R-23 保持 pending。单次 live 不得 confirmed。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-01` | 离线两夹具绿。#124 已合切 | `pending` | 保持 Open |

### 2026-08-17 R-20260817-01 同题 live（未同形）

8792=`31ee58ce`。`run_20260817_022655_519631` ≈68s。user=`verify-r22-r23-0817`。
seq2 PLAN+7 工具调用后 first finish `deadline_exhausted` / `carried_draft_chars=0` /
`rejection_code=none`。没有 FINAL_JSON，不是 M2「有稿未结转」。
repair `previous_draft_chars=0`，`evidence_search` `tool_timeout`，
stop=`repair_deadline_exhausted`，公开答案是「现有证据不足」模板。
不得 confirmed，也不得写成 R-20260817-01 refuted。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-01` | live 未走到 finalize JSON；空稿停机符合工具轮夹具 | `pending` | 保持 Open。不得 refuted |
| `R-20260816-22` | 本发未打到退出探针 | `pending` | 保持 Open |
| `R-20260816-23` | 本发无 `invalid_query` | `pending` | 保持 Open |
| `R-20260816-07` | 未调 T / 30 / 档位 | `pending` | 绊线未触 |

### 2026-08-17 R-20260817-01 同题第二发（合成超时，仍未同形）

8792 仍 `31ee58ce` / dirty=false / match=true。`run_20260817_093755_447794` ≈148s。
工具：`mainline_sector_daily` 0 行、`market_daily` 有行、`memory_lookup` 空、`kb_search` `tool_timeout`。
随后 `finalization`，seq12 `TimeoutError` / content 空。first finish
`deadline_exhausted` / `carried_draft_chars=0` / `rejection_code=none`。
repair 两发 TimeoutError，`previous_draft_chars=0`，stop=`repair_deadline_exhausted`。
公开答案仍是「现有证据不足」。无 `subject_exited_universe`，无 `invalid_query`。
没有 FINAL_JSON 可结转，不得 confirmed / refuted。未再切 8792，未动 T / 30 / 档位。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-01` | 合成超时空稿，不是有稿未结转 | `pending` | 保持 Open。不得 refuted |
| `R-20260816-22` | `mainline_sector_daily` 0 行，退出探针未触发 | `pending` | 保持 Open |
| `R-20260816-23` | 无 `invalid_query` | `pending` | 保持 Open |
| `R-20260816-07` | 未调 T / 30 / 档位 | `pending` | 绊线未触 |

### 2026-08-17 R-20260817-01 同题第三发（**首次同形 hit**）

8792 仍 `31ee58ce` / dirty=false / `code_matches_repo=true` / `workers.active=0`（发起前 `/api/health` 实测）。
`run_20260817_094617_943922` 墙钟 156.6s。user=`verify-r22-r23-0817`，`skill_mode=auto`，新会话。
未切 8792、未动 T / `_REPAIR_SECONDS_CAP` / 档位。

**结转判据逐项对表**（handoff §3 的严判据，不放宽）：

| 判据 | 实测 |
|---|---|
| 某条 `model_turn.content` 能 `json.loads` 出 `draft` | ✅ seq14，1404 字符，keys=`[bindings,draft,gaps,status]`，`draft`=732 字符 |
| 紧随 first finish `carried_draft_chars>0` | ✅ seq16 `carried_draft_chars=732` |
| `rejection_code` | `none`（`stop_reason=deadline_exhausted`） |
| 交卷带稿 | ✅ `answer.md` 1901 字节，含阶段判断 / 依据 / 反方 / 升级 + 降级信号 |

工具轮：`finance_query`×2 有行（`mainline_theme_daily`、`market_daily`）、`memory_lookup` 空、
`kb_search` `tool_timeout`、`news_search` `tool_budget_exhausted`；`finalization` reason=`retrieval_deadline_closed`。
repair cycle 1 `previous_draft_chars=732` / granted 40s，seq19 出 1299 字符，
second finish `repair_model_stop`，4 个 output 槽 `basis=evidence` 全绑上。
`structural_verifier` `verified_status=partial`（`factual_grounding` / `task_coverage` 均 fulfilled）；
`semantic_verifier` `status=partial`，公开答卷带「语义核验因瞬时服务问题未完成」前缀。

⚠ **本发暴露一条判据洞（新，未修，不在本窗动手）**：seq19 的 repair content
**`json.loads` 失败**——`draft` 字符串里 `"AI算力"` / `"7月中旬即为高点…"` 的双引号未转义。
但生效解析器把它捞了出来，`outcome.draft`(612) 取自 seq19 而非 seq14 那份 732 字符的合法稿。
即 **handoff §3 写的严判据与生效解析器不同口径**：照严判据读，seq19 应判「无 FINAL_JSON」，
而产品实际出了稿。本次结论只依赖 seq14+seq16（两者都过严判据），不依赖 seq19，故 hit 成立。
但下一任若拿严判据去判 repair 轮，会把出了稿的 run 误记成空稿。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-01` | **首次同形**：seq14 合法 FINAL_JSON + seq16 `carried_draft_chars=732`，答卷带稿 | `pending` | 保持 Open。**单次不结案**，本交接未授权 confirmed |
| `R-20260816-22` | **未打到判据点**：本发问的是 `mainline_theme_daily`（题材表）且有行，R-22 预测点名的是 `mainline_sector_daily`（板块表）。答案层出现「8月7日之后退出主线题材名单（构成要素退出，非数据陈旧）」，形状对但数据集不对 | `pending` | 保持 Open。不得据此 confirmed |
| `R-20260816-23` | 本发无 `invalid_query`（tool_error 仅 `tool_timeout` / `tool_budget_exhausted`） | `pending` | 保持 Open |
| `R-20260816-07` | 未调 T / 30 / 档位 | `pending` | 绊线未触 |

### 2026-08-17 R-20260817-02 开行：检索预算分配（立案，未动手）

同一个 run `run_20260817_094617_943922` 的工具批读数：

```
kb_search    batch_grant_asked=30.0  stage_timeout_granted=11.955  queued_ms=2.2  → tool_timeout
news_search  同一批                                                              → tool_budget_exhausted
finalization reason=retrieval_deadline_closed
```

同批还有 `finance_query`×2（有行）与 `memory_lookup`（空），先跑完把窗口吃掉。

`kb_rag` 本体实测：同进程冷调 **39.06s**，之后 **4.25s / 5.10s**（`persistent_worker` 协议）。
8792 常驻 worker 已在启动期 prewarm（`prewarm_latency_ms=38516`、`lifecycle=startup_prewarm`、
`model_load_count=1`），**冷启动不在请求路径里**。

**结论：不是检索慢，是一个 4~5 秒的工具排在 12 秒窗口的第四位。**

**已排除、不要再走的两条**（避免下一任重跑）：

1. **不是串行。** `intelligence/runtime/episode_tool_batch.py` 用 `ThreadPoolExecutor`
   同批**并发**提交，注释原文「一个批次里的工具是并发提交的，**但共享一个 deadline**」。
2. **subagent 化不解这题。** `intelligence/runtime/sub_research.py` 的 `_BranchBudgetView`
   docstring 原文：**"A non-minting child view whose consumption debits one parent ledger."**
   ——子分支**不铸新预算，消耗直接记父账本**。所以缺的**不是** subagent 机制
   （`SubResearchCoordinator` / `SubResearchWorker` / `BranchRequest` 都在），
   **缺的是不铸币的那层能铸币**：是预算模型的改动，不是拓扑的改动。
   （按 ai-agent-book ch10 判据「有没有新信息」，同批工具搬进子 Agent 也没有新信息。）

spec 侧已同步：`2026-08-15-agent-base-dsh-absorption-design.md` §4.1 给「工具批次预算」
加限定（机制在、分配策略未验证），§4.2 补第 6 条。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-02` | 开行。批次预算把 4~5 秒的工具饿死；冷启动与串行均已排除 | `pending` | 立案不动手，触 R-07 绊线 |
| `R-20260816-07` | 未调 T / 30 / 档位 / 并发度 | `pending` | 绊线未触 |
### 2026-08-17 T-C：FINAL_JSON 判据对齐（验收尺，不成案）

尺子：`intelligence/eval/finish_json_criterion.py`。夹具 `run_20260817_094617_943922` seq14 / seq19 原文。
「写出答案」=`parse_finish_json` 取出非空 draft（与产品生效解析器同一条路）。
「合法 JSON」=`json.loads` 成 object，**分开计数**。seq19 repair：写出答案=是，合法 JSON=否。
上表「没有 FINAL_JSON」的两发 live 是 content 空，两条计数都是否，结论不变。
R-20260817-01 / R-16..23 仍 pending。不切 8792。T1 hit 结论不依赖 seq19。

| ID | 新证据 | outcome | 处理 |
|---|---|---|---|
| `R-20260817-01` | 验收尺与解析器对齐。未改结转代码，未改 live 结论 | `pending` | 保持 Open。尺子落地 ≠ 结案 |

### Closed

| ID | 来源 | fix_type | verification_prediction | outcome | evidence |
|---|---|---|---|---|---|
| `R-20260816-11` | 十题窗 #94 + 检阅 #96（非 M1 开行）；M2 结案 | `EVAL_ONLY` | 下一份分诊须把「修后判断槽 `evidence_hashes=0`、旁槽仍有哈希」立为独立 PRIMARY 候选或显式 REJECT；并进 R-06、或写成 judge 窗地板副作用，即本预测 **refuted** | `confirmed` | `docs/verification/2026-08-16-outlook-eb-judgment-slot.md` E-001/E-003/E-006/E-007/E-011/E-012。PRIMARY 点名 0-hash 形状；H1 REJECTED |
| `R-20260816-06` | 2026-08-16 有稿 judge 案 F-001 | `EVAL_ONLY` | 下一份 draft>0 且 `semantic judge transient provider error` 的 run，judge 调用带 `timeout_asked` 与原始异常类（TimeoutError / HTTP status / 连接） | `confirmed` | 8795 `02fa203e` 12 槽：11 槽 asked=5.208 / TimeoutError / remaining≥170 → H9；0 槽 H8。收据 `docs/verification/2026-08-16-judge-transient-r06.md` E-001–E-004 |
| `R-20260816-05` | outlook 预算回归 M1 E-012 | `EVAL_ONLY` | 观测台/收据把 L01 空稿 `(repair_model_unavailable, draft_len=0)` 与 L05 候选草稿 `(repair_model_stop, draft_len>0, judge transient)` 分成两行 | `confirmed` | `docs/verification/2026-08-16-outlook-off-arm-typology-judge-case.md` E-001：`(repair_model_unavailable,0,unavailable)=7` 与 `(invalid_repair_finish,0,unavailable)=3` 对 `(repair_model_stop,>0,unavailable)=8` 等有稿行。禁止 151–159s 合并 |
| `R-20260816-04` | outlook 预算回归 M1 F-003 | `EVAL_ONLY` | 用 `run_20260816_131941_597875/answer.md` 跑 `evaluate_marker_coverage` 仍得 `warnings=[]`、`marker_coverage=complete`（#327 缺口模板不触发 `uncheckable_judgment_empty`） | `confirmed` | 原文夹具 `test_l01_gap_template_does_not_trigger_uncheckable_judgment_empty`（#84 / `21dbf6c1`）。`direct_answer` uncheckable + 模板句被当成非边界正文。改探测器另开观测台 |
| `R-20260815-23` | 轨道 A Round 4 M1 F-001 | `DATA_CONTRACT_FIX` | 本修复部署到 8792 之后的下一批：主路径 `deadline_exhausted`、修复轮已收集证据的同形 case，修复终局应解析出绑定且 `evidence_bound>0`。该批若再出现 `invalid_action.reason` 含 `unknown evidence hash`（誊抄 16-hex），本预测 **reproduces → refuted**。越界序号 / 歧义拼接仍拒收；不做模糊纠正 | `confirmed` | 批 #3 `sha256=e475f3c889946b2ef87507ca303effa5bf9a1ca153821009f60e6b4edaf1ebf0`。检阅方重扫：hash-reject 0；修复路径验收 eb>0 为 14/15；B8 `no_substantive_answer` 不同形。8792=`fdb23114` pid 70403 |
| `R-20260815-10` | Round 3 轨道 B（M1 F-002） | `EVAL_ONLY` | B 组结论改报交付率而非单批布尔后：连续 3 批的 B 组读数按题给出 N 次中的交付次数；任一只引用单批「失败成员名单」的结论可被评审据此打回 | `confirmed` | 批 #1 `sha256=b712bd2ee10fb431dba937416fb5882c6984ac65bb5421b5472f71c7ead8d350`；批 #2 `sha256=51e617100b4a72dcd58109c21d685d25b5a4ccae9c0e34507db494ee87304ef4`；批 #3 `sha256=e475f3c889946b2ef87507ca303effa5bf9a1ca153821009f60e6b4edaf1ebf0`。N=3：B1 2/3、B2 3/3、B3 2/3、B4 2/3、B5 2/3、B6 0/3、B7 2/3、B8 2/3。只 `evidence_bound>0`。报告 `docs/verification/2026-08-15-r6-clean-baseline-3.md` E-005 |
| `R-20260815-09` | Round 3 轨道 B（M1 F-001） | `HARNESS_FIX` | `invalid_repair_finish` 落盘拒收原因码与被拒 payload 的结构摘要（字段名/计数，不落正文）后：下一个该形状的 turn 其原因码非空，可据以在 REASONING（收尾产出不合法）与 HARNESS（修复轮契约拒收）之间定夺 F-001 的 L0 | `confirmed` | 批 #3 21/21 末条 finish 带 `rejection_code`/`rejection_reason`；B8 `run_20260815_182902_790837` seq 21 `rejection_code=no_substantive_answer` `rejection_reason=required output lacks substantive answer: scenario_range`。报告 E-006 |
| `R-20260815-12` | Round 5 轨道 B（preflight 数据源盖戳 + RU-3） | `EVAL_ONLY` | 开批前 `finance_query` 冒烟探针写入 `preflight_detail`（`data_probe: finance_query=ok/tool_exception/empty`）；失败处置写死 `DATA_PROBE_ON_FAILURE=run_and_flag`：不中止，产物顶层 `window_contamination="finance_query"` 且 `data_probe_ok=false`。探针失败的批必须可被评审一眼识别为污染窗口；静默混进「看起来干净」的批（无顶层标注）即 refuted。并行字段 `episode_fulfilled_hashed` 与 `evidence_bound` 同时在场、互不覆盖；B3@批#2 两值不等（2 vs 0） | `confirmed` | `test_preflight_probe_failure_does_not_abort`、`test_run_stamps_window_contamination_when_probe_failed`、`test_run_output_writes_exact_requested_path`（未探测不盖戳）、`test_b3_batch2_episode_fulfilled_hashed_unequal_to_frozen_eb`。处置常量写死 `run_and_flag`。冻结批 JSON 未改 |
| `R-20260815-11` | Round 4 轨道 B（检阅 E-r3 新缺陷） | `EVAL_ONLY` | 多轮题的 `execution_state_tally` 按轮计数且含 `execution_state_turn_rows`；case 级 `execution_state_aggregate` 取最后一轮（`last_turn`，写死）后：重放 C10（`20260814T1926Z-r3-clean-baseline`）时 tally 含 1 个末轮 `bound_but_dropped`，该 case 的 aggregate 同为 `bound_but_dropped`，二者不再互相矛盾 | `confirmed` | `test_c10_frozen_multiturn_tally_matches_last_turn_aggregate`：C10 三轮 delivered/clarification/bound_but_dropped；tally 按轮 `{bound_but_dropped:1, clarification:1, delivered:1}`；`execution_state_aggregate=bound_but_dropped`（`last_turn`）；turn_rows[-1] 与 aggregate 同态。批 JSON 未改。`test_acceptance_execution_state` 16 passed |
| `R-20260815-08` | Round 3 轨道 B 开批前实测 | `EVAL_ONLY` | 验收台改为从 `/api/health` 取服务端的 users 目录（或在自身 env 与服务端不一致时**响亮失败**）后：故意把 `FORESIGHT_USERS_DIR` 指向一个存在但错误的目录跑一次，产物应报错或显式标注不一致，而**不是**整批静默落 `undetermined`/`api_only` | `confirmed` | 离线负夹具：`test_users_dir_mismatch_against_health_raises`、`test_preflight_rejects_mismatched_users_dir`、`test_wrong_users_dir_does_not_emit_plausible_five_state`。错目录存在但无 episode 时 `require_episode_if_expected` 抛 `UsersDirMismatch`，`cmd_run` 返回 2 且不落盘五态；对目录读到 `no_hash`。health 增 `runtime.users_dir`（未部署 8792 时 env 不一致仍由 missing-episode 门拦住）。`test_acceptance_execution_state` + `test_acceptance_board` 覆盖 |
| `R-20260815-06` | Round 2 轨道 B（M2 F-002） | `NO_SYSTEM_FIX` | 生产代码身份属用户裁决；裁决后 `loaded_code_root` 对应目录 `git status --porcelain` 为空，且 `/api/health` 的 `source_revision` 与该目录 `git log -1` 一致 | `confirmed` | 8792 蓝绿切到干净快照 `~/.finance-runtime/finance-workspace-cb09f895734a`（main `cb09f895`，含 #11/#12/#13/#10）。`git -C loaded_code_root status --porcelain` 空；`/api/health` `source_revision=cb09f895734a65a38ae23f04d940f18ece2959fd` 与该目录 `git log -1` 一致；`source_dirty=false`；`code_matches_repo=true`。启动器 `WORKBENCH_REPO_ROOT` 改指 runtime 软链（数据根仍 `FINANCE_WS`）。旧脏树 `07af9160a677`（**23 dirty @2026-08-15 03:0x**，其中 20 M + 3 未跟踪）未改、可回滚。pid 30091 |

> **该脏树计数随时间变化，引用时必须带测量时刻**（轨道 B Round 3 开工核对）：
> 轨道 B Round 2 报告记的是 **20 @02:13**（17 M + 3 未跟踪），本行记的是 **23 @03:0x**。
> 两者都对——差额是 `episode_protocol.py` / `test_episode_protocol.py` /
> `test_episode_verifier.py` 三个文件在 **08-15 02:17** 被改动（轨道 A 面）。
> 不带时刻地引用其中任一个数字，会被后来人读成两轨之一算错了。
> 附带一条时序事实：轨道 B Round 2 的 B′ 补跑（02:13:19–02:15:52）**早于**这三个
> 改动，故那批读数不受影响。
| `R-20260815-05` | Round 2 轨道 B 任务 3（源自 `R-20260804-02` refuted） | `EVAL_ONLY` | 08-03 那份真 rollout（`sha256=62385ee5…b316a7`）重过归一化器后 `function_call_output` 归入 `observe`；`unmapped` 由 264 降至**声明目标 ≤60**；新增一条真产物形状回归夹具 | `confirmed` | 实测 `unmapped 264 → 53`（≤60 ✅）；step 分布 `synthesize=127 / tool=42 / observe=42 / unmapped=53`，**tool 与 observe 恰好配平**；首个工具结果 `custom_tool_call_output` 落 `observe` ✅ 且 `source_event_type` 为语义类型而非信封名。剩余 53 中 43 个是 `token_count`（遥测，非控制面步骤，按契约正确保持 unmapped），其余为 `session_meta`/`task_started`/`task_complete`/`world_state`/`turn_context`/`inter_agent_communication_metadata`/`sub_agent_activity` —— **给这批补词表是另一个变量，本 PR 刻意不捆绑**。回归夹具 `test_real_rollout_envelope_shape_maps_instead_of_falling_to_unmapped`，`test_normalize_harness_trace` 31 passed |
| `R-20260815-01` | 标准 M1 分诊 F-002（Round 1 轨道 B） | `EVAL_ONLY` | 重放 19 个 run 目录后 `evidence_bound` 扩为三元组 + turn 级 `execution_state`：B4 读作 `retrieved=125,bound=0`、B3 读作 `retrieved=0,bound=0`、C2-C10 读作 `not_run`，三者不再同码 | `confirmed` | 用真实的 19 个 run 目录（非夹具）重放 `20260813T1810Z-qc28-full.json` 逐条自证：B4 `retrieved=125,bound=0` ✅；B3 `retrieved=0,bound=0` ✅；C2-C10 九题全 `not_run` ✅；三者落在 `retrieved_unsynthesized` / `no_evidence` / `not_run` **三个互不相同的值** ✅。五种状态各至少命中一例（delivered 11 / not_run 9 / bound_but_dropped 3 / retrieved_unsynthesized 3 / no_evidence 2）。实现在 `intelligence/eval/acceptance.py`，11 条新单测 + 既有 acceptance 套件 127 passed |
| `R-20260815-02` | 标准 M1 分诊 F-002（Round 1 轨道 B） | `EVAL_ONLY` | `status=error` 且 `trace_steps=0` 的 turn 不进入任何质量分母；同产物重算后 C 组分母由 10 降为 1（仅 C1） | `confirmed` | 同次重放：计入分母的 C 组题恰为 `['C1-future-date-no-data']` ✅。`summarize_execution_states()` 把 `quality_denominator` 与 `excluded_from_denominator`（逐题列名）写进 run 产物本身，剔除留痕 |
| `R-20260815-07` | Round 2 轨道 B（M2 F-001） | `EVAL_ONLY` | `bound_but_dropped` 细分出 `gap_zeroed`（有哈希且带 gap）与 `no_hash`（真缺口）后：重放 B1/B3 落 `gap_zeroed`；B7 同一 turn 内 `direct_answer`（0 哈希真缺口）与 `evidence_boundary`（13 哈希滑档）分别可见 | `confirmed` | 三个冻结 run 夹具逐字自证：B1@RunB → `gap_zeroed`（slots `gap_zeroed`/`gap_zeroed`/`no_hash`）✅；B3@RunB → `gap_zeroed`（三格全 `gap_zeroed`）✅；B7@RunA → `direct_answer=no_hash` 与 `evidence_boundary=gap_zeroed` **同一 turn 内分别可见** ✅。干净基线批 `20260814T1926Z-r3-clean-baseline`（`sha256=b712bd2e…d8d350`）另贡献 6 个 `no_hash` 真缺口格（A4 `evidence_boundary`、C6 `direct_answer`+`evidence_boundary`、C9 `chain_mapping`、C10-t3 `direct_answer`+`evidence_boundary`；勘误 E-r3-2，原稿漏计 C10 两格），**该批 `gap_zeroed` 出现 0 次**——R-001 部署后该形状未在本窗口再现，故 `gap_zeroed` 一侧仅由冻结夹具覆盖，未冒充有 live 样本。15 条单测绿 |
| `R-20260804-01` | 收口审计 §修复1 | `EVAL_ONLY` | 左短右长且左为前缀时 `compare_sequences` 不再抛 `IndexError`，返回 `equivalent_before_divergence`，evidence 含 `continues_on` | `confirmed` | `test_compare_sequences_survives_prefix_on_either_side`；两种传参顺序均返回 `synthesize @ ordinal=3` |
| `R-20260804-02` | 收口审计 §修复2 | `EVAL_ONLY` | 真 Codex rollout 中 `function_call_output` 归入 `observe`，与 workbench 的 `validate→observe` 对齐；第一个工具结果处不再出现**词表性**分叉 | `refuted` | 真 rollout `sha256=62385ee5…b316a7` 过 `normalize_harness_trace`：264/264 `unmapped`，无 `observe`/`tool`；三种 `--kind` 传法一致。`_codex_mapping` 读 `item.type`，真产物语义类型在 `payload.type`，四份跨月真 rollout 的 `item` 键出现次数均为 0。详见 §2026-08-15 Round 1 开工前回填 |
| `R-20260804-03` | 收口审计 §修复4 | `EVAL_ONLY` | 归一化产物能**独立**复现审计表第三列，不必回原始 receipt | `confirmed` | 重跑历史收据，5/5 `finish` 事件带 `status` + `stop_reason`，与 arm 级逐条对齐（`ruihuatai-valuation` 的已知不一致除外） |
| `R-20260804-04` | 收口审计 §修复A | `HARNESS_FIX` | 新 run 中仅 `headless_timeout` 的 case **不再**出现 `runtime_invalid_actions:N` | `confirmed` | `intelligence/eval/measurements/2026-08-04-budget-calibration/b-floor-ablation.json`：`ruihuatai-valuation`、`weekly-market-cause` 的 `runtime_result.payload.issues=["headless_timeout"]`，同题 `protocol_issues=[]` |
| `R-20260804-05` | 收口审计 §修复B | `HARNESS_FIX` | 新 benchmark artifact 的 `diagnostics.events[0].kind == "task"` 且 `sequence == 1`；其 payload 只有 `task_frame_hash`；题面不出现在 `events` 内 | `confirmed` | 跑真 benchmark CLI（合成 runtime，真实序列化路径）：`{"kind":"task","sequence":1,"payload":{"task_frame_hash":"432d9856…"}}`，题面确认不在 `events` 内。两条发射路径（`codex_headless_runtime:903`、`agent_episode:155`）均为 sequence 1 |
| `R-20260804-06` | 收口审计 §修复C | `EVAL_ONLY` | 新 run 若产生 `mode_decision` / `branch_*` / `finalization`，归一化后 `unmapped_count` 仍为 0，且 `mode_decision → plan` | `confirmed` | 同上收据归一化：10 事件 / **0 unmapped**，`mode_decision→plan`、`branch_started→retrieve`、`tool_request→tool`、`tool_error→observe`、`finalization→synthesize`、`finish→stop` 逐条命中 |
| `R-20260804-07` | 设计评审 G2 词表对齐 | `EVAL_ONLY` | 下一份 triage 报告的 `first_bad_step` 可与本仓 `first_divergence_step` **直接比较，无需翻译**；L1=`tool` 的 finding 在本仓可表达 | `confirmed` | `docs/verification/2026-08-04-budget-calibration.md`：`first_bad_step=stop`；三份 comparison 的 `first_divergence_step=observe/stop`，均为 `triage-l1-9` 且 `unmapped_count=0` |
| `R-20260804-08` | 设计评审 §仪器覆盖矩阵 | `HARNESS_FIX` | 补齐埋点后，`configure → intent → plan` 三步在 workbench 与 codex **两侧都非空**，`first_divergence_step` 首次具备行为含义 | `confirmed` | 两侧真实路径实测：workbench 真 turn 读 `trace.jsonl` → `configure→intent→plan→route→retrieve→synthesize→observe`；codex 跑 `CodexHeadlessRuntime.run()`（真 `_to_outcome`，仅 subprocess 用 fake stdout）→ `configure→intent→plan→tool→observe→observe→stop`。**门槛 3/3**，两侧共有由 1/9 升至 **4/9**。测试：`test_runtime_emits_configure_and_plan_landmarks_in_l1_order`、`test_turn_trace_exposes_configure_and_plan_as_their_own_l1_steps` |
| `R-20260804-09` | 标准 M2 分诊 F-001 | `HARNESS_FIX` | 显式 finalization handoff 后，瑞华泰进入 finalization 并以 `model_finish` 在 root 前结束 | `refuted` | `2026-08-04b-finalization/c-long-capped-t2.json`：事件级 `headless_protocol_rejected` / 135.555s，5 requests / 4 mailbox exchanges / 0 finalization；最后一个 in-flight `evidence_search` 无 result/error，交接未激活。wrapper 60s timeout 是静态支持的候选退出路径，非 artifact 直接读数 |
| `R-20260815-22` | 轨道 A Round 2 F-001 | `EVAL_ONLY` | ① 重放 R7-A7 冻结 FINAL_JSON 形状（`run_20260813_034211_544672`，两格 hashes+gap）经 `validate_episode_finish` 后 `caveat_slips` = 被搬运格数（2）；② 干净 finish（无 gap 或 gap 已在顶层）`caveat_slips=0` 且字段在场；③ 无哈希 gap 的拒绝路径不产生搬运计数，拒绝语义不变 | `confirmed` | `test_caveat_slips_replays_r7_a7_frozen_finish`、`test_caveat_slips_zero_on_clean_finish`、`test_caveat_slips_not_emitted_on_true_gap_reject`、`test_finish_event_exposes_caveat_slips_count`。R-001 跨组夹具：`test_r001_fixture_b5_all_slot_slip`、`test_r001_fixture_b7_mixed_true_gap_still_missing`、`test_r001_fixture_a6_all_slot_slip` |
| `R-20260815-21` | 轨道 A M1 F-001 | `DATA_CONTRACT_FIX` | 全格 `evidence_hashes`+非空 `binding.gap` 的 partial FINAL_JSON 经 `validate_episode_finish` 后，各格 `binding.gap=""`、原 gap 文本进入顶层 `gaps`；再过 `verify_episode_outcome` 这些格 `fulfilled`，issues 不再含 `required output reports gap:`。无哈希的 gap 仍被拒绝。绕过 validate 把 leftover gap 直接喂 verifier 仍 missing（判据不变） | `confirmed` | 干净基线批 `intelligence/eval/runs/20260814T1926Z-r3-clean-baseline.json`（B 分支，`sha256=b712bd2ee10fb431dba937416fb5882c6984ac65bb5421b5472f71c7ead8d350`，`generated_at=20260814T200212Z`，`revision=cb09f895`，`quality_denominator=28`）。轨道 A 独立重扫：C1 9 题 slips>0 全交付且 eb>0；C2 6 个真缺口格全 missing；C9 混合形（slips=1 + `chain_mapping` missing）同 turn。预注册原文未改。详见 `docs/verification/2026-08-15-trka-r3-r21-canary.md` §Post-batch closure 与母本 Round 3 批注 |
| `R-20260823-SPTTECH-01` | SPT 科技三臂 M2 R-001 | `HARNESS_FIX` | 同一冻结 replay 中，首次合成不再以 12s 窗口超时；**或** fallback 成功后 `finish/report business_status=complete`，且无 illegal `finalizing → research` | `confirmed` | 本轮 8792/8796 首次 synthesis 仍在 23.412s/20s 超时，但 fallback/repair 后均 `business_status=complete`，未见 `finalizing → research`；只确认原预测的第二个析取分支，尾延迟问题仍在 |
| `R-20260823-SPTTECH-02` | SPT 科技三臂 M2 R-002 | `DATA_CONTRACT_FIX` | `gate_receipt.issues=[]`；不支持的 evidence type 要么在模型输出校验时被拒绝重写，要么只留 report | `refuted` | 目标症状 `evidence_type_stripped` 已消失，但本轮 gate 仍分别有 7/15 条其他 issue，故原预测中过宽的 `issues=[]` 条件不成立；这是预测口径被证伪，不等于目标修复没生效 |
| `R-20260823-SPTTECH-03` | SPT 科技三臂 M2 R-003 | `HARNESS_FIX` | `answer.md` 不含内部 gate code；API/UI 同时可见 `transport=completed, business=partial` | `refuted` | 两臂 `answer.md` 仍把内部问题以“输出质检”拼入公开答案；8796 核心正文缩至 115 字且 15 条 issue，但 `business_status=complete` |

### fix_type refuted streak（作用域：本项目累计）

**不跨项目共享**：同一 `fix_type` 在别的被审系统上失败，不构成本项目升格的证据——
升格线要回答的是「**这个系统**的问题是不是不在我以为的那层」。跨项目的同类失败属于
skill 自身的方法论证据，走 `known-gaps.md`，不进本表。

| fix_type | 连续 refuted | 距升格线 |
|---|---|---|
| `SYSTEM_PROMPT_FIX` | 0 | 3 |
| `TOOL_DESCRIPTION_FIX` | 0 | 3 |
| `ROUTING_FIX` | 0 | 3 |
| `DATA_CONTRACT_FIX` | 1 | 2 |
| `HARNESS_FIX` | 0 | 3 |
| `EVAL_ONLY` | 0 | 3 |

计数规则：同 `fix_type` 的 `refuted` **连续**出现才累计，中间出现一次 `confirmed`
即归零。达到 3 时下一份报告的 `fix_type_refuted_streak` 必须写明已触线，并把架构 /
`HARNESS` 层列为本次的竞争假设之一。

截至 2026-08-04：`R-20260804-09` 是本项目第一条 `HARNESS_FIX` refuted，连续 streak=1。

截至 2026-08-15：`R-20260804-02` 是本项目第一条 `EVAL_ONLY` refuted，连续 streak 曾为 1。
Round 2 轨道 B 的 `R-20260815-01/-02/-05` 与轨道 A 的 `R-20260815-22` 均为
`EVAL_ONLY` confirmed，按「中间出现一次 confirmed 即归零」规则，`EVAL_ONLY`
streak 已归零（0/3）。Round 6 批 #3 将 `R-20260815-09`（`HARNESS_FIX`）confirmed，
同规则把 `HARNESS_FIX` streak 从 1（`R-20260804-09`）归零（0/3）。

截至 2026-08-23：SPT 科技三臂的 `HARNESS_FIX` 先出现一条 confirmed（重置旧 streak），随后一条 refuted，故当前连续 streak 仍为 1；`DATA_CONTRACT_FIX` 因原预测过宽的 `gate_receipt.issues=[]` 被证伪，当前 streak=1。两者均未触发升格线。

### Residual uncertainty（不是预测，是没结论的观察）

与 Open 表**分开放**：它们没有可证伪预测，不参与 streak，混进 Open 会污染命中率分母。

| 观察 | 状态 | 下一步取证 |
|---|---|---|
| `test_live_runner_uses_fresh_context_per_backend_without_cross_arm_state` 在一次全量跑中失败，其余多次（单测 / 整文件 / 后续三次全量）均通过 | 未归因 | 连跑 5 次全量记录命中率；若可复现再定位是哪个前序文件泄漏状态。**当前不归因到 2026-08-04 的改动**——它的断言不触及任何被改的面 |
| 收据的 arm 级 `stop_reason` 与事件级 `finish.payload.stop_reason` 在 `ruihuatai-valuation` 上不一致（`semantic_repair` vs `model_finish`） | 已记入 [trace-profile.md](trace-profile.md) §2 | 无需修复，属分层语义差异；跨 harness 比较一律用事件级 |
| `route` 在 codex 侧结构性不存在（episode 不做 skill 分派，backend 由 benchmark 选定、registry 固定） | 已记入 [trace-profile.md](trace-profile.md) §8 | 无需埋点。门槛已由四步收窄为三步——把结构差异写成埋点缺口，会诱导为满足指标而制造事件 |
| **`judge_status=unavailable` 把两种成因压成同一个值**：①「无稿⇒判官从未被调用」（液冷 `run_20260820_032014_595378`，`correlated_judge=null`）；②「判官被调用但 provider 报错」（`run_20260820_103042_376640`，`correlated_judge=false`，issue 为 `semantic judge transient provider error`）。两者公开 `judge_status` 完全相同，**只有 `correlated_judge` 的 null / false 能分开** | 2026-08-20 两发实测并列，未归因 | 读收据时不得只看 `judge_status` 判「判官挂没挂」。若要在字段层分开，最小埋点是给 `judge_status` 拆出 `skipped_no_draft` / `provider_error` 两个值（或加 `judge_skip_reason`）——本行只记观察，不提议改产品 |
| 批 #3 B4 验收 `timeout`/`eb=0`/`run_id` 空，仓外 `run_20260815_182037_434217` 已 `completed` 且三格 hashed | 已记入 `docs/verification/2026-08-15-r6-clean-baseline-3.md` E-008 | R-10 不改口径。是否让验收超时后回填已存在的 run_id 属排期，本轮不修 |
| 2026-08-16 长尾 off 有稿槽 `semantic judge transient provider error`（22/26）与 G01–G05 同形；零槽 `deadline exhausted` | 已记入 [trace-profile.md](trace-profile.md) §2 | 下一份 asked + 原始异常切开 H8/H9（`R-20260816-06`）。G01–G05 无 off 基准 |
| 十题窗核心集判断句机器列 0pp（诚实闸仍 uncheckable，公开正文常有「基准判断」） | 已记入 [trace-profile.md](trace-profile.md) §2 | 另案。不并进 R-11 |
| `#72` 判断槽 `model_reasoning` 后，同合同有的 run 仍给哈希（`post:L01:r1` n=35） | 已记入 [trace-profile.md](trace-profile.md) §2 | 不阻塞 R-11。要「每次必空」充分性才开 #72-only 臂（R-15 不依赖） |

### 溯源说明

`R-20260908-05` 来自用户授权的方法实验立案与应用实现，非单次 run 的四阶段分诊；不能作为已确认根因的 PRIMARY 引用。方法效果仅作描述性观察，不进入修复类型连续证伪统计。

`R-20260804-01..08` 来自 2026-08-04 的**代码审计 + 收口 + 设计评审**，不是标准四阶段
`agent-run-triage` 分诊：没有走 Triage → Static → Dynamic → Synthesis，没有分配
L0/L1/L2，也没有 3 条以上排名假设。因此这些条目**只有 `fix_type` 与
`verification_prediction` 可用于 streak 统计，不能当作已确认根因的 PRIMARY 引用**。

`R-20260804-09` 来自第一份标准 M2 分诊
[`docs/verification/2026-08-04-budget-calibration.md`](verification/2026-08-04-budget-calibration.md)，
已按 Evidence → Finding → Path、四条可证伪假设和冻结 taxonomy 定位
`F-001: LOOP/stop/execution-error-category-timeout`；它可以作为后续 Prior prediction
closure 与 PRIMARY 证据引用。

`R-20260815-21` 来自轨道 A 标准 M1 分诊
[`docs/verification/2026-08-15-trka-repair-finish-gap-slip.md`](verification/2026-08-15-trka-repair-finish-gap-slip.md)，
PRIMARY=`HARNESS/configure/task-instruction-category-non-compliance`。Round 3 开批前预注册
C1/C2/C3；Round 4 按预注册原文收口为 `confirmed`（批 `sha256=b712bd2e…`，9 题 slips
全交付，6 个真缺口格仍 missing）。它可以作为后续 Prior prediction closure 与 PRIMARY
证据引用。轨道 A 不回写 `R-20260804-02` / `R-20260804-10`。

`R-20260815-22` 来自轨道 A Round 2 标准 M1
[`docs/verification/2026-08-15-trka-r2-caveat-slips.md`](verification/2026-08-15-trka-r2-caveat-slips.md)，
PRIMARY=`HARNESS/stop/local-missing-caveat-slips-count`（EVAL_ONLY 观测洞，不改判定）。
三条离线断言均已兑现，故进 Closed；`EVAL_ONLY` refuted streak 因中间出现
`confirmed` 归零。轨道 A 不回写 B 轨行与 R-10。

`R-20260815-23` 来自轨道 A Round 4 标准 M1
[`docs/verification/2026-08-15-trka-r4-evidence-ordinals.md`](verification/2026-08-15-trka-r4-evidence-ordinals.md)，
PRIMARY=`HARNESS/configure/task-instruction-category-non-compliance`（终局契约逼模型
誊抄 16-hex `content_hash`）。离线门已绿。Round 6 批 #3 live 臂由检阅方收口
`confirmed`（hash-reject 0；修复路径 14/15 验收 eb>0；B8 不同形）。不回填 B 的 R-09
（该行已由执行方按字段在场性关闭）。

`R-20260815-24` 来自轨道 A Round 5 标准 M1
[`docs/verification/2026-08-15-trka-r5-e007-split.md`](verification/2026-08-15-trka-r5-e007-split.md)，
PRIMARY=`HARNESS/synthesize/orchestration-related-errors-category-reasoning-mismatch`
（`_marker_loss_partial_public` 删已 fulfilled 格正文并设 `gap_output_ids`，不收缩绑定）。
2026-08-15 特性分支 `fix/r24-marker-loss-binding` 已实现收缩：lost 格在
`semantic.verified` 上改为 `missing` 并清空绑定哈希。outcome 仍 `pending`，
等独立部署窗 + 下一批 live。不改 adapter 去给已删正文发引用；不改
`acceptance.py` 的 `episode_fulfilled_hashed` 口径（该字段继续读结构快照，
历史夹具 `b3-r4-batch2-episode.json` 的 efh=2 vs eb=0 保持冻结）。

`R-20260815-26` 来自 S10 Phase A 标准 M1
[`docs/verification/2026-08-15-s10-branch-activation.md`](verification/2026-08-15-s10-branch-activation.md)，
outcome=`ROOT_CAUSE_NOT_CONFIRMED`（冻结集调用率 1/5，原「零调用」未复现；三条机制未分出全班 PRIMARY）。
本行只锁定评测夹具。报告里的 `R-027`/`R-028` 是 Phase B 候选，未进 Open——未确认根因不得把 ROUTING / SYSTEM_PROMPT 写成已确认预测。

`R-20260815-25` 来自同一份 Round 5 报告的并行缺陷 F-003（`tool_exception` 吞 `detail`），
`HARNESS/observe/context-handling-error-category-context-handling-failures`。
离线门已绿；批 #3 数据层健康，零 `tool_exception` 样本，outcome 保持 `pending`（unobserved）。
本轨只出数，不改该行。

`R-20260815-09` / `R-20260815-10` 来自轨道 B Round 3 标准 M1
[`docs/verification/2026-08-15-trkb-r3-clean-baseline.md`](verification/2026-08-15-trkb-r3-clean-baseline.md)，
Round 6 批 #3 按预注册判据收口为 `confirmed`（报告
[`docs/verification/2026-08-15-r6-clean-baseline-3.md`](verification/2026-08-15-r6-clean-baseline-3.md)）。
R-09 用字段在场性 + B8 非空拒收码；R-10 用三批 `evidence_bound>0` 交付率。
本轨不回写 R-23 / R-24 / R-25。

`R-20260816-01..05` 来自标准 M1 分诊
[`docs/verification/2026-08-16-outlook-verification-budget-regression.md`](verification/2026-08-16-outlook-verification-budget-regression.md)，
outcome=`ROOT_CAUSE_NOT_CONFIRMED`，PRIMARY=`UNCLEAR/synthesize/DEPTH_INSUFFICIENT(D4)`。
它可以作为后续 Prior prediction closure 引用，但不能当作已确认单一刀（#72/#75/#79）的 PRIMARY。
#84（`21dbf6c1`）落地 R-01 埋点与 R-04 夹具；R-04 已 Closed。R-01 仍等带 `timeout_asked` 的同形 live run。

`R-20260816-05` 在
[`docs/verification/2026-08-16-outlook-off-arm-typology-judge-case.md`](verification/2026-08-16-outlook-off-arm-typology-judge-case.md)
按 45 槽三元组收口为 `confirmed`。同报告立 R-06（judge `timeout_asked`）、R-07
（书面豁免：禁无实测抬 T/30）、R-08（G0x 无 off 基准）、R-09（60s reserve
杠杆须 08-08 实测）。R-02 因未动预算保持 pending。R-03 45 槽已否证充分条件，
单变量仍 pending。8795 identity 收齐后 R-01/R-06 仍 pending（形状未再现 / judge 字段仍缺）。

`R-20260816-11` **开行**来自十题窗收据 #94 + 检阅 #96，当时不是四阶段分诊。
**结案**来自标准 M2 `docs/verification/2026-08-16-outlook-eb-judgment-slot.md`
（`validate-report.sh` RC=0）。PRIMARY 可引用该 M2，不可引用 #94/#96 开行文字。
`R-20260816-15` 是该 M2 的量具修复行。2026-08-16 离线分层已算（三对 post=1.00，
main42 +5.3pp 未入 ±5），outcome 仍 pending；收据
`docs/verification/2026-08-16-outlook-eb-r15-rescore.md`。该收据不是新 PRIMARY。

`R-20260816-16`..`21` 来自生产线交接
[`docs/handoffs/2026-08-16-provider-outage-and-glm-failover.md`](handoffs/2026-08-16-provider-outage-and-glm-failover.md)
（分诊全文 `/tmp/triage-run_20260816_221823.md`，`validate-report.sh` RC:0）。
本 PR 只开行与重编号。dsh 草稿曾把同一事故写成 `R-06`..`11`——那些号在本账本
已有含义（R-06/R-11 Closed），**作废那份编号**。这 6 行的 `fix_type` 与
`verification_prediction` 可进 streak；在本仓四阶段报告合入前，**不能当 PRIMARY 引用**。

`R-20260818-01`..`04` 于 2026-08-18 收口，收据见
[`docs/verification/2026-08-18-caliber-pure-ruler-28q.md`](verification/2026-08-18-caliber-pure-ruler-28q.md)
与各 Phase 收据 `docs/verification/2026-08-18-caliber-phase*.md`。

- **R-01 `confirmed`**：由**独立验收方**（非实施方）复算，不是抄实施方收据。同一份
  `20260818T051630Z` 与 `20260815T1005Z` 各重算一次，**变化题数均 = 2 且只有 B7 / C1**
  （08-18 ❌❌→✅✅；08-15 ❔❌→✅✅），A1 保持 ✅；正反单测与变异测试（注释掉万亿展开
  → B7 回到 ❌）均绿。两份复算与实施方 `/tmp` 下原始输出**逐字节相同**。
  自证：两份基线各解析 28 题、真值列非空 28。
- **R-02 `partially_confirmed`**：预测正文（A3 的 `close=12.11` 出现在答案）**兑现**；
  同行判据里的「可判分母 ≥22」**未兑现**（纯尺子实跑 18/28），该判据已按
  spec §8.1 裁决一改判为观察项。**不整条写 confirmed。**
- **R-03 `partially_confirmed`**：字段非空、脱敏（`tool_result` 载荷内绝对路径 0 处）、
  体积（184 KB vs 旧 264 KB）三项兑现；「每条 fact 失败能二选一」**只部分兑现**——
  A5 能标 retrieve、A10 能标 synthesize，但 C4/C5 走的路径**没有 episode `tool_result`**，
  仍是 unknown。
- **R-04 `held`**（不是 refuted）：#202/#203 确有产品侧改动，但本绊线的措辞只管
  「**自称修「B7 回归」**的 PR」，两张都不自称修 B7。产品侧改动的授权补记见 spec §8.1 裁决二。

> 本批留下一条方法论：**看板自带的「fact 层 0% 翻转」方差校准被实测证伪**
> （同尺子下 A4 / A6 / B6 在两份 run 间翻转）。此后 `n=1` 的真值差异不得直接写成归因；
> 本批只有 C3 因走确定性罐头短路才敢归给产品。

`R-20260821-09` 来自 spec #300 W3（形状 D 收口），不是标准四阶段分诊。
它升级 R-05 台账里「个股数值缺证回填市场总览」那条候选观察。
`fix_type` 与 `verification_prediction` 可进 streak；开行文字不能当 PRIMARY。

对应审计记录：
- [docs/verification/2026-08-03-cross-harness-shared-layer-audit.md](verification/2026-08-03-cross-harness-shared-layer-audit.md)
- [docs/verification/2026-08-04-improvement-loop-design-review.md](verification/2026-08-04-improvement-loop-design-review.md)
- [docs/trace-profile.md](trace-profile.md) §2 字段陷阱、§6 投影契约、§8 仪器覆盖矩阵
- commit `09657e2a`
