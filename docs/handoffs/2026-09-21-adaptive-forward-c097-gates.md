# Adaptive research：收尾期间 main 再漂移后的最终工程门禁

## 背景与决定

前一轮 `c07dda427` 合入 #830 后工程门禁已通过，留证与三项遗留决定见 `2026-09-21-adaptive-forward-830-closeout.md`，文档提交 `257d8fafb`。提交后最后检查发现共享 `gitea/main` 又推进到 `c097d712f`，新增 5 个提交，涉及夜跑 launchd（macOS 定时服务）安装器/固定根、S7 脚本、测试与证据归档。

选择再前向合入并重跑全部工程叶子；否沿用 `c07dda427` 收据称最新主线已验。新业务文件使旧收据不再代表当前候选，即使这些文件没碰研究回路，也不能移绑结果。

干净树无冲突合并产生：

`be66029342bfe2c57e62c78be3a6c502fdb73543`

本片没有增加业务补丁，没有执行真实安装/夜跑脚本；只运行包含隔离替身的测试。2026-09-21 11:06Z 收尾 fetch 时 `gitea/main` 仍为 `c097d712f`，基座漂移 0。之后主线是否继续前进需重新查，不作永不过期的“已追平”断言。

## 精确提交上的结果

以下只签 **be66029342bfe2c57e62c78be3a6c502fdb73543**，不签后续文档 tip：

| 叶子 | 结果 |
| --- | --- |
| Python 全量 | 12698 passed / 87 skipped / 2 xfailed / 17 warnings，0 failed / 0 error，exit 0 |
| Ruff | exit 0 |
| 前端 lint / typecheck / test / build | 全部通过，Vitest 110 passed |
| 浏览器 E2E | 34 passed / 2 skipped，exit 0 |
| registry 四项 | 全 exit 0；仅本仓 ws 在场，跨仓 23 个 skill 跳过 |
| spec↔台账对账 | exit 0；反向仍 98 条 warning |
| Python 收据校验 | 精确 revision、解释器、依赖指纹、代码干净、基座漂移 0 全过 |

Python 原始收据：

`~/.finance-runtime/test-receipts/20260921T110550Z-be660293.json`

新证据目录：

`~/.finance-runtime/adaptive-forward-c097-20260921/`

- `python-run.json`：实际命令、首尾 Git 身份、退出码；`pytest.log` 为完整日志；`pytest-receipt.json` 为原件副本。
- `frontend-be6602934/frontend.json`：六步日志及 SHA256、`complete=true / identity_stable=true / dirty=false / exit_code=0`，首尾精确绑定 be6602934。复用已有 `run_frontend_gate.py`，解释器为主树 workbench venv，端口 19961/19964。
- `local-checks.json`、`registry-*.log`、`ruff.log`、`ledger-crosswalk.log`、`pytest-receipt-check.log`：独立结果与校验。
- `revision.txt`、`main-ref.txt`、`main-delta.txt`、`merge.log`：输入身份与合流记录。
- `SHA256SUMS`：23 个文件的校验清单。与前一轮 #830 证据分目录，不覆盖旧结果。

Python 和前端运行首尾工作树均完全干净；不是只以“代码面无变化”推断身份。全量比前一轮多 20 条测试，来自此次主线增量；本片没有新增测试文件。

## 磁盘与临时目录

开跑前剩约 5.6 GiB，因此 Python 使用本次新建的独占 `--basetemp`：

`~/.finance-runtime/adaptive-forward-c097-20260921-pytest-temp`

完整通过后只清理此临时根（约 3.1 GiB），未删除共享 pytest 历史、旧红日志、K3 原件、生产或他人工作树。第一次清理因测试故意留下只读夹具目录而 PermissionError；仅在这个独占根内恢复目录的 owner 读写执行权限、不跟随软链，随后清理完成。`scratch-cleanup.json` 留有原错误、范围、文件数和完成时间；日志和收据均位于该临时根之外并保留。清理后空间约 4.3 GiB，整机仍紧张，不作空间问题已解决结论。

## 产品边界未变

- 裸六位股票代码精确比较闸已修；不猜交易所，contains 不拦。
- 删句残片不做已接受正文的外科手术，先量化再议。
- 自然模型“无工具修复 + 自报 partial”仍未闭合。本轮新 live 调用为 0，没用离线或无密钥 E2E 顶替；K3 的同请求 200/400/200 证据与变体表勘误见上一快照。
- 不把 main 上的 K3 temperature 兼容当作上游间歇 400 已修；不放宽全局 HTTP 400 重试；不把推理正文漏 content 写成已修。
- 独立 Spec/Quality 与自然金融质量验收没有新增通过结论。本片工程绿也不替夜跑原分支签其独立审查/生产部署。
- 未 push、未开 PR、未合回 main、未部署。下一步推送/合入/部署或新 live 都待明确授权；如主线再漂移，为最终待合提交重新取得相应收据。

本轮复用已有测试与收据工具，没有新 runtime 决策或通用脚本；仅清理本次自有可重建临时夹具，不另造跨仓清理工具。
