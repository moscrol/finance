# Prediction Ledger: finance-workspace-private

- last_updated: 2026-08-27（21:00 P0 复跑回填：`R-20260827-07` **改号 `-07a`**（预注册落分支期间 main 经 #462 落了 export 事故同号行，按 `-03a` 先例改号、工单引用同步）并 **→ refuted**——两臂+冻结原始三 run `ablation_activation_step=none`，但非预写形状：controller `unparsable_response` 一次失败即降级 chat 零检索，检索计划从未生成，#454 装没装上轮不到问；归因升格 controller 层，**不并入 `-09`**，修复+复验预注册 `R-20260827-10`（分支 `fix/turn-controller-unparsable-fallback`，重试一次+留首次原文+显式日期检索地板，TDD 6 钉先红后绿、变异 3/3）。发生面：8792 生产 39 run 中 4 个 unparsable 恰=全部 chat lane（B6/C8/D6/D9），D6 3/3 复现=题面相关。与 `-08` 同反模式（LLM 组件失败→粗标签留下、载荷丢弃、无重试），streak 关注。收据 `~/.finance-runtime/p0-d6-20260827/`。17:55 预注册 `R-20260827-07/-08/-09`：四臂对照（`~/.finance-runtime/four-arm-20260827/`，unseen 集 react 0.857 vs 8792 0.567）D6/D2/D5 三题差距收口，工单 `docs/superpowers/specs/2026-08-27-longtail-react-gap-remediation-workorder.md` 同批落地——发现此前全部留在 runtime 目录、docs/ 零字提及，正是「账本住址漂移则闭环静默断裂」的现场，本次补上。05:20 P1 收口：**#445（P1 三件）+ #447（证据页载荷修复）已合并，8792 已切 `40fd5a847c65`（27d）**，health 三读一致 / readiness 13/13 / 长电 grounded completed / 简报生产 run payload=dict·4 袋·数字⊆载荷。`R-20260827-01/-02` → confirmed（读数在行内）；`-03` pending（原生注册表四绿被他人在途 capability-switchboard 交接脏文件阻塞主树前移，CI 语义已 4/4×3 轮，不代解）。**live 首验逮到 P1b 真缺陷并当轮修复**（详见 -02 行）。今晚并发切流两起（03:06 #444→35e1b291、~03:45 #443→47cf855d），本 session 27c（67c88b27）被超越属正常并发，最终态 27d 含全部。备份 post441/post447 两份。教训两条：管道 `| tail` 吞 git 退出码曾让链切在 worktree add 失败后继续走（靠 launcher fail-closed + 补建目录恢复，服务中断约 2 分钟）；harness 壳一次楔死在 bootstrap `cat <&3`（35 分钟假等待，杀后重跑，读数无污染）。02:50 用户裁决切流：8792 已切 `67c88b27b75b`（27a），三项验证全过、回滚锚与备份在位，自选简报生产门冻结题过（读数见 inflight/main.md 02:50 行）；切流把 #427 首次送进夜跑运行时（`FINANCE_CODE_ROOT`=runtime 符号链，plist 实证），今晚 18:30 夜跑自此才是 `R-20260826-04` 的干净判据。01:55 验收收口：**#439 已合并 @`547653c4`**，`R-20260826-05/-06/-07` live 过 → 全部 confirmed（收据在各行内）；批次门禁四叶全绿 @`547653c4`：pytest 6654P/0F/12S + 前端四连 + e2e 15（8811 端口 + venv PATH）+ registry 4/4；**8792 未切**（spec §10 本单默认不切）待用户裁决；真画像 linxiaoqi5111 已钉（watchlist=飞书自选股表 13 只逐字，派生题材 10 个 n≥4，focus_themes 留空待手钉）。21:35 预注册 `R-20260826-05`…`07` 自选简报包（watchlist_digest）：原会话预注册号 -01…-03 与当日其他 session 撞号，实施分支 `feat/watchlist-digest-pack` 改号入表；离线 24 钉已绿、live 未跑、三行均 pending。20:05 追加 `R-20260826-04`：夜跑 sector-daily EMFILE——**归因更正**：非「上游数据未就绪」而是 fupanhui 直连 401 风暴下 HTTPError 持 socket 等 GC（与 -03 同族、同日第二例），修复 #427 已合；19:32 并行 session 手动补跑已换名进生产、readiness 13/13，但高 ulimit 壳成功不作 confirmed 依据，干净判据=明晚 launchd 夜跑，本行 pending。19:20 状态：#417/#418 已合并、8792 已切 `c0226f34`，`R-20260826-01/-02/-03` 全 confirmed（-02 带成立条件：sw_l1 映射缺口 119/403，回填工单 #429 已立）。实测目录 `~/.finance-runtime/trace-diff-spt-forward-20260826/`、`~/.finance-runtime/boundary-probe-20260826/`、`~/.finance-runtime/cutover-20260826f-8792/`。）
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
| `R-20260827-10` | P0 D6 复跑分诊 2026-08-27（`-07a` refuted 的归因升格：controller `_parse_llm_decision` 一次解析失败即 `_safe_fallback(chat, needs_retrieval=false, detail="")`，`_enforce_task_frame_route` 因关键词分支漏「高标股/晋级/空档」不生效——8792 生产 39 run 中 4 个 unparsable 恰=全部 chat lane（B6/C8/D6/D9），D6 3/3 复现=题面相关；收据 `~/.finance-runtime/p0-d6-20260827/`。实施分支 `fix/turn-controller-unparsable-fallback` @ `111af0f7`，与 `-08` 同反模式的 controller 侧修复） | `HARNESS_FIX` | 三道修法后：① 解析失败重试恰一次（坏输出贴回+纠错指令，provider 挂不重试）；② unparsable 的 `llm_failure_detail` 留首次原文（声明式截断 200 字）——下一个 unparsable 的 run 可验尸；③ `task_frame_requires_retrieval` 显式日期地板（timeframe/题面含完整日历日期即需检索，月份粒度不触发、model_reasoning 豁免优先）。live 预测：修复树复跑 D6 frozen 题面，controller 步不再落 `chat+needs_retrieval=false`（重试成功路由检索车道，或 fallback 被地板拦成 research），trace 出现 tool 步；届时按 `-07a` 原判据检验 #454（finance_query 出现 `dataset=limit_advance_daily`）。失败形状 ①：地板拦住（needs_retrieval=true）但检索计划仍不选连板表 → 回到「装了没用」，升格检索计划层与 `-09` 合并归因；失败形状 ②：controller 出牌正常但 D6 rate 仍 0 → 合成/判分层，另立 | 离线：TDD 6 钉先红（收据 `20260827T121838Z-fea0633e`）后绿（`20260827T122000Z-fea0633e`，135P）；变异 3/3 精确击杀（删日期地板→恰 3 钉红；删重试→恰 2 钉红；detail 置空→恰 2 钉红，变异前提交 `111af0f7`）。live：修复树起临时服务复跑 D6，对照 `-07a` 读数（三 run 一字不差的 unparsable-chat）做单变量自对照（变量=本修复），结论携带 revision 条件 | `pending` |
| `R-20260827-09` | 工单 `docs/superpowers/specs/2026-08-27-longtail-react-gap-remediation-workorder.md` §P2-D5（四臂对照 D5 三产品臂 0.0 vs react 1.0；react 首跳 `graph_lookup` 实体解析 [实测 session.json 5 跳序列]，8792 侧仅见 6 次粗粒度 `research`、载荷未取证；main 无对应改动。**预注册非四阶段分诊**，归因假设待 M2，只供 streak） | `HARNESS_FIX`（暂定；本行预测的是归因走向，M2 定层后如改判 ROUTING_FIX 须更新本行并留档） | 跨臂 M2（按工单 §P1 映射表对齐 8792 `run_20260827_134712_662543` 的 continuous-episode research 载荷 vs react calls）将把 8792 的缺口定位在 retrieve/tool 前缀——**从未发出实体解析类查询**，而非 synthesize/判官段。失败形状 ①：8792 实际发过 graph_lookup 但结果空/被丢 → DATA_CONTRACT 层，本行 refuted 重立；失败形状 ②：D5 同样被判官扣留（judge_status=unavailable）→ 并入 `-08` 族，本行 refuted | M2 报告 `validate-report.sh` RC:0 且 residual_uncertainty 含 plan/observe 两条损耗（映射表门槛 2/3 的显式声明）；确认后修检索计划层再自对照复跑，D5 按 machine-truth 该 case checks 复打 ≥2/3。⚠ D6 复跑教训（`-07a`）：controller unparsable 降级会让「从未发出某类查询」在 plan 之前就成立——M2 定层前先查 controller 步 `llm_failure_reason`，排除同因 | `pending` |
| `R-20260827-08` | 工单同上 §P2-D2（[实测] 8792 probe `run_20260827_152937_309324`：`judge_status=unavailable` + `semantic judge provider error` + `verified_status=partial` + `terminal_phase=evidence_gap_fallback`；生产同形 8/38=21%；main 现状 `_stable_semantic_judge_error` 瞬时档仅认 `empty_model_response`，grok CLI **类名**串被 invalid 分支抢走判永久；修复 `b614daf0` 在 `fix/range-cutoff-and-judge-fallback` 未合。**预注册非四阶段分诊**，先验假设=掉在判官层非作答层，M2 拿到 trace 才能定，只供 streak） | `HARNESS_FIX` | `b614daf0` 合并+切流后同题复跑：`judge_status ≠ unavailable`、`verified_status=verified`、D2 rate 0.25→≥0.75；生产下一个 38-run 等宽窗口 `judge_unavailable ≤ 3/38`。搭车判据（同 commit 修缺陷 D-1）：区间题 `requested_information_cutoff` 取终点、D10 复跑 rate>0（当前三臂 0.0）。失败形状：retryable=True 但三连重试仍失败 → 判官容量/超时层而非分类层，本行 refuted 另立；若跨臂 M2 发现 8792 在 retrieve/tool 前缀已分叉 → 先验假设翻车，本行 refuted 重立 | 跨臂 M2 只做假设生成（模型/引擎双混杂声明在工单 §1），确认走自对照：合并前后同题复跑单变量=`b614daf0`；合并走正常 PR（CI 绿才可合），红线「未经复核的草稿不出稿」不动 | `pending` |
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
| `R-20260816-13` | 宽题取证饿死 M1（`run_20260816_205439_732198`，2026-08-16 20:54 生产首发实测） | `EVAL_ONLY` | 8795 含工具批埋点 tip 重放：每发 `tool_request` 带 `batch_grant_asked`/`stage_timeout_granted`/`episode_remaining_at_dispatch`/`remaining_slots_at_dispatch`/`turn_elapsed_at_dispatch`。**deep 自然完成值合计 > standard 总窗 → H-a**（架构支，不调参）；**evidence_search 自然时长 ≤10s 且失败仅与 dispatch 授予≤0 / slot 耗尽相关 → H-c**（顺序/信号）。缺字段不得结案。工具批读数对 `R-20260816-11` 冻结样本是**移交证据**（其独立 PRIMARY 候选之一），eb 结案权在 R-11，本行不代结 | 判定不得混入 R-10 判据（同侧车不同读数）；`tool_timeout`（时间闸 `episode_tool_batch.py` L355-366）与 `tool_budget_exhausted`（次数闸 L340-352）分开计 | `pending` |
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
