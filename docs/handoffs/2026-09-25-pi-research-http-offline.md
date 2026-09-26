# Pi 研究链：Workbench 入口离线组合

## 背景与边界

用户本轮说「推进」。继续交付 #911 的离线验收，不接管 #868 owner 的独审、不调用真实模型、不合 main、不部署 8792。上一份记录为 `2026-09-25-pi-research-forward-delivery.md`。

此前 36 个研究链场景走真实 Runtime/Harness，但没从 Workbench API 入口发消息。本轮新增 `intelligence/tests/test_workbench_research_chain.py`，从 FastAPI TestClient 走真实路由、TurnOrchestrator、ContinuousTurnAdapter、GLMAgentRuntime、ContinuousAgentEpisode、FinanceResearchHarness、结构/语义验证器和文件持久化。TestClient 是进程内 ASGI 测试客户端，不是 TCP 服务、浏览器或线上 8792。

模型（含判官）和数据源注册表是替身；判官返回脚本化通过，不认证金融判断质量。本轮没有修稿质量、子研究、真实源检索或自然模型自主性的新增结论，也没有修改任何生产文件。

## 按发现顺序

1. #911 工作树 `~/fwp-wt-pi-research` 干净，起点 `125d340054d2`。底层仍是固定组合的 #868 `f2610293fdbe`，本轮没有追入 owner 的新 HEAD。
2. 共享环境曾有 httpx 0.25.2 与锁 0.28.1 不一致；不在他人全量测试期间修共享环境。执行 `python3 scripts/workspace.py bootstrap --python /opt/homebrew/bin/python3.12 --install`，在本树创建独立 `.venv-workbench`。doctor：ready、dependency_drift={}、scope=offline_development、production_verified=false。代码地图保鲜警告不等于环境依赖失败，亦不据此声明架构完整。
3. 用真实 HTTP 路由提交市场情景题。替身模型读取工具消息里的 next_query / empty / tool_exception，才决定下一次查询；第二份证据通过实际 E 序号映射进入 binding。
4. 开发时纠正了测试本身的导入、API/私有产物字段形状、空结果必须携带 ProviderTrace 等错误。保留开发失败收据，未改产品以迁就替身。
5. 一次 9P/1F 暴露测试读序：消息完成时，私有审计产物可能尚未发布。沿用已有异步交付合同，在本测试自有 supervisor 执行器上 wait-join，再读审计工件并撤销环境/替身；不改生产终态，不用 sleep 赌时序。
6. 20 个新增场景：开关 off/on × 四种观察 × 正常/伪造证据，共 16；再加两种变异 × off/on，共 4。变异分别替换模型可见追查线索、在 finish 准入前将伪造引用洗成有效引用，必须被对应具体断言检出。
7. 代码冻结为 `0c57cd0d7181902fd26fcb4f8ffcc4cfbd65d959` 并推送现有 #911，随后跑十目标联合回归。没有另建 PR。

## 断言覆盖

- 两次工具执行、三次写手模型调用，第二次查询必须来自实际观察；工具异常的具体 detail 也必须到达模型。
- 正常结果的原始草稿、语义验证器公开稿、answer.md 和 HTTP 消息正文一致；公开消息带引用。
- 绑定只指向实际证据，正常终稿只绑定第二份证据；伪造引用不得 completed、不得把原始草稿交给用户，保留 invalid_action。
- 私有 contract、RuntimeHandle、持久化 Episode 的身份一致，明确 user/conversation/run/assistant_message/episode；事件序号连续，持久化状态终态，handle closed，严格消息派生零失配。
- HOME、用户、Episode、金融数据和知识目录隔离到 tmp_path；清除外部模型配置，阻止 socket connect/connect_ex。即使外呼错误被上层捕获，夹具收尾也断言外呼尝试为零。
- 只等待和回收本测试的执行器，不访问或停止其他 owner 的进程/端口。

