# feat/e2-p6-conditioned-input

## 这个分支做什么
E2 P6（D6）第一片：material_only 逐句事实带材料锚点（`binding.claims`）、纯度按 data_scope 条件化、历史句分离；判官删句连带撤绑定。树 `fwp-wt-e2-p6-input`，主树不动。

## 决策与被否方案
- 锚点=（material_id, 逐字 quote）只证身份不证蕴含；否「quote 命中即通过」（算错也过），逐句事实/输入/推导仍交语义判官。
- 来源目录 `MaterialGrounding` 冻结进合同、from_dict 校验正文哈希；否从 prompt 现算（writer/判官/恢复三处会漂）。
- 纯度看 data_scope 不看真实性；`io_effect` 由 registry 按 spec 盖章；否 runner 自报（可自证本地）。
- 判官删句连带撤该句 claim（`_without_deleted_claims`：只撤被删句，清空转 gap）；否放宽 `binding_source_errors`（洗白洞）、否重验跳过 claims（投影漂移不再 fail closed）。
- P2 编号题残料保持一份材料，多输入靠多 quote；否改切分器（动 material_id 口径，波及跨轮身份）。
- 展开：`docs/handoffs/2026-09-16-e2-p6-material-grounding.md`。

## 当前状态
已提交 `d17ebc27`（14 文件，新模块 `material_grounding.py`，测试 54 条），未推送、未合。gitea/main 已到 `0758a423`，merge-tree 0 冲突。P5 `feat/e2-p5-cross-turn-inheritance` 并行在途，仅 `episode_factory.py` 文件级重叠。

## 已验证
`d17ebc27` 干净树：ruff 绿；pytest 11006P/0F/81S，收据 `20260916T070950Z-d17ebc27.json`（`--expect-revision` exit 0，漂移 1≤5）；pre-commit 11 道过；graph_audit exit 0（新行 PENDING）。反例：适配器修复测试修前红修后绿；删句只撤被拒句，其余漂移仍报违规；全删转 gap 不成 legal_gap。

## 未验证 / 已知边界
判官全是离线替身 + 算术夹具，未跑 live 判官；作者自验非独立 QC；前端/e2e 未跑（本枝无前端改动）。无编号 material_only（`direct_answer`）被拒后 `material_question_outputs()` 为空 → 不进 input-only rewrite，直接 degraded（实测，P4 边界）。local_only 原题号槽、fictional×full 前提送达、方法规则干扰未做。

## 下一步
1. 无编号 material_only 的 input-only rewrite 准入（`classify_repair_failure` 的 material_ids 只认编号题）。
2. live 判官真跑一次（先探网关）；独立 QC。
3. 合并等用户确认；合入后图谱行去 `@branch`。

## 踩过的坑
`repair→degraded` 且 resume 没被调：别看 phase_trace 猜，spy `admit_repair` 看 need.shape 与 issue codes；「claim text is absent」那句是判官自己删的。
