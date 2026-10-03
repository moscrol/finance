# Thin ReAct Budget Visibility Implementation Plan

> 执行：本会话按顺序完成；状态回写 FINANCEWORKS-5。

**Goal:** 在既有预算内向模型公开资源并留出最后作答轮，阻止工具菜单持续诱导已无额度的调用。

**Architecture:** `run_thin_react` 在每轮调用点计算资源状态，给模型末尾资源消息和实际可用菜单；硬门保持原有独立检查。逐轮收据保存同一资源状态，避免只修改观测字段。

**Tech Stack:** Python、现有 AgentModelClient、pytest；无新增依赖或服务。

## 顺序

- [x] 在 `intelligence/tests/test_thin_react.py` 增加依菜单选择动作的脚本模型，旧实现必须重现 `tool_budget_exhausted` 空答；另验最后模型轮收菜单。
- [x] 执行 `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_thin_react.py`，记录原失败及已有通过数。
- [x] 仅修改 `intelligence/eval/thin_react.py` 调用点：计算 `max_tool_calls - calls`、`max_turns - index`、同一 deadline 剩余时间；任一菜单关闭条件满足就传 `[]`；追加资源消息，将状态记在 `model_turn` 事件。保留超额/权限/截止的既有返回。
- [x] 原红针转绿；测试余量递减、末轮总请求数、关闭后不听指令的模型仍失败、无身份不交付。运行 thin ReAct 与模型准入相关回归，以及改动路径 Ruff。
- [ ] 固定提交做两轴审查。完成本机等价门禁与 GitHub Actions 后按用户既有授权合并；F4/正式实验状态单独保持未通过，部署若无生产路径变化按发布流程记录实际边界。
- [ ] 记录修复结果、命令/产物与限制，回写预测和任务板；下一步是冻结新 R 及完整 P 的真实冒烟，不重复使用 R17/R19 启动器或结果。
