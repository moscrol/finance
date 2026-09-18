# RAG 修复与单次 GLM 验收收据

[决策、发现顺序、被否方案及后续](../../handoffs/2026-09-19-rag-framing-and-glm-live.md)。

| 层 | 结论 |
|---|---|
| 固定工程20939b18 | **11703P/81S/2X；前端115P、E2E34P/2S；全部叶子绿**，检查前后干净 |
| 响应分帧 | 定向69P，六撤保护各红/恢复绿；合并/半行/UTF-8/绝对deadline/身份/进程替换均有回归 |
| 原件回放 | 旧Mapping失败44证据反馈不丢，旧保稿两路径过；0新模型/工具/DB |
| 新live一次 | `run_20260919_002806_645542` completed，published精确匹配，probe exit0，2137字答案、报告partial |
| 自然纠参 | 缺entity_codes后补全并有compute结果；find_analogues参考窗口4次错误未解，原缺end未触发 |
| 自然结束纠格式 | turn13拒收→turn14正确JSON；正文2096→2094字仅两处替换，bindings/refs不变 |
| 系统保稿 | **未证明**；首稿字符串有未转义换行，候选None、保留计数0；模型自然重写不是机制证明 |
| 金融质量 | **作者复核not_passed**：8误写12、正终点收益外推无下跌路径、不同PCB口径未区分等；同源judge通过不代签 |
| 总裁决 | **not_passed**，未push/合main/部署，旧两次失败不改判 |

## 精确身份与主要原件

`R=~/.finance-runtime/reviews/research-rag-framing-repair-20260919/`

- revision `20939b18bcb4a00f1eec9098dc52887ab1f71c02`。
- user `probe-rag-framing-20260919`；conversation `conv_b1cf0368ed3f4a66ad0bb5f437f27f0a`；assistant `msg_04f66e8b950242888b8703babe3317b6`。
- `checks-summary.json`＋各叶log/exit、`pytest-receipt.json`：全量收据源 `~/.finance-runtime/test-receipts/20260918T162610Z-20939b18.json`。
- `red-framing.*`、`red-process-state.*`、`green-*.log`：开发先红后绿；不移绑完整收据。
- `mutation-summary.json`及六撤保护日志、`mutation-restored.log`：独立副本69P恢复，非独立QC。
- `rag-repaired.json`正确期待exit0；`rag-opposite-expectation.json`反向期待exit1；`offline-repaired.json`、`preservation-replay.json`是旧原件离线验证。
- `protocol.json`＋`launch-config.json`：代码/行情/实际provider、预算和一次性约束；`submission-reserved.json`在POST前预占名额。
- `probe.log/.exit`、`capture.json`、`public-projections.json`、`public-answer.md`；私有episode在本根精确users/run，事件在`capture.json`指明的episodes目录。
- `live-review.json`：正式作者裁决。`capture.json`保留最初pending_artifact_review，不覆盖它。
- `inspect-live.log/.exit`第一次错把私有episode要求在公开列表里，exit1保留；`inspect-live-corrected.*`修量具后exit0。不是服务失败也不是重发。
- `closure.json`：所属服务关闭，七项生产身份和启动器/数据未变，生产仍bf662e9310ff。
- `previous-bundles-before/after.json`：旧214/44/90/6/82/296/338/341文件包逐项未变。
- `secret-scan.json`首扫14个模块引用词形命中、exit1；reviewed精确核销未决0，非全包零命中。文本/ZIP文本扫，二进制只hash。
- `artifact-index.json`：423文件/17991204字节，SHA256 `877af81dfbabec17eba778faa14f364aca22a801bdd958a614dbd7c6afe6b720`；仓内manifest为同字节副本。

`receipt.json`为acceptance-summary副本加archive身份。不继承到文档tip，不改变原7a9380bd全量1F或旧live裁决。

## 可复跑离线量具

```bash
PY="$HOME/finance-workspace-private/.venv-workbench/bin/python"
OUT="$(mktemp -d)"
"$PY" scripts/review_probes/replay_rag_buffered_late_response.py \
  --expect repaired --output "$OUT/rag-repaired.json"
```

默认`--expect failure`仍期待老缺陷；在新修复上应exit1。它只验真实消费者＋合成process/OS管道，不调用模型/知识库，不证明本次自然模型使用过kb_search（实际未调用）。
