# P1b 第三片验证：跟踪 / 排序方法不再另立完成门

## 结论与固定对象

**本片作者离线 Python 工程验证通过；不是完整 P1b、独立审查、合入 / 发布批准或模型质量证明。**

| 对象 | 固定值 |
|---|---|
| 工作树 / 分支 | `~/fwp-wt-harness-output-provenance-1003` / `feat/harness-output-provenance-1003` |
| 代码 / 测试 pin（固定受测版本） | **`631ea887618b0044a79fd1e0c3621e99b70c4505`** |
| 生产逻辑提交 | `ae03b189a4bdb6af87def3e4b32b89e09dc8afa9` |
| 前一片文档基座 | `7c90d8526436aa356e5ce3f91425eef601bbdc6c`；不是本片受测版本 |
| 证据根 | `~/.finance-runtime/reviews/harness-expression-advisory-20261003/`（下文原件均相对此目录） |
| 解释器 | `/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python` |
| 环境 | Python 3.12.13、依赖指纹 `66726d345bf37ce5`；正式执行使用 `env -i`、`FWP_WORKBENCH_PYTHON`、`FORESIGHT_LLM_KEYCHAIN=0` |

`631ea8876` 在生产提交之后只改两个测试文件：固定积分测试时钟、更新方法提示标题预期。本报告及交接是其后的文档，不把该收据移签为文档 tip（最新提交）上的新测试。第三片独立 `closeout.json` 记录最终文档和 Memory 身份；前两片收据 / closeout 不覆盖。全程未推送、合并、部署或新增真实模型请求。

## 实现与行为边界

| 接缝 | 本片变化 / 覆盖 | 保留或未声称的边界 |
|---|---|---|
| 完成权责 | Episode 的结构、语义、公开及可信旧稿恢复出口删除模板缺项合并 / 补全链 | 任务合同和证据检查仍判真实缺项；不是所有旧默认槽均退出 |
| 方法支架 | 跟踪 / 排序提示改为可选建议；自然段、自选标题列表、旧模板均可交付 | 无基线不能编造；机械再排序只是旧箭头假设的参考，不是新证据 |
| 诊断收据 | v2、`authority=advisory`、`missing_template_elements`；兼容 `missing_outputs=[]` | 空兼容键不代表任务完成；解析 / 登记仍走原授权 |
| 输出身份 | 合同内 `track_ttl` / `ranking_matrix` / 普通附录要求仍履约；合同外陌生绑定仍拒绝 | 不按名字豁免用户义务或授予 `contract_rewrite`；伪造引用仍拒绝 |
| 核验修订 | `review_feedback` 提供可行动诊断，纯核验可无缺项地申请关闭工具的 delivery repair（文字修订） | 与事实拒绝 `rejected_claims` 分账；材料诊断不误撤既有 input-only rewrite 权限 |
| 预算 / 机会 | 文字修订仍受根时间余量、单轮帽、档位轮次和一次机会约束；成功补证消耗该机会 | delivery 被拒不能回落到 progress / cold restart 重新拿工具；不重置或返还预算 |
| 历史 / 材料 / 恢复 | 保留历史意图、材料 grounding、真实期限矛盾、可信旧稿与存储失败边界 | 退休拒绝码只退出活动表，历史 payload 原样读取；不迁移旧 CLI `ask_synthesis` |

## 固定 pin 的全仓门禁

- `scripts/run_main_gate.sh`：Ruff 全仓通过；pytest **18,912 passed / 0 failed / 0 error / 76 skipped / 2 xfailed / 0 xpassed / 18 warnings**，**991.34s**，exit 0。
- 收据：`full-631ea887-receipts/gate-3K3tWPBM/pytest.json`；原始 pytest 日志在同目录 `pytest.log.txt`，门禁日志 `full-631ea887-rerun.log`。
- 收集 **18,990**，与 `18,912+76+2` 对平；无 ignore、keyword、mark、deselect、maxfail 或 last-failed 收窄；`dirty=false`、无依赖门绕过。
- `check_test_receipt.py ... --require-full-scope --expect-revision 631ea887618b0044a79fd1e0c3621e99b70c4505`：exit 0，核对 revision、解释器、Python、依赖和收集面。初查 `full-631ea887-receipt-check.log`，文档改动前再查 `final-pin-receipt-check.log`。
- 本片代码 / 测试提交 hooks 通过（`code-commit-2.log`、`test-fix-commit.log`）。首次代码提交被 runtime catalog freshness 拦截，生成运行目录后仅 `docs/runtime/harness-seams.md` 一行变化；没有绕过 hook。
- hooks 中的层级、路径、字段、数据集归属、工具可达性检查**不是 registry 五项专项**，本片没有为后者领取验收结论。

