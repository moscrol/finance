# 判官与准入层能力损失：只读证据（2026-09-09）

## 版本边界

- 只读主目录 `/Users/a77/finance-workspace-private`：detached HEAD `b4a35fa2`，大量不属于本次任务的未提交改动；未修改。
- 本地基准 `gitea/main`：`f90af450b1be1fe80d5ad1515973503c646e15d0`。
- 当次采样冻结在上述revision；后续gitea/main移动不改变该证据归属。第一条重跑命令已固定提交；第二条若执行树已变更，需先在该提交的独立检出运行，不能拿新树输出冒称原复现。
- 第二条复现在干净树 `/Users/a77/fwp-wt-capability-upgrade-plan`（同 `f90af450`）执行。
- 生产监听 `127.0.0.1:8792` 的 PID 为 `28861`；`lsof -p 28861 -a -d cwd -Fn` 返回 `/Users/a77/.finance-runtime/finance-workspace-0060da5c1a08`。未外呼模型、未启动/修改服务。生产版本与本地主树/本地 main 不同。
- 下面两项都是确定性函数级实测，不是生产自然运行发生频率。需后续 live 对照量化用户影响。

## 实测一：同源新页补齐缺口，却不算研究进展

命令在 `/Users/a77/finance-workspace-private` 执行。通过 AST（Python 语法树）仅取 main 中相关纯函数与数据类，不导入当前混合工作树的运行时：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python - <<'PY'
import ast, dataclasses, subprocess
source=subprocess.check_output(['git','show','f90af450b1be1fe80d5ad1515973503c646e15d0:intelligence/services/repair_coordinator.py'],text=True)
tree=ast.parse(source)
names={'CoverageDelta','ProgressSnapshot','RepairWarrant','max_repair_cycles_for_tier','cycle_within_tier','warrant_repair','repair_is_warranted'}
module=ast.Module(body=[n for n in tree.body if getattr(n,'name',None) in names],type_ignores=[])
ns={'dataclass':dataclasses.dataclass}
exec(compile(ast.fix_missing_locations(module),'<gitea/main:repair_coordinator>', 'exec'),ns)
P=ns['ProgressSnapshot']
base=dict(before_evidence_ids=('old-page',),after_evidence_ids=('old-page','new-page'),before_covered_outputs=('context',),after_covered_outputs=('context','financial_anchor'),before_open_gaps=('financial_anchor',),after_open_gaps=(),independent_source_families=('official',),before_evidence_source_families=(('old-page','official'),),after_evidence_source_families=(('old-page','official'),('new-page','official')),before_evidence_targets=(('old-page',('context',)),),after_evidence_targets=(('old-page',('context',)),('new-page',('financial_anchor',))))
for kind in ['same_source_new_page','new_source_new_page']:
    data=base.copy()
    if kind.startswith('new_source'): data['after_evidence_source_families']=(('old-page','official'),('new-page','exchange'))
    p=P(**data)
    print(kind,dataclasses.asdict(p.coverage_delta),'repair_allowed',ns['repair_is_warranted'](p,cycle=2,research_tier='deep'))
PY
```

完整输出：

```text
same_source_new_page {'new_evidence': 0, 'narrowed_gaps': 1, 'newly_supported_outputs': 1} repair_allowed False
new_source_new_page {'new_evidence': 1, 'narrowed_gaps': 1, 'newly_supported_outputs': 1} repair_allowed True
```

解释：两臂都新增一页、关闭一个缺口、新支持一个答案部分，唯一变量是来源家族。`ProgressSnapshot.effective_new_evidence` 把新证据数量等同于新来源家族数量（`repair_coordinator.py:56–83`）；`CoverageDelta.progressed` 又要求该量至少为 1，因此同源新页被判没进展。`warrant_repair` / `repair_is_warranted`（`:309–334`）据此拒绝进度修复。生产快照同文件 `:70` 仍有 `and family not in before_families`，本问题不只存在于未部署分支。

能力含义：同一交易所的新公告、同一知识库新页补上关键事实，也应计入内容覆盖进展；来源独立性适合另作交叉验证维度。该函数被否并不证明每次真实 run 都立即停止，交付修复等其它路径可能兜底，需 live 查实际分流。

## 实测二：额外绑定一个答案部分，让已完成的核心答案进不了判官

命令在 `/Users/a77/fwp-wt-capability-upgrade-plan` 执行，复用现有夹具但不修改测试、不运行整套测试：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python - <<'PY'
from intelligence.tests.test_episode_verifier import _contract, _evidence, _outcome
from intelligence.services.agent_runtime import OutputEvidenceBinding
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.episode_semantic_verifier import _can_semantically_release_partial
base=[OutputEvidenceBinding('direct_assessment',('market-1',)),OutputEvidenceBinding('evidence_boundary',('market-1',))]
for label,extra in [('all_required_fulfilled',[]),('same_answer_extra_output_binding',[OutputEvidenceBinding('extra_analysis',('market-1',))])]:
    v=verify_episode_outcome(_contract(),_outcome(evidence=(_evidence('market_data','market-1'),),bindings=tuple(base+extra)))
    print(label,{'status':v.verified_status,'issues':v.issues,'fulfilled':[(o.output_id,o.status) for o in v.completion.outputs],'can_release_partial':_can_semantically_release_partial(v)})
PY
```

