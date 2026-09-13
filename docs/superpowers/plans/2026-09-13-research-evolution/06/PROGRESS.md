# 06 · Workbench 集成与验收 · 进度（换会话先读这里）

> 总合同 `docs/superpowers/specs/2026-09-13-research-evolution/README.md`，本轨 spec 同目录 `06-workbench-integration.md`
> （规格提交 `194241dd`，交接 `28804505`，分支 `docs/river-next-specs`，已合入本组合分支）。
> 跨轨缺口与未做项写同目录 `BLOCKED.md`。

## 状态一句话

**engineering_complete：是。** 四个端点接真实 01–05，前端「维护」页可用，单 writer 与两个受控入口有测试。
**product_verified：部分**——I01–I12 / I16 在真实 API + 真实模块 + 临时用户态上走通并有反向证伪；
I13 / I14 / I15 未验（缺真人参与者、浏览器可见性事件、已授权结果源，逐条见 BLOCKED §3）。
**field_evidence：无。** 没有冻结任何真实前向协议，没有任何真人试点数据；03 一律 pending，05 `commercial_status=unstarted`。

## 任务 0 · 开工登记（2026-09-13）

| 项 | 值 |
|---|---|
| 工作树 / 分支 | `/Users/a77/fwp-wt-research-evolution-06` · `feat/research-evolution-06-workbench` |
| 代码基线 | `gitea/main` = `631786ab362f4c2118f65b6a1373ccddb7b0271d`（比总合同所记 `5fb13a8c` 新 3 个合并；重新 fetch 后核对） |
| 组合基底 | `5f931258` = 基线 + 依次 `--no-ff` 合入规格分支与 01–05（六次 `merge-tree` 预演与实合**零冲突**，149 文件 / 27450 行新增） |
| 各模块分支与 SHA | 规格 `docs/river-next-specs@28804505`；01 `feat/judgment-maintenance-01@e8db50db`（代码 `9735103c`）；02 `feat/research-priority@a7c9dec1`（代码 `add35fc8`）；03 `feat/research-validation-03@f2a12fa3`（代码 `49197160`）；04 `feat/research-diagnostics-04@b5cee17a`（代码 `4d457d7a`）；05 `feat/research-evolution-05-product-value@46ea6cdd` |
| 解释器 | 主树 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（3.12.13）；前端 e2e 需 `PATH=.venv-workbench/bin:$PATH` |
| 实际用户态根 | `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`（真实用户 `a77` 与若干 probe 用户）。本轨代码**只**经 `userspace.user_space(user).root` 解析；测试与 E2E 一律临时目录，未读写任何真实用户记录 |
| 生产服务 8792 | PID 59347，cwd `~/.finance-runtime/finance-workspace-2ee664fae9c4`，`source_revision=2ee664fa`（部署家，非任何工作树）。**本轨不接管、不重启**；隔离 E2E 用 8797 |
| 代码地图 | 主树 `ready n=22076 @b4a35fa`；本轮按精确文件与符号定位，未以地图无结果断言缺失 |

### 计划修改路径（= 实际）

新增 `intelligence/services/research_evolution/{__init__,contracts,access,store,adapters,facade,pilot_io,study_io}.py`、
`intelligence/api/research_evolution.py`、`intelligence/webapp/src/components/ResearchEvolutionPanel.{tsx,test.tsx}`、
`researchEvolution.css`、`intelligence/webapp/e2e/research-evolution.spec.ts`、
`intelligence/tests/test_research_evolution_{api,falsification,store,io}.py`、`intelligence/tests/research_evolution_fixtures.py`、
`intelligence/tests/fixtures/research_evolution/06/`。
薄改 `intelligence/api/app.py`、前端 `App.tsx` / `api.ts` / `types.ts` / `ResearchInspector.tsx` / `components.test.tsx`。
公共文档 `docs/learning/ledger-map.md`、`docs/agent-product-door.md`、`UBIQUITOUS_LANGUAGE.md` + 能力图谱。
**未改** 01–05 目录内实现、`market_feature_store/schema.sql`、交易日历、LLM 模型 / 预算、全局路由 / 注册表、任何旧台账。

