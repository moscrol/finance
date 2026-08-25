# feat/disclosure-scan-p1c-claims（已收口：#401 已合、8792 已切、R5 重放通过）

## 这个分支做什么

修 P1-① 残差写手被有据呈现器必然拒收的根因：`prepare_disclosure_residual_answer`
此前走通用 builder（claim 被 `[:8]` 截断），shadow 有据链输入完全从 answer_spec
生成，#395 预置的完整包与残差契约进不了这条链。两件事：①
`build_disclosure_residual_answer_spec` 全行 VERIFIED claim + 聚合统计 claims；
② 残差契约经 `spec.prompt_constraints` 进 shadow 链 required_outputs 槽。

## 当前状态

**已收口（2026-08-26 凌晨）。** #401 已合（merge `fe657cbca987`；main 在 PR 开出后
前移 #400，已在 PR 树并入重跑合并闸：ruff 绿 + 全量 6531P/0F/12S，merge commit
与已测树零 diff）。8792 已从 `06622cc6` 切 `fe657cbca987`：T+45s healthy /
readiness 13/13 / 账本 record+check ok。冻结题 R5 重放**通过**
（`run_20260826_013124_466907`）：公开稿 = P0 纯包形状（骨架 0 命中）、31 公告号
全部包内、主名单 21 行零删除、degrade `disclosure_residual_dropped:grounded_rejected`；
**shadow raw_answer 1631 字符归纳形状**（m 轮 2541 字符复述消失），逐句绑行级
claim（`disc:row:*`），registry 64 条全装下无截断注。切流正文
`~/.finance-runtime/cutover-20260826b-8792.md`，探针归档
`~/.finance-runtime/disclosure-scan-p1c-probe-20260826/`。

## 下一步

1. **judge URLError 根因已查明**（三轮误标 zhipu）：`LLM_JUDGE_BACKEND=grok-cli`
   下 `judge_provider()` 返回 `cli://grok`，`synthesize_messages` 缺 `complete()`
   那个 cli 分支，发包前 URLError。修复 **PR #402 已开等确认**
   （`fix/judge-cli-synthesize-transport`，ruff 绿 + 6533P/0F/12S）。合并切码后
   R5 判据：shadow status 离开 `judge_unavailable`，残差具备真上场条件。
2. R5 遗留观察：模型解读**反证行**时越界一次（claim_type 不符 + 混入华北制药，
   绑了 `disc:summary:1` 而非反证行自己的 claim），被修复层删句消化。若下轮复发，
   候选加固：反证行 claim 在 registry note 里点名「解读反证请绑 disc:counter 行」。
3. deterministic_issues 的 4 个标题 warning（建议标题集合外）不阻塞；若要消除，
   把残差契约的建议标题集合与 composer 实际产出对齐。

## 踩过的坑

- `disclosure_scan_pack` 顶层 import `answer_model` 会循环，import 下沉函数内。
- `AnswerSpec.system_notices` 是必填位置参数。
- worktree 无 venv：用主树 `.venv-workbench/bin/python`，cwd 决定加载哪份代码。
- 账本 `record`/`check` 的 `--repo-root` 必须给**数据仓**（`$FINANCE_WS`），给快照
  会把 switch 行写进快照自己的 `state/`（误置账本），check 则读到 `~/.finance-runtime/`
  回退位的陈旧账。
- shadow 存证的 provider/model 字段是 **composer** 的，不是 judge 的——判 judge
  用哪个 provider 要看 `judge_provider()` + 生产启动器 env。

## 工具沉淀盘点

无新脚本。「组件写正文、模型只写边注」的补全应用：claim 集就是组件事实的完整
投影，投影缺行（[:8]）= 边注必然越界。本轮实证：投影补全后模型边注首次全部
落在投影内（越界的 1 句被确定性修复删除，不再整稿拒收）。
