# 2026-09-20 质检意见落实

本次依据用户在复核结论后的「执行」，修正文档并补做前端身份验收；历史收据和失败退出码没有补写。正式入口为 `scripts/run_frontend_gate.py`，代码提交 `30ad71a8`，文件哈希见 `runner-source.json`。

## 本轮实际验证

| 对象 | 新结果 | 证据 |
|---|---|---|
| 门禁脚本 | 10 passed；Ruff 通过 | `runner-checks.json`、`runner-tests.log.txt` |
| 撤去末尾身份保护 | 源码变化与 HEAD 漂移两例均失败（2F），候选源码未改 | `mutation-end-identity.json`、对应日志 |
| #795 `ec92b31b` | install/lint/typecheck/test/build/E2E 全 0；前端 110P，E2E 34P/2S | `frontend-795/frontend.json` 和六份日志 |
| #796 `4ace5ec2` | install/lint/typecheck/test/build/E2E 全 0；前端 110P，E2E 34P/2S | `frontend-796/frontend.json` 和六份日志 |
| 旧保全 | 52 status、104 diff、166 未跟踪副本哈希一致；50 棵非执行者工作树现状的 diff/未跟踪内容一致 | `preservation-content-recheck.json` |

两份前端新收据均在原 SHA 的独立固定检出执行，首尾 revision 相同、dirty=false、identity_stable=true、exit_code=0。记录的是本轮测试条件，不补证历史时点；首尾采样也不保证期间没有发生又恢复的编辑。无新 Python 全量、真实模型质量或生产切换验收。

## 文档纠正依据

- #796：用户原「你来执行」及附件「独立复核……决定生成根合入还是回滚」是附条件源码合入授权，来源时间、附件 SHA-256 和摘录见 `authorization.json`。
- #597：Gitea 的 merged_at/closed_at 是 09-12；09-16 是追加说明的 created_at。本轮没有关闭该 PR，原字段和评论见 `pr597.json`。
- KB 日期交接改为固定 `3a210103` 的仓库链接，删除工作树不会使该链接失效。
- `26d9e34f` 是最终记忆版本，包含祖先 `d851ebea` 所改的七行；不是首次修改提交。`memory-provenance.json` 保存祖先校验和最终文件哈希。

## 收尾发现的 Git 归档缺口

原清单的 110 份原件在本机均可读取且哈希正确，其中 24 份 KB `.log` 文件受忽略规则影响，未进入 Git。原质检的本机哈希检查没有覆盖「远端实际包含该文件」。本轮保存内容完全相同的 `.log.txt` 副本，清单把这 24 项的 path 改为可提交的文本路径，增加 original_archive_path；source、bytes、sha256 不变，本机旧副本不删。映射见 `historical-log-paths.json`。正文引用历史 `.log` 名时，按此映射找入仓文本原件。

最终清单同时验证文件哈希和 Git 跟踪状态；不能以本机存在替代已提交。README 和 manifest 自身由 Git 管理，不参与证据清单自哈希。

可迁移方法已在 harness-reference 的 `docs/frontend-receipt-0920@f48bb4d` 同步 KIT/BUILD，已推未合；其原主树的他人 BUILD.md 改动未动。本分支与生产的合入、切换边界维持原交接。
