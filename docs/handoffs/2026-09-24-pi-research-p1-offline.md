# Pi 式研究 P1：组合候选离线复验

日期：2026-09-24；执行分支 `feat/pi-research-loop`，独立树 `~/fwp-wt-pi-research`。
用户本轮授权「执行」，承接本单设计、分支实施、离线验证；未解释为增加模型额度、合 main 或部署许可。

## 背景与发现顺序

1. P0 的 `03453614b` 在 main 基线 `4cc15e703f81` 上证明观察驱动的研究链可达，未包含 #868 自适应候选。旧在途记的 `ce2a27131 / 166/209` 只是 1405 批快照。
2. 查到新批 `~/.finance-runtime/reviews/pr868-glm-qc-20260924-2105/`，先读 `authorization.json`、`batch.json`，随后核 `STATE.md`。原 owner 已取得累计上限 244 的授权并执行新批，不能再沿用「尚待 244 授权」的旧阻塞。
3. 2105 候选是 `f531d2d00add2bfcef04dbe7163990b1348c2317`。完整工程结果由原 owner 维护在 `pr868-gates-20260924-train-b/engineering/`；本轮没有重跑或替其签工程门禁。
4. 新批 spec 轴 `PASS_WITH_LIMITS`，C1/C2/C4/C5/C6 verified，C3（迟到判官回包的语义字段）与 C7（收据身份）not_verified。quality/explore 交付路径漏了 `/Users`，控制器退出后拒收；execute/report 未跑。整体 `BLOCKED_NO_RETRY`，累计 **213/244、余31**。完整 quality 新轴需 39，余量不足；spec 欠项也尚未闭合。本轮未把这些未分类/未运行项算作产品缺陷或通过。
5. `complete` 字段已有别的 owner 修协议，并已在 2105 的 spec 三阶段交付中生效，不重复修。路径校验前移是新建议，仍归独审 owner；本分支不修改封存批、审查者交付物或授权。
6. 在本任务分支组合 `f531d2d00add`，生成合并提交 `d21a42efe9c7f3ccff806fd71b92d8f11e355203`；没有修改 #868 分支。原定向回归在该组合为 175P/3S/1X。
7. 将本单研究链测试扩展到自适应开关 off/on、quick/deep 档，提交 `59ab6e5cf54a123737f4002c34a7bc800abc3ebc`。相对 f531，生产 runtime/services/webapp/market_feature_store/scripts 的差异为空；没有新的生产逻辑改写。

## 决策与取舍

| 方案 | 决定与理由 |
| --- | --- |
| 在本任务分支组合确切候选，离线复验 | 采用；可以推进兼容验证，又不变更原 owner 的受审候选身份 |
| 直接修改 adaptive 树或另造研究循环 | 否；已有 owner 与实现，不建立第二写者或第三条生产循环 |
| 只跑开关默认值 | 否；无法区分关闭状态的兼容性与打开后的可达性 |
| 空工具菜单一律视为预算耗尽 | 否；深度复核也是无工具模型轮，替身必须读实际消息再决定 PLAN 或终稿 |
| 从封存批剩余额度续跑，或自行抬总帽 | 否；新批需独立协议与授权，本轮不消耗真实模型请求 |
| 用 606 条定向绿代替工程/独审/自然验收 | 否；这是组合行为回归，不是完整放行证据 |

## 本次增量覆盖

`intelligence/tests/conformance/test_research_chain.py` 共 36 个参数化场景：

- 两个开关状态都验原观察驱动、失败恢复、越权拒绝、伪造引用拒绝、预算与取消边界、四类变异对照。
- deep 开关打开时，在首批成功/空/异常观察后插入一次无工具复核；替身根据实际观察构造 PLAN，之后第二 runner 收到真实线索或对应恢复查询。两种成功线索验证参数不是固定播放。
- 开关关闭的 deep 档不增加复核轮；打开时仅增加一次模型轮，工具调用仍为两次。
- quick/deep 调用槽耗尽都不插入复核或重新开放工具；取消后保留已有证据、不派第二 runner。
- 固定 `FORESIGHT_STRICT_DERIVATION=1`，沿真实 Runtime、FinanceResearchHarness 和事件投影运行；没有用放行 Harness 替身。计划中的视角自报不等于语义事实核验。

## 验证与收据

- 开发态新增文件：36P；ruff 与 `git diff --check` 通过。开发态收据不冒充干净 revision。
- 干净提交 **59ab6e5cf54a123737f4002c34a7bc800abc3ebc**：**606P/3S/1X，collected=610，18.30s**。
- 收据：`~/.finance-runtime/test-receipts/20260924T134639Z-59ab6e5c-1160ab7b55b4.json`；`dirty=false`、`worktree_dirty_total=0`，解释器与依赖指纹匹配，精确 revision/目标校验通过。
- 三个 skip 是参考后端已声明的不适用部分；xfail 是原有 codex_headless 的缺少显式修复收据基线，不是本轮新增。
- 本次真实模型请求 **0**；没有启动旁路服务、冻结数据、向 8792 发问或更改部署。

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
$PY -m pytest -q -rsx intelligence/tests/conformance \
  intelligence/tests/test_glm_agent_runtime.py \
  intelligence/tests/test_research_progress.py \
  intelligence/tests/test_adaptive_research.py \
  intelligence/tests/test_research_plan.py \
  intelligence/tests/test_episode_semantic_verifier.py \
  intelligence/tests/test_research_harness.py
$PY scripts/check_test_receipt.py \
  ~/.finance-runtime/test-receipts/20260924T134639Z-59ab6e5c-1160ab7b55b4.json \
  --expect-revision 59ab6e5cf54a123737f4002c34a7bc800abc3ebc \
  --require-target intelligence/tests/conformance
```

这是显式选取七个目标的定向回归；不能加 `--require-full-scope` 或将它写成全仓工程门禁。后续文档提交不会迁移此收据的 revision。

## 未验与下一步

1. #868 owner 先闭合独审：更新即时交付校验协议、确认新预算和新批范围，再开独立证据根。1405/2105 两个旧批都不续跑。
2. P1 只完成组合离线部分。P2 等独审和 #76 逐行授权；使用真实 Workbench HTTP 入口、独立用户根与冻结数据，验自然模型追查/换路、反证修订和公开稿一致性。本轮没有这些结论。
3. 如 #868 候选变化，按精确新组合复验；不能把 59ab 的收据签给 f531、下一候选或生产。
4. 完整工程门禁及合 main/部署分别确认后才进入 P3。没有 push、合 main、切 8792 或生产能力声明。

工具沉淀：沿用既有测试、收据校验与分支交接，没有新建临时验证脚本；本次是已有方法的组合应用，不新增跨项目工具清单，不改脏的 harness-reference。
