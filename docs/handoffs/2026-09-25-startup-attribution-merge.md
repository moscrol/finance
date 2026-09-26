# 启动归属、验收隔离与精确版本合入回读

日期：2026-09-25。本文是动作完成后的快照，不是后续 revision 或部署的验收证书。

## 背景与结果

Finance #922 已通过 Gitea 原生 `fast-forward-only` 合入。合入前基座是 `853c4b7fac1321d2e442bef813b71980143c79b4`；受测提交、`merge_commit_sha` 和合入后的远端 main 都精确等于 `9d5b9800a5500e6f64875432f8df3a06713d6f52`。未生成另一个未受测的合并版本。

代码包括原件绑定的无端口 startup 追加归属、读侧重验、前端验收公共入口固定独立账本，以及新主干离线审查测试的跨工作树解释器夹具修复。#926 的两份旧归档已包含在同一受测范围；已留 #922 接替指针后关闭 #926，未删分支。旧归档仍保留历史结论。

恢复与部署未完成。未写生产数据库、未切 runtime、未改 launcher、未重启服务；本轮未调用真实模型或供应商数据接口。已有恢复授权仍有效，不重复索要；工程结果不授予额外模型调用或豁免数据证据门。

## 按发现顺序

1. `authorized-data-05`：候选 `8406cd1c3` 的四叶工程检查通过，Python 15681P/75S/2X；main 在结束前合入 #868，零漂移检查拒收。旧绿不转签。
2. `authorized-data-06`：前向 `1751e21e0` 后候选 `07a271411` 全量为 16184P/3F/89S/2X。三红来自 `test_pi_review_repair`：临时配置选了实际 Python，但 `tools.sb` 仍只允许旧主树虚拟环境，`sandbox-exec` 在执行解释器时拒绝。该轮未合入，失败原件保留。期间 main 又合入文档 #927。
3. 在独立树新增直接沙箱边界回归，旧夹具先复现 1F；只同步临时夹具中的虚拟环境子路径和父目录元数据许可后，该文件 44P。正例启动实际解释器，反例确认受限目录不可读、候选树不可写。正式审查策略、历史归档和网络权限不改。
4. 修复提交 `acee7993f` 再整合 #927，冻结新候选 `9d5b9800a`。提交后独立回归再获 44P；完整四叶、精确 revision、干净树及零基座漂移检查通过后才执行合入。
5. 合入后回读 PR、远端 main 与生产只读指纹；结果如下。PR 留言只是串行协调请求，不是已取得全局锁。

## 精确收据

证据根 `~/.finance-runtime/reviews/agent-foundation-0924/deploy/authorized-data-07/`，解释器固定为 `~/fwp-wt-agent-foundation-closeout/.venv-workbench/bin/python`。

| 证据 | 结果与边界 |
|---|---|
| `python/gate-iPnJWlHZ/pytest.json` | 16202 passed、75 skipped、2 xfailed，完整收集 16279；无忽略、筛选或依赖门绕过，干净树 |
| `receipt-check-result.json`、`premerge-receipt-check.log` | `--require-full-scope --expect-revision 9d5b9800a5500e6f64875432f8df3a06713d6f52 --base-drift-max 0` 通过 |
| `frontend/frontend.json` | install/lint/typecheck/unit/build/E2E 六步通过；123P，E2E 34P/2S；合前重验日志哈希 |
| `acceptance-result.json` | Python、frontend、E2E、registry 全部通过；仍须另读 receipt-check，不能只看叶子聚合 |
| `extra-checks-result.json` | 离线 smoke 2P、doctor --frontend 与地图 status 通过；不是真模型质量验收 |
| `code-map-consistency.json` | 34180 节点，索引行同数，漏项/悬空项均 0 |
| `frontend-ledger-verification.json` | 两个真实 E2E startup 在本轮账本，端口 20941/20944；canonical 无对应 revision/PID |
| `merge-922.json`、`archive-926.json` | 原生快进保留受测 SHA；#926 已被包含并有关闭接替指针 |

这些收据不转签本归档分支、后来的 main、#913 恢复主体或生产部署。定向 44P 不替代全量；旧红与基座漂移拒收不删。

