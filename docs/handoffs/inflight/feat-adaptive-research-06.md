# 在途交接 · feat/adaptive-research-06（能力包 06 · 自适应研究）

## 这个分支做什么
给连续 Episode 加「研究进展账」：每批工具后把本批新证据数（content_hash 去重）、同查询重复次数、工具连续空手、分支状态、下一轮时间窗装不下的工具，连同确定性建议码（switch_query / switch_tool:<tool>→<alts> / stalled / follow_up_divergences / branch_failed:<id>）叠进既有 `runtime_budget` 递给模型；连续 N 批零新证据且已有证据在手时收口（`finalization.reason=research_stalled`）。新文件 `intelligence/runtime/research_progress.py`，接线 `agent_episode.py`。范围合同 = 06 号单（`codex/docs-capability-upgrade-plan` 分支任务包）；任务 0 核验、命令与返回码全在 `docs/superpowers/plans/2026-09-09-capability-upgrade/progress/06.md`。

## 决策与被否方案
- 进展块骑在 `tool_budget_state` 的 `runtime_budget` 上 / 否新增事件种类——INV-R1 派生零改动。
- 底座只递事实与建议码，模型自选下一步 / 否领域规则进底座。
- 停滞收口 `WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES` **缺省 0 只提醒** / 否缺省 3——既有 loop 测试按批预算会被改账；开几批由候选臂 live 读数定。
- 去重闸拒绝记 duplicate；用户 steer 认领后停滞计数清零。

## 当前状态
提交 `4f9cfee2`+交接（基线 `gitea/main@5eb24515`，未前向合并）。**已验证**：新 15 测 + 相关套件 389 绿；全仓 8313P/1F（唯一红 watchdog 计时 flaky，base 树同红）；ruff / layer_audit / 三道棘轮门禁全绿；能力图谱在途行已加（graph_audit OK）。
**live 验收进行中**：冻结 12 题（8 复杂+4 简单）`intelligence/eval/fixtures/adaptive-research-06.questions.json`，key_outcomes 跑前写死。双旁车在跑：base=main tip 检出 `~/fwp-wt-adaptive-research-06-base` @:8811，cand=本树 @:8812（stall_finalize=3）。**首跑被 cockpit 网关整模型冷却（429 model_cooldown）打断**：污染收据归档 `~/.finance-runtime/cap06-20260909/arms/base-attempt1-429/` 不计基线；驱动器已加逐题网关预检。16:58 读 reset≈4h（约 21:05 恢复，04/10 号单同阻塞）；已挂 21:12 会话内定时续跑，会话死了按 progress §4 手动：base 批→cand 批→`cap06_read_runs.py` 两臂→差分写 progress §7。

## 未验证 / 已知边界
- 判据未跑：复杂题 key_outcomes 候选 ≥ 基线+2；简单题 0 sub_research 且 ≤6 调用且 completed；事件流可读出「建议→换路」或收口。
- 02/03/04 未交付 → 串深读/关系包/计算与 graph_lookup 适配只留合同（progress §5）。
- 8792 未切；生产启动器仍钉已被清掉的判官二进制 grok-1.0.5（旁车已改指 `~/.grok/bin/grok`，生产待用户处置）。

## 下一步
1. 续跑两臂 → 读数差分进 progress §7；三轮无改善交差分与阻塞原因。
2. 差分定收口缺省（0/3）；合 main 后图谱在途行转常规行。
3. PR 合 main 等用户确认。

## 踩过的坑
- 429 中途打批：11 题 2 秒 failed 像代码失败，降级模板还撞关键词——读数器按「failed 或答案<300 字不计答案类命中」处理；memory 已沉淀 live-batch-must-precheck-model-gateway-cooldown。
- `tool_budget_state` 不进投影，读数要读旁车独立 durable 流（`FORESIGHT_EPISODE_STORE`）。
