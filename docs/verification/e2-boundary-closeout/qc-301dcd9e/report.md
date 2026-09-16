# E2 P3b / P3c + 返修独立审查报告

状态：**审查完成**  
固定 revision：`301dcd9e1eef5095424027ffa703bfeab2472cc6`  
工作树：`/tmp/e2-qc-301dcd9e`（实际路径 `/private/tmp/e2-qc-301dcd9e`）

## 一、最终裁定

| 审查片段 | 裁定 | 判据 |
|---|---|---|
| **P3b** | **通过，仅限本片** | local_only 的能力、全部 requirements 和输出 evidence_types 同源收窄；认证本地 runner 实际走临时 DuckDB、JSON 和用户台账；未知/混合实现不能借本地标签获得授权。 |
| **P3c + 返修** | **通过，仅限本片** | 实际持有的 registry 在消费者之前绑定；批次/repair 的当前 runner、菜单、执行授权与拒绝原因一致；原同名替换反例关闭；更严 ceiling、任务身份、历史诊断及晚结果归属未见本片回归。 |

**本片未发现需退修的 P1/P2/P3 产品问题，也无未解决的本片阻塞项。** 唯一未判清红针已独立追踪，裁定为**探针构造错误**，不是产品晚结果错记新 Scope。原失败源码、日志完整保留；没有删针、改应用、放宽产品超时或仅加 sleep 求绿。

这不是完整 P3、合并、部署或产品验收许可。审查为**同型号、独立上下文**，不是不同模型交叉验证；作者全测 9781P 不作放行依据。

## 二、身份、范围与证据完整性

- 开始及结束均核验目标 HEAD，`git status --short` 为空，结束 `git diff` / `git diff --cached` 无差异。见 `git-start.log`、`git-finish.log`。未修改应用、原题、评分或原 46 针，未提交/合并/推送/部署。
- 已读原完整 prompt、续接范围、`AGENTS.md`、产品门材料边界、设计 D4/A16，以及指定 launcher、独立探针和三份日志。
- 已核验三个保存 diff 与指定 git 区间的 SHA-256 完全一致，逐项审读应用变更及有关测试：

| 区间 | 文件 | SHA-256 |
|---|---|---|
| `e0051804..8ea6c5c1` | `p3b.diff` | `f74a2cc6541f56f8bf307834fd0d0e98983d957d6a743b39118c00486a7f099f` |
| `812b4d46..b4ba6fb5` | `p3c.diff` | `0bc08aae6584a829661b268647de91da466ad7b9056004f33b9bd59bcf0384c5` |
| `c942fcd1..301dcd9e` | `repair.diff` | `b122d6bf344eca0dd06403d90e2ed135f7cc4891f011bfb2a22821d930e1df1c` |

- 先前服务 Concurrency limit 及 harness 退出码不作为测试通过证据。原 `independent.log` 明确 **36 passed / 1 failed**。
- **focused 历史记录差异说明**：续接文字提示它含初始隔离错误与后续绿结果；本次实际读到的 `/tmp/e2-qc-301dcd9e-evidence/focused.log` 只有 38 passed / 1.57s 的完整后续 session，未见初始错误正文，不能杜撰其错误类型或次数。已另存 `focused-finish.log` 重新验证，不依赖历史退出码，也不将审查设施拦截冒充产品缺陷。
- 原 `adjacent.log` 是 281 passed / 3.17s；该短日志没有测试路径清单，本报告不推断它的覆盖范围。原 prompt 中更早的 709P/12skip、31P/2F 只作历史背景，不与本次结果相加。

## 三、唯一红针：实际顺序与判定

### 3.1 原针为什么必然不能证明“晚结果”

原文件 `test_independent_scope.py:169–199` 中：

