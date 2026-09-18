# `35ee8a5c`：GLM 一次真实验收（未通过）

详见 [发现顺序与决策](../../handoffs/2026-09-18-finish-candidate-glm-live.md)。

| 层 | 本次事实 | 不能推出 |
|---|---|---|
| 已授权模型 | 持久事件3轮glm-5.3-flash响应；兜底未触发 | 之后调用/额度一定成功 |
| 产品交付 | 首发1、重发0、续问0，run failed / report blocked，无答案 | 202/health是交付通过 |
| 保稿机制 | 未到finish或候选保留 | 无丢稿事件就算保稿通过 |
| 原形状重放 | 缺end→合法拒绝→旧版进展JSON崩溃；已有修复正常反馈，44证据不变 | 已在本枝修好/整轮自然自修已验 |
| 工程 | 校验35ee既有收据；邻枝相关24P | 当前文档/量具或整合版本全量通过 |
| 关闭 | 8849已停，锁移除，8792身份/启动器不变 | 所有共享缓存无副作用 |

## 原件索引

R=`~/.finance-runtime/reviews/research-candidate-glm-live-20260918/`

- `protocol.json` **连同** `protocol-budget-amendment.json`：首发前协议，后者改正量具误读CLI默认档位，原文件保留。
- `launch-config.json`、`candidate-health-before.json`、`readiness.json`：模型/代码/隔离根，非验收通过。
- `submission-reserved.json`、`server.log`、`probe.log`、`probe.exit`：一次性提交与exit2。
- `capture.json`、`public-projections.json`、`public-message.json`：精确公开run/message。
- `users/probe-candidate-glm-20260918/runs/run_20260918_213933_397262/`：原始失败工件。
- `episodes/run_20260918_213933_397262_msg_18e9ac951cd44153addc360fa573d2be-999dfb64a202/`：模型响应、工具请求/结果、未终结的durable state。
- `offline-baseline.json` / `offline-existing-repair.json`：同一source hash上的旧版stack与已有修复反馈。
- `countercheck-*.json|log|exit`：错误期待与覆写必须红；`existing-repair-focused-tests.log` 24P。
- `closure.json`、`launcher-unchanged.json`、`previous-bundles-verified.json`：关闭、启动器及旧214/44/90/6包的逐项完整性。
- `secret-scan.json`、`seal.log`：首次扫描未分类而拒绝；`secret-scan-reviewed.json` 精确核销，5个文件/marker命中，6个词形，未决0；不称全包零命中。
- `acceptance-summary.json`、`artifact-index.json`：新旧live均not_passed，无promote。索引82文件/623321字节，SHA256 `ac3fcf713460f2363ac96b3c9efb597ce3c34b81ed042db98a28db7f1b00f855`。

仓内 `artifact-manifest.json` 为索引副本，`receipt.json` 只列结论与关键指针，不把私有正文/DB进Git。大行情和代码副本由snapshot manifests/revision锚定，`closeout/` 是封存后的文档/提交日志，不在82文件分母。

## 可复跑的离线检查

从本分支树运行（解释器由主树venv提供；不会执行模型、工具runner或数据库查询）：

```bash
PY="$HOME/finance-workspace-private/.venv-workbench/bin/python"
R="$HOME/.finance-runtime/reviews/research-candidate-glm-live-20260918"
E="$R/episodes/run_20260918_213933_397262_msg_18e9ac951cd44153addc360fa573d2be-999dfb64a202/events.jsonl"
OUT="$(mktemp -d)"
"$PY" scripts/review_probes/replay_history_progress_failure.py \
  --events "$E" --code-root "$R/code" --expect crash --output "$OUT/baseline.json"
"$PY" scripts/review_probes/replay_history_progress_failure.py \
  --events "$E" --code-root "$HOME/fwp-wt-8792-boundary-integration" \
  --expect feedback --output "$OUT/existing-repair.json"
```

第二条会记录实际revision/dirty，不能把移动了的树当历史 `068e2a46`；若要精确重复，用该提交的新干净detached树。工具不会改源码，拒绝已存在的输出。把expect交换应exit1；输出复用应exit2。

## 未验 / 后续

局部Mapping修复源为 `a969d30a`，本轮比较的干净邻枝tip `068e2a46`；它尚未整合到本枝。候选完整保留、自然纠参、模型答案质量、跨进程恢复、独立QC均未获本次证明。先整合与工程验证，再单独授权新一次真实验收；不得覆写此次失败或用新成功重标旧run。
