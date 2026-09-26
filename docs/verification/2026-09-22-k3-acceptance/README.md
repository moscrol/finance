# K3 / 无判官 · 2026-09-22 只读验收证据

**总体 blocked。** 仅补旧内容复核、当前生产身份/行情日期及原备份完整性，不是新的上线或恢复演练。

详细结论：[日期交接](../../handoffs/2026-09-22-k3-acceptance-readonly.md)。

| 断言 | 原件 |
|---|---|
| 旧证据提交104件均已在Git且哈希吻合 | `evidence/prior-archive-check.json` |
| 直接读取两旧run的不可变原文；K3/终稿0调用与内容问题分账 | `evidence/frozen-run-review.json` |
| 09-22 18:00健康三读，当前源码重算，仍GLM/判官llm | `evidence/health-{1,2,3}.json`、`evidence/production-readonly-receipt.json` |
| 快照09-22，五表09-18，09-21/22各0行 | `evidence/snapshot-contract.json`、`evidence/database-readonly.json` |
| 启动器/快照等未改，主库仅元信息前后对照 | `evidence/protected-files.json` |
| 原Gitea包哈希/gzip全流/tar遍历过，但未验恢复 | `evidence/backup-integrity.json` |
| #830已合、#840/#844仍open/WIP；只读GET | `evidence/pr-status-readonly.json` |
| 采集/归档的准确程序，不是下一次部署入口 | `scripts/{collect,archive_evidence}.py.txt` |

`sources.json`列所选原件、来源SHA256与归档路径；不含备份本体、生产启动器、凭证、原始进程环境或数据库。`secret-scan.json`是敏感信息形状扫描，不是绝对无泄漏认证。

清单覆盖本目录全部文件（仅排除清单自身），提交后用正式工具对Git内字节核验：

```bash
python scripts/check_evidence_archive.py docs/verification/2026-09-22-k3-acceptance \
  --repo <本分支工作树> --revision <本轮证据提交>
```

如果当前main尚无该校验器，可从原#840文档树调用并显式传`--repo`，不要自行复制出第二份校验实现。无模型请求、无readiness、无真实query、无重启/合并/生产写入。两旧题每题n=1；归档可读不能证明在线事务一致或恢复成功。