1. 第 176 行 `base = spec(count)` 已构造 ToolSpec；应用 `research_tool_registry.py:930–932` 将其回调包装成 **ToolRunnerAdapter（调用前检查并统一结果格式的适配器）**。
2. 第 177–179 行的 slow 回调先等待 release，再调用 `base.runner(q, tc)`；此处不是直接生成 fixture 结果，而是**再进入一次适配器**。
3. 批次的 `.08s` deadline 到期后先返回，测试接着绑新 Scope，再设置 release。第二次调用进入 `research_tool_registry.py:807` → `agent_research.py:2073–2081`，发现同一个 deadline 已过期，在真正的 `spec.<locals>.run` 增加 runner 计数之前抛 `TimeoutError`。
4. 因而第 191 行 `count['runner'] == 1` 得到 0。不是 Scope 把结果丢失/串账，而是这个 fixture 从未产生它声称要观察的晚结果。

保留原函数及其断言不动的 `test_trace_original_late.py` 仅包裹记录执行点。重跑仍然 **1 failed，真实 pytest_exit=1**，并保存 `original-late-trace.json`：

| 相对时间 | 实际事件 |
|---|---|
| 1.334ms | 外层 slow 进入适配器，deadline 未过期 |
| 82.055ms | batch.execute 返回 `timeout / tool_timeout`，持有旧执行 Scope |
| 82.134ms | 新 Scope 绑定完成，allowed_tools 为空 |
| 82.215ms | `base.runner` 二次进入适配器，deadline 已过期 |
| 82.221ms 起 | `TimeoutError: agent tool deadline expired` 传播 |
| 82.228ms | `tool/error` 仍由**旧执行 Scope**发出；没有 `tool/result` |

这里 `release.wait(3)` 没有等满 3 秒，也没有导致死锁：批次约 80ms 超时退出等待后，主线程重绑并释放回调。`ThreadPoolExecutor.__exit__` 在 release 之后才等待工作线程收尾。应用 `episode_tool_batch.py:781–810` 到期后 `future.cancel()` 不能杀死已运行回调；其 `partial(..., scope=self._scope)` 在第 750–764 行提交前已经捕获旧视图，不在晚返回时读取新的 `batch._scope`。

### 3.2 修正不弱化断言

另存 `test_independent_scope_v2.py`，差异见 `independent-probe-correction.diff`。仅修正上述一针，其余原针源码不变：

- 使用**单层已经进入执行的 slow 原始回调**，release 后直接返回同样的临时证据/ProviderTrace，不在超时后发起第二次受 deadline 检查的 runner 调用。
- 产品适配器、超时实现、授权、发射逻辑均保持原样；原 `.08s` deadline、`release.wait(3)` 和新 context 的 5s 期限均未调大，未新增 sleep。
- 原来的 7 个 assert 表达式全部保留，包括：runner 恰好一次、结果仅属于旧执行 Scope、新旧 context 身份、共享历史集合、超时批次 observation 仍为 None、新 Scope 不再允许工具。AST 核对记录 `probe-assertion-preservation.json`：**原 7 / 修正 18，missing_original_asserts=[]**。
- 新增：回调进入时未过期、返回时已过期；真实 dispatch 超时且未释放前无结果；新 Scope 先绑定再产出；PRE_EXECUTE 和 RESULT 同属旧 Scope；无 TOOL_ERROR；结果 call_id / evidence_count / hash 有效。

完整修正版 **37 passed / 0.49s**。实际时序为进入回调 → 批次超时返回（85.121ms）→ 新 Scope 绑定（85.188ms）→ 回调产出（85.211ms）→ 旧 Scope 发结果（85.267ms）。

再以 `test_late_repeat.py` 各重复 5 次：无活动 QueryLedger / 有活动 QueryLedger，共 **10 passed / 1.15s**。两者都保留全部归属断言；有账本时另断言成功缓存为空、在途项清空、恰有一条 `late_result_discarded(reason=subscription_inactive)`。晚结果的旧 Scope 可观测事件不等于其被采纳为新批次证据；本次验证了这一区别。

## 四、本片代码及回归判断

### P3b：同源上限与认证路径

