# 2026-09-22 #848 授权合并与实际 main 完整门禁

## 最终状态

#848 已按用户明确授权合并，实际提交 `a2c8d1f90773fdf3dcb7cf53f5d9733590924ae1` 获得新的完整工程绿收据。最终回读 main 仍为该 SHA；#846 仍 open/WIP，生产继续保持恢复快照，未部署、重启、写行情或调用生产 readiness。

前置验收与一位独立审查者的 `PASS_WITH_LIMITS` 见 `docs/handoffs/2026-09-22-watchdog-848-acceptance.md`。本文接替其中“等待合并授权”的状态，历史快照和独立原报告不改写。文档仍在 `docs/watchdog-848-acceptance-0922`，不合入 main、不把代码收据移签到文档提交。

## 授权与动作顺序

1. 用户原话“授权，推进”，承接明确的请求：只合 #848 head `2007edfa5de9c0db704095a51fa54a318362d59b` 到 base `e82717d9a7c3dfa811a4538bd44985b61258355a`，接受已披露限制，实际合并提交再跑完整门禁。来源为会话 `01a0c3fd-64a8-7216-baa4-fde82fbbb078`，用户消息 `aa752be6`，2026-09-21T18:49:55.577Z。
2. 重新读取远端引用和 PR，确认身份未漂移；复核候选 evidence-audit 所有列示文件哈希。Gitea 的 mergeable=false 是 WIP 平台保护，不用于替代本地冲突判断；`merge-tree` exit0，预览树等于受审树。
3. 仅解除 #848 WIP，以 merge 方式合入，不删分支、不改 #846。API 无错误，回读 closed/merged，Git 双亲、main 指针、合并树一致。
4. 新建独占 detached 检出 `/Users/a77/fwp-wt-watchdog-main-gate-0922`，固定实际 merge commit。未使用主检出的混合源码或搬动其 HEAD。
5. 空间约56GiB时启动 Python-registry 与前端两叶。继承上轮持久证据 runner，只更换受测树/完整SHA；每命令2400s硬上限，低于2GiB仅终止本轮自有进程组。并发其他 pytest/清理任务不干预。
6. 前端六步一次通过；Python全量一次通过，随后registry五项通过。立即从日志解析并复制原生收据，不依赖共享latest。两个runner和本轮测试服务均已退出。
7. 执行来源校验、JUnit/日志哈希/完整身份核验，归档本轮前端test-results约11MB，产出 `evidence-audit.json`，结论PASS。PR评论5558记录进行中，最终评论5563记录完整结果，均回读一致。

## 合并身份

| 字段 | 值 |
| --- | --- |
| merge commit | `a2c8d1f90773fdf3dcb7cf53f5d9733590924ae1` |
| 第一双亲/base | `e82717d9a7c3dfa811a4538bd44985b61258355a` |
| 第二双亲/head | `2007edfa5de9c0db704095a51fa54a318362d59b` |
| merge tree | `eed2e239853b628be272babc0f884b1d976df33b` |
| 授权/预检/guard/API/Git核验 | `~/.finance-runtime/reviews/848-authorized-merge-20260922/` |
| 正式合并记录 | 同根 `merge-record.json`、`full-identity-verification.json` |

## 实际提交门禁

证据根：`/Users/a77/.finance-runtime/reviews/848-postmerge-main-20260922/`。

| 检查 | 实际结果 |
| --- | --- |
| Python全量 | 12511 passed / 85 skipped / 2 xfailed / 0 failed，17 warnings，1155.85s |
| Ruff | exit0 |
| registry五项 | parseability、registry、backfill-tables、generate-views、ledger crosswalk均exit0 |
| 前端六步 | install/lint/typecheck/test/build/E2E全部exit0，完整叶142.2s |
| 前端单测 | 110 passed |
| E2E | 34 passed / 2 skipped，首次即绿，无重跑 |
| JUnit解析 | 12598 tests，0 failures/0 errors，87 skipped含2 xfailed |
| 两条watchdog | 全量中均通过，JUnit耗时0.250s、0.196s；不是性能趋势结论 |
| 身份与来源 | 首尾SHA/tree/全树干净一致；来源校验exit0，base drift0 |