## 步骤状态

| 步 | 内容 | 状态 | 证据 |
|---|---|---|---|
| 0 | 基线 / 组合基底 / 所有权 / 用户根 / 8792 归属 / 各模块 SHA 与签名 | 完成 | 上表；六分支 `merge-tree` 零冲突 |
| 1 | 只读适配、访问校验、单 writer、GET 投影 | 完成 | `916f7e6f` |
| 2 | 接 01 真模块：绑定 → 变化 → 复核 → 继续核查 → 关联 run 终态 | 完成 | I01–I04、I08 |
| 3 | 接 02 / 04 真模块；05 事件；03 收据与曝光登记 | 完成 | I03、I05、I07–I09、I16 |
| 4 | 前端三个内容区 + 组件测试 + E2E | 完成 | `6137dcd9` / `0b03f84e` |
| 5 | 全链 I01–I12 / I16 与三项反向证伪；重启重建 | 完成 | I10、`test_research_evolution_falsification.py` |
| 6 | 受控入口 `pilot_io` / `study_io`；台账地图 / 产品门 / 术语表 / 能力图谱 | 完成 | `e0dec906`；本文「收据」节 |

## 接线矩阵

| 模块 | 入口 | 真实/夹具 | 场景 | 结论 |
|---|---|---|---|---|
| 01 判断维护 | `assess` + `reduce_actions` + `validate_action` + `parse_binding` + `adapters.*` | **真函数**；证据目录为固定输入 | I01–I04、I08 | 哈希变 → `requires_review`；条件三值；动作幂等与 409 |
| 02 研究排序 | `adapt_candidates` → `prioritize` → `render_view` | **真函数**；`evaluation_at` 服务端可信 UTC | I03 | 01 真实项进第一组；点击带 `click_payload` |
| 03 方法验证 | `Repository` + `record_exposure`（+ `study_io` 调 freeze/register/settle/evaluate） | **真函数**；无真实协议 | I07、I16、I15(未验) | 未冻结 → `unknown(no_study_frozen)`；揭示前原子登记曝光 |
| 04 流程诊断 | `diagnose` + `evaluate_exercise_response` + `adapters.load_legacy_inputs` | **真函数**；策略/题包为合成登记件 | I09、I16 | 无策略 → `unknown(policy_not_registered)`；合成标 `synthetic` |
| 05 使用测量 | `validate_event` + `prepare_events` + `measure_pair` + `summarize` + `RunStoreEvidenceReader` | **真函数**；事件为合成 | I08、I11、I13(机制) | 前端只能报白名单类型；服务端盖章；失败 run 入分母 |
| 既有入口 | `research_project.load_project`、`POST …/messages`、`RunStore`、`ConversationStore` | **真实** | I12 | 逐字节不变；`research-project` 端点回归通过 |

## 合同版本与关键设计决定

- 封套 `research-evolution-view/v1`：`maintenance` / `priority` / `diagnostics` 各保持自己的 schema，不压成总分；
  `module_status` 五段（`ok` / `unknown` / `pending` / `error` / `unavailable`），`gaps` 带 `module`。
- **`view_digest` 只摘要内容**：剔掉 `generated_at` / `evaluation_at` / `report_id` / `input_digest`
  （后三个由服务端时钟派生）。不剔就是同样内容每秒一个新摘要，spec §4.4「GET 的报告摘要稳定」落空。
- **错误外壳沿用本仓既有的 `{"detail": ...}`**，内层放稳定业务码 `{code, message, detail}`；
  响应统一经 `scrub_paths` 擦绝对路径（本仓已有 `"/Users/" not in response.text` 的断言家族）。
- **归属**：`?user=` 不是认证。`cf_access` 模式下中间件已改写 `user`，直接采信；`off` 模式只认
  服务配置用户 + `RESEARCH_EVOLUTION_ALLOWED_USERS` 白名单，越界一律 `owner_forbidden`；
  他人对象与不存在对象返回**同一个** `not_found`，不泄漏存在性。
- **两次取数**：绑定时按当天 cutoff 解析到的真实版本存进绑定记录（baseline），view 时按今天的 cutoff
  重读**同一个 ref**（同一 `as_of` 的切片）。绝不声称知道原判断当天的版本。
