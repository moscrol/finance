# W1 判官降级权：必需输出块的否决改「降级保留」（R-20260821-07）

> spec：`docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md` §W1（形状 C 主修）。
> 分支 `fix/judge-block-degrade`，基线 `gitea/main = 0ed258b5`（spec #300 合入后）。
> 实施方文档；判据预注册见台账 `R-20260821-07`。

## 1. 前置核查（spec 要求的三条）

### 1.1 r24 合入后 marker_loss 的现行为（基线确认）

- 既有测试基线：`intelligence/tests/test_episode_semantic_verifier.py` 改动前 **170 passed / 0 failed**（收据 `~/.finance-runtime/test-receipts/20260821T135726Z-0ed258b5.json`）。
- 现行为逐层核对（一手读码 + 新钉先红时的实际输出）：
  - `_repair`（verifier）= `_drop_rejected_sentences` **精确句级删除**（accepted prose byte-for-byte 不动）+ `_restore_lost_observations` 槽保护回填。没有「删整段/删整格」的机械动作。
  - `_marker_loss_partial_public`（verifier:2330 邻域）= r24 记账收缩（`_shrink_verified_for_marker_loss`：missing + gap + 清绑定，**不动 draft**）+ wiped 稿发布 + **`_marker_loss_gap_sentence` 道歉横幅**挂稿尾（「结构缺口：X…应重做这些部分」/「证据缺口：X…需补充直接证据后再判断」）。
  - 所以「删整格正文」的物理动作发生在**判官删句**层（reject 的句子恰为该格全部实质内容时，效果=整格消失）；lost 格未被 reject 的句子（残块）实际保留在 wiped 稿中——新钉先红输出实证：`'申万电力设备指数同期涨幅需另行核对…' 已在 public，尾随旧横幅`。W1 的增量因此收敛为：**横幅→块级标注**（呈现形态），删句纪律与记账口径不动。

### 1.2 「输出质检」段呈现通道（B 臂反查）

- 机制名：`conversation_orchestrator._with_review_appendix`（`_REVIEW_APPENDIX_HEADING = "输出质检"`）。
- 写入口：`SemanticEpisodeOutcome.to_dict()` → `continuous_turn_adapter.py:1069` `private_artifact["semantic_verifier"]` → `_continuous_review_notes` 取 `issues` → 拼「## 输出质检」附录。
- B 臂 `run_20260821_164659_624916` answer.md 实证：判官批评（1 条）在「## 输出质检」段、正文零删句——通道已存在且覆盖 marker_loss 路径（A 臂/955225 的 answer.md 同样有该段）。W1 不改此链路。

### 1.3 道歉横幅的生成点与触发条件（两条路径已区分）

| 路径 | 生成点 | 触发条件 | W1 处置 |
|---|---|---|---|
| 部分 marker_loss 横幅 | `_marker_loss_partial_public` 的 `gap_body=_marker_loss_gap_sentence(...)`，经 `view(TerminalFacts(cause=CAUSE_EVIDENCE_GAP,...))` 拼「残稿\n横幅」 | marker_loss 非空且非全灭 | **改为【待复核】块级标注** |
| C3 全灭闸 | `_marker_loss_or_withhold` → `_repair_wiped_all_required` → `_emit_withheld_repair`（回退 pre-repair 稿，`repair_withheld=True`，verifier:1033/1168/1293 三个调用点） | 修复删空**每一个** evidence-grounded 必需格 | **语义不动**（判据④回归钉守着） |

## 2. 实施内容

单文件核心改动 `intelligence/services/episode_semantic_verifier.py`：

1. `_marker_loss_gap_sentence` → `_marker_loss_block_annotation`：道歉横幅（含「应重做这些部分」「需补充直接证据后再判断」行动指令）改为【待复核】块级标注——状态陈述，点名降级格 label（含 `_gap_task_context` 任务上下文前缀），**r24 归因分流保留**（`all_were_fulfilled=True` → 「结构核验原判达标，非证据不足，无需补充数据」；`False` → 「缺少直接证据支持」）。标注文本由 harness 结构化生成（判官只产 issue 不产正文，never-add 不破）。
2. 呈现结构（`TerminalFacts` cause=EVIDENCE_GAP、残稿+gap_body 拼接）、r24 记账、句级删除、numeric gate、C3 闸、`_gap_answer` 全部不动。

## 3. TDD 记录（先红后绿）

钉位对齐 spec §W1 判据小节：

| 钉 | 测试 | 先红证明 |
|---|---|---|
| ①⑤ 块内 N 句删 1 句→残块保留+missing+批评在案+块级标注可见 | `test_partial_block_deletion_keeps_remainder_and_annotates`（新增，`_counterpoint_remainder_structural` 三句稿、judge 桩按文本 reject） | 红于 `assert "【待复核】" in public`（当时输出=残稿+旧横幅） |
| ② numeric_unsupported 句仍被删（白名单回归钉） | `test_semantic_repair_cannot_remove_a_visible_required_output_marker` 保留 `assert "99999亿元" not in` | 改造前后均绿（回归钉） |
| ③ 残块为空→无横幅 | 同上测试改造：`"结构缺口" not in`+`"应重做" not in`+`"需补充直接证据" not in`；另 `test_outlook_repair_that_leaves_only_boundary_is_partial_with_gap`、`test_valuation_marker_loss_gap_keeps_task_context` 同向改造 | 三钉先红（旧横幅在档） |
| ④ 全灭→C3 横幅路径保留 | `test_terminal_redaction_withholds_when_last_required_slot_would_vanish`（既有钉，**未动**） | 全程绿 |
| 归因分流单元钉 | `test_judge_delete_keeps_grounded_values.py` 三钉改造为 `_marker_loss_block_annotation`：fulfilled→含「非证据不足」禁「应重做/需补充直接证据」；not-fulfilled→含「缺少直接证据」禁「非证据不足」；上下文前缀 `【待复核】钙钛矿电池的直接回答` | 先红（旧函数名+旧文案） |

