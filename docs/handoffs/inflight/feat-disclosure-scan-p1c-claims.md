# feat/disclosure-scan-p1c-claims（P1-①c：披露残差全行 claim 集）

## 这个分支做什么

修 P1-① 残差写手被有据呈现器必然拒收的根因：`prepare_disclosure_residual_answer`
此前走通用 builder `_build_base_answer_spec_from_sections`，证据 claim 被截 8 条
（`ask_synthesis.py` 的 `evidence_lines[:8]`），而 shadow 有据链（composer/judge）
的输入完全从 answer_spec 生成——#395 预置的完整包渲染与残差契约进不了这条链，
模型解读全名单必然越出 claim/atom 集（live R5 m 轮 `run_20260825_200157_247884`）。

两件事：① `disclosure_scan_pack.build_disclosure_residual_answer_spec`——主名单/
排除/反证每行一条 VERIFIED L3 claim（EvidenceAtom 由 evidence_ids 自动派生，fact
句有的绑）+ 聚合统计 claims（分档计数/各桶命中/关键词预算/窗口——归纳句数字出处）；
② 残差契约经 `spec.prompt_constraints` 进 shadow 链 `build_grounded_composer_messages`
的 required_outputs 槽——composer 第一次真正看见「不复述名单、点名 ≤8 家」。

## 当前状态

代码完成，本树（`/Users/a77/fwp-wt-disclosure-p1c`，从 `gitea/main@92686a9c` 开）
ruff 绿 + 全量 6527P/0F/12S。改动面：`disclosure_scan_pack.py`（builder + 常量）、
`ask.py`（prepare 换 builder，通用 builder 调用移除）、测试 +3（全行覆盖 /
registry 12k 预算内全装下 / 绑定行级 claim 的解读句过确定性校验、包外码仍拦）。

**不动的**：`gate_disclosure_residual` 四判据、#397 拒收回纯包、bind 放行条件、
`_build_base_answer_spec_from_sections` 本体（其他调用方还在用 `[:8]`）。

## 下一步

1. 合并（等用户确认）→ 切 8792 → R5 重放：预期 shadow `deterministic_issues`
   无 error、raw_answer 为归纳形状；judge 若可用则残差真上场（尾段出现档位/
   集采双重性/反证解读），公开稿名单行零增删。
2. **judge zhipu URLError 仍未排查**（m/n 两轮同形，composer 同 provider 成功）。
   它不修，judge 环节仍 fail-closed 回纯包（安全空转但比 m 轮前进：composer
   输出已可过确定性层，具备 judge 修好即上场的条件）。疑 LLM_JUDGE_* 端点/超时
   配置，查生产环境变量与 judge_provider() 分支。
3. 若 R5 重放 composer 仍复述名单（>8 码）被闸丢弃：契约在 required_outputs
   槽的遵守率问题，候选加固是把「点名 ≤8」写进 registry note 或 brief。

## 未验证 / 已知边界

- 从未 live。R1–R4 级离线判据全绿，R5 需切码后重放。
- registry 预算：冻结题夹具 11 行全装下（12k 内）；live 名单 35 行（24+8+3）
  估算 ~9-10k 也应装下，但未实测——重放时看 `grounded_composer_shadow.json`
  的 registry 是否带「因窗口预算未纳入」注。
- `prepared_synthesis_messages` 仍预置（grounded_presenter 关闭时旧散文路径用），
  与 shadow 链双轨并存，行为向后兼容。

## 踩过的坑

- `disclosure_scan_pack` 顶层 import `answer_model` 会循环：
  `research_contract → query_resolution → query_understanding → disclosure_scan_pack
  → answer_model → research_contract`。答案 import 下沉函数内 + TYPE_CHECKING。
- `AnswerSpec.system_notices` 是必填位置参数，直接构造时别漏。
- worktree 无 venv：用主树 `.venv-workbench/bin/python`，cwd 决定加载哪份代码。

## 工具沉淀盘点

无新脚本。「组件写正文、模型只写边注」模式的补全应用：claim 集就是组件事实
的完整投影，模型边注的每句都要能绑回组件行——投影缺行（[:8]）= 边注必然越界。
