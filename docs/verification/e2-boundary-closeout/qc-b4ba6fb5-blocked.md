# P3b/P3c 独立复核仍阻塞，不是代码通过

2026-09-14；固定候选 `b4ba6fb5aa1f6e4f27bac1fcc2db163fe74bacf0`，独立树 `/tmp/e2-p3bc-qc-b4ba6fb5`，开始/结束干净。P3b diff `e0051804..8ea6c5c1`，P3c diff `812b4d46..b4ba6fb5`。未推、未合、未部署。

## 本轮尝试

1. 固定 P3b `8ea6c5c1` 重试 Codex：WebSocket 502 后 HTTPS 429，exit 1，无审查工具执行与最终报告。日志 `/tmp/e2-p3b-qc-8ea6c5c1-retry.log`。
2. 同一 P3b 的 Claude CLI 备用尝试：503 `No available accounts`，exit 1，tool_use block=0。`/tmp/e2-p3b-qc-claude.jsonl` 的 result 虽有 `subtype=success`，但 `is_error=true`，不可按成功判。没有改服务配置/账户池或改用金融模型。
3. 冻结 P3c 后，Codex 复核两个切片：
   ```sh
   codex exec -C /tmp/e2-p3bc-qc-b4ba6fb5 -s workspace-write \
     --add-dir /Users/a77/.finance-runtime/test-receipts --ephemeral --color never \
     -o /tmp/e2-p3bc-qc-b4ba6fb5-report.md - < /tmp/e2-p3bc-qc-prompt.txt
   ```
   Codex `0.154.0-alpha.6.2`，配置选择 `gpt-6-astra/openai`、ultra。WebSocket 被服务端关闭，转 HTTPS 后重试，最终 503 `Service temporarily unavailable`，exit 1。没有审查工具执行，没有有效报告。启动 hooks 字段/code-mode-host 警告仍在，未证实与 503 有因果关系。

第三次完整请求与原始输出已归档本目录 `qc-b4ba6fb5-prompt.txt` / `qc-b4ba6fb5-log.txt`。失败是审查基础设施事实，不是代码发现或通过。作者收据另见 `frozen-b4ba6fb5-tests.txt`、两份 `full-b4ba6fb5-*-tests.txt`，不能代替独立 QC。

## 恢复后

固定上述 revision，按归档 prompt 分别审 P3b/P3c，跑临时源测试并自行构造反例。得出有效结论后再处理发现、重冻与复验，不可把本报告改成通过。其余 P3（来源过滤/预取前澄清/旁路等）及 P4–P7 仍未完成。
