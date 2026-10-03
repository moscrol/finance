# 薄 ReAct 预算可见性工程验证

任务 `FINANCEWORKS-5`，预测 `R-20261004-01`。基线 `ee8f3c48c`，只改评测用薄循环及其测试；不改生产 P、不改真实金融题答案。

## 结果

旧实现：新增三个场景均失败，原有 18 条通过。工具用尽后的场景返回 `tool_budget_exhausted` 空答；最后模型轮场景返回 `model_turn_budget_exhausted`，即使此前工具已返回证据。

候选：每轮给出剩余工具/模型轮数和同一截止的余秒。工具用尽或最后轮时菜单为空，模型使用现有证据自主作答。最后一轮是既有配额中的一轮；超额工具意图仍拒绝，绝对截止前再次检查，未增加默认额度。

同针转绿；薄循环及父子模型身份相关 **78 passed**，Ruff/diff 检查通过。定向结果是开发工作树读数，不能转签固定提交的完整门禁；独立审查、全量门禁与合入状态另记。

## 原件与复验

- `~/.finance-runtime/harness-quality-closeout-1003/thin-budget-red.log`：3 failed / 18 passed。
- 同目录 `thin-budget-green.log`：78 passed。
- 开发收据 `~/.finance-runtime/test-receipts/20261003T165729Z-ee8f3c48-9718eed23639.json`，包含未提交源码状态，不称干净 SHA 验收。
- 命令：`.venv-workbench/bin/python -m pytest -q intelligence/tests/test_thin_react.py intelligence/tests/test_model_admission.py tests/test_model_admission_self.py tests/test_model_admission_branches.py`。

最初抓取测试退出码时用了 zsh 只读变量 `status`，外壳报错；pytest 已完成且原始日志显示 3F/18P。后续改用 `thin_test_rc`，没有将外壳错误当产品失败。

## 限制与下一步

脚本模型只证明预算信号、菜单和实际派发一致，不证明真实模型听从或金融回答正确。R17 的真实 RG/RC 空答与 R19 的质量失败保留；本次零真实模型调用，不回填历史结果，不启动正式 240 次。

下一次 F4 前必须重新固定 R 文件/提示哈希及 P 的主干 SHA，再使用原始评分器和完整身份审计。薄循环资源策略属于 harness 干预，须在实验收据中披露，不能把旧 R 结果与新 R 结果混算。
