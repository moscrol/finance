# 在途收尾质检意见落实计划

> 用户在复核结论后于 2026-09-20 回复「执行」。按该已确认范围在本会话串行实施；更新 #789 分支，不合 main、不切生产。

**Goal:** 修正交接的授权、历史日期和持久链接，补齐前端门禁的测试时点身份与新收据。

**Architecture:** 原始失败和历史收据不改。新增 `scripts/run_frontend_gate.py` 负责固定目标树、顺序执行既有 pnpm 命令并记录身份；使用原 #795/#796 的独立固定检出重跑，结果另存。旧临时 `gate_leaf.py` 作为历史证据保留，不把其中本次专用的目录、分支名单复制成长期接口。

**Tech Stack:** Python 标准库、Git、pnpm、项目既有 Playwright 浏览器测试。

## 实施与验收

- [x] 新增 `scripts/run_frontend_gate.py`。必填 `--tree`、`--expect-revision`、`--output`；输出目录必须是目标树外的新目录。`--python` 默认当前解释器，端口参数同时设置端口及配套 URL。顺序运行 install --frozen-lockfile、lint、typecheck、test、build、test:e2e。每步保存命令、退出码及日志哈希；测试首尾分别记录完整 revision、dirty、porcelain 状态。初始脏树或错 SHA 不执行测试；末尾脏树、SHA 漂移、Git 查询失败或任一命令非零，都不能写通过结论。首尾采样不宣称检测到了期间发生并恢复的所有改动。
- [x] 新增 `tests/test_run_frontend_gate.py`，用临时 Git 仓及真实子进程验证干净成功、初始脏树拒绝、结束变脏、HEAD 改变但树干净、失败命令、错误 SHA、Git 失败、输出目录复用/在树内拒绝。运行项目解释器 `-m pytest -q tests/test_run_frontend_gate.py` 与 `-m ruff check scripts/run_frontend_gate.py tests/test_run_frontend_gate.py`。撤去末尾身份保护后，结束变脏与 HEAD 改变两个反例必须失败。
- [ ] 提交脚本后，在外部运行目录调用该正式脚本，分别指定 `ec92b31b5300bbbb4abc64e41f96854f1438aea0` 与 `4ace5ec2e9b7735d90eb15bc2351fa193c1120b8` 的既有干净检出。两次串行、使用独立输出目录；核首尾同 SHA、dirty=false、六命令退出码 0。只重跑前端相关门禁，不冒充本轮新 Python 全量。
- [ ] 修 `docs/handoffs/2026-09-20-open-work-execution.md`：补 #796 原授权出处；#597 写 09-12 合并关闭、09-16 补说明、本轮核实；KB 日期交接改固定 SHA 的 Gitea 链接；精确区分旧前端证据与新增复验。保留 `26d9e34f` 的最终记忆版本表述。
- [ ] 在 `docs/verification/2026-09-20-open-work-execution/qc-followup/` 保存新收据、日志、授权及 Gitea 精简证据，追加到原 manifest；旧 110 条文件哈希保持不变。README 说明清单覆盖原件，说明文件和清单自身由 Git 管理。
- [ ] 更新 `docs/workflows/acceptance-workflow.md` 的前端入口、分支 inflight（≤3K 字节）及项目一行索引。检查文档链接、历史证据哈希、提交检查；使用 pathspec 提交并正常推送既有分支，回读远端 SHA。
