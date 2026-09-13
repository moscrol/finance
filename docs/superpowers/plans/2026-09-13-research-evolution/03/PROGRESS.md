# 03 · 方法验证与真实前向概率实验 · 进度

> 换会话先读这里。规格：`docs/superpowers/specs/2026-09-13-research-evolution/03-method-validation.md`
> （规格源分支 `docs/river-next-specs`，提交 `28804505`；总合同 README 同目录）。
> 本轨只写白名单路径；问题与 06 依赖见同目录 `BLOCKED.md`；决策留痕见 `docs/handoffs/2026-09-13-research-validation-03.md`。

## 状态一览（2026-09-13）

| 状态 | 值 |
|---|---|
| engineering_complete | **达成**（白名单代码 + 8 组反例 + 6 处变异各至少 1 红 + 既有四组回归 + 11 道 pre-commit 门禁 + 全量套件） |
| product_verified | 待 06：接 userspace 根 / 可信时钟 / PIT 校验器 / ledger-map 登记 / 投影契约传参 / Workbench 收据入口 |
| empirical_complete / field_evidence | **无**：未冻结任何真实协议，无真实前向样本；一切 pending |
| 代码提交 | `e38d6a63`（首版）→ `49197160`（projection_hash 接受河投影哈希 + Brier 对拍）；分支 `feat/research-validation-03`，基线 `gitea/main@5fb13a8c`，未合 main、未推送 |

## 任务 0 · 登记

