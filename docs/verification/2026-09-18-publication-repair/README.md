# 研究答案保留：两处修复已提交，新真实验收未运行

[发现顺序、被否方案与后续](../../handoffs/2026-09-18-publication-repair-blocked.md)。

## 结论分账

| 对象 | 结果 | 不代表 |
|---|---|---|
| Mapping进度投影 `365627fd` | 真parser/错误消费者能反馈，旧44证据不变 | 真模型自然补日期 |
| 发布边界 `49fd8d72` + 静态产物 `7a9380bd` | 确定性回归、四撤保护、前端115P/E2E34P2S通过 | 跨进程补发布/金融质量 |
| 干净7a9380bd全量 | **11686P/1F/81S/2X**，RAG worker复用测试红 | 完整工程通过 |
| RAG诊断 `18c7c7fc` | 两行一起到达可确定导致当前响应滞留/超时；控制组正常 | 已修生产RAG；原全量现场所有调度已还原 |
| 新真实GLM | **0首发/0重发/0续问，未运行** | 目录名live、离线回放或health是新验收 |
| 旧两次live | 仍not_passed | 新修复可改旧样本分母 |

ruff、前端lint/typecheck/test/build、注册表四项exit0。Python收据
`~/.finance-runtime/test-receipts/20260918T153933Z-7a9380bd.json`，校验exit0仅证适用条件；pytest本身exit1。

## 私有证据根

`R=~/.finance-runtime/reviews/research-publication-live-20260918/`

- `checks-start.json`、`checks-summary.json`、各叶子`.log/.exit/.json`、`pytest-receipt.json`：签固定7a9380bd、dirty为空、all_green=false。
- `e2e-artifacts/`、`e2e-artifacts-index.json`：本版第一次浏览器检查；不覆盖旧365627fd桌面红。
- `offline-repaired.json`、`preservation-replay.json`：本revision只读回放，0模型/网络/DB，不改旧live。
- `mutation-summary.json`及四日志：撤保护各exit1、恢复exit0；隔离副本，不动候选源码。
- `old-e2e-race-diagnosis.json`：首轮trace三次GET的时间/产物投影；完整原zip在前序包。
- `rag-buffered-diagnosis.*`：首个开发量具；`rag-buffered-confirmed.*`：18c7c7fc干净复验，带消费者与量具hash。
- `control.py` / `capture.py`：未执行的准备脚本。无`protocol.json`、`data/`、`users/`、`submission-reserved.json`。
- `closure.json`、`production-health-closeout.json`：相对旧GLM关闭身份/启动器未变，隔离端口无监听、无锁；不是OS全局无副作用证明。
- `previous-bundles-verified.json`：旧214/44/90/6/82文件包及296/338前序检查包逐项未变。
- `summary.log/.exit`：索引list/dict误读exit1；`summary-corrected.*`：修解析后exit0，旧失败保留。
- `secret-scan.json`、`secret-scan-reviewed.json`：首扫24词形命中，逐项代码引用核销未决0；非零命中/独立安全审查。UTF-8及zip文本成员已扫，二进制只hash。
- `artifact-index.json`：341文件/10754779字节，SHA256 `8ed34ffe865a5c3c7eae2b2d1939ecc6eed923cc7ce5c3d682a3b3f12bfd03b1`。仓内`artifact-manifest.json`为副本；源码/数据/缓存/后续closeout不在分母。

前序根：`research-progress-repair-20260918`（296文件、365627fd E2E红），
`research-publication-repair-20260918`（338文件、49fd8d72构建弄脏树后主动中止Python）。这些都不是全绿收据。

## 最小离线复现新阻塞

在含量具的本分支上，输出必须是新文件；不会起模型或查询知识库：

```bash
PY="$HOME/finance-workspace-private/.venv-workbench/bin/python"
OUT="$(mktemp -d)"
"$PY" scripts/review_probes/replay_rag_buffered_late_response.py \
  --output "$OUT/rag-buffered.json"
```

exit0表示**缺陷已复现**，不是修复通过。量具使用真消费循环、合成process与OS管道，控制组reader仅诊断；生产修复须另补半行/合并响应/EOF/超时测试。`receipt.json`记录当前裁决；不允许拿旧工程绿、收据校验绿或原件回放绿绕过新全量红灯。
