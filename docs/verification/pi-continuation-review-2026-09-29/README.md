# Pi 续做接收复审证据

本目录是代码 `d9eeb69b7d82b159d6635ca7664ee77b0be43653` 的选定原件归档；[manifest.json](manifest.json) 记录16件文件的原路径、字节数与SHA-256。它不改写另一个目录的Pi原始证据。

- `python-d9eeb69b7.json`、日志及`receipt-check.txt`：完整干净Python18,638P/74S/2X，收集18,714项，0F/0E；gate exit0，Ruff通过。后续文档提交不更换此收据的代码身份。
- `history.answer.md`、`history.episode.json`、`history.record.json`与`history.adjudication.json`：一次预先声明的真实Workbench历史首发，四项旧值与未重核边界正确，1模型/0工具/0非法动作，usable。样本没有触发修复，不证明稳定性或后端追平。
- `preflight.json`、`health.json`：原题及两消息历史身份、隔离用户根、实际加载代码。`sidecar-stop.json`确认只停本任务8837；shutdown完成、端口无监听。
- `repro-red.txt`、`edge-red.txt`：修前反例日志。不是最终失败、也不是自然问法重试。第一组有一项测试最初受草稿夹具不匹配干扰，后续修正；最终代码与独立复审见[复审报告](../2026-09-29-pi-continuation-review.md)。

前端/E2E与注册表沿用Pi `7c16a38ec` 的原身份收据，存于[原证据包](../answer-capability-2026-09-29/README.md)。本轮未改那些输入，但不将其冒签为d9新运行。未合并、未部署，财务/消息质量继续WIP。
