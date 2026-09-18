# runtime-contracts-0918

## 这个分支做什么
沿 OPT-08 吸收 pi/dsh 行为合同，不叠框架；先 P0 保存/截断，再 P1 恢复/子存储/回读/插话，最后 P2 工具属性。

## 决策与被否方案
- 关键保存失败阻断新效果，普通进度 sink 不夺权；否静默降级为临时运行。
- 已收结果/费用私有保留，未知效果标 uncertain；否清空历史/无限等线程。
- 模型与 Episode 共享执行取消，产品用户取消独立；否把内部错误伪装成用户停。
- 明确截断不执行合法 JSON/工具，不暗重试；否「能解析即完整」。
- 背景/方案对比/完整收据：`docs/handoffs/2026-09-18-runtime-contracts-p0.md`。

## 当前状态
独立树 `~/fwp-wt-runtime-contracts-0918`；代码 `48823062`，基线 `0a1cb8c4`。P0 工程验收通过；P1/P2 未实施。未 push 金融分支、未合 main、未部署；用户授权继续实施，不含上线。

## 未验证 / 已知边界
- 活进程保存故障隔离≠崩溃续跑；写后确认丢失可能留下 terminal state，内存 failed 收据未必可恢复。
- Future 顺序桩≠真实外部线程强杀/排空；API 装配真跑但 provider/tools 为 double。
- `restore_episode` 只出 ResumePlan，不消费；子研究无完整 store；E 号回读、Workbench 插话仍待接。
- 未做真实同预算模型质量对照或独立复核，不外推 SDK、exactly-once、重复费用。

## 下一步
1. 先检查恢复所需 snapshot/预算/父子身份/消息是否齐全；缺失 fail closed，不以日志缺席推断未执行。
2. 同一 loop 接 driver，临时目录中断验已确认工作不重做、预算不重置、消息不丢；再子存储、回读、API/UI。
3. P2 逐工具 replay/parallel/exclusive；每批变异+四叶另验；合并/部署需确认。

## 踩过的坑
- E2E 改端口时必须同时传 `RE06_E2E_URL`；首轮1F/33P/2S保留，补变量才34P/2S。
- pytest/收据检查都用主树 `.venv-workbench/bin/python`；全局 latest 会被别枝覆盖。
- SSE 规范事件 `message.complete`；读到终态≠已送达，检查 cursor 后未发事件。
- 图谱脚本在 `~/agent-memory/scripts/graph_audit.py`，不在金融仓。

## 已验证
干净 `48823062`：Python11495P/81S/2X、ruff；前端四项（107P）；E2E34P/2S；registry四项+crosswalk。13变异全红→还原绿，所选三文件前后167P（非全仓）。证据 `~/.finance-runtime/reviews/runtime-contracts-48823062/`；精确全量收据 `20260918T091215Z-48823062.json` 七项核验通过。