- **管理动作不冒充事实**：`reviewed_no_change` 只关闭维护项；`link_run` 要求 run 已终态，
  且 completed 时必须指到**原写入者写下的**新判断行，否则拒绝关闭。
- **不可变件不加字段**：`publish_immutable` 不往正文塞 `owner_user_id`——那会打坏内容寻址件自己的哈希。
  归属靠路径隔离（每个 owner 一个根）。
- 自用测量事件的 `protocol_version = workbench-self-use/v1`、`pilot_id = workbench:<conversation_id>`：
  05 的 `summarize` 按 `pilot_id` 分区，自用事件永远混不进真人试点读数。

## 过程中修掉的四个真 bug

| # | 症状 | 根因 | 钉住它的测试 |
|---|---|---|---|
| 1 | 每条维护项的**第一个**动作都返回 409，且错误里前后两个版本号一模一样，看起来像并发 | `int(expected_revision or -1)`：合法的修订号 **0** 是假值，被当成缺省 | `test_i04_same_key_replays_once_and_stale_page_gets_409` |
| 2 | 绑定基线取到了**晚于绑定时刻**的版本，于是「跟踪后被改」这条线永远不成立 | 证据目录按 ref 去重时取插入顺序最后一条 → 基线随取数顺序漂 | `test_i01_binding_keeps_original_timestamp_and_never_backfills_strict` |
| 3 | 同样内容每秒得到一个新 `view_digest` | 摘要覆盖了 `evaluation_at` 及其派生 id | `test_i10_view_digest_is_stable_but_tracks_content` |
| 4 | 冻结协议存盘后再读，05 报「protocol_hash 与内容不符（冻结后被改过？）」 | `publish_immutable` 往内容寻址件正文里 setdefault 了 `owner_user_id` | `test_pilot_rebuild_is_reproducible_and_never_upgrades_synthetic_to_real` |

## §7 验收场景对照

| 编号 | 状态 | 测试 |
|---|---|---|
| I01 | 通过 | `test_i01_binding_keeps_original_timestamp_and_never_backfills_strict`、`_evidence_refs_must_come_from_the_controlled_catalog`、`_catalog_hides_versions_recorded_after_the_cutoff` |
| I02 | 通过 | `test_i02_hash_change_is_needs_review_not_refuted_and_close_leaves_judgment_untouched` |
| I03 | 通过 | `test_i03_triggered_condition_ranks_first_and_rejudge_carries_scope_into_a_real_turn`、`_task_selection_records_the_click_without_changing_any_verdict` |
| I04 | 通过 | `test_i04_same_key_replays_once_and_stale_page_gets_409`、`_snooze_expires_back_to_open_without_losing_the_item` |
| I05 | 通过 | `test_i05_missing_inputs_stay_unknown_and_never_collapse_to_zero` |
| I06 | 通过 | `test_i06_unauthenticated_mode_refuses_arbitrary_user_switch`、`_other_users_conversation_is_not_found_not_forbidden`、`_path_traversal_is_rejected_without_leaking_paths`（5 条路径参数化）、`_allowlist_lets_an_explicitly_permitted_user_through` |
| I07 | 通过 | `test_i07_no_probability_promise_on_the_default_panel` + 前端 `不出现概率承诺或「方法已验证」徽章` |
| I08 | 通过 | `test_i08_frontend_events_are_stamped_by_the_server_and_deduped`、`_frontend_cannot_self_report_success_quality_or_money`、`_failed_run_cannot_be_laundered_into_a_closed_item`、`_completed_run_without_a_new_judgment_cannot_close_the_item` |
| I09 | 通过 | `test_i09_diagnostics_needs_a_registered_policy_and_marks_synthetic`、`_answer_key_is_not_in_the_default_projection` |
| I10 | 通过 | `test_i10_bindings_and_actions_survive_a_restart`、`_one_broken_module_does_not_blank_the_others`、`_view_digest_is_stable_but_tracks_content` |
| I11 | 通过 | `test_i11_core_flow_works_with_no_measurement_events_at_all` |
| I12 | 通过 | `test_i12_existing_research_project_endpoint_is_unchanged`、`_the_whole_flow_leaves_every_legacy_ledger_byte_identical` |
| I13 | **部分**（机制通过，无真人数据） | `test_research_evolution_io.py` 六条（幂等、整批拒收、渠道盖章、rebuild 同内容 id、synthetic 不升级） |
| I14 | **未验** | 见 BLOCKED §3 |
| I15 | **部分**（拒收侧通过，未走完一轮） | `test_study_io_refuses_input_packs_that_try_to_backfill_the_clock`、`_settle_without_an_authorised_outcome_source_fails_closed` |
| I16 | 通过 | `test_i16_reveal_records_exposure_before_returning_the_answer` + 反向证伪 `test_reveal_is_refused_when_the_outcome_identity_cannot_be_parsed` |