## 成对反例与撤保护验证

撤保护验证是故意撤掉一条约束，确认测试确实会失败，再还原重测；它检查测试能否抓住指定退化，不证明模型研究质量。

### 本片 13 项定义

定义：`scripts/review_probes/expression_advisory_mutations.json`；原件：`mutations-631ea887/results.json`；字节 / 行为对账：`mutation-audit.json`。
定义 SHA-256：`83b3e4c0d7bc14615eeda755561df4612293f6f1a3207b8354df47d9ea3a7423`。

baseline / restored-full 均 **286 passed**。13个红轮均 exit 1、有实际断言失败、0 errors / 0 skips；逐项还原后绿轮均 exit 0、执行数相同。定义内容、变异字节与还原字节已对固定 Git 内容核对；临时变异树已移除。

| 变异定义 | 红轮失败 / 执行 | 还原后通过 |
|---|---:|---:|
| `template_reopens_structural_gap` | 20 / 24 | 24 |
| `template_reopens_semantic_gap` | 10 / 26 | 26 |
| `public_template_stub_restored` | 18 / 34 | 34 |
| `template_name_grants_rewrite` | 2 / 3 | 3 |
| `template_name_rejects_user_binding` | 2 / 3 | 3 |
| `track_method_becomes_mandatory` | 13 / 26 | 26 |
| `ranking_method_becomes_mandatory` | 13 / 26 | 26 |
| `track_receipt_claims_missing_obligations` | 8 / 24 | 24 |
| `ranking_receipt_claims_missing_obligations` | 12 / 24 | 24 |
| `review_only_requires_fake_output` | 3 / 8 | 8 |
| `spent_delivery_falls_through_to_tools` | 1 / 6 | 6 |
| `backfill_buys_second_prose_turn` | 4 / 24 | 24 |
| `diagnostic_revokes_material_rewrite` | 1 / 1 | 1 |

**13/13 是定义捕获率，不是每个参数化用例都红。** 强制提示两项只证明文案 / 接线退化被捕获，不证明自然模型会采纳建议。四文件测试面为 `test_expression_advisory.py`、`test_boundary_partial_delivery.py`、`test_continuous_turn_adapter.py`、`test_e2_material_delivery.py`。

`test_expression_advisory.py` 覆盖两种问法 × 三种表达 × GLM / SDK × 0 / 60秒余量，以及同名用户义务和六格纯核验准入。GLM 分支使用真实连续循环与脚本模型；SDK 分支注入 runner、走 SDK runtime 适配接口，**不是第三片新增的真实 SDK provider 生命周期测试**。第二片生命周期测试仍在全仓内，旧专项收据不移签。所有这些都是离线接线测试。

### 历史 8 项 / 边界 16 项

- `history-mutations-631ea887/receipt.json` 及同目录逐项 `.txt`：8/8 captured，源码哈希与 pin 一致、源码未改。覆盖历史跟踪 / 排序提示、公开 scope、收据 scope、checkpoint 上下文及三处登记边界。旧 `drop_history_public_scope` 已替代针对删除函数的过期 patch。
- `boundary-mutations-631ea887/results.json` 及逐项 `.xml/.log/.exit`：16/16 exit 1、有实际 failures、0 errors。覆盖来源解析、数字 / 条件、收据过滤、期限角色 / 冲突、箭头 / 列表 / 节边界、映射投影、日期非触发、语义反馈、可信恢复、登记、数字核验及 opt-out。`post_semantic_feedback_removed` 改 patch 真实反馈接口。
- 汇总日志分别是 `history-mutations-631ea887.log`、`boundary-mutations-631ea887.log`。两套是进程内变异，不改源码；不能描述成与13项同一种逐项红 / 还原绿 runner，也不把三套累加成一个全覆盖百分比。未变异基线由同 pin 全仓及相关测试提供。

