# #911 前向已合入的 #868/main

## 身份与操作

用户本轮“执行”承接候选冻结、改基座和离线验证，不扩为新增付费审查、main合入或部署授权。owner评论7092/7096确认#868已合入并要求本PR改指main。

- 固定main：`1751e21e0fd30642e0b223604b64b30e38c46f41`。
- 原#911 HEAD：`6c6a6774fcd2667078071a9356e6a21394d114f8`。
- 新代码候选：`86da22fda1f8fa02c71cd5d8759ee55a65e6fd37`；两个父提交依次为原HEAD和固定main。
- 源码树 `c7ceec198d114f108e9a22b726fcc00f9a418872` 与事前merge-tree预览完全一致，无冲突、无手改产品实现。
- 自有树 `/Users/a77/fwp-wt-pr911-main-0925`，本地分支 `test/pr911-main-0925`；发布仍走原PR分支 `feat/pi-research-loop`，只快进不强推。
- base已改为main并读回，仍open/WIP/未合入。未动#868 owner分支或main。

相对main仍只有两份测试与六份设计/交接，没有生产代码差分，也不含#910修补。后续文档交付HEAD不自动继承代码候选收据。

## 验证

固定Python `/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`，3.12.13/httpx0.28.1，依赖指纹66726d345bf37ce5。受测前后干净。

- workspace doctor、全仓Ruff、完整PR diff-check均exit0。
- 注册表parse/check/tables/views与台账crosswalk五项exit0。
- 完整执行本PR两份测试文件：`intelligence/tests/conformance/test_research_chain.py` 与 `intelligence/tests/test_workbench_research_chain.py`，合计 **56 passed / 0 failed / 0 error / 0 skipped**，无-k/-m/忽略/额外deselect。
- 本树唯一收据通过精确revision、目标、固定main零漂移核验；这是两文件定向收据，不是全仓scope。保留JUnit逐例记录。

这些测试覆盖开关双态、观察改变后续查询、空/错恢复、伪造引用拒绝、预算/取消、负向变异，以及真实进程内Workbench入口到Episode/持久化的身份与公开稿一致性。模型和数据源脚本化；TestClient不是TCP或浏览器，脚本判官通过不是自然金融质量。

原根 `~/.finance-runtime/reviews/pr910-911-forward-20260925/911/`；27份原件保全在 `docs/verification/2026-09-25-pr911-main-forward/manifest.json`。日志不修剪，脚本txt仅供审计，pytest临时夹具未放Git。

## 决策与被否方案

| 选择 / 否掉 | 原因 |
| --- | --- |
| 各PR独立前向 / 重新拼整包 | owner已单独合#868，#910与#911应各自守范围和证据身份。 |
| 保留合并父链 / rebase强推 | 方便核来源及快进更新，原历史和旧收据不变。 |
| 新56例 / 旧fb41完整数字移签 | 组合对象和main基座不同，需实测新树。 |
| 先定向 / 并发再加全量 | 当时三套他人全量运行，记录资源拒绝，不动其进程。 |

## 未验证与后续

没有执行新候选全仓Python、前端、浏览器E2E、独立spec/quality；真实来源、自主子研究、语义判官/反证修订、8792身份、L6均未验。不用56P替代这些结论，也不借#910四项作为本PR覆盖。

资源空闲后补全四叶；main变化则重评组合和收据。工程齐备后明确申请新候选的审查额度，再另根准入。旧已撤销批不能恢复，当前新增付费请求0；main合入和8792部署另待确认。
