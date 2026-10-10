# 原会话交接快照（非当前状态）

保留自 `feat/knevo-skill-layer-1009` 未提交成果。2026-10-10 接手发现工具被白名单屏蔽、自检循环和失败误报；
下文是修复前原文，不代表当前验收。当前状态看 `inflight/fix-knevo-pi-runtime-1010.md`。

## 这个分支做什么

把 knevo 的 skill 层（1 入口 + 专项）炼化成 harness 中立的运行时资产，先挂到 Pi 原生验证，再作为 8792 可切换后端接入。
基 `6c1d9f5d4`（gitea/main = origin/main）。用户决策：先 Pi 原生。审计结论：10-06 至 10-09 的线一条 knevo 工具包机制都没进代码。

## 决策与被否方案

| 选择 | 否了什么 | 理由 |
|---|---|---|
| 方法论进 SKILL.md 让模型执行 | 再加程序门 / 判官 / 合同槽 | 同模型对照里 8792 输在出口拒收门，knevo 的交付前检查是模型自检 |
| 先 Pi 原生再接 8792 | 直接改 Episode | Pi 四个接缝现成、无出口门包袱、对照架子（bridge）已在；Codex 线正在改 Episode 出口文件，避免同改 |
| 硬触发只定「必须查」，不定「用哪张表」 | 沿用 mandatory `mainline_context` | Pi 赢的那行（行业全截面）就是被预塑形合同锚死的 |

## 当前状态

- 资产：`skills/finance-mode`（OS）+ `finance-market-review / finance-analyze-stock / finance-industry-track / finance-forecast-event`。
- 接线：`integrations/pi/{finance-mode.ts, bridge.py, rag_binding.py, run_native.py, README.md}`。
- 测试：`intelligence/tests/test_knevo_skill_layer.py`（frontmatter 合同、无市场事实、knevo 锚句、Pi 对照错句形状、扩展接缝文本合同）。
- 设计：`docs/superpowers/specs/2026-10-09-knevo-skill-layer-design.md`。
- **没有模型读数**：尚未跑首发；`run_native.py run --dry-run` 与扩展加载冒烟见本分支提交说明。
- 8792、生产库、Codex 分支、全局 Pi 配置均未动。

## 已验证 / 未验证

已验证：见提交说明里的 pytest / ruff / 注册表四项 check / dry-run / 扩展冒烟读数。
未验证：真实首发（需用户授权花钱）；`spawn_sub_agent` 子进程真实跑通；`--second-look` 效果；bridge 在受管 RAG 代际下的 `/configure`（dry-run 不起 bridge）；与 8792 的同题对照。

## 下一步

1. 用户授权后：选对照题（建议沿用 10-09 的 9/30 复盘题与同一只读库），`prepare` → `run`，单变量：只挂 skill 层，second-look 关。
2. 独立全文阅读五类错句 + `RESULT.json` 的 `skill_reads / tools_used / sub_agent_calls`。
3. 读数清楚后再做 8792 接线（spec §4），且基于 Codex 线出口门收完之后的 HEAD。
4. A（机制全表子 agent）回来后补 skill 正文里缺的条目。

## 踩过的坑

- Pi 只有在 `selectedTools` 含 `read` 或 `bash` 时才把 skills 列进 system（`dist/core/system-prompt.js`）；`--no-builtin-tools` 会让专项静默消失。所以开 `--tools read` + `tool_call` 守门限定 skill 目录。
- 子 pi 进程不会继承父进程的 `-e` / `--skill`，要在 spawn 参数里显式带上；深度用环境变量钉死。
- `pi_bridge.py` 的 `/configure` 依赖产品臂的 `continuous-episode.json`，Pi 单独验证时没有它，改为从载荷取截止日 / tier / 日期。
- `~/agent-memory` 的项目笔记已登记本分支归属（2026-10-09 深夜那条）。
