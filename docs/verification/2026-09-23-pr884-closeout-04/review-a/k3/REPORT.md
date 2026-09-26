# 独立动态审查终稿 review-a（mirasim-kimi/kimi-k3）

## Spec（边界/规则）

- 候选只读树：`/Users/a77/.finance-runtime/reviews/pr884-closeout-20260923-04/finance-workspace-private`，revision `db2605d1b1a6a929d9bac468c84ef6aeaddce9ff`（已核 `git rev-parse HEAD` 一致、工作树干净）。运行时审查 baseline：`da761024ed54c46b8e650d1b86076e1f9d261ed2`。
- 本场负责：**C1、C2、C3**；C4–C8 一律 NOT_REVIEWED，聚合留给宿主。
- 规则来源：`docs/agent-product-door.md` 运行时/交付段（OPT-08 保存失败围栏、恢复判定纪律、预算/授权/证据/入口身份快照、未知效果双向保守、重复恢复幂等）+ 候选实现（`episode_restore.py`、`episode_effects.py`、`episode_authorization.py`、`episode_evidence.py`、`episode_entry_identity.py`、`research_contract.restore_root_budget`、`agent_episode._EpisodeLedger`、`episode_store.FencedEpisodeStore`、`api/app.py._build_continuous_turn_adapter`）。
- 边界：离线、不启动服务、不改候选树、不联网、不用真实模型/金融数据；pytest 一律经外置 wrapper 先固定 `USERS_DIR` 到 work 目录再 `pytest.main`，新 basetemp + JUnit 全量输出。

## Quality（环境/回归对照）

- 作者现有 9 个相关套件作为环境/回归对照（非本人探针）：`test_episode_persistence_failure / test_episode_effects / test_episode_entry_identity / test_episode_authorization_snapshot / test_episode_evidence_snapshot / test_episode_evidence_presentations / test_episode_restore / test_episode_restore_repeatability / test_episode_restore_persistence` → **374 passed in 13.19s**，JUnit：`review-a/k3/work/junit_control.xml`。
- 本人独立探针 17 例（`work/test_k3_c1.py / test_k3_c2.py / test_k3_c3.py`，断言均带具名语义标签如 `[C1-NO-NEW-MODEL]`、`[C3-EFFECT-DEDUP]`）：**14 passed, 3 failed**，JUnit：`review-a/k3/work/junit_probes.xml`。3 个失败均为**探针侧夹具缺陷**（对 `_json_freeze` 产出的 frozen `mappingproxy` 做 `copy.deepcopy` 触发 `TypeError: cannot pickle 'mappingproxy'`，traceback 止于 `copy.py`；C1 树fence例同属探针构造问题），首红已保留在 junit_probes.xml，未改写。**不计为产品缺陷，也不计为通过**。
- **撤保护变异实验未能在预算内执行**（探索在第24请求前被切断），此为方法学缺口，直接影响 verdict。

## 逐项合同状态

### C1（保存ACK失败围栏）— 证据不全，不计 PASS
- ✅ 已动态验证（3 探针绿）：`model_turn` 结算 ACK 失败后 `outcome=failed/storage_failed`、`persistence=failed`、模型调用数锁死在 1、工具零派发、失败后零写存储、usage 如实保留、无 completed finish；`state:done` 失败后草稿保留在私有结果且磁盘保持前缀；修复/续轮共用的 `_EpisodeLedger.model_complete` 与工具意图入口 `record_dispatch_intent` 在同一点被闸（直接构造 ledger 注入失败，真实入口调用）。
- ❌ 未覆盖：父子树 `FencedEpisodeStore` 探针因夹具错误未得出判断；变异实验未做。

### C2（预算/授权/证据/身份）— 证据不全，不计 PASS
- ✅ 已动态验证（6 探针绿）：`restore_root_budget` 对非空 `unreconciled_effects` 拒放余额、空清单精确恢复余额；`charge_unknown_effects` 每条恰扣一格、不扣秒、超额记 `slots_unavailable` 不写负余额、无快照有未清即抛错；`unknown` 效果按可能已计费（fail closed）、损坏凭证抛错；授权快照篡改（io_effect 提权、max_steps 放宽、空 registry、跨 episode）全部 ValueError；`ToolSpec.io_effect` 域外值拒绝；`_build_continuous_turn_adapter` 跨用户/跨会话在门内即拒（身份只认服务端 run 记录）；恢复门身份双向（绑定↔未绑定两方向都拒、None↔None 放行）。
- ❌ 未覆盖：证据快照 v3 roundtrip/篡改与 v1/v2 保守兼容两探针因 deepcopy 夹具错误未得出判断；变异实验未做。

