# feat/e2-material-contract-impl：E2 材料题边界实施（P1 已落，待评审）

## 基线
设计稿 v10 已获 QC 复审通过（b397764f/c36c57af，分支 feat/e2-material-contract-design
@ ec54ef55）。QC 三条实施守则：①两处识别共用同一份词表（已做到：第 1 步复核与第 2
步指令识别共用 _STATE_OP_LINE_RE/触发表常量）；②模糊续轮测试断言 boundary_uncertain
+未复位+零预取+零工具调用（未复位/零副作用属 P3+ 阶段接线后断言）；③A17 覆盖引导块/
缩进/长文/闭合引用对照，A7 用全新会话+原始 T2→T3。

## P1 已落（本提交）
- `intelligence/services/user_task.py`：新增 `classify_top_level_regions`（先保护后解释、
  强弱保护分级、内容复核两类状态操作、指令区三类、编号题组允许空行分隔、三态分类）；
  `MessageParts.regions` 新字段；`split_user_message` 改为包装（旧抽取行为零改动）。
- `intelligence/tests/test_e2_top_level_regions.py`：10 测试——T2 形态（8 题+约束）、
  T3 形态（引导块内续轮→uncertain）、缩进禁令、引导块尾禁令、闭合引用不升级、
  未闭合围栏、顶层约束指令、纯贴研报不触发、句中「继续」叙述不误报、旧行为兼容。

## 验证
- P1+S1/N1 回归锁：40 passed + 1 xfailed。
- 广扫 8039 passed / 4 failed——4 个全是已记录在案的旧缺陷与本次 diff 无关：
  scripts_module_references×2（扫 .claude/worktrees 残留，隔离也挂、基线即挂）；
  conversation_orchestrator 与 ticks_scales_price 隔离复跑即过（顺序依赖旧缺陷）。
- ruff 干净。

## 下一步（P2，按设计稿 §5）
TaskFrame 载体（premise_marks 并行字段+默认省略）+ D2 两轴检出 + D3 投影。
P1 的 regions 目前只挂载、未被消费——消费方接线从 P2 开始。

## 不要做
- 不在主检出树跑 CI/下结论；不改原始 T3；不跑正式 PK；不宣称材料题契约就绪。