- 红读数：4 failed（20260821 先红轮，`-k "partial_block_deletion or cannot_remove_a_visible or outlook_repair_that_leaves or valuation_marker_loss_gap"`）。
- 绿读数：`test_episode_semantic_verifier.py` **171 passed**（收据 `20260821T140708Z-0ed258b5.json`）；受影响四文件合跑 **280 passed**（`20260821T140825Z-0ed258b5.json`）。

## 4. 变异测试（≥2，先 commit 后变异）

第 0 步：实现已提交 `6e954192`（变异用 `git checkout --` 还原到已提交态，不丢实现）。

| 变异 | 改了什么 | 哪条钉红 |
|---|---|---|
| A「降级改回删整格」 | `_marker_loss_partial_public` 中 `public = ""`（残稿不发布，等效恢复整格连坐删稿） | 4 钉红：`test_partial_block_deletion_keeps_remainder_and_annotates`（残块正文断言）、`test_semantic_repair_cannot_remove_a_visible_required_output_marker`、`test_outlook_repair_that_leaves_only_boundary_is_partial_with_gap`、`test_valuation_marker_loss_gap_keeps_task_context` |
| B「块级标注去掉」 | `gap = ""`（降级块静默保留，破诚实红线） | 同 4 钉红（红在【待复核】可见性断言） |

两次变异后均 `git checkout --` 还原并复跑绿。

## 5. 机制证明：原始工件重放 before/after（沿 #298 模式）

live 不可按需强触发。夹具冻结自原始 run 工件（`~/.local/share/finance-workbench/users/linxiaoqi5111/runs/run_20260821_171744_955225` 与 `.../users/probe-r05a-0821/runs/run_20260821_185226_491046` 的 `continuous-episode.json`：draft/evidence/bindings/required_outputs + 判官删除范围片段 + 历史 answer.md），进 CI：

- 夹具：`intelligence/tests/fixtures/judge-block-degrade/huangshi-direct-assessment-955225.json`、`taichen-counterpoint-491046.json`（命名沿 `pv-perovskite-e4.json` 惯例）。
- 重放测试：`intelligence/tests/test_judge_block_degrade_replay.py`（2 passed）。

| 案 | before（历史 answer.md，工件在档） | after（当前代码重放读数） |
|---|---|---|
| 955225 个股 direct_assessment | 残稿+「结构缺口：直接回答用户问题并说明判断强度…应重做这些部分。」横幅 | 残稿逐句保留（「走势分四段…」）；被删三句（缩量一字板/基本回吐全部涨幅/题材连板脉冲）照删；`gap_output_ids=('direct_assessment',)`；尾行=`【待复核】直接回答用户问题并说明判断强度：相关表述在质检复核中被移除，已按缺口记账（结构核验原判达标，非证据不足，无需补充数据）。`；「结构缺口/应重做」0 命中 |
| 491046 R-05 A 臂 counterpoint（残块为空形态） | 194 字残稿+「结构缺口：提供主要反证或竞争性解释…应重做这些部分。」横幅 | 残稿保留（太辰光区间+市场宽度句）；反证段 12 句照删；`gap_output_ids=('counterpoint',)`；尾行=`【待复核】提供主要反证或竞争性解释：…（结构核验原判达标，非证据不足，无需补充数据）。`；无横幅 |

## 6. 全量门禁

- `ruff check .`：All checks passed。
- 全量 `pytest -q`：见交付收据（`~/.finance-runtime/test-receipts/` 最新一条，报告正文引用具体文件名与 passed/failed 数）。基线 5888 passed / 0 failed，只升不降（本单新增 3 钉：1 新钉 + 2 重放钉）。

## 7. 禁区自查

- `acceptance.py` `episode_fulfilled_hashed` 口径：**未触碰**（历史夹具 `b3-r4-batch2-episode.json` 相关测试全绿）。
- 判官 never-add：标注由 harness `_marker_loss_block_annotation` 结构化生成，判官仍只产 issue。
- 无第二修复窗：未新增任何判官/修复调用。
- #298 投影选集、#289 槽保护、#296 题形降级：零改动（全量绿佐证）。

## 8. 已知边界

- 「块」无机械边界（marker 是词表子串匹配，非段落结构），块级标注因此挂在公开稿尾部、按格 label 点名，而非内嵌到残块句间——内嵌需要块边界判定，会引入新的误判层（spec「认不出来就 fail closed」纪律）。
- 残块为空与非空共用同一标注文案（状态陈述对两者均为真）；判据③的「无横幅」按横幅特征文案（结构缺口/证据缺口/应重做/需补充直接证据后再判断）断言。
- `_gap_answer`（sanitize 后 public 为空的整稿缺口档）与 rejected 终态路径不属本单，未动。
- live 前瞻观测（部署后 marker_loss>0 的 run 公开稿无横幅+带标注）待部署窗执行；本单交付止于 PR（不合并、不部署）。