## 生产回读

`production-premerge-fingerprint.json` 与 `production-final-readback.json`：生产仍为 `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`，health 200、readiness 503。runtime target、launcher 和数据库元数据与既有基线一致。新读器对 8792 的账本对账通过，不等于生产旧读器已升级。

本轮合入前后生产库整文件 SHA256 均为 `5f8e86cd854b7c6569cdcb62bfb5e9861d1d3a804d8f521480003185323dc91e`，读取期间元数据稳定。它证明这两个采样点内容相同，不追认早先只有元数据回读的时间窗。

本轮前后 canonical 账本指纹一致、原始前缀保留；与更早的回读不同，因为其他工作树另有已标端口的测试 startup 追加。历史误入记录全部保留，没有删除、重标为生产或迁入本轮临时账本。

## 数据恢复仍阻塞

- 冻结基线仍是 403 个板块中 323 个数量/处置检查通过，80 个板块缺 113 个身份位置；数量通过不等于目标日身份认证。逐项清单见 `authorized-data-03/frozen-baseline-audit.json`。
- `authorized-data-04/member-probe/response-envelope.json` 是 HTTP 401 / `HIGH_VALUE_DATA_AUTH_REQUIRED`；已停止，不重试、不换接口绕过。
- 对最终隔离库补跑既有只读 `qa_backfill_align.py`：09-23/24 合计 42 FAIL、2 WARN、50 项，退出码 2。缺市场/板块/申万/派生数据；不能发布。明细见 `authorized-data-06/prepared-input-qa/`。
- 两日涨跌幅重算各 0 不符，但前收链分别 42/5556、51/5557 不等，只是处于基线量级，不能替代逐条公司行为/参考价核实。turnover 全 NULL 的警告符合原输入口径，未以改门槛掩盖。
- 隔离库 QA 前后 SHA256 都是 `bb68713763af50c2eb701e0160384dbcd0d05d9be3295ffbeeccaa8f47317cba`，且匹配 03 封存清单。该探针未开生产库、未联网、未写库。
- 09-21/22 历史修复、目标日身份/IPO/公司行为/参考价、完整派生、same-day/cross-day/L2 与发布门仍待闭合；官方历史全集认证是独立证据阻塞，不另设授权门。

## 决策与被否方案

| 选择 | 被否方案 | 理由 |
|---|---|---|
| 新组合版本重跑完整门禁 | 旧绿移签、放宽基座漂移 | 收据只对实际运行版本成立 |
| 原生快进与合后回读 | 新生成 merge SHA 后沿用候选收据 | 保留精确受测 revision，并核对真实结果 |
| 测试配置与沙箱许可同源 | 换回旧解释器掩盖问题、关闭沙箱、放行整个家目录 | 修复可重复环境的夹具契约，同时保读写限制 |
| 独立验收账本、历史记录保留 | 删除误入 startup、伪造 switch | 部署事实 append-only，不能污染生产归属 |
| 固定证据目录、一轮一份原件 | 覆盖失败收据或反复执行覆盖式脚本 | 保留因果和失败路径 |
| 数据证据与工程通过分账 | 测试绿即恢复/部署成功 | 金融事实和运行代码是两组独立条件 |

## 接续与沉淀

恢复 owner 继续 #913：只复用 03 的 `final-replay`，取得可认证成员原件与历史事实后，在同一受保护恢复 owner 内接完整派生。运行锁、输入校验、逐字段回读和发布门不得绕过。数据门闭合后，再冻结部署版本并验工程、环境绑定、备份与实际切换。

Harness #17 维护开发基线、沙箱夹具与账本隔离模式；Memory #5 维护本轮能力节点和项目索引。文档仓只推各自分支/PR，不直接合 main。引用检查的行数漂移、跳过项和未解析引用应看原始审计日志；退出码 0 不表示全部引用被验证。

复用工具已在产品入口：`audit_deploy_ledger.py` 与 `run_frontend_gate.py`。私有证据目录中的控制脚本固定本次 PR、SHA、路径与采样窗口，只调用既有门禁，不包装成新的通用发布入口；相同失败形状沉淀进 Harness，而不复制第二套工作流。
