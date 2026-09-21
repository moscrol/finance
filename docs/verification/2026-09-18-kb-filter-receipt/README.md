# 作者验收原始收据

被测金融实现 `698555e28784480c92be33b43f48c250ea0d0a09`，被测时整树干净。
配套知识库代码来自 `fix/agent-retrieval-reliability`（检索实现 `b62c58cb5`，全量金融运行期间
KB只提交既有导航修改为 `1f614b694`，检索代码未变）。本目录后续归档不等于对文档HEAD重跑。

| 文件 | 覆盖/边界 |
|---|---|
| finance-all-final.txt / pytest-receipt.json | 全量11481P、73S、2xfail、0F；17 warnings保留；收据dirty=false |
| finance-receipt-check.txt | 对698555e2的七条件一致性校验exit0 |
| finance-ruff-final.txt | 全仓Ruff exit0 |
| frontend-final.txt | lint/typecheck/test/build exit0，107P |
| finance-e2e-committed.txt | 同实现提交E2E34P/2S；隔离端口18871/18874、隔离用户/现造行情库 |
| finance-registry-final.txt | 四个registry命令exit0；既有弃用告警保留 |
| finance-target-final.txt | 提交前181P，含3项真实跨仓hash测试；不是干净revision收据 |
| finance-base-failure.txt | 干净base 0a1cb8c4 的展示测试同红；该测试随后隔离数据根 |
| worker-upgrade-red.txt | 修改代码前同mtime+size换码的两条真实子进程反例失败 |
| memory-lint-comparison.txt | 共享记忆全库lint仍有20错误，与本次四笔记改动前HEAD内存对照完全一致；不是全库通过 |
| SHA256SUMS | 本目录原始收据字节指纹；用于检查归档后是否变化，不认证执行者身份 |

工程绿只证明本实现的作者检查。不证明生产已迁移、不证明真实BGE/多模式质量、不证明所有
问句已自动带as_of。真实跨仓测试必须显式设置KB_RECEIPT_CODE_ROOT；缺省skip不是通过。
详见 `../../handoffs/2026-09-18-kb-filter-receipt.md`。

共享能力图更新另跑 `agent-memory/scripts/graph_audit.py` exit0；其MERGED只判断同名符号
存在，不证明新行为已合入，所以候选行仍保留@branch。共享记忆lint的20处既有错误未顺手改，
也未修改其阈值或外仓TOOLKIT镜像。没有新增通用工具需要改共享harness-reference。
