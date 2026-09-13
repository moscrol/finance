# feat/research-validation-03 · 2026-09-13

## 这个分支做什么
spec 03（方法验证与真实前向概率实验 v1）：冻结案例的删轨消融 + 事前概率到期评分，六函数服务 + eval 二桶适配器。只写 03 白名单路径。

## 决策与被否方案
- 外来曝光 = 任何非本 study 写的访问（否「同框架不算外来」：开「只留赢家」洞；否「只看 lineage」：换谱系即洗白）。
- 曝光匹配按同实体 + 结果区间相交（否 case_id：改描述即洗白；否精确键：相邻日共享 4 天收益判未见）。
- 已暴露 case 仍出描述读数但 verdict 置空、eligible=false（否剔除：全暴露读成「样本不足」）。
- 期末未到只报 pending 数 + 单项，平均差 / verdict 置 None（否照报：pending 却像结论）。
- 人工概率只进 forward；历史规则只收确定性；LLM 只收 replay 原件，永不改 forward。
- 详见 `docs/handoffs/2026-09-13-research-validation-03.md`。

## 当前状态
- 代码 `e38d6a63` 已提交（services/eval/tests/fixtures）；本文与 PROGRESS/BLOCKED/快照同一提交。未合 main，未推送——等用户确认。
- 无真实协议、无真实前向样本；empirical 一律 pending。

## 已验证（最终 SHA e38d6a63）
- `pytest -q intelligence/tests -k research_validation` → 89 passed；collect-only 89。
- 四组既有回归 117 passed。收据 `~/.finance-runtime/test-receipts/20260913T0702*-e38d6a63.json`。
- 全量（提交前脏树 @5fb13a8c，排除 test_codex_sandbox）8432 passed / 15 skipped / 2 xfailed。
- pre-commit 11 道全过；6 处变异各至少 1 红后复原（PROGRESS 有表）。

## 未验证 / 已知边界
- 未接真实 userspace 根 / 可信时钟 / PIT 校验器 / 真实结果源：`PitVerifier`、`OutcomeSource` 只有测试桩与旁路库实现。
- 曝光台账完整性靠 06 置 `exposure_ledger_complete=True`，缺省一律 exploratory。
- 历史规则模式的重建标签固定带 `unverified_pit` gap。
- 前向 `supported` 只在 synthetic 夹具上出现，不是方法证据。

## 下一步
1. 06 按 `docs/superpowers/plans/2026-09-13-research-evolution/03/BLOCKED.md` 接线并在 ledger-map 登记对象布局。
2. 首例真实 D0：`freeze_study` → 盘后 `register_forecasts` → 到期 `settle_outcomes` → `evaluate_study`；非交易日预建下个合格日协议。
3. 合并前重跑 AGENTS.md 等价 CI；变异探针脚本化（`scripts/` 不在 03 白名单，交集成人）。

## 踩过的坑
- `git commit -- <paths> -F -`：`--` 之后全是路径，`-F -` 被当文件；选项要放 `--` 前。
- `stats.readout / block_bootstrap_readout` 会 `bool(±0.1)`；胜出序列必须先过 `strict_bools`。
- 夹具公式要让「条件真 + 字段未知」的日子真的存在，否则三值逻辑测试测不到分支。
