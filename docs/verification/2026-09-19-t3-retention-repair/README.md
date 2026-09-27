# T3 误删返修证据

被验业务 revision：`a2a3301963d11a073f511e1552b53daee7ecd704`，非将来归档提交。

- 工程门通过，旧原样反例 6P/0F，17 组变异逐项红→还原绿。
- 独立审查预检完成，但模型审查 CLI 一次尝试 600 秒超时，无有效裁决；因此不合 main，不部署。
- 自然金融会话 0 次，旧 not_passed 不翻案；审查的真实 provider 调用次数/用量未知。
- `outcome.json` 是本轮总裁决；`candidate-a2a33019/result.json` 的 `passed=true/live_model_calls=0` **仅指工程检查**，不包括后续独立审查尝试，也不是整体准入。
- `before.log.txt` 保留修复前新增测试首红。旧 QC 原件仍在兄弟目录 `2026-09-19-t3-convergence/`。
- `candidate-a2a33019/`：完整门、冻结三仓身份、原样探针与首轮变异；`qc/`：独立请求/claim、隔离机械预检与超时日志，没有 PASS verdict。
- `manifest.json` 将每件原始文件绑定字节数、SHA-256 和来源。日志、diff、一次性编排脚本只加 `.txt` 后缀，原字节不改；不纳入锁文件或临时 worktree。

归档检查说明：`git diff --cached --check` 对原始 pytest/JUnit/diff 日志报告尾空格与文件尾空行；这些字节本来就在原件中，为保持 SHA-256 一致而不清洗。业务提交及新写说明文档单独做 diff 检查，不关闭全局检查、不改原始失败日志，也不把归档的空白警告算成业务测试失败。

详见 `docs/handoffs/2026-09-19-t3-retention-repair.md`。这些存档不是可部署源码，也不是新的永久编排入口。
