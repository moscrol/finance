# #83 / #813：3c5 工程验收完成，待独立 QC

## 最新结论

2026-09-24，作者四叶与整库副本验收全部通过，**ENGINEERING_READY_PENDING_QC**。#75 独立审查尚未完成，#813 保留 WIP；未合 main、未执行生产回填、未动 8792/launchd/其它股票，也未停止其它任务。

- 唯一候选：`3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59`，已推 #813 的 `fix/backfill-main-ready-0921`。
- 集成基线：`4cc15e703f81bce8abadee00f68caacdb0c72b4d`；完成核验时远端 main 一致，漂移 0。
- 唯一被验树：`~/.finance-runtime/reviews/backfill-302132-0923/forward-02/tree`。
- 证据原件：同根 `continue-08/`；动态入口 `CURRENT.json`；归仓小收据 `docs/verification/2026-09-24-backfill-302132-current-main-ready/`。
- 本文只推文档分支 `fix/backfill-302132-0923`，不再移动 PR head。本分支代码仍旧，不能从这里执行验收或生产命令，执行根只认被验树。

## 为什么再次前向

ca4 已完整通过，原件在 continue-07，归仓在 `docs/verification/2026-09-24-backfill-302132-ready/`。发布最终 PR 记录前，远端检查拦下 main 新增 #884：除归档文档外，还改了门禁日志捕获、运行时探针及测试，因此没有发布过期的“当前 main 就绪”。本轮从 ca4 无冲突合入固定 4cc，未手改产品代码；父提交就是 ca4 和 4cc。新组合重新跑全套，不把 ca4 绿收据移签 3c5。中途进度评论 6789 已明确这一点。

更早的主线漂移、来源路径误判、资源中断、系统模拟生命周期修复及被否方案，见 `2026-09-24-backfill-302132-engineering-ready.md` 和 `2026-09-24-backfill-302132-gate-continuation.md`。旧收据保持原样。

## 3c5 原件对账

| 检查 | 结果 | continue-08 相对入口 |
|---|---|---|
| 定向 | 118P | focused-receipt.json |
| Python 全量 | ruff PASS；15457P/0F/0E/85S/2X；收集15544 | python-receipts/gate-47iUwvcM/pytest.json |
| 完整范围与身份 | exit0；版本/解释器/Python版本/依赖指纹一致，干净树，漂移0 | scope.command.json、scope.log.txt |
| 前端 | install/lint/typecheck/120P/build 全0 | frontend/frontend.json |
| E2E | 34P、2个既有跳过，超时标准未变 | 同上；e2e-results/ |
| registry CI | 工作流五项全0，finance-only及缺席跨仓项口径与CI一致 | registry-complete/receipt.json |
| 整库副本 | 37PASS；错误输入不发布、金额负对照、恢复及生产身份均符合预期 | rehearsal/summary.json、acceptance.json、amount-control.json |
| 合并预览 | 4cc+3c5 无冲突；树20101d9ea85cb3f732483aa0747a8233d2c0ae5c | verified-closeout.json |

全量命令 runner 用时1087.781秒，最低空间72841564160字节，没有触发4GiB保护线。保持中性 basetemp、pytest原生失败保留策略，无筛选、无断言或超时放宽；前后身份一致，进程已退出，成功临时目录已由门禁清理。新主线门禁另保留完整实时 `pytest.log.txt`，但只凭最终收据采信，不把实时输出当终局。

PR相对4cc的增量未命中 data-quality-check 路径条件；本条是条件判定，不声称额外工作流执行过。verified-closeout 对14份小原件计算哈希；归仓镜像不改写版本或来源路径，前端/registry步骤日志已一并归仓，其中三份前端日志末尾空行触发diff-check，改用Base64无损编码，解码后哈希仍与原收据一致。所有原日志及E2E完整产物也保留在树外原目录。

## 本版本副本结果

固定范围仍为 `302132.SZ / 2026-06-15..2026-09-11`：53 INSERT（并跑51日、冻结parquet两日）+06-23空壳UPDATE；09-11钉值及其它股票/目标窗外全列不变。

- apply=`65b86fe466d8`，verify=`45c0bb089166`。窗内由11行、close/pct_chg/amount各10非空，变为64行、三项各64非空，无相邻三元值整行克隆。
- technical=39，window=161；5/10/20/60日窗口为59/54/44/4。37项正常验收全过。
- 错误parquet父命令exit2且未发布；amount=1e15时验收exit2，唯一失败项为 `keyset_fullfield_oracle`，属于预期负对照。
- 恢复SHA、基线SHA及生产前后SHA均为 `5f8e86cd854b7c6569cdcb62bfb5e9861d1d3a804d8f521480003185323dc91e`；生产stat与fact最新日期不变。
- 冻结parquet SHA：`51f9ee9cba1ceb4a6ff50c4c4dce8267cb39f78add28d6a33699cbf90bf28d17`。四个大库副本成功核验后已清理，输入和运行记录保留。

## 待办与授权边界

1. #75 以3c5独审。本轮为作者工程验收，不冒充独立Spec/Quality结论，也没有补签旧的中断审查。#802已关闭，评论6446指向#813，原分支保留。
2. 独审通过后请用户明确确认合入；再次核对PR head、main和干净状态。未来主线/候选变化需要重新评估，本文不是滚动许可。
3. 生产另需对命令、日期、冻结输入和本轮真实父备份回滚点逐字授权；待授权模板位于上述新归仓目录及树外根目录 `production-authorization-draft.md`，均指向forward-02/3c5。CLI没有--record，授权另存JSON。
4. 回滚只认本次父收据 `backup.backup_path / backup.backup_sha256`，不用演练或“最新”备份。出现WAL、活跃写者或回填后新业务写入先停下，不覆盖后续数据。生产前重新冻结，不把历史SHA当未来事实。

方法沉淀沿用 agent-memory 的 `pytest-temp-paths-and-mock-lifetime`；这一轮没有新增通用框架或产品能力，不另建能力清单。中性临时目录仍只是环境隔离，不代表修了产品来源路径股票代码误判。