### 反向证伪（spec §7 要求至少三项）

| 植入的偷懒实现 | 必须变红的场景 | 测试 |
|---|---|---|
| 不调 01，返回固定空报告 | I03 | `test_faking_the_maintenance_report_breaks_i03` |
| 去掉归属校验，请求里的 `user` 直接当 owner | I06 | `test_dropping_the_owner_scope_check_breaks_i06` |
| 把失败 run 当成没发生（只认 completed） | I08 | `test_filtering_out_failed_runs_breaks_i08` |
| （本轨自加）盘面读数换一个值 | 条件判定必须跟着变 | `test_condition_wiring_is_live_not_a_constant` |

## 收据

| 命令（工作树 `/Users/a77/fwp-wt-research-evolution-06`） | revision | exit | 结果 |
|---|---|---|---|
| `pytest -q intelligence/tests/test_research_evolution_*.py` | `e0dec906` | 0 | **63 passed** |
| `ruff check intelligence/` | `e0dec906` | 0 | All checks passed |
| `scripts/layer_audit.py` / `check_path_literals.py` / `check_unread_fields.py` | `e0dec906` | 0 | 三道全过（ERROR 0 == 基线；无新增家目录字面量；无新增未读字段） |
| `pnpm lint` / `pnpm typecheck` / `pnpm build` | `0b03f84e` | 0 | 全过 |
| `pnpm test`（vitest） | `0b03f84e` | 0 | **84 passed**（新增 8） |
| `pnpm test:e2e --project=desktop` | `0b03f84e` | 0 | **8 passed**（新增 3，既有 5 未受影响） |
| `scripts/build_registry.py check` | `e0dec906` | 0 | 注册表与源一致 |
| **`pytest -q --ignore=test_codex_sandbox.py`（全仓等价 CI）** | **`d460b3aa`（最终 SHA，干净树）** | **0** | **9997 passed / 0 failed / 77 skipped / 2 xfailed**，381 s |
| `graph_audit.py --repos-root /Users/a77` | 同上 | 0 | 60 行 / 106 条断言无漂移；本批 8 条为 PENDING（在途分支，预期） |
| pre-commit 11 道 | 五次提交均通过 | 0 | — |

全仓收据：`~/.finance-runtime/test-receipts/20260913T090200Z-d460b3aa.json`
（`tree` = 本工作树、`dirty` = false、`failed_ids` = []）。第一次全仓跑绑的是 `0b03f84e`，
之后又叠了两次提交，所以按最终 SHA 重跑了一遍——收据要能指回它度量的那个 revision。

收据文件按 revision 取 `~/.finance-runtime/test-receipts/<stamp>-<rev8>.json`，**不读 `latest.json`**（多树并发覆盖）。
排除 `test_codex_sandbox.py` 的理由：本机已知随机红（记忆 `codex-sandbox-test-fails-on-this-machine`），与本轨无关。

## 返修（2026-09-13，QC 结论「建议返修后再合」后）

按 `REWORK.md` 完成 13 条发现（S1–S3 / R1–R10）的修复，并新增 17 条合同测试
（`intelligence/tests/test_research_evolution_rework.py`）钉住新行为：

