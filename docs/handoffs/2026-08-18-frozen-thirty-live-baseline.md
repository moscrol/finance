# Handoff：冻结 30 题 live 基线——端到端答案质量评估重启

日期：2026-08-18
派单人：主 agent（2026-08-18 评估盘点批次）
背景：端到端答案质量评估断档两周——最近的合成质量回放停在 08-03/08-04，28 题产品验收台是 08-09 时代；之后新增评估全在检索层（08-15 rerank 基线）与运行时层（08-16 Arm A 45×）。冻结 30 题目前只跑 dry-run 契约缺口，不判质量。本单把它跑成可对比的质量基线。

## 目标

用冻结 30 题（`intelligence/eval/frozen_question_set.py` 所辖题集）跑一发 **live 全管线**，逐题机器判分，产出：

1. 机读基线文件（放 `intelligence/eval/measurements/`，命名带日期与 8792 等效 revision）
2. 人读报告 `docs/verification/2026-08-18-frozen-thirty-live-baseline.md`：分轴分布、失败分类、成本延迟统计
3. 台账登记：这是答案质量的**回归对比锚**，后续大改动（数据根修复、死资产接线、prompt 变更）前后各跑一发对比

## 先决条件（顺序硬约束）

1. **#164 数据根修复已合并**且 sidecar 环境继承了修复——否则盘面依赖题全拿「无市场数据」降级分，基线记录的是残废状态，失去对比价值。执行前用一题带盘面依赖的题冒烟验证市场通道确实通了。
2. 若 #164 迟迟未交付而用户要先看基线：允许跑「降级基线」，但报告标题与台账必须写明「无市场数据状态」，且不得与修复后基线混序对比。

## 执行规格

- **跑法**：#152 sidecar live probe（不碰 8792），`WORKBENCH_GROUNDED_PRESENTER=1` 等生产同参；逐题落 `llm_context.json` / `answer.md` / trace 收据（探针已支持）。
- **判分**：用仓内现成判分机器——`finance_answer_rubric`（含机构胜率等维度）+ acceptance axes。判分模型与答案模型**异源**（答案走 relay 主模型，判分走 builtin GLM，或反向；不可行则在报告里显式记录同源 confound）。判分代码只读不改。
- **次数**：每题单跑。方差治理已有文档（`10_knowledge/eval-harness-variance-governance.md`），报告里引用其结论说明单跑局限；不在本单做多跑统计。
- **失败分类纪律**：题目跑挂分两类记——`infra_fail`（探针/超时/环境）不计入质量分布，`quality_fail` 才计入。infra_fail 的题重跑一次，仍挂就记档不硬凑。
- **成本延迟**：逐题记 elapsed 与 token 用量（trace 有），报告出分布，供后续「评估一轮多少钱多少分钟」决策用。

## 已知局限（报告必须自陈）

- 题集非独立出题（08-10 章审自陈「题目我出、判分我判」，用户独立出题复测只有 8/10）。本基线用于**回归对比**，不做绝对质量宣称。独立出题人是 open item，不在本单。
- 30 题覆盖面偏知识/逻辑题；接线修复后的盘面能力覆盖靠其中市场依赖子集，报告里把这个子集单独列出。

## 实施边界

只动：

- 跑评估的驱动脚本（若需要薄封装，放 `intelligence/eval/`，不改判分器本体）
- `docs/verification/` 报告 + measurements 基线文件 + 台账

不动：

- 题集本体（一个字都不改）
- prompt、检索、判分器逻辑（发现判分器 bug → 记档另单，不顺手修）
- 8792 与 launcher

## 验收标准

1. 30 题全部有收据（llm_context/answer/trace 三件，路径写进报告附录）
2. 机读基线 + 人读报告落盘并合并
3. 判分异源（或 confound 记录在案）
4. infra_fail / quality_fail 分类清楚，infra_fail 有重跑记录
5. 台账登记「基线锚」用法：后续对比跑法与本次同参
6. 四件套绿（若加了驱动脚本）

## 红线

- 不切 8792
- 结果不好看也原样入账——基线的价值就是诚实
- 不许为提分重跑挑好的（cherry-pick）；重跑只允许 infra_fail 场景且记录在案

## skill 与工具建议

skill：leila-runtime + tdd（若写驱动脚本）。工具：live_probe（#152 sidecar）、pytest、Gitea API。