- `material_permissions.py:14–28` 定义四项审定本地能力；`episode_factory.py:655–665, 724–730` 在 mandatory 回补之后用同一 capability_tuple 过滤全部 requirements 并生成输出 evidence_types，不能被下限补回禁用能力。
- `research_contract.py:915–921` 对本地合同的能力、含可选项的证据计划及输出生产者做校验；替换与序列化恢复重加外部能力的测试通过。这只是合同校验，**不是崩溃恢复纯度验收**。
- `research_tool_registry.py:999–1029, 1046–1064, 1166–1194` 的收窄副本、菜单和 dispatch 共用能力/IO 判据。unknown / external_or_mixed 即使 cost=local、freshness=stable 也被拒；拒绝先于解析和 runner。
- `episode_tools.py:1460–1465, 1506–1588, 1782–1796, 1928–1940` 在实际装配点认证 runner、要求 memory 身份已解析，受限返回不携带预取或 calc_loader。
- 实际路径已追读：finance_query → `FinanceQuery` 的只读连接（`finance_query.py:2128`）；mainline → `ask_blocks.py:290–365` 的本地只读查询；evidence_lookup → `agent_research.py:1257–1293` 的 KnowledgeAdapter JSON；memory_lookup → user_memory 本地台账读取。
- 本次实跑 `test_e2_local_freeze.py` 的 **current / missing / empty / stale** 四个临时源场景，验证真实 DuckDB 查询、主线、JSON 证据、临时用户判断的内容及来源定位。缺库不补外部源、空/旧数据不冒充当前事实。此文件全部 19 项通过。

### P3c + 返修：绑定时机、授权和历史

- `continuous_turn_adapter.py:539–548` 在升档判定和预检消费 prefetch 前绑定；`agent_episode.py:1161` 在配置快照、prompt、证据播种前绑定。现有 runtime tests 检查外部/未知哨兵不进入模型、账本为空、原 full registry 不变；不兼容受限 registry 失败前不消费其 prefetch。
- `EpisodeScope.for_execution`（`episode_scope.py:257–270`）拒绝不同 task_id、叠加更严 read_scope，并以 dataclass.replace 生成新视图，保留 user_id、sink、调用/派生不匹配/sink失败的累积容器，不篡改旧视图。
- `episode_tool_batch.py:356–371, 389–392, 427–437` 在同一批次锁内绑定并执行；授权拒绝分支读取本次视图的 reason。10 项替换矩阵（菜单先/执行先 × unknown、mixed、不同 capability、删除工具、合同移除能力）均在 parser/runner/dispatch 前拒绝，reason 非空且匹配当前授权。原 batch 同名反例关闭。
- `agent_episode.py:2189–2196` 在实际 downgrade 合同完成后重新绑定 state.episode_scope、state.registry 和 derive_mismatch_sink。独立 6 类 repair 替换及真实 downgrade hook 均通过；原 repair 同名反例关闭，没有带 replay 的持久 dispatch 意图。
- 9 组 ceiling 格、3 个跨 task 拒绝入口、full/local_only 普通本地执行正例、2 个并发批次，以及上述真实晚结果测试通过。修复历史 accumulator/messages/evidence ledger、sink 与诊断集合保留；正例实际 runner 共 4 次，不是全拒绝造成的假绿。

## 五、执行命令、结果与 IO 计数

所有 pytest 都由指定解释器启动。复现命令如下（每条 shell 显式 cd；launcher 内调用 pytest.main，关闭自动插件及缓存）：

```bash
cd /tmp/e2-qc-301dcd9e
QC_LOG_NAME=original-late-trace PYTHONDONTWRITEBYTECODE=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python /tmp/e2-qc-301dcd9e-evidence/run_offline.py -vv -s /tmp/e2-qc-301dcd9e-evidence/test_trace_original_late.py

cd /tmp/e2-qc-301dcd9e
QC_LOG_NAME=independent-v2 PYTHONDONTWRITEBYTECODE=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python /tmp/e2-qc-301dcd9e-evidence/run_offline.py -vv -s /tmp/e2-qc-301dcd9e-evidence/test_independent_scope_v2.py

cd /tmp/e2-qc-301dcd9e
QC_LOG_NAME=late-repeat PYTHONDONTWRITEBYTECODE=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python /tmp/e2-qc-301dcd9e-evidence/run_offline.py -vv -s /tmp/e2-qc-301dcd9e-evidence/test_late_repeat.py

cd /tmp/e2-qc-301dcd9e
QC_LOG_NAME=focused-finish PYTHONDONTWRITEBYTECODE=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python /tmp/e2-qc-301dcd9e-evidence/run_offline.py -vv -s --basetemp=/tmp/e2-qc-301dcd9e-data/focused-finish intelligence/tests/test_e2_local_freeze.py intelligence/tests/test_e2_runtime_ceiling.py

cd /tmp/e2-qc-301dcd9e
QC_LOG_NAME=adjacent-finish PYTHONDONTWRITEBYTECODE=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python /tmp/e2-qc-301dcd9e-evidence/run_offline.py -q --basetemp=/tmp/e2-qc-301dcd9e-data/adjacent-finish intelligence/tests/test_episode_scope.py intelligence/tests/test_episode_tool_batch.py intelligence/tests/test_episode_factory.py
```

