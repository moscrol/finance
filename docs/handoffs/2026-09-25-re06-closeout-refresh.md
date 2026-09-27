# 2026-09-25 RE06固定新主干工程验证

## 背景与范围

接用户继续推进，处理旧候选8088b4af7因主干漂移6>5被拒的问题。旧树`fix/re06-closeout-forward-0924`保持原样；没有借旧绿给新组合签字。

复核Gitea main仍为03352758cf9b31e3f5d179b517be48cb89588679，原候选树干净且无执行进程，另建`fix/re06-closeout-refresh-0925`。Git对象预演无冲突；实际合流提交a30e7e4594ac09310271739c8beb30ee8b2cd3ef，父提交依次为03352758和8088b4af776125c0ef8dbf8d9c1409e4f8aa7387，tree=156fdda70f2476ed71d7667957247ef02e2f12a4。

只形成本地候选，未push、PR、合main、部署、生产写入或新增模型请求。原三组独审/C1-C10与自然验收预算、发布边界不变。

## 执行顺序与证据

证据根：`~/.finance-runtime/reviews/pi-closeout-execution-20260924/re06-a30e-refresh/`。

1. 固定候选干净，差分格式检查通过；主解释器`~/finance-workspace-private/.venv-workbench/bin/python`。00:47启动前load1=4.98，无其他pytest，磁盘约51GiB可用，未放宽load<=8/预计pytest<=2约束。
2. 复用仓内`run_extraction_mutations.py::_run_logged_command`包住正式`run_main_gate.sh`，2700秒硬限；PID41888/进程组41867，00:47:59至01:04:53，真实exit0、未超时、进程组已退出。没有仅凭stdout推测退出码。
3. 正式完整Python：Ruff0；15471P/85S/2X，0F/0E/0XP，collected15558，无ignore/deselect/-k/-m/lastfailed，dirty=false、全树脏文件0。JUnit15558条，15471通过、87跳过含2预期失败，与收据一致。成功basetemp由正式门禁清理，日志与JUnit保留。
4. Python唯一收据：`receipts/gate-qXwwsFSR/pytest.json`，完整原始stdout为同目录`pytest.log.txt`；外层`full-python.process.json`记录真实进程状态，`full-python.log`保留原门禁输出，`pytest.xml`是完整JUnit。
5. 前端在同SHA隔离树`frontend-tree`运行既有`run_frontend_gate.py`六步：install/lint/typecheck/test/build/test:e2e全部exit0；122单测，E2E34P/2S。端口19981/19984启动前空闲，结束后无监听。`frontend/frontend.json`确认首尾身份稳定且干净；外层`frontend-command.process.json`为exit0，子进程组已退出。
6. registry四项及ledger crosswalk均exit0，逐项`.process.json`和`.log`在证据根。没有用Python绿跳过其他叶子。
7. 结束时远端main仍03352758；在干净a30固定树运行`check_test_receipt.py --expect-revision a30... --require-full-scope --base-drift-max 5 --main-ref gitea/main`，exit0，收集/计数/解释器/依赖指纹/身份/干净状态均一致，实际基座漂移0。见`receipt-check.log`。后续文档提交不移签代码收据。

## 工程通过不等于整体准入

`workspace-doctor.json`仍exit1/blocked：共享httpx实际0.25.2、锁要求0.28.1。缺模块0，未改共享环境、未设置依赖门禁绕过。正式收据只说明“该固定代码在当前受验环境通过且环境指纹一致”，不能称锁定依赖CI环境通过。新工作树代码地图为空，仅作告警，不据此做架构完整性结论。

三组独立审查、C1-C10逐项覆盖及自然验收没有新增证据。工程四叶齐不能把旧147/218请求账改写、填补缺失终稿或授予合并/部署权限。

## 决策与被否方案

| 选择 | 否决方案 | 理由 |
| --- | --- | --- |
| 最新已观察main固定后另建候选 | 追移旧8088并沿用旧收据 | 旧漂移拒收要保留，新组合必须新验证 |
| Python与前端用同SHA不同树 | 构建产物与Python共用可写树 | 避免前端构建影响Python受验身份 |
| 用既有日志器捕获真实退出并留完整JUnit | 按尾部“passed”人工补exit0 | 日志内容、进程结果与收据身份是不同证据 |
| 环境锁偏差单列blocked | 顺手升级共享httpx或当doctor无关 | 共享环境属于多执行者；当前绿不证明锁定环境合规 |
| 保持本地与未验收状态 | 四叶绿直接push/合main/部署 | 独审、自然验收和发布授权仍缺 |

## 下一步

1. 在授权的独占环境方案下处理httpx锁偏差；不改当前共享解释器。环境变化后新收据需重验，不能重签本轮。
2. 按原有界方案协调独审与C1-C10，再做自然验收；不得自动追加模型预算。
3. 合入前重新核远端main与受验身份；生产发布另行授权。

工具盘点：全部复用现有门禁、前端runner、日志器、registry与收据校验，无新增应用能力或临时自动批准器。本轮所有检查均已结束，无后台等待/重试任务；同SHA前端隔离树暂留作证据定位，不删他人现场。