| 轴 | 修复要点 |
|---|---|
| S1 | 动作口读校验与追加收进 `EvolutionStore.transaction()` 一个事务；并发同键异载荷 → 一方 409 |
| S2 | `pilot_io import-events` 整批先对台账验冲突再写：同 id 异内容 → exit 2 零写入 |
| S3 | `study_io evaluate` dry-run 只读预览（不碰 evaluate_study），`--apply` 才写 |
| R1 | 「继续核查」拿到 run_id 后回写 `link_run` 关联；消息未被接受则 `cancel_rejudge` 退回 open；前端不再造空 run_id continuation |
| R2 | 练习提交与揭示同走曝光边界：先 03 登记曝光再评分，身份不可解析 → 拒绝且不登记 |
| R3 | 新增 `ObservingRunStore` 包装 Workbench RunStore：run 生命周期自动落 05 事件，失败只 stderr 不阻塞被测 run |
| R4 | 面板未绑定记录给出「从现在开始跟踪」表单（受控目录勾版本 → POST bindings） |
| R5 | 练习卡（作答/揭示/评分反馈）与收据原件查看器进面板 |
| R6 | `select_task` 回包含 continuation；前端经同一 continue helper 发真消息 |
| R7 | `link_run` 四道闸：run 属于本会话 / 不许折回原判断 / 判断 run 会话一致 / 事件时刻不早于请求 |
| R8 | 绑定创建自然键幂等：同键同载荷回 201 `created=false`；同键异载荷 409；事件重试同理 |
| R9 | 当前来源读不动的绑定不进评估；模块报 `unknown(current_source_unreadable)` + gap，维护段空态文案按状态区分；`RiverEvidenceSource` 历史切片带 `allow_hindsight` |
| R10 | 幂等键与会话绑定：跨会话重放 → 409 `idempotency_payload_mismatch` |

探针复核（QC 探针指向候选树重跑，预期全红=旧病不再复现）：
`root_probes.py` 5/5 fail（各以新合同报错）、`spec_api_repro.py` fail（read_receipt 已是真动作）、
`standards_probe.py` barrier 死锁（验证已进事务，旧竞态面消失，仅 1 条动作记录落盘）、
`standards_cli_probe.py` dry-run 零写入 / 冲突批零写入。

| 证据 | 结果 |
|---|---|
| `ruff check .` | All checks passed |
| `pytest -q --ignore=test_codex_sandbox.py`（全仓等价 CI，最终 SHA `297c47c3`、干净树） | **10014 passed / 0 failed / 77 skipped / 2 xfailed**，530 s；收据 `~/.finance-runtime/test-receipts/20260913T131404Z-297c47c3.json`（`dirty=false`、`failed_ids=[]`） |
| `pytest intelligence/tests/test_research_evolution_*.py` | **80 passed**（63 既有 + 17 新） |
| `pnpm lint` / `typecheck` / `build` | 全过 |
| `pnpm test`（vitest） | **87 passed**（面板新增 3：R4 表单 / R5 练习+收据 / R9 空态） |
| `pnpm exec playwright test e2e/research-evolution.spec.ts`（三 project） | **15 passed**（新增 R1/R8 两条回归针；顺带修了存量 mobile 用例的开关等待） |
| `pnpm exec playwright test --project=desktop`（全量） | **10 passed**（workbench.spec 的聊天/深潜/停止用例均过，submitResearch 改动无回归） |

## 提交（原始批次）

| SHA | 内容 |
|---|---|
| `5f931258` | 组合基底（规格 + 01–05 六次 `--no-ff` 合并） |
| `916f7e6f` | services/api 接线 + 51 例测试 |
| `6137dcd9` | 前端「维护」页 + 台账地图 / 产品门 / 术语表登记 |
| `0b03f84e` | 重建 `intelligence/api/static` |
| `e0dec906` | 受控入口 `pilot_io` / `study_io` + 12 例测试 |

## 下一步

1. 返修批次提交 → 等用户确认后合并；合并顺序不变（规格分支先进 main）。
2. 部署仍按现役流程，`/api/health` 的 revision 才算线上状态——仓内有代码不等于 8792 已更新。
3. BLOCKED §2 的五条跨轨缺口交对应 owner；§3 剩余未做项要等真人授权或补前端事件。