本次 stdout/stderr 均重定向为独立日志，真实 `$?` 另存同名 `.exit`，不是用 shell 最后一个 printf 的 0 判定。

| 新日志 | 逐项/summary 已读结果 | 真实 pytest exit | 禁止 IO 尝试 |
|---|---:|---:|---:|
| `original-late-trace.log` | 1 failed，原探针错误重现，未标 xfail | 1 | 0 |
| `independent-v2.log` | 37 passed（36 项行为测试 + 1 项汇总打印） | 0 | 0 |
| `late-repeat.log` | 10 passed（重复/账本变体，不算10个全新缺陷面） | 0 | 0 |
| `focused-finish.log` | 38 passed（P3b 19 + runtime 19） | 0 | 0 |
| `adjacent-finish.log` | 106 passed | 0 | 0 |

- launcher 清除密钥类和 FORESIGHT/SUBCONSCIOUS 环境，HOME/FINANCE/KB/DB/users 定向专属临时目录；审计钩子拦并计数网络、未许可子进程和宿主私有路径读取。focused 仅放行 3 次 git 元数据基础设施子进程，无金融 API/金融模型调用，也无测试 Python 子进程。
- P3b 作者测试的 `fail_external` 由 launcher 自动夹具计数后再抛异常，并于 teardown 断言为零；临时源测试另计 socket/Popen 尝试，均为零，防止异常被应用吞后造成假绿。
- 独立拒绝矩阵中 parser、runner、forbidden_runner 及 dispatch intent 计数均为零；2 个直接 dispatch 拒绝、3 个跨任务拒绝、6 个 repair 拒绝亦断言未执行/派发。late/普通本地 runner 是许可的临时正例，不算禁止 IO。
- 上述为本次选择路径的离线计数证据，**不是恶意 Python 强隔离证明**。未跑全仓，也未跑金融模型/正式原题对照。

## 六、证据位置与未覆盖边界

全部证据保留在 **`/tmp/e2-qc-301dcd9e-evidence/`**：

- 原件：`run_offline.py`、`test_independent_scope.py`、`independent.log`、`focused.log`、`adjacent.log`、三份应用 diff 及原 `*-io.json`。
- 新件：原针跟踪脚本/日志/JSON、修正版及修正 diff、断言保留 AST 收据、重复脚本/日志、11 份 `corrected-late-trace-*.json`、新 focused/adjacent 日志、各 `.exit` / `*-io.json`、git 结束状态。
- `review-progress-before-final.md` 保留最终覆写前的进行中状态；`sha256-manifest.json` 为证据哈希清单。
- 临时数据在 `/tmp/e2-qc-301dcd9e-data/`；**本次未清理任何证据或数据**，便于宿主归档。仅此专属 data 可按用户规则后续清理。

以下严格范围外，**未验收且不得借本报告冒充完成**：controller 早读；普通上下文及全部四组九类输入注入来源过滤；预取前歧义/基底不可恢复澄清；可信逐轴继承；registry_factory 内部已发生的 IO；压缩/崩溃恢复/子研究；确定性旁路；local_only 原题号槽；P4–P7、逐题交付、纯度和材料锚点。内存 repair 不等于崩溃恢复，合同 from_dict 校验也不等于恢复链安全。io_effect 只在可信装配声明和已测实际路径的意义下成立。

**最终短结论：P3b 通过；P3c + 返修通过，均只限本片。原 36绿1红中的红针是二次 runner 适配器触发过期检查的探针错误；保留原失败并完成不弱化断言的修正验证，无应用修改。**
