# #83 发布时新增的 main 边界

这是 `2026-09-25-backfill-302132-main1751-continuation.md` 封存后的补记，不修改原快照及manifest。

## 真实顺序

1. 封存时 main 为853，相对1751只有三个文档变更；ae3的最新scope校验exit0，merge-tree无冲突。
2. 产品ae3已快进推至PR813，归档2738份逐项哈希通过。Git忽略规则漏掉750份`tmp/`或`*.bak-*`路径下的JSON/text收据，显式按manifest加入后缺失0。未加入数据库/缓存/凭据。文档先由cb381、3ed4推送。
3. PR状态发布前的远端精确main断言拒绝。重新fetch后main为 `9d5b9800a5500e6f64875432f8df3a06713d6f52`，相对1751共13文件变化，包括 `intelligence/runtime/deploy_ledger.py`、`scripts/audit_deploy_ledger.py`、`scripts/run_frontend_gate.py` 和对应测试，以及 `tests/test_pi_review_repair.py`。
4. 新main与ae3的 `merge-tree --write-tree` exit0，预览树 `e8fb62782ae9838afc831f6967849f3875800c86`；**没有在该组合上执行门禁或独审**。ae3工程16259P等仍只绑定ae3/main1751。

## 判断与下一步

保持WIP。拒绝把新的main代码组合当作已验，也不因快进追逐而自动追加模型请求。先定位批20沙箱内两例clean-checkout拒绝和离线格式问题；之后冻结新的组合、重跑相关工程门禁，再决定新的有界独审。

文档推送后，发布脚本将把PR真实回读和文档SHA写入运行根 `pr813-ready-main1751-20260925/publication-continuation.json`；CURRENT是最终动态指针。本补记不把尚未执行的发布记为已完成。合入与生产授权仍false。
