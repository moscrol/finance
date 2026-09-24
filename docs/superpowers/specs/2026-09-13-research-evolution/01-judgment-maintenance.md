# 01 · 私有判断的持续维护

日期：2026-09-13。状态：首版设计，未上线；核对基线 `5fb13a8c`。公共入口、授权、持久化及展示归同目录 06。

## 1. 目标与边界

沿私有判断**已绑定的证据**检查变化，交付可重复计算的维护报告与管理动作归约器，回答“哪条依据变了、哪条显式条件触发了、哪里需要复核”。

范围：单用户私有对象、日频、已知 ref/hash；legacy 缺依赖为 gap。非目标：猜文本依赖、搜索新源、模型判真伪、推送、改原判断/规则、团队协作。哈希变化不能判“原判断被推翻”。

默认纯投影，复用旧对象身份，只由 06 存管理事件；不建平行判断台账。相比一次性摘要，多出依赖绑定和跨次去重。

## 2. 当前实现与复用点

任务 0 核对以下精确符号：

| 文件与符号 | 已有能力与本单用途 |
|---|---|
| `intelligence/services/checkpoints.py::register_checkpoint/load_checkpoints/object_type_of/due_checkpoints/record_verdict/load_verdicts` | 原判断/回检写入者不变；`unverifiable` 仍待回检 |
| `intelligence/services/judgments.py::record_judgment/load_judgments/record_validated_judgment` | 加载过滤 pending/退出；维护项不能越 promotion 门 |
| `intelligence/services/scenario_trees.py::ScenarioTree/load/current_state/compile_condition/eval_predicate` | 持久化树原条件、逐步 ref；复用编译/三值比较，不调用 `register/resolve/append_step` |
| `intelligence/services/scenario_tree.py::ScenarioTreeArtifact` | 单数文件只是表达产物，不能替代持久化树 |
| `intelligence/services/judgment_delta.py::classify_material/judgment_delta_receipt` | 材料分类不是依赖绑定或语义证伪证明 |
| `intelligence/services/research_project.py::load_project/prior_for_turn` | 已有会话/对象投影，沿用范围筛选，不造研究项目 |
| `intelligence/services/foresight.py::_judgments_path/_checkpoint_paths`；`intelligence/userspace.py::user_space/users_dir/resolve_user_id` | 06 复用用户路径，本包只收授权输入 |

checkpoint 有 `id/ts/due/metric/projection_hash`，基础 judgment 有 `id/ts/memo`，但都不统一保存 ref/hash、owner、完整修订链。`projection_hash` 不可反解证据。06 只绑定可验证关联，缺字段留 gap。

## 3. 输入与输出合同

纯函数类型归本包；04 用同合同 JSON 夹具并行，06 适配真实类型。未知版本/枚举拒绝。

```text
assess(*, owner_user_id, as_of, knowledge_cutoff,
       bindings, evidence_versions, condition_observations, policy) -> MaintenanceReport
reduce_actions(*, report, events, now) -> MaintenanceReport
validate_action(*, item, command, owner_user_id, now) -> ActionResult
```

06 管理 `DependencyBinding`：`binding_id/binding_version/owner_user_id/object_ref/baseline_evidence_refs/baseline_source_hashes/baseline_cutoff/created_at/binding_origin/conditions`；origin=`user_confirmed/verified_structured_output`，conditions 每条带 id、表达式及 role=`upgrade/downgrade/abandon/review`。旧对象原登记时刻与 cutoff 另存引用，保持不变。

绑定可在今天由用户明确确认，也可来自可验证结构化输出；这是**自绑定时刻起持续维护**的元数据，不能伪装为原判断当时已有证据。baseline_cutoff 不晚于 created_at，前向样本从 created_at 开始；无法绑定旧记录仍 gap。主题同名不够。版本/条件观测冻结并带来源、标签版本和时间；包内不访问文件、数据库或网络。

```text
MaintenanceReport
  schema_version = "judgment-maintenance/v1"
  id, owner_user_id, as_of, knowledge_cutoff, input_digest
  generated_at                 # 展示元数据，不参与 id/hash
  pit_grade, hindsight, gaps[], items[], counts

MaintenanceItem
  schema_version = "judgment-maintenance/v1"
  id, item_version, owner_user_id
  object_ref {kind, id, namespace, version_or_hash, scope, ref}
  before: EvidenceVersion[], current: EvidenceVersion[]
  change_type, reason_code, epistemic_state, condition_result
  as_of, knowledge_cutoff, pit_grade, gaps[]
  action, status, dedup_key
  binding_id, binding_version, condition_ref?, condition_role?
  supersedes_item_id?, management_revision

EvidenceVersion
  ref, source_hash, valid_from, valid_to, recorded_at, expired_at
  supersedes_ref?, derivation, label_version?
```

object_ref 复用原身份；无原生版本可标 `content_sha256:` 加原不可变记录哈希。无 id 保留 null，用可验证旧行 ref；无 ref 拒绝绑定。报告不复制正文。

item_version 为证据/绑定/条件快照哈希，不含管理状态；management_revision 单独递增。ActionResult 带 `status=accepted/replayed/conflict/rejected`、reason_code、拟追加事件，不执行写入。

pit_grade 取最弱 `strict/trade_date_only/unverifiable`；gap 带 `reason/ref/checked_at/retryable`。counts 为 `objects_seen/objects_bound/objects_unverifiable/dependencies_checked/items_open`，多依赖不膨胀对象数。

## 4. 判定、时钟与去重

