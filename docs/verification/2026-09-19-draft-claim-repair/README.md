# 畸形正文保留与有限证据诊断｜离线验收

**本轮离线修复及完整工程检查完成；新真实模型验收未运行，旧live仍not_passed。**

- 分支：`feat/research-answer-preservation`。
- 实现：`4d541a907e1207d9c72979ac909563bfba756e7c`；统计范围收窄及最终工程revision：
  **`cdcbc5a82b37e0cecc0640f3c8da77d3a6f64881`**。
- [因果、方案取舍与未验边界](../../handoffs/2026-09-19-draft-claim-offline-repair.md)。
- 本目录`receipt.json`与`artifact-manifest.json`分别是验收摘要加归档身份、证据索引同字节副本。

## 分账结果

| 项目 | 结果 | 不代表什么 |
|---|---|---|
| 顶层draft排版恢复 | 原件2096字保留，retained=1，122证据不变 | 不放宽正式finish准入；不做跨进程恢复 |
| 有限证据诊断 | 终稿8条发现覆盖7类，原文保留并批注 | 非通用金融事实核对器、非自然模型改对 |
| 修订反馈 | 原句＋原因进入同会话修订，沿旧预算 | 不保证有剩余额度或模型修订成功 |
| 判官关系 | passed不能抵销机械发现；partial/rejected | 同源/脚本判官不是独立QC |
| 工程 | 精确干净cdcbc全绿 | 不代签后续revision、合流或生产 |
| 新live | 首发0、重发0、续问0 | 不翻案三个旧实际失败/未通过样本 |

## 完整门禁

固定解释器`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；清洁环境、umask022。

- Python **11769P / 81S / 2X**，exit0，17条warning保留；Ruff通过。
- 前端lint/typecheck/build通过，**115P**。
- 浏览器端到端 **34P / 2S**，端口8851/8852。
- 四项registry检查与收据适用性检查均exit0，开始/结束同revision且干净。
- 正式pytest收据：`~/.finance-runtime/test-receipts/20260918T180956Z-cdcbc5a8.json`。

`4d541a90`先前全量因新发现范围误报主动中止，pytest=-15、无完整收据、receipt_check=125；
其他叶子通过也不拼成成功。误用两次`-k`各exit5/41 deselected；正确反例3F/13P、修后定向532P。
以上日志均保留。

11项撤保护逐项exit1，恢复66P/exit0且变异树干净；正确/错误期待交叉测试分别成功/失败。
原Mapping进展、早期保稿与RAG分帧三个离线旧边界在cdcbc均通过，实际模型/工具/数据库调用0。

## 精确原件与复跑

源run=`run_20260919_002806_645542`，task还包含
`:msg_04f66e8b950242888b8703babe3317b6`；SHA256：
`02f536171512cb2c7fb0bf30e86f1243ba22f50c5ac1e566d3035b153e5dbd68`。

在干净cdcbc检出中，只读复跑（输出必须是新路径）：

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
OLD="$HOME/.finance-runtime/reviews/research-rag-framing-repair-20260919"
OUT="$(mktemp -d)"
"$PY" scripts/review_probes/replay_layout_claim_failure.py \
  "$OLD/users/probe-rag-framing-20260919/runs/run_20260919_002806_645542/continuous-episode.json" \
  --code-root "$PWD" --expect repaired --output "$OUT/replay.json"
```

本量具钉住该封存原件，不承诺接受任意样本。网络连接禁用、使用脚本模型，不调用真实provider；
`--expect missing`在新版本应失败。不得覆盖原件、原裁决或复用旧live名额。

## 证据索引与扫描范围

根：`~/.finance-runtime/reviews/research-draft-claim-repair-20260919/`。

- 根层：开发、反例、4d中止轮；`final/`：cdcbc最终工程、11变异与原件回放。
- `acceptance-summary.json`、`closure.json`：分账摘要、只读生产身份检查与端口关闭。
- 9份旧包214/44/90/6/82/296/338/341/423成员逐文件复验不变。
- 最终 **748文件 / 21659513字节**；索引 **142036字节**，SHA256：
  `bd265e79206fb4d6de028c1e94f86e3337423fe592b9b84e7d25c8ba7f9a14c4`。
- 初扫744文件/738文本项/6二进制项，18个`jwt_shape`命中、exit1保留。
  已逐项核为5个精确源码模块名，文件hash/行/匹配hash复验后未决0。
  **非全包零命中，非独立安全认证**。UTF-8及ZIP文本成员才做文本扫描；二进制仅hash。
- 代码按revision定位；code/mutation-code/data/cache、后续closeout和索引自身不进成员分母。
  本轮未创建新的live行情副本；E2E夹具库不是行情冻结证据。

生产仍`bf662e9310ff`，七项身份和启动器hash与前轮一致；8849/8851/8852不监听、无live锁。
未push/合main/部署。后续真实验收、合流和上线另行授权，不能用本页偷换验收层级。
