# 724续修证据包提交后回执

本目录只保存归档提交完成后的检查与PR/记忆回写，不重签测试。固定被测代码仍为`7249378a5bdb9b01cc62ec3bca13af3149bd48df`。

- `committed-archive-check.json`：Git归档提交`50c9bfcf243b47b985469f21b3883a91792f3000`，新包79/79非manifest文件完整且字节一致，ok=true/errors=[]；总80文件326556字节。
- `prior-archive-check.json`：同一提交内旧f90包73/73仍完整；`git diff bbd948a6..50c9bfcf -- docs/verification/2026-09-21-history-evidence-integration`为空。
- `pr-841-followup.json`与`PR-followup.md`：#841在归档头50c9处回读，open/WIP、未merged、mergeable=false；正文与评论5461明确当前main批次漂移门未过、独立和自然验收未过。后续docs头不覆盖本回读时间点。
- `memory-graph-final.log.txt`：隔离记忆树接上同时更新的远端后，93行265断言无漂移，214条在途/未校验；exit0仅为路径/符号检查，不认证行为。记忆提交`134bc4cf00ead405fa2a882afc2986175598f40a`正常快进推送，保留他人#844/#845/日期策略记录，未动共享脏树。

完整JUnit、成功与失败原件、变异及固定代码收据见同级`2026-09-21-history-authority-followup/`。其中`receipt-exact` exit0和`receipt-drift` exit1必须同时消费：当前main比共同祖先多6个merge，超过5个阈值，不可当合入许可。

本目录同样使用`sha256-manifest.txt`与`check_evidence_archive.py --revision <本目录提交>`核Git文件集合和blob字节，不改主包来追加检查自身的循环收据。日期交接在`docs/handoffs/2026-09-21-history-authority-followup.md`。