完整输出：

```text
all_required_fulfilled {'status': 'completed', 'issues': (), 'fulfilled': [('direct_assessment', 'fulfilled'), ('evidence_boundary', 'fulfilled')], 'can_release_partial': False}
same_answer_extra_output_binding {'status': 'partial', 'issues': ('code=unknown_output_binding subject=extra_analysis :: unknown output binding: extra_analysis',), 'fulfilled': [('direct_assessment', 'fulfilled'), ('evidence_boundary', 'fulfilled')], 'can_release_partial': False}
```

解释：第一臂的 `can_release_partial=False` 正常，因为已是 completed，不需要部分放行。第二臂两个必需部分仍然 fulfilled，正文与证据完全一样，额外部分还绑定已有真实证据；`episode_verifier.py:103–110` 标 unknown output，`:368–372` 将整体变 partial；`episode_semantic_verifier.py:3069–3095` 拒绝部分放行，`:958–978` 随即返回 gap，语义判官没有机会查看核心答案。这个实验没有声称 `extra_analysis` 内容经过语义核验；它证明多余结构字段可连坐已合法完成的部分。

建议局部隔离多余绑定、保留已有核心部分进入常规判官；补充部分若能匹配任务目标再接纳，不以新增一层模板限制模型发挥。该问题仍需从自然 run 统计发生频率。

## 其它已核实边界，避免重复施工

- V8 语义降级、W5 数值/财务锚补证、部分答案放行、删句后 `_restore_lost_observations` 都已存在。不要再提成新功能。
- `episode_semantic_verifier.py:1210–1232`：纯语义拒句被降为 issue 后直接 `_completed_public`，并无按该句补检索。`2026-08-22-v11-judge-guided-retrieval-design.md` 在本地 main 中仍为设计，代码树未发现 V11 guided retrieval 实现。现有 `judge_source_recheck.py` 是默认关闭、窄范围数值回查，不等于 V11。
- V11 旧稿写了公开稿带【质检存疑】；当前 `_annotate_semantic_rejects`（`:3390–3397`）已直接返回原文，问题留在 issues/控制面。实施 V11 前需更新集成合同，不能照旧文描述判现态。
- `kb_rag.py:1270–1295` 会在 `require_fresh=True` 时过滤索引状态非 fresh 的命中。这是检索准入，不是 LLM 判官；不能把索引版本落后等同事实过时。金融侧 #571 / `a8022698` 已将常驻 worker 改为按页判新鲜度，禁止再说整个旧知识库都被拒。该路径目前给重建提示而非当轮定向重新读取/恢复证据，可能是下一项能力提升；需与知识库侧现行 page_freshness 一起验。
- main `company_financial_evidence` 已授权 `web_search`；`financial_data_runner` 已读取 `report_period`；`web_fetch` 已存在。茅台旧案例的这些修法已做，不能再派重复单。
- 仍存在按工具名粗分来源的提示词：`research_tool_registry.py:1176–1194` 将 web_search/web_fetch 一律描述为二手材料，即使抓到官方发布页面也如此。属于策略/提示语的潜在能力损失，不是本轮实测出的 live 拒答。可把页面的真实发布主体与文件类型写入证据，使官方网页和转载文章走不同的事实使用规则。

## 建议任务拆分

1. **P0：核心答案局部放行**。文件边界 `episode_verifier.py`、`episode_issues.py`、`episode_semantic_verifier.py` 的结构入口及相关小测试。输入=已完成核心部分+异常额外绑定；输出=核心部分继续接受常规核验，异常局部隔离。以本页第二条为确定性验收，另冻 20 条真实题做逐条对照：核心事实保留率、任务完成率、有效答案长度、不必要全篇 gap 数；建议目标是该形状全篇误挡归零。
2. **P0/P1：研究进展按新信息和缺口计算**。文件边界 `repair_coordinator.py` 的 ProgressSnapshot/CoverageDelta、相关消费测试；预算分配接口保持不改。输入=同源新页、重复页、新来源转载、确实新增答案覆盖四组；输出=内容进展与来源独立性两个读数，修复依据前者与剩余任务需要。以本页第一条为确定性验收，真实同源公告补证/跨报告期/知识库跨页题验证至少能继续完成一个未完子问题；重复抓同页不得冒充进展。
3. **P1：判官指出缺口后主动补搜并局部修正**。沿现有 V11 设计与现有修复路径升级，边界 `episode_semantic_verifier.py`、`continuous_turn_adapter.py`/实际当前 finalizer 接缝、检索回调；避免与任务 2 同时改进度算法。输入=问题、已有答案、逐句质检问题、已取证据；输出=可补齐的句子完成补证/局部改写，已有成立部分保持，补不到的仍可给出研究判断和明确缺口。不能只接一个永远不开的开关。真实验收含液冷产业链因果、公司财务跨期、旧方法论+新公告各类同题两臂，统计缺口补齐率、可回答子问题数、无意义弃权率、总延迟；建议以任务完成率至少提升 15 个百分点且已有正确事实保留率不降为目标，指标须在跑前固定。

三个任务不启动生产、不自动合 main；文档以用户授权执行独立开发为准，最终 live 验收要绑定具体 revision，不拿单测数量冒充答案能力。