- 原生收据：`/Users/a77/.finance-runtime/test-receipts/20260921T191851Z-a2c8d1f9.json`；即时副本 `python-registry/native-receipt.json`，两者SHA256相等。
- 解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，Python3.12.13，依赖指纹 `3328bed61f3e21ea`；最小环境白名单等价env-i，umask022，未绕依赖门禁。
- `python-registry/execution.json` 与 `frontend/execution.json` complete/identity_stable均true、exit0；嵌套 `frontend/gate/frontend.json` 六步收据齐全。
- `receipt-check.log` 校验完整revision、解释器、依赖指纹、干净和基座漂移；来源校验通过与测试退出0分别确认。
- `evidence-audit.json` 核日志哈希、原生原件/副本、JUnit、双亲、预览树和远端main；审计时远端main==受测SHA。
- 本轮前端产物已复制至 `frontend-artifacts/test-results/` 并逐文件记哈希，不复用上轮失败产物。

## 决策与被否方案

| 问题 | 选择 | 被否方案及理由 |
| --- | --- | --- |
| 授权边界 | 仅合#848和验实际提交 | 顺手合#846/部署：未获授权，#846独立结论仍欠 |
| 合并收据 | 新实际merge commit重新完整验 | 用候选tree相等代签：revision合同不同，用户明确要求重新验 |
| 测试耗时 | 同一次全量等到结束 | 只拿定向或中间进度签绿：不能覆盖完整叶 |
| 文档归属 | 独立docs分支交接 | 修改实际受测树或顺手合文档：会改变门禁对象 |
| 原始红证据 | 保留旧main与候选首次红 | 将新绿写成历史红从未存在：不符合实际发生顺序 |

## 残余限制与勘误

- 独立 `PASS_WITH_LIMITS` 仍来自同一会话的规格/质量两轴，不是两人签字，也没有新签字覆盖 merge commit。此处只核合流内容身份与工程证据。
- 0.8s测量起止点已从整轮收窄到到期事件至watchdog返回；0.2s业务预算未增加，不表示旧端到端保证保留。模块假钟影响同进程deadline，线程窄窗口、间接异常诊断仍有边界。全量绿不证明这些限制消失。
- 原main e82717d9的12509P/1F仍为那次真实结果；候选首轮缺Chromium红及其trace丢失仍保留原口径。当前a2c8d1f9的新绿只结束本修复的实际提交工程验收。
- 本轮预检的是21881/21884，但复制runner实际仍用20881/20884；从日志确认两个本轮服务分别成功启动并退出，没有端口冲突，不冒称已预检实际端口。
- 监控中一次省略日期的错误路径读不到文件、一次macOS不支持find -printf，均不是门禁失败。后段再次使用错误路径的只读探测没有提供证据，最终核验只用正确路径原件。
- 助手曾把并行ps的exit1误报为收据校验非零，随即查原件纠正；真实来源命令exit0，ps的1表示所列自有进程已退出。没有额外测试重跑。
- 补独立报告计数勘误：原报告写+151/-21，实际测试文件是+130/-21；原报告不改，操作者核对不冒充审核者签字。

## 后续与禁止事项

本轮授权范围已完成，无运行中的自有门禁任务。#846仍open/WIP@`efcf34ff5b7bba381cf64960b6a65b9ea91173be`，后续独立验收需另处理；不得用本次绿填补它。

生产软链保持 `/Users/a77/.finance-runtime/finance-workspace-adcda94b5e40-recovery-20260921`。本轮未调用部署脚本、未重启8792、未写行情、未跑生产health/readiness或新真实金融问答。含未验K3的main仍禁止整体部署；工程绿不是生产发布授权。

本轮runner与审计器固化一次性身份并留在持久证据根；长期门禁仍复用 `scripts/run_frontend_gate.py`、`check_test_receipt.py`，未扩产品能力或另造设施。通用收据/进程返回码纪律已在既有方法记忆，未触碰他人修改的harness-reference/BUILD.md或主检出。