## 第二轮返修（2026-09-14，复审 ba10747d「返修，不放行合并」后）

复审新查 9 条（Q1–Q9）全部修复；方案明细在 REWORK.md「第二轮返修」表。

| 编号 | 修法落点 |
|---|---|
| Q1 表单 422 | 后端 `object_ref` 收字符串按受控清单解析；前端 BindForm 改发完整 dict；双保险 |
| Q2 终态无收尾 | `ObservingRunStore` 终态 claim 后回调 `facade.fold_run_terminal`（app.py 接线注入）；幂等键 `link_run:{item}:{run}:terminal` 与客户端恢复路径共用；缺新判断时诚实拒绝、项停在 rejudgment_requested 可恢复 |
| Q3 同会话假关闭 | 折回必须有**运行中登记的** run_links 行；同会话只剩注册闸；无关/失败旧 run 一律 400 `run_binding_mismatch` |
| Q4 练习 UI | `selected_choices` 输入 + `cited_refs` 勾选真发出；反馈渲染嵌套 `checks[].expected/got` 与 `missing_evidence_refs`；揭示渲染 `answer_key` 正确选项/引用/解析 |
| Q5 running 重试 409 | 登记分支写无事件幂等记录（`append_action_record`，`event=None` 不进 01 折叠）：同键重试重放首个注册结果、同键异 run 409、终态同键重试升级折回（派生键去重） |
| Q6 select_task 无幂等 | 收进事务：同键重放原 continuation（digest 基不含 client_at）、同键异任务 409、`task_selected` 恰好一条 |
| Q7 来源引用丢失 | `ContinuationRequest.click_payload` 字段：02 任务卡 source_refs/object_refs 随用户消息落盘 |
| Q8 summary 400 | 前端 `receipt_id ?? summary_id`；后端收 `kind`/`summary_id` 别名，pilot_summary 无 id 读最新一份，measurement 兜底 process_receipts；顺带修了 `created_at` 时区口径（上海日 vs UTC 刻，每天 00:00–08:00 真实绑定必被 01 误拒） |
| Q9 等锁阻塞 run | `EvolutionStore.try_transaction(timeout)`（进程锁 acquire(timeout) + flock LOCK_NB 重试）；观察器事件写入与终态收尾全走有界事务，超时只 stderr「跳过」 |

### 复审探针复核（对着候选树重跑）

| 探针 | 结果 |
|---|---|
| `test_review_contracts.py`（复审 9 败 1 诊断） | **10/10 全绿**（诊断条在裸观察器下成立=「未接线不收尾」；接线路径由仓内 `test_q2` 钉住） |
| `probe_cas.py` | 同版本并发 200+409 恰一条；同键异载荷 409 |
| `ResearchEvolutionReview.test.tsx`（拷入临时跑） | **3/3 全绿** |

### 第二轮验证收据

| 项 | 结果 |
|---|---|
| 06 全部 pytest 文件（api/rework/io/store/falsification + 01 四个） | **174 passed** |
| 全仓 `pytest -q --ignore=test_codex_sandbox.py` | **10022 passed / 0 failed**（收据 `20260913T163415Z-089526ab.json`，revision=代码 HEAD、dirty=false） |
| `pnpm lint` / `typecheck` / `build` | 全过 |
| vitest | **90 passed**（含复审三条 UI 探针移植 + Q1 载荷断言更新） |
| e2e `research-evolution.spec.ts`（三 project） | **15 passed** |
| e2e 新 `research-evolution-binding.spec.ts`（desktop） | **1 passed**：真浏览器表单 → 真 bindings API → 刷新投影 bindings 0→1（放行条件 #1） |
| e2e `workbench.spec.ts`（desktop） | **5 passed**（双 webServer 配置无回归） |

### 第二轮提交

| SHA | 内容 |
|---|---|
| `347bf8b2` | 后端 Q1–Q9 + 25 例合同测试（返修文件现有 25 例） |
| `e8b1bd85` | 前端 Q1/Q4/Q8 + e2e 双服务与新 spec |
| `089526ab` | 重建 static（全量收据绑定此 SHA） |
