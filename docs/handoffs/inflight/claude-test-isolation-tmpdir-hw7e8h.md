# 在途交接 · claude/test-isolation-tmpdir-hw7e8h

## 这个分支做什么
嵌套 `run_main_gate.sh` 的测试与外部环境完全隔离（TMPDIR、GATE_*），并让留只读目录的用例收尾时改回可写。纯测试侧，合入不重启服务。决策全文见 `docs/handoffs/2026-09-30-test-isolation-tmpdir.md`。

## 决策与被否方案
| 选了 | 否了 | 为什么 |
|---|---|---|
| gate_env 设私有 TMPDIR 并先 mkdir | 只设变量 | gettempdir 遇不存在的 TMPDIR 静默退回 /tmp |
| 断言嵌套 pytest 实际临时根位置 | TMPDIR 指不可写目录 | 同上静默回退；root 无视权限 |
| 根 conftest autouse 收尾补 u+rwx | 逐条 finally | 20 条分散 5 个文件，新增会漏 |
| gate_env 剥 GATE_* | 不管 | 外层 GATE_KEEP_BASETEMP=1 漏进嵌套 gate，09-30 实测变红 |

## 当前状态
- GitHub `origin/claude/test-isolation-tmpdir-hw7e8h`，头 `3d2b1ba9`（代码）+ 本交接与 runbook 文档提交。**未开 PR、未合入**，合入等用户确认。09-30 起 GitHub 为主、本地 Gitea 只做备份。
- GitHub CI：main 近 100 次 workbench-check 0 成功，python 叶卡 `timeout-minutes: 15`（全量 Mac 18 min）。本 PR 在 GitHub 上会同样红，与本分支无关，以 Mac 收据为准。
- Mac 树 `.claude/worktrees/unclosed-session-stats-838ac4` 的未提交测试已原样并入 `bca70085`，可按 `worktree_closeout.py` 收口。

## 未验证 / 已知边界
- 收尾夹具只管函数级 tmp_path/tmpdir；`tmp_path_factory.mktemp` 与测试内动态 `getfixturevalue("tmp_path")` 不管（全量扫描未见此类残留）。
- `test_workbench_correction_http.py::test_http_correction_lock_contention_*` 负载下偶发 busy≠cancelled：09-28 在 `6d973953`、`9da61029`（无本分支改动）已红过，单跑 3/3 绿。未修，另开。

## 下一步
1. 用户确认后：在 GitHub 对本分支开 PR → 合入（代码收据绑定 `3d2b1ba99af6`；之后只加文档提交）。不再推 Gitea。
2. 收口上述 Mac 树。

## 踩过的坑
- 隧道 exec 的 PATH 没有 node：门禁 18 条 node 用例假红；跑前 `export PATH="$(zsh -lic 'printf %s "$PATH"')"`。
- 隧道 524/502：命令可能已执行，先查现场；长命令 base64 写脚本、nohup 后台、短请求轮询。
- 带 `GATE_KEEP_BASETEMP=1` 跑门禁能暴露嵌套 gate 的环境泄漏，值得保留作对照。

## 已验证
- **Mac 全量门禁绿**：`3d2b1ba99af6` 18709P/0F/75S/2X，collected 18786 对平，`check_test_receipt.py --require-full-scope` exit 0（`~/.finance-runtime/test-receipts/gate-Hu4e6NDk/pytest.json`）。
- 容器：最终提交 60 红全同见于未改 main 基线，零新增；前端、e2e、registry 绿。
- 变异 7 种均被抓；只读目录：基线 114 个 → 修后全量 0。Mac 共享根 garbage-* 已清。
