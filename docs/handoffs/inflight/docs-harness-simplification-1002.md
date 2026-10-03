# docs/harness-simplification-1002

用户2026-10-02再次纠偏：不要逮单一题型持续补丁，参照Knevo但不照抄规则。已正式记录0bc5a0633c6d（承接62498cc2e02b）。

本分支为减法设计/源码审计，起点3b78fda25；没有产品修改、新模型调用或新的质量评测。真实累计142。R19封存/凭据退役，不得重开；R18工程结论、正式240禁止不变。

审计正文：docs/verification/2026-10-02-harness-simplification-review.md。已读Knevo原始对话存档与E-008/E-009：不是源码，存在声明/生效差异。旧“更多自动门=领先”推理撤回；不反向断言无门更强。

零模型6类装配/接口探针：给料计算、方法、指定事实、假设比较、历史研究、观点修订。发现不仅M0：方法问题也装配relation_map/mainline_current，单价格查询装配stock_deep_dive。align_task_frame允许goal但不接受type/required_outputs/subject/timeframe修订；提案是合成接口夹具，不是正确模型解读或完整入口证明。另有rebase/clarification既存路径，勿声称无语义修订机制。

下一项只处理“启发式猜测被升级成不可撤销交付义务”的结构问题：复用TaskFrame/RequiredOutput和来源结构，将建议与用户明确要求分开；模型可修订语义，不能删除用户要求/扩权/重置预算/把假设当事实。所有型号同权。不补关系词/M0例外，不同时改工具目录、方法检索、缓冲和修复轮数，不再造框架。

reading_baseline已有“可跳过/证据优先”声明，勿重复修复或全删用户确认领域知识。Knevo规则数及内部实现未核；R19超时原因仍未证。

私有探针 ~/.finance-runtime/harness-simplification-20261002/authority-probe.json；authority_probe.py禁止socket/子进程、LLM固定stub，0禁止项触发。source_revision=3b78fda25。产品实现与真实效果均未完成，未合并部署。

用户已选择整体架构范围，新增v0.1 Draft spec：docs/superpowers/specs/2026-10-02-model-owned-harness-spec.md。覆盖语义权、按需工具/方法、执行收尾、反馈及P0–P4分阶段迁移。此为设计提案，未实施；新增模型0。下一步先评审整体契约，再明确P1切片入口与版本更新方案，不把整份架构一次重写。