## 首轮失败及修正归因

1. 首个固定生产提交 `ae03b189a` 全仓 **18,906P / 6F / 76S / 2X**，完整红收据保留于 `full-ae03b189a/gate-k11ArO8F/pytest.json`，不覆盖为绿。
2. 两项积分测试 `test_overrun_becomes_debt_blocks_admission_and_is_repaid_by_next_grant`、`test_balance_endpoint_and_bootstrap_summary` 使用真实墙钟，却把到期日固定在 `T0+30天`。在改动前干净 `7c90d8526` detached 树再次复现 **2F**（`clock-baseline.log`、`clock-baseline-receipts/`）；因此仅向测试注入 `_Clock()`，不改生产计费。
3. 四项材料 prompt 失败是旧强模板标题预期：三个 `test_unsettled_or_non_material_scope_keeps_legacy_prompt` 参数格和 `test_unnumbered_material_prompt_is_unchanged`。测试改为区分 `TYPE_GUIDANCE_HEADINGS` / `RETIRED_HEADINGS`，不为过期词面回退 advisory 实现。
4. 上述两文件修正形成 `631ea8876`。提交前定向 **54P**（`postfix-targeted.log`）只作开发证据；最终全仓和三套变异在新 pin 重新执行。
5. `full-631ea887.log` 记录一次 shell 路径误指向虚拟环境内不存在的 `bin/bash`，exit 127，测试未启动。随后用宿主 bash、仍锁定 workbench Python，另起目录完成本报告全仓。开发阶段1343项读数和脏树红 / 绿也均保留，不代替固定版。

## Memory 候选与证据归档

- 独立候选树 `~/agent-memory-wt-harness-output-provenance-1003`，固定 **`6643bb3a57d8145bb458247d4783b2b754c1a4ff`**；基座 `2d540127942291b5879e098d73c50f85767795b9`。只改项目索引、既有原则笔记和能力图谱，未写共享主目录、未推送 / 整合。
- `memory-frozen-lint.log`：仍 **46 errors / 31 warnings，exit 1**；错误逐条相同，警告仅既有项目页字节数改变，没有新增问题。对账见 `memory-lint-comparison.json`，不是全库 lint 通过。
- `memory-frozen-graph.log`：exit 0，112行 / 342符号断言。新增四项被标 `MERGED`，只是被检查的默认金融树也有同名符号；默认树当时是 `main@47a05e36b dirty`。**不据此宣称本分支已合并或行为等同**，因此保留候选分支限定。图谱本身有295条在途 / 未校验提示，不是完整行为覆盖。
- `audit_slice.py` / `slice-audit.log` 对本片原件作只读汇编检查；`build_closeout.py` 仅生成本证据根的不可覆盖身份 / 哈希归档，不运行模型、测试或发布。归档不是新验收，不改前两片 closeout。

## 未验证 / 后续范围

- 未执行本片 registry 五项：`build_registry.py check-parseability`、`check`、`backfill-tables --check`、`generate-views --check`、`audit_ledger_spec_crosswalk.py`。
- 未执行前端 lint / typecheck / unit / build、浏览器 E2E、GitHub CI、独立规格 / 代码质量审查。本报告不是完整合入门禁。
- 没有真实弱 / 强模型对照；金融研究质量、自然语言履约、用户满意度与性能收益均未证明。
- legacy CLI 强模板 / 补全链、其它旧默认槽和词面硬门未全部迁移；题型 / 主体 / 时间窗重装配、合同 / 恢复投影版本分离、SDK 跨进程磁盘恢复执行器仍待另片。
- 收尾时本分支基座落后本地 `origin/main`；本报告只签候选 pin，不对最新主线缺什么作结论。R17/R19继续封存，正式240格不放行；后续发布或模型执行需另行授权。

设计见[第三片计划](../superpowers/plans/2026-10-03-harness-expression-advisory.md)；决策因果和被否方案见[日期交接](../handoffs/2026-10-03-harness-expression-advisory.md)；接续状态见[inflight](../handoffs/inflight/feat-harness-output-provenance-1003.md)。
