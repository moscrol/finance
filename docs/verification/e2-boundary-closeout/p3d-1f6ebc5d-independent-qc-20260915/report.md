# E2 P3d 独立复核报告

## 裁定
**P3d：通过（仅限本片四个生产者）；不代表完整 P3、整链零读取、合并、部署或产品验收。** 未发现本片 P1/P2/P3 退修项。审查应用固定为 `1f6ebc5de9e906ccedf70c0377d45919fb5f7b34`，工作树 `/tmp/e2-p3d-qc-1f6ebc5d`；未修改、提交或联网。

## 独立阅读与源码结论
我实际阅读了 AGENTS、指定 prior-read handoff、既有 P3b/P3c 报告，并审读 `git diff dcd57d60..1f6ebc5d`。`intelligence/runtime/conversation_orchestrator.py:1975-2129` 在 controller 返回 `TaskFrame` 后，从同一 `task_frame.material_contract.data_scope` 派生 `material_only`：

* inherited answer spec 在 `_load_answer_spec` 前短路；
* stance pack 在 `should_run_stance_pack` 前短路；
* research lane 的 `research_project.prior_for_turn` 前短路；
* `perspective_lab.active_runtime_prompt` 前短路并注入空串。

因此 Episode 工厂事后丢字段不再是唯一防线。非 `material_only` 路径仍调用生产者；项目先验异常仍位于原 try/except 内（不能据此声称异常路径零尝试，测试需验证“已尝试后吞错”）。注释明确不覆盖 controller 之前已经读取的 history/context。

## 实际执行
命令（指定解释器、显式 cd）：
```
cd /tmp/e2-p3d-qc-1f6ebc5d && /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_e2_turn_prior_reads.py
```
独立执行结果：**16 passed in 0.67s，pytest exit 0**。日志及 exit 保存在：
`/tmp/e2-p3d-qc-1f6ebc5d-resume-20260915-evidence/focused.log`、`focused.exit`。
测试使用临时 store / 脚本化生产者并真实运行 `run_turn`，覆盖 canonical/legacy frame、material_only 与普通/full/local_only 路径、四生产者计数、项目先验异常吞掉、Episode 边界内容传递等断言；本次不把作者全仓收据当独立通过依据。

## 关键限制与未覆盖
1. 当前针的题号断言已动态取 frame 题号；因此它证明 frame→Episode 一致性和材料文本传递，但**不证明原始输入中的 q3 一定被识别为题目**。续接材料指出 BODY 合成 q3 被解析进材料；这是上游输入解析/夹具边界，不能归因成 P3d 回归，也不能用本片通过掩盖。建议后续单独审 QueryResolver/预取解析。
2. `local_only` 正例证明本片不误杀路径，但不等于 local_only 各先验真实 IO 审计；本片没有覆盖 controller 前 history/context、可信继承链、预取澄清、九类来源过滤、恢复/压缩/子研究、交付后读取、P4–P7。
3. 本次未运行全仓、前端或服务健康检查；无网络/金融 API/生产库访问。禁止 IO 计数应以独立测试的计数器为准，而非异常或退出码；本轮四生产者 material_only 计数为 **0/0/0/0**，正例各为 **1**，项目先验异常场景记录了尝试后被吞异常。测试未声称整链零 IO。

## 证据完整性
证据目录未清理；应用树无改动。作者此前 29P、全仓 9797P、变异测试和宿主修正版仅作背景，不是本独立裁定。报告路径：`/tmp/e2-p3d-qc-1f6ebc5d-resume-20260915-report.md`。
