# #846 工程门禁与独立审查边界

## 固定身份

2026-09-21，候选 `d3d27bce2302b5d3fcc7ebaaba09fa302ba54f1c`，树 `77f9bc599a37bfa59d1269097f8a8830d95c6362`，专用检出 `~/fwp-wt-deploy-help-0921`，基线 `028a251a1b2ca98245326a6b59376f4f7f8e5e81`。源码变更为 `4f9a2af56`、`8a82ec780`，d3d27bce仅追加交接。

`git merge-tree --write-tree <base> <candidate>` 退出0，预览树等于被测候选树。这证明该固定基线下合流内容未增加差异，不等于已合并或获得独立批准。后续文档提交也不能直接继承整提交SHA认证，须区分代码不变与提交身份改变。

## 已完成门禁

- 全仓 Ruff 退出0；全量 Python 12528 passed、85 skipped、2 xfailed、0 failed，657.70秒，退出0。
- 原生收据 `~/.finance-runtime/test-receipts/20260921T142641Z-d3d27bce.json`。解释器为主仓 `.venv-workbench/bin/python`，Python 3.12.13，依赖指纹 `3328bed61f3e21ea`，dirty=false、worktree_dirty_total=0；首尾revision一致且porcelain为空。
- `check_test_receipt.py` 对完整d3d27bce及base-drift-max=5核验退出0，基座漂移0。
- 前端六步全部退出0，110单测、E2E34 passed/2 skipped；规范收据identity_stable=true、complete=true、dirty=false。
- Registry五项check-parseability/check/backfill-tables --check/generate-views --check/crosswalk均退出0。crosswalk警告不冒充失败，也不声称零警告。
- 三轮撤保护3/6/2例断言红，正式源码已恢复；最终干净定向59P收据 `20260921T140406Z-d3d27bce.json`。前两轮在专用工作树串行进行，第三轮临时副本，详见事故快照。

完整证据根：`~/.finance-runtime/reviews/deploy-help-846-20260921/`。其中python含JUnit、原日志、rc和首尾身份；frontend含规范收据及逐步日志；registry含五项日志和rc；evidence-audit.json是事后交叉核对与哈希索引，不是独立审查或重造pytest收据。

本次设置的 `FWP_TEST_RECEIPT_DIR` 不被该版conftest读取，原生收据仍写默认目录。先前口头断言“没有标准收据”错误，已从同次完整stdout找到精确路径并核验，未补写过去身份。JUnit的skipped元素含2个xfailed，与pytest终端85 skipped分开计数。

## 独立审查没有结论

为审查新建专用detached `~/fwp-wt-deploy-help-qc-0921`，未编辑源码。

1. Claude `--bare --tools Read` 尝试退出1，原文 `Not logged in`。该模式跳过已有登录，不能外推机器无账号；首次提示范围误写HEAD父提交，但审查未启动，不存在有效结论。
2. 改用保留认证的safe-mode，只给Read/Glob/Grep，无shell/写工具，禁MCP；审查范围固定完整base..head。240秒工具超时，stdout/stderr空，无verdict、无进程退出码文件，随后确认本轮审查进程已消失。原因未查明，不能归为认证故障。没有再重试、换账号或把作者自查当独立审查。

**NO CONCLUSION / NO INDEPENDENT SIGNOFF**。即使将来这类只读审查PASS，也只证明静态意见，不冒充独立动态复跑。#846继续WIP，未合并、未部署；已有CLI认证链路需由独立验收会话有界恢复。

## 生产与其他队列

本次用户“继续”之后未执行部署、未重启生产。更早本轮确实误执行旧脚本造成故障，不能用这句话覆盖事故，详见 `2026-09-21-deploy-help-incident.md`。

8792仍healthy，加载同revision adcda94b5e40 的recovery快照、source_dirty=false、code_matches_repo=true；readiness仍HTTP503，数据库2026-09-18与快照2026-09-21不一致。只读观察存health-closeout/readiness-closeout.json，未改数据或关闭检查。

#831仍WIP，旧基线候选165038af四叶通过不能签main028a251a与ea5c3a94合流树c4ebdbd4；该树仅确认无冲突，未重跑。不为测试夹具/代码地图改动重启生产，最新main含已回滚K3，禁止整体切入。

PR评论：#846 comment5464、#831 comment5465。#846原评论称“合流预览不是合流树全量验收”，精确补充为本次预览内容与已测试候选树完全相同；仍无独立签字、未合并。

## 下一步

独立验收者固定当前base/head，审完整补丁并在临时目标重跑防护反例；缺结论不解除WIP。合并仍需真实用户授权。旧主检出脚本尚危险，不运行它探测帮助；生产快照与受损事故目录保留。

全量后磁盘约5.7GiB，不开启第二套全量或批量清理他人树。临时QC树仅在核完ignored、reflog、进程、launcher/ledger/软链引用后普通worktree remove，不force；外部证据全部保留。harness-reference有他人BUILD.md改动，通用目录登记暂缓，实际保护已在正式部署入口和回归测试中。