| 项 | 值 |
|---|---|
| 工作树 | `/Users/a77/fwp-wt-research-validation-03`，分支 `feat/research-validation-03` |
| 开工基线 SHA | `5fb13a8c26986e6a0a24eb2687a2635131426694`（gitea/main，与总合同一致） |
| spec 来源 SHA | `28804505`（`docs/river-next-specs`，文件已提交；03 分支树里没有这些 spec 文件，合并时无冲突） |
| 解释器 | `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（3.12.13） |
| 实际用户态根 | 服务不自行解析；`Repository(root, owner_user_id)` 由 06 以 `userspace.user_space(user).root / "research_validation"` 注入。测试只用 `tmp_path`。本轨代码不读 `FORESIGHT_USERS_DIR` |
| 四组回归基线 | 117 passed / 19.05s @5fb13a8c，收据 `~/.finance-runtime/test-receipts/20260913T061107Z-5fb13a8c.json` |

### 源码与签名映射（实测读源码，非代码地图）

| 复用点 | 符号 | 本轨用法 | 已知坑 |
|---|---|---|---|
| Wilson / 四态 / 二项 p | `methodology_backtest/stats.py::wilson(k,n)`, `four_state(n,k,p0,p_first,p_second,min_n)`, `binom_two_sided_p(k,n,p0)`, `split_halves(seq)` | `scoring.paired_readout` 直接喂原语，p0=0.5 显式传入 | `readout()` 会 `bool(x)` 强转且 p0 只能由 `baseline_k/baseline_n` 得到 → **不调用 `readout()`**，不虚造 baseline_n=2/k=1 |
| 依赖感知读数 | `stats.block_bootstrap_readout(events,p0,block_len,n_boot,min_blocks,seed)` → `DependenceReadout`; `combined_verdict(independent, dependence)` | 事件 = 每个交易日一条 (comparison_id, date, win) | 第 419 行 `bool(s)` 把 ±0.1 都变 True（`test_strict_bools_rejects_…` 里保留了这条反例）→ `scoring.strict_bools()` 在入口拒绝非 bool |
| 冻结常量 | `rules.DEFAULT_MIN_N=20`, `stats.DEFAULT_MIN_BLOCKS=10`, `stats.DEFAULT_BLOCK_BOOT=500`, `stats.DEFAULT_BLOCK_SEED=20260911`, `checkpoints.DEFAULT_CALIBRATION_MIN_N=10` | `contracts.default_analysis_policy`；低于缺省 / 改 seed / 改 p0 一律拒绝冻结 | — |
| 规则白名单 | `rules.validate_rule` / `parse_rule` → `Rule.predicates`, `METRICS`, `SUCCESS_OPS`, `MAX_HORIZON`, `LABEL_KINDS` | 臂规则、outcome_spec、allowed_fields 校验；臂规则 success 必须与 study outcome_spec 一致 | 规则必须带 `sharing/owner`；本轨不改规则文件 |
| 河投影哈希 | `river_projection.HASH_PREFIX`（`cp:`）、`ContextProjection.projection_hash`（前缀 + sha256[:16]） | `contracts.validate_projection_hash` 接受它与 64 位 sha256 两种形状；正则从常量拼，不手抄 | §4.5 设计文本只在主树未提交改动里，代码在 main 上 |
| 旁路库 | `methodology_backtest/store.py::open_labels_db / read_meta`，表 `history_calendar/labels/outcomes/build_meta` | eval 只读；`runner._purge_cut_date` 的跨窗 purge 口径复刻为 `baseline.purge_cut_date` | 编译器只给「条件成立集」，答不了 False vs Unknown → eval 用 Python 三值合取 |
| 不可覆盖发布 | `method_validation/store.py::_publish`（tmp + `os.link` + fsync） | `repository.publish` 同原语，但返回 `(existing, created)` 供同意图/异意图判定 | 原版内容不同即抛；本轨要区分「重试」与「冲突」 |
| 时钟与收盘 | `method_validation/protocol.py::clock_now`, `SHANGHAI`, `study.py` 的 `time(15)` | 结算 `now ≥ D+h 15:00 Asia/Shanghai`；forward 登记 `now ≥ D0 15:00` | 客户端不得传 now |
| 校准数学 | `scripts/dual_blind_forecast.py::_calibration_metrics`（五桶边界、Brier 舍入 4 位） | 五桶 `[0,.2)…[.8,1]` 对齐；**本轨不舍入**；`test_brier_and_five_bucket_error_agree_with_retired_dual_blind_formula` 用 `ast` 只抽该函数编译执行做对拍 | 退役脚本：不 import、不启动；脚本被删则对拍跳过，主断言不依赖它 |
| 历史演练字段 | `eval/replay_engine.py`：`confidence_probability/pit_grade/memory_bucket/arm` | `eval/research_validation/historical_llm.py` 只读 replay 原件 + 文件 sha256 | service 不反向 import eval |

## 对象布局（06 登记 ledger-map 用）

唯一 writer：`intelligence/services/research_validation/repository.py::Repository`（tmp + `os.link`，只增不改）。根 = 06 注入的私有根 `/research_validation/`：

```
studies/<study_id>/protocol.json                       research-study/v1
studies/<study_id>/forecasts/<case_id>/<arm_id>.json   probability-forecast/v1（唯一键即路径）
studies/<study_id>/observations/<forecast_id>/<id>.json outcome-observation/v1（追加）
studies/<study_id>/receipts/<receipt_id>.json          method-validation-receipt/v1
exposures/<operation_id>.json                          exposure-receipt/v1（owner 全局）
```

## 逐单元记录

- [x] 任务 0：树 / base / 总合同确认；四组回归 117 passed；签名映射登记
- [x] 合同 + repository：`contracts.py` / `repository.py`；`test_research_validation_contracts.py` / `_repository.py`
- [x] 登记 / 结算：`service.freeze_study / register_forecasts / settle_outcomes`；`test_research_validation_service.py`
- [x] 评分 / 消融：`scoring.py` / `baseline.py`；`eval/research_validation/{recipes,rule_two_bucket,runner,outcome_source,historical_llm}.py`；`test_research_validation_scoring.py` / `_eval.py`
- [x] 谱系 / 曝光：`service.record_exposure / foreign_exposures / exposed_case_ids / evaluate_study / read_receipt`
- [x] 门禁与回归（`e38d6a63`）
- [x] 2026-09-13 补发说明核对（见下节；`49197160`）
- [ ] 06 联调（product_verified）：接线依赖见 `BLOCKED.md`

## 2026-09-13 补发说明 → 03 的核对

| 条 | 对 03 的影响 | 处置 |
|---|---|---|
| 1 设计文本缺失（§4.5 投影契约等只在主树未提交） | 03 的 `predict_fn(projection)` 要对齐河投影 | 只读主树 §4.5；`projection_hash` 改为接受 `cp:`+16 hex（原来只认 64 位 sha256，会拒收 06 传来的 ContextProjection 哈希）；规则臂仍记字段投影 sha256；是否强制存在留 06 拍（BLOCKED） |
| 2 不荐股只约束渲染输出 | 无冲突 | 03 首版限板块；forward 登记不过滤 entity_type；不碰观察剧本硬门 |
| 3 spec 目录先合 main | 无冲突 | 03 分支树里没有 spec 文件；等用户确认 |
| layer_audit | services 不 import runtime | 通过（pre-commit 与手跑均 0 条） |
| 路径字面量棘轮 | 不新增家目录路径 | 通过（23 文件 / 37 处不变）；测试只用 `tmp_path`，夹具无绝对路径 |
| 收据别读 latest.json | 按 revision 取时间戳文件 | 本文所有收据均为 `<ts>-<sha>.json`；代码与测试不含 `latest.json` |
| Brier 与脚本对拍、不 import scripts | 对拍测试 | `test_brier_and_five_bucket_error_agree_with_retired_dual_blind_formula`（ast 抽函数，不 import） |
| 分支命名 | 带编号 | `feat/research-validation-03`；本批不取工单号 |

## 验收命令与收据（最终 SHA `49197160`，2026-09-13）

| 命令 | 结果 | 收据 |
|---|---|---|
| `pytest --collect-only -q intelligence/tests -k research_validation` | 91/8451 collected，exit 0 | — |
| `pytest -q intelligence/tests -k research_validation` | **91 passed**，exit 0 | `~/.finance-runtime/test-receipts/20260913T071102Z-49197160.json` |
| `pytest -q test_methodology_dependence.py test_method_validation.py test_replay_engine.py test_dual_blind_forecast.py` | **117 passed**，exit 0 | `~/.finance-runtime/test-receipts/20260913T071118Z-49197160.json` |
| `pytest -q intelligence/tests -x --ignore=intelligence/tests/test_codex_sandbox.py`（@5fb13a8c 脏树，含 89 版测试） | **8432 passed / 15 skipped / 2 xfailed**，375.7s，exit 0 | `~/.finance-runtime/test-receipts/20260913T065310Z-5fb13a8c.json`；`49197160` 只改 03 白名单内 4 个文件，未重跑全量 |
| `ruff check`（本轨全部路径） | All checks passed | — |
| pre-commit 11 道（三次提交时） | 全部 Passed / Skipped（无文件） | 提交 `e38d6a63` / `2e6adc90` / `49197160` 的 hook 输出 |
| 变异探针（6 处，逐个改→跑→复原，`PYTHONDONTWRITEBYTECODE=1` + 清 `__pycache__`，@首版） | 去 bool 守卫 1 红 / 平局算赢 1 红 / 忽略外来曝光 2 红 / 放行 bool 概率 4 红 / 忽略到期 1 红 / 覆盖发布 7 红 | 对话内执行，未沉淀为脚本（`scripts/` 不在 03 白名单） |

排除 `test_codex_sandbox.py` 的理由：本机已知随机红（记忆 `codex-sandbox-test-fails-on-this-machine`），与本轨无关；它只是没跑，不是「已知红带过」。

## 规格 §9 八组反例 → 测试映射

| § | 反例 | 测试 |
|---|---|---|
| 1 | 幂等 / 并发收敛 / 改义新身份 / 异意图冲突 | `_repository::test_concurrent_*`, `_service::test_freeze_is_idempotent…`, `test_same_case_arm_is_idempotent…`, `test_record_exposure_is_idempotent…`, `_contracts::test_study_identity…` |
| 2 | D0 零 outcomes / 预塞未来值仍 pending / 到期缺值 / bool·NaN·越界拒收 | `_service::test_d0_registration…`, `test_due_missing_and_invalid…`, `test_register_rejects_bad_inputs…` |
| 3 | 手算 Brier / 正胜出率 + 负平均差并列 / 与既有口径对拍 | `_scoring::test_brier_hand_calculation…`, `test_positive_win_rate_and_negative_mean…`, `test_brier_and_five_bucket_error_agree…` |
| 4 | 复制同日 case 不增证据 / 板块不增日期块 / 连续差拒进 bool / 依赖不足不支持 / 平局不丢分母 | `_scoring::test_duplicated_same_day_cases…`, `test_strict_bools…`, `test_dependence_insufficient_blocks…`, `test_ties_keep_denominator…` |
| 5 | 删轨残留被拦 / 覆盖率损失可见 / unknown 不变 false | `_contracts::test_arm_isolation…`, `_eval::test_residual_track…`, `test_ablation_end_to_end…`, `test_three_valued_condition…` |
| 6 | 跨窗 / 错版本 / 缺 PIT 原件 / late 登记 / 历史与前向不混 / 投影哈希形状 | `_service::test_forward_registration_time_gates`, `test_settlement_refuses_version…`, `test_pit_grade_only_upgrades…`, `test_historical_llm_probabilities_never…`, `test_projection_hash_accepts_river…`, `_eval::test_runner_refuses…` |
| 7 | 改 p 被拦 / 换 study·谱系·别名复用 holdout 被拦 / 未知曝光不 eligible / 崩溃恢复幂等 / 跨 owner 失败 | `_service::test_full_forward_flow…`, `test_unknown_external_exposure…`, `test_cross_owner…`, `_repository::test_owner_mismatch…`, `test_leftover_pending_temp_file…` |
| 8 | 临时真实文件两次结算 → 收据；未到期 / 块不足完整返回 pending / insufficient | `_service::test_revised_outcome…`, `test_full_forward_flow…`, `_eval::test_ablation_end_to_end…`, `_scoring::test_dependence_insufficient…` |

---

## 2026-09-13 返修（评审 RV1 / RV2 / RV3）

来源：`/Users/a77/.finance-runtime/reviews/research-evolution-20260913/review.md` 需求符合性轴三条。
基线 `f2a12fa3`（干净树）。三条都先写「调用真实 freeze/register/settle/evaluate + 临时 Repository」的回归测试并证明现版红，再改实现。

### RV1 [P1] 逐日登记后再评估抛 ConflictError

- 根因：`service.py` 里 evaluate 的 `operation_id` 只摘 `{kind, study_id, settled}`，而 `record_exposure` 比对的是**整份意图**（含 `case_manifest_hash` / `window` / `actor` / `outcome_identities`）。D0 登记一对 → evaluate=pending；D1 再登记一对合法预测，期限都没到 → settled 集合不变（仍为空）、case 集合变 → 同 id 撞上异载荷 → `ConflictError`。这是正常使用路径，不是并发重占，违反 spec §5「未来未到 / 块不足也能完整返回 pending/insufficient」。
- 修法：`operation_id` 改为**逐字段覆盖 `build_exposure_intent` 的全部身份输入** —— `{kind, lineage_id, study_id, framework_hash, window, case_manifest_hash, settled, stage, actor}`。`settled_manifest_hash` 是 `outcome_identities` 的无损摘要（`identity` 本身即整条身份的 sha256），`reason` 在该调用点是常量，故二者不必再入摘要。顺带修掉同一根因的第二个症状：不同 `actor` 评估同一 study 原本也会撞冲突，现在各自留痕。
- 新测试：`test_incremental_registration_keeps_pending_evaluate_instead_of_conflict`、`test_evaluate_is_idempotent_for_identical_inputs_and_separates_actors`。
- 修前红：`ConflictError: operation_id=9b579cf4… 已被另一意图占用（stage=evaluate, actor=research_validation.evaluate_study）`。
- 保住的既有语义：同输入重跑仍返回同一条曝光原件（`accessed_at` 不刷新）；同 `operation_id` 异载荷仍 `ConflictError`（由 `test_record_exposure_is_idempotent_and_conflicts_on_reused_operation_id` 直调 `record_exposure` 钉住）；崩溃恢复按原 id。

### RV2 [P1] PIT 截止比较方向反了

- 根因：`_build_forecast` 只拒「forecast cutoff 晚于收据 cutoff」，不拒反向。于是 09-14 的预测可以采用可知时刻为 09-15 的收据并升 `strict`。
- 修法：**换方向**，改为 `receipt_cutoff > cutoff` → 拒收，reason `pit_receipt_after_forecast_cutoff`。
- 为什么是换不是加：两条判据在实践中互斥，同时保留只剩「两个 cutoff 严格相等」才放行，等于废掉该功能。取舍依据是危害方向 —— 收据**晚于**本次截止意味着捕获件含截止后信息，拿它当事前证据就是前视偏差，正是 spec §5「晚于 cutoff 拒收」要防的；反向（收据早于本次截止）是正常事前证据，更早可知者在更晚的截止前必然也可知，拒绝它会把「盘中抓料、收盘定 cutoff」这类正常流程整批打掉。修前实测即如此：探针里唯一被拒的是那条**合法的**早期收据，两条未来收据反而放行。
- 「收据晚于可信 now」由同一判据覆盖：`cutoff ≤ market_close(as_of) ≤ now` 恒成立（前向模式要求 `now ≥ market_close(as_of)`，历史模式 as_of 在过去），故 `receipt_cutoff > now ⟹ receipt_cutoff > cutoff`。未另设不可达分支，改在测试里用 `cap-after-now` 钉住。
- `PitVerifier.verify(ref)` 端口签名未动；方向判断留在 `_build_forecast`。
- 新测试：`test_pit_receipt_later_than_forecast_cutoff_is_rejected`（四条：晚于截止、远晚于 now、早于截止、等于截止）。
- 修前红：`assert ['knowledge_cutoff_late'] == ['pit_receipt_after_forecast_cutoff', 'pit_receipt_after_forecast_cutoff']`。

### RV3 [P2] pending 状态泄露累计评分

- 根因：comparison 分支已清空期末前累计均值，但 `calibration[arm]` 随后**无条件**汇总全部已结算案例，`mean_brier` 与桶的 `mean_p` / `observed_rate` 成了同一份累计表现的第二个出口，可直接推回累计改善。两处各写一份封存条件，只有一处生效。
- 修法：把封存闸门提成**唯一变量** `confirmatory_test_run = evaluation_end_reached and pending_total == 0`，comparison 与 calibration 共用（收据里的同名字段也改用它，不再第三次重算）。期末未到时 `mean_brier=None`、各桶 `mean_p` / `observed_rate` 置 None 且 `reason=sealed_until_evaluation_end`，并加 `sealed` / `sealed_reason` 两个显式字段。保留 spec §7 明说可报的「pending 数与单项」：`n_settled`、桶计数、`origins` / `pit_grades` / `recipe_id`。
- 新测试：`test_cumulative_calibration_is_sealed_until_evaluation_end`、`test_calibration_opens_after_evaluation_end`（55 日实验走到期末，确认封存只在期末前生效、到期后原样输出）。
- 修前红：`KeyError: 'sealed'`；探针显示期末未到时 base/full 的 `mean_brier` 为 0.26 / 0.34。

### 收据

| 命令 | 结果 | 收据 |
|---|---|---|
| `pytest -q -p no:cacheprovider` 本轨 5 个测试文件 | **96 passed**（91 基线 + 5 新），0 failed / 0 skipped，exit 0 | `~/.finance-runtime/test-receipts/20260913T075023Z-f2a12fa3.json` |
| `pytest -q -p no:cacheprovider test_methodology_dependence.py test_method_validation.py test_replay_engine.py test_dual_blind_forecast.py` | **117 passed**，0 failed / 0 skipped，exit 0 | `~/.finance-runtime/test-receipts/20260913T075045Z-f2a12fa3.json` |
| `ruff check`（`service.py` + `test_research_validation_service.py`） | All checks passed | — |
| 评审独立探针 `probe_03.py`（只读、临时根） | 三场景均转正：`incremental_pending.day2_evaluate={"status":"pending"}`；`later_capture` accepted=0 / rejected `pit_receipt_after_forecast_cutoff` / pit_grade=null；`pre_end_cumulative` 两臂 `mean_brier=None, sealed=true` | 对话内执行 |

上表收据文件名里的 `f2a12fa3` 是**跑测试时的 HEAD**（改动尚未提交），非最终 SHA；最终 SHA 见本节提交。收据目录多树共用，按时间戳取本 revision 的文件，未读 `latest.json`。

未做：全仓 / 前端 / registry 未重跑（本次只改 03 白名单内 2 个文件）。真实前向样本仍 pending，与本次返修无关。
