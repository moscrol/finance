# 2026-09-22 #848 独立审查与固定版本完整门禁

## 状态与授权

用户本轮“执行 / 继续”授权推进 watchdog 测试修复的验收流程，不是合并、部署或解除 #846 WIP 的授权。#848 仍 open/WIP，head 固定 `2007edfa5de9c0db704095a51fa54a318362d59b`；main 仍 `e82717d9a7c3dfa811a4538bd44985b61258355a`。

本轮结果：该固定候选取得一位独立审查者的 `PASS_WITH_LIMITS`，Python 全量、Ruff、registry 五项通过；前端前五步通过，E2E 首次缺浏览器失败，安装对应缓存后单次复验通过。可提交合并申请，但原 main 红灯、独立审查的限制和生产发布禁令均不消失。

为避免收据移签，验收文档提交到 `docs/watchdog-848-acceptance-0922`，不推进 #848 head。文档检出 `/Users/a77/fwp-wt-watchdog-closeout-0922`；代码作者检出 `/Users/a77/fwp-wt-watchdog-test-0922` 保持干净、远端同步。本文及本分支 inflight 接替早期交接中的“没有 PR / 未独立 / 未完整门禁”状态；原日期快照保留为历史。

## 发生顺序

1. PR 创建此前两次超时，后续回读确认创建成功为 [#848](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/848)，并保持 WIP。
2. 作者在 `2007edfa5` 重跑编排与合同模块 `107 passed / 17.15s`，收据 `20260921T171659Z-2007edfa.json`。早期文件名 `independent-pytest.log` 有误导性：那只是作者另起进程复验，不是独立签字。
3. 磁盘曾跌至约 248MiB，暂停新增重任务。仅删除自有旧 #831 两棵验收树的 `intelligence/webapp/node_modules` 与 `intelligence/webapp/test-results`，约 400MB；源码、Git、外部日志与收据保留。随后空间大幅回升不是全部由该清理造成，不清他人工作树或事故现场。
4. 新独占审核检出 `/Users/a77/fwp-wt-watchdog-qc-0922`，固定 `2007edfa5`。Codex 会话触及 usage limit，exit1，无报告；另有 hooks 解析提示，不能算独立结论。
5. 首次 Claude `--bare` 未显式载入既有认证 helper，立即 `Not logged in`，exit1、0 token，同样无结论。保留该失败，不更换凭据。
6. 显式加载现有 helper/本机代理后，新 Claude 会话真正读取 diff/实现并运行自拟验证，480s 上限内完成，exit0、首尾干净一致、无权限拒绝。配置及事件记录的模型为 `claude-opus-5[1m]`，session `7bf22b99-ba7a-4dbf-aa0e-08e8848a8fb6`。Spec 与 Quality 是同一位审查者的两轴裁决，不是两位独立签字。
7. 独立结果为 `PASS_WITH_LIMITS`：watchdog 两例 2P、合同文件 2P；自拟删除时钟推进的反例 1F、无假绿；另验证模块时钟对跨线程实例可见、Event/Future 仍走真实时间。原报告见 `docs/verification/2026-09-22-watchdog-848-independent-review.md`。
8. 新门禁检出 `/Users/a77/fwp-wt-watchdog-gate-0922` 固定同 SHA；空间、独立端口预检后执行一次完整 Python 和前端叶。不用主检出的混合源码，不运行危险部署脚本，也不杀其他 agent 任务。
9. 前端先得到 27F/9P，27F 全部在浏览器启动处报缺少 `chromium_headless_shell-1179`，前五步 exit0。只安装 Playwright 指定的 Chromium v1179 缓存，再单次重跑 E2E，34P/2S、exit0。没有再次跑 Python 全量凑绿。
10. Python 单次完整结果 12511P/85S/2X、17 warnings、1045.96s、exit0；Ruff 与 registry 五项 exit0。收据和 JUnit 核对通过，两条 watchdog 回归在全量里均通过。
11. 回读 #848、#846 均 open/WIP；生产软链仍指向 `adcda94b5e40-recovery-20260921`。未合并、未部署、未重启、未改行情；本轮没有新的生产 health/readiness 或真实金融问答结论。

## 独立限制与作者核对

原报告不改写，下面是作者核对，不是新的独立签字。

| 事项 | 接受的范围 / 限制 |
| --- | --- |
| 0.8s 起止点 | 从整个 `run_turn` 收窄到到期事件至 watchdog 返回，这是实质性范围改变。0.2s 业务预算未增，不代表旧端到端耗时保证保留。独立审查将补真实时钟有界测试列为非阻断建议。 |
| 真实时钟覆盖 | 审查者只详细核对两个自然落点，不能推导“全仓没有”。现有 `test_root_budget_invariants.py` 有 from_timeout、stage_timeout、真实 monotonic 过期断言；`test_research_policy.py` 也有真实时钟预算测试。这些不等于恢复被移除的 0.2s 整轮亚秒返回断言。 |
| 挂起风险 | 当前阻塞 worker 的 `release_worker.wait(timeout=5)` 是显式测试防死锁帽，失败会完成 Future。独立反例已实测 7.90s 以 `KeyError: returned` 失败；因此不能把报告中假设未来同时改变 deadline/worker 行为的场景称为当前版本已复现永久挂起。测试进程的外部硬上限仍保留。 |
| 模块时钟隔离 | 不是线程局部或单实例隔离；窗口内所有 `ResearchDeadline` 都受影响，包括先前遗留线程。finally join 在 monkeypatch teardown 前执行只收口本例自有线程。全量通过不证明跨用例污染绝不存在。 |
| 失败诊断与线程边界 | worker 异常经 Future 进入 runtime 后可能被后续 KeyError 间接检出，诊断不够直接；记录线程前的窄窗口与 finally 异常覆盖原异常也保留为限制。未扩改生产代码。 |
| 原全量因果 | 历史 e82717d9 的失败 trace 已丢失，0.25s 延迟实验只证明一种可触发机制，不证明唯一根因。 |

选择先保留小范围测试修复并完整验收，而不是扩改 runtime 或增加业务预算。若要保留原端到端墙钟断言作为合并必要条件，需补测试、冻结新版本并另行验收，不能借此报告宣称已覆盖。

## 门禁与来源

证据根：`/Users/a77/.finance-runtime/reviews/watchdog-full-gate-20260922/`。

- revision：`2007edfa5de9c0db704095a51fa54a318362d59b`。
- base：`e82717d9a7c3dfa811a4538bd44985b61258355a`；最新 fetch 后仍一致。
- 本地 `merge-tree --write-tree` exit0，预览树 `eed2e239853b628be272babc0f884b1d976df33b` 等于候选树。
- Python：`python-registry/execution.json`，首尾 identity 一致且全树干净；环境为最小白名单，等价 `env -i`，`umask 022`；指定主树 `.venv-workbench/bin/python`，Python3.12.13，依赖指纹 `3328bed61f3e21ea`，依赖门禁未绕过。
- 全量原生收据：`/Users/a77/.finance-runtime/test-receipts/20260921T183408Z-2007edfa.json`，已即时复制 `python-registry/native-receipt.json`。JUnit 12598 条，0 failure/0 error，87 skipped 内含2 xfailed；终端为12511P/85S/2X。
- `receipt-check.log`：完整 revision、解释器、依赖指纹、干净和 base drift 0 校验 exit0。来源 exit0 与测试 exit0 分开确认。
- Ruff、parseability、registry、tables、views、ledger crosswalk 均 exit0，各日志保留。
- 前端首轮：`frontend/gate/frontend.json`，install/lint/typecheck/test/build 均0，单测110P；E2E 为1，27F/9P。原收据不修改。
- E2E 环境修复后：`frontend-e2e-retry/execution.json`，34P/2S、119.16s、exit0、首尾干净相同；独立测试端口20881/20884已退出，不是生产8792。
- `audit/evidence-audit.json`：上述原件的 SHA256、JUnit解析与叶子交叉校验；状态是 `PASS_AFTER_BROWSER_ENVIRONMENT_REPAIR`，不是“所有首次尝试全绿”。
- 独立证据根：`/Users/a77/.finance-runtime/reviews/watchdog-qc-20260922/`，三次启动失败/成功各有 execution、事件与日志。有效报告在 `authenticated-claude/`，仅绑定相应 base/head 的测试增量。

## 证据保全与记录器教训

- 原 main `20260921T160947Z-e82717d9.json` 的12509P/1F仍是正式 main 的完整红收据。候选通过不改签 main；合并后实际提交必须重新验。
- 独立报告自述“原生收据副本已存”，审核目录实际只有 JUnit 副本。作者核对两个原生收据的树/SHA/2P后，在本轮最终 audit 时才补复制到 `audit/`，不冒充审查时已保存。
- 首次 E2E 的文本日志和收据保留；重跑复用 Playwright 默认 `test-results`，首次 trace.zip 未事先独立归档，已经被重跑清理，不能声称所有失败现场仍在。后续同类复验应先复制失败产物或使用不同 `--output`。
- 浏览器安装第一次从错误 cwd 执行，报 `ERR_PNPM_RECURSIVE_EXEC_NO_PACKAGE`；还发生后台目录重定向竞态。之后正确 cwd 下载完成。原第一次短安装日志被后续安装覆盖，错误只在本轮会话留痕。安装进程退出码未采集；后来 `ps` 找不到 PID 返回1，不是安装退出码。已当场纠正。
- E2E 记录器两次未启动：重定向目标目录不存在、目录预建与 `mkdir(exist_ok=False)` 冲突；均未运行测试。修正记录器后只有一次真正 E2E 复验，失败的 runner.log 与 PID 原件保留。
- 这些只服务本次验收的运行器放在持久证据根，不扩进产品模块；已有 `scripts/run_frontend_gate.py` 承担长期门禁入口。未接管 #814 收据设施或改 `run_main_gate.sh` 的已知 shell 问题。`harness-reference/BUILD.md` 的他人修改不触碰。

## 下一步与禁止事项

1. 请求用户明确授权：只合并 #848 的 `2007edfa5...` 到指定 base `e82717d9...`，接受上述测试范围限制；授权前保持 WIP。
2. 执行前回读完整 base/head、检查合流树；任何身份变化停止，不以旧批准覆盖新代码。
3. 合并成功后，实际 main merge commit 再取得完整门禁收据；不拿本候选或文档提交代签。
4. 本文的文档分支没有新的完整工程收据，不纳入 #848 合并请求；后续单独处理文档。
5. #846 独立结论仍欠，保持 WIP；含 K3 的 main 禁止整体部署，测试修复不重启8792，不操作行情和生产数据，不清事故/他人证据。