### C3（重复 restore 幂等）— PASS（本场范围内）
- 4 探针全绿：model_pending 悬空意图重复恢复 3 轮计划逐字段相同、`phase/reserved_ids` 不前移、执行前缀不变、`effects_unknown` 恰一条且未清清单不随重启膨胀；tools_pending replay=safe 按 `call_id` 去重同一结论；恢复全程零工具执行、零结算合成（计划不是执行/结算授权）；截止已过 close 后重复恢复 `already_terminal` 零新字节，且 close 不抹未对账凭证。

### C4–C8：NOT_REVIEWED（非本场范围）

## 实际命令与证据

- 对照：`python -B work/run_pytest.py intelligence/tests/test_episode_{persistence_failure,effects,entry_identity,authorization_snapshot,evidence_snapshot,evidence_presentations,restore,restore_repeatability,restore_persistence}.py -q --basetemp=work/tmp/base1 --junitxml=work/junit_control.xml` → 374 passed。
- 探针：`python -B work/run_pytest.py work/test_k3_c1.py work/test_k3_c2.py work/test_k3_c3.py -q --basetemp=work/tmp/base2 --junitxml=work/junit_probes.xml --rootdir=work` → 14 passed / 3 failed（探针侧）。
- 探针源码：`review-a/k3/work/test_k3_c{1,2,3}.py`；wrapper：`review-a/k3/work/run_pytest.py`。

## 缺陷

- 无已确认产品缺陷。3 个探针失败为本人夹具缺陷（frozen mapping 不可 deepcopy），首红保留于 `junit_probes.xml`，未复验故不结论化。

## 限制

- 撤保护变异实验未执行（硬性要求未达成）；C1 父子树 fence、C2 证据快照 v3/v1/v2 两子合同缺本人动态证据。
- 真实费用、跨机锁、完整崩溃续跑 driver、服务端多 worker 不在本场可证明范围；作者测试仅作环境对照。

```json
{"revision":"db2605d1b1a6a929d9bac468c84ef6aeaddce9ff","baseline":"da761024ed54c46b8e650d1b86076e1f9d261ed2","verdict":"BLOCKED","checks":[{"id":"C1","status":"NOT_REVIEWED","evidence":"核心子合同已动态验证：work/test_k3_c1.py 3例绿（model_turn ACK失败→failed/storage_failed、模型锁1次、工具零派发、零后写、usage/草稿留私有、磁盘前缀；model_complete与record_dispatch_intent共用闸门），junit_probes.xml。但父子树FencedEpisodeStore探针因夹具错误（mappingproxy deepcopy）未出判断、变异实验未执行，子合同证据不全，按规则不计PASS"},{"id":"C2","status":"NOT_REVIEWED","evidence":"6例绿：restore_root_budget非空未清拒绝/空清单精确恢复；charge_unknown_effects扣格不扣秒、无负余额、无快照抛错；unknown按可能已计费；授权快照四类篡改全拒；io_effect域外值拒；门内跨用户/跨会话即拒；恢复身份双向匹配（junit_probes.xml）。但证据快照v3/v1/v2两探针因deepcopy夹具错误未出判断、变异实验未执行，证据不全"},{"id":"C3","status":"PASS","evidence":"work/test_k3_c3.py 4/4绿：重复restore保持phase/reserved_ids/执行前缀、计划逐字段相同、synthesized为空、effects按call/effect identity去重不膨胀、计划不执行不结算、close后already_terminal零新字节且不抹未清凭证；junit_probes.xml"},{"id":"C4","status":"NOT_REVIEWED","evidence":"非本场范围"},{"id":"C5","status":"NOT_REVIEWED","evidence":"非本场范围"},{"id":"C6","status":"NOT_REVIEWED","evidence":"非本场范围"},{"id":"C7","status":"NOT_REVIEWED","evidence":"非本场范围"},{"id":"C8","status":"NOT_REVIEWED","evidence":"非本场范围"}],"issues":[],"limits":["撤保护变异实验未在预算内执行（硬性要求缺口）","C1父子树failure fence、C2证据快照v3/v1/v2保守兼容两子合同缺本人动态证据（探针夹具错误，首红保留于junit_probes.xml，非产品缺陷）","真实费用、跨进程/跨机锁、完整崩溃续跑driver、多worker不在本场可证明范围","作者374例仅作环境/回归对照，不计入本人动态判断"],"complete":true}
```