## 决策对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 修改共享 venv 解决依赖漂移 | 会改变并行 owner 已冻结环境 | 否 |
| 本 worktree 用现有 bootstrap 安装锁依赖 | 隔离环境，无新安装框架 | 采用 |
| 继续只测 Runtime 或替换整个 Adapter | 不能补入口到持久化之间的组合证据 | 否 |
| 真实路由/调度/适配器，替换模型与源 | 零真实模型成本，能验身份、消息和落盘合同 | 采用，限定进程内离线 |
| 将脚本化 judge=passed 视为答案质量验收 | 判官结论来自夹具，不能证明自然语义 | 否 |
| 消息 completed 后立刻读所有工件 | 消息与产物是分开发布的对象 | 否，join 本测试拥有的 worker |
| 同步追入正在独审的 #868 新 HEAD | 扰乱候选身份，也可能重复 owner 工作 | 否，单独交付测试提交供后续采用 |

## 冻结验证

受测提交：`0c57cd0d7181902fd26fcb4f8ffcc4cfbd65d959`，干净树。
解释器：`~/fwp-wt-pi-research/.venv-workbench/bin/python`，Python 3.12.13，httpx 0.28.1，依赖指纹 `66726d345bf37ce5`，依赖门禁未绕过。

```bash
.venv-workbench/bin/python -m pytest -q -rsx \
  intelligence/tests/conformance \
  intelligence/tests/test_glm_agent_runtime.py \
  intelligence/tests/test_research_progress.py \
  intelligence/tests/test_adaptive_research.py \
  intelligence/tests/test_research_plan.py \
  intelligence/tests/test_episode_semantic_verifier.py \
  intelligence/tests/test_research_harness.py \
  intelligence/tests/test_workbench_research_chain.py \
  intelligence/tests/test_workbench_conversation_integration.py \
  intelligence/tests/test_continuous_turn_adapter.py
```

结果：787P/0F/0E/3S/1X，collected=791，33.31 秒。收据：`~/.finance-runtime/test-receipts/20260924T165102Z-0c57cd0d-bcce35088223.json`。`check_test_receipt.py` 已用精确 SHA、require-full-scope 及十个 require-target 校验成功；这里 full-scope 只指指定目标未被 -k/ignore 等收窄，不是全仓。

3S：参照后端 deadline 分窗/finish 协议不适用，以及部分 RuntimeHandle 接口未接；1X：既有 codex_headless 无 resume 明确收据，2026-08-29 已登记。Starlette 对 httpx TestClient 的弃用警告仍在，未为消警告偏离锁。全仓 Ruff 与本次提交钩子通过。开发期 20P 收据 `20260924T164847Z-125d3400-943ff8f9659a.json` 为脏树诊断，不作冻结验收。

不移签后续文档 HEAD、#868 新 HEAD 或未来组合；未运行完整 Python/frontend/E2E/registry 四叶门禁。旧 6b7 的 606P、#910 的 3e8/57P 保留历史归属。

## 同期 owner 状态，必须重读

00:47 左右 API 查 #868 仍 open/WIP，HEAD `89624eac7e76`。00:51 左右读 `~/.finance-runtime/reviews/pr868-glm-qc-20260925-next/authorization.json`：approved=true，owner 桌面会话用户「执行」，candidate=f2610293fdbe、baseline=03352758c，本批上限 78、累计 291、自动重试 0。`spec/gateway/receipt.json` 为 4 请求预检 PASS，purpose 明确不是 QC。该目录 STATE.md 仍写未授权，已经滞后于授权原件；本记录不把 STATE 的旧口径继续当当前事实，也不从网关绿推出独审通过。

这是原 owner 的在途批次，不是本会话新增调用或额度。本会话不变更其冻结输入、授权、审查者产物或环境。最终独审结论、C3/C7、自然质量和合入/部署均由 owner 继续按原件核验。

## 下一步与沉淀

#868 owner 可在当前冻结批次之外审阅并采用 #911 增量；最终组合需重新绑定候选与适用验证，不能借本收据替代。独审闭合后再接 #76/L6 逐行自然验收，main 合入与 8792 部署另行确认。

没有新通用工具：安装/doctor/收据/路由夹具/线程回收均复用现有能力；机械断言留在正式测试文件。异步产物等待已覆盖在共享知识 `10_knowledge/terminal-signal-scope-and-projection-waits.md` 的「测试夹具撤销也是一个独立边界」，不另造等待框架或重复方法清单。