`change_type`：`content_changed/source_corrected/source_expired/dependency_missing/condition_evaluated/unchanged`。`reason_code`：`hash_changed/explicit_supersession/validity_ended/ref_unresolved/time_metadata_missing/dependency_unbound/condition_true/condition_false/condition_unknown/no_change`。

epistemic_state=`observed/requires_review/unknown` 只描述变化证据，不描述原判断对错。condition_result=`true/false/unknown/null`，null=未登记确定性条件。

- 相同 ref/hash 且有效：unchanged/no_change，只计覆盖；哈希变/显式更正：保留前后引用、requires_review；源失效/缺引用/时间不明：unknown+gap。
- 只有原对象或已确认绑定明示、编译器接受的条件可出 true/false；缺值 unknown。自然语言、冻结模型散文、otherwise 不强转二值。true 仅说明条件触发，按 condition_role 区分升级/降级/放弃/复核，不能一律放弃。
- 复用 `scenario_trees.compile_condition/eval_predicate`；checkpoint 其他 metric 只引用旧 verdict，不调用取数/写回 resolver，不造新计算口径。

先按 cutoff 过滤版本，再选 as_of 有效版本。前态固定 binding 的 baseline ref/hash；created_at 前不生成维护样本。后知更正产生当前项，不改原回放。日期粒度降级，不截时分秒冒充严格回放。历史 as_of 配更晚 cutoff 标 hindsight，不能进有效性校准。

dedup_key 含 owner_user_id、原身份/版本、binding 身份/版本、依赖、前后哈希、变化类型、条件/观测窗口，不含扫描时间。稳定排序后同输入同 id/hash；乱序/重复 ref 不重造项。恢复新版本关联旧项；更正链断裂为 gap；跨用户不去重。

## 5. 用户动作与管理状态

状态 `open/claimed/snoozed/rejudgment_requested/closed/superseded`；claimed=本人开始复核。建议 action=`review_evidence/restore_evidence/rejudge/none`。

命令带 `command_id/item_id/owner_user_id/expected_item_version/expected_management_revision/action/acted_at`，稍后加 snooze_until；reviewed_no_change 加已核对 source versions。06 验权、单 writer 原子比较/保存；异载荷/旧 item/旧源版本/旧 revision 为 conflict，重复同载荷同结果，跨 owner 拒绝。

open 可 claimed；open/claimed 可 snooze，到期同 id 恢复。rejudge 返回请求，由 06 接旧研究正门，成功关联同 owner 新判断后 closed，失败/取消留待办。人工核对后选择 `reviewed_no_change` 可关闭，收据须绑定本项前后 hash，不改变原判断有效性。新项替代旧项为 superseded；新更正/权限变化不继承旧 snooze。本包无 writer。

## 6. 文件白名单与并行交接

可写：`intelligence/services/judgment_maintenance/**`、`intelligence/tests/test_judgment_maintenance_*.py`、`intelligence/tests/fixtures/research_evolution/01/**`、本规格、`docs/superpowers/plans/2026-09-13-research-evolution/01/{PROGRESS.md,BLOCKED.md}`。

第 2 节只读；API/UI、userspace、ledger-map、注册表、旧对象/框架/行情库、公共配置不改。公共依赖写进度交 06，不扩大白名单。04 依赖合同不等实现。

## 7. 执行顺序与完成条件

0. 核对树/解释器/代码地图/符号；完成：临时目录取得 judgment/checkpoint/tree 样本，明确 ref/hash 可绑定性。
1. 合同与夹具；完成：完整/缺源/legacy 可序列化供 04/06 使用。
2. 差分与条件；完成：前八项反向验收通过，未知带原因。
3. 动作归约；完成：重复请求不重做，冲突/失败不误关闭。
4. 只读集成；完成：旧读取器接临时对象产报告，旧文件字节不变，交收据、diff 白名单、限制。上线归 06。

## 8. 验收与反向证伪

必须能用以下反例使错误实现变红：

1. 只改版式，hash 变但无显式条件：requires_review，不写失效/miss。
2. 新公告只有主题同名不自动绑定；用户今天明确绑定可向前维护，不补成旧判断当时证据。
3. 同 ref 内容被更正：当前报告看到新版本，历史 cutoff 仍保留旧版本。
4. 某依赖缺失但其他两轨利好：缺口仍 unknown，不能补齐或判 false。
5. 确定性条件真实/虚假/缺值各一例；冻结模型散文作为条件被拒绝。
6. 相同数据连续扫描两次、输入乱序、同事件重复三份：内容 id 与待办数量稳定。
7. 同 id 位于不同 owner；伪造 owner、路径穿越及未授权 ref：不串读，不泄露存在性。
8. 旧记录缺原 ref/hash、精确时间或版本：显示相应 coverage/gap，不声称完整历史复现。
9. snooze 到期恢复同项；新更正产生关联新项；重新判断失败保持未关闭。
10. 重复 command_id、并发相同 revision、异载荷重放：至多一份有效管理动作。

用主树 `.venv-workbench/bin/python -m pytest -q` 跑新增测试及旧读取器回归，ruff 查改动范围；离线、临时用户目录。收据含 revision、命令、exit code、输入摘要。

`docs/superpowers/plans/2026-09-13-research-evolution/01/PROGRESS.md` 写步骤、合同版本、下一步、收据、公共依赖；缺源先完成 gap/夹具。同目录 `BLOCKED.md` 附最小复现、缺字段/符号、解阻责任单与续跑步骤。
