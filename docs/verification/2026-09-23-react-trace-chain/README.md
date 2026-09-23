# #81 / #832 前向合流验收

## 固定身份与范围

- 候选：`d1b30e1a068ccd0559f091f3c664ca2ca82f1e7c`，已普通推送至唯一产品载体 PR #832（`fix/react-trace-qc-0921`）。
- 双父：旧头 `0888ea98477bf07292f41336538d7b3b904b1248` + 本次 main `626d8a508c1c`（完整身份见 `git show --no-patch --format=raw d1b30e1a0`）。未合回 main。
- 固定检出：`/Users/a77/fwp-wt-react-trace-chain-0923`。本验收文档在独立 `docs/react-trace-chain-0923`；不得把候选收据移签文档头。
- 证据根：`/Users/a77/.finance-runtime/reviews/react-trace-chain-20260923/`。
- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
- #841 仍归 #68；本轮无真实模型请求、无生产写入、无部署、无新增独立审查预算。

## 六项覆盖对照

行号均指固定候选 `d1b30e1a0`，不是主干的漂移行号。#863 的落地合并为 `8e79893729da`；中间来源提交只说明改动沿革，不移签其测试。

| 项 | #863 落地提交 / 覆盖情况 | 本分支文件:行 / 增量处理 |
|---|---|---|
| 1. E 引用序号不作数值事实 | `8e79893729da` 含 `0b688c368` 的 `strip_evidence_ordinals` 与证据数字过滤 | `intelligence/services/episode_protocol.py:750`、`episode_semantic_verifier.py:4909,5451`；实现零增量。冲突采用主干完整的标题、表格、比较符阈值检查，未回退成旧触发词规则；原 numeric/protocol 测试仍在。 |
| 2. finance_query 安全错误反馈 | `8e79893729da` 含 `7edfe24e7` 的标识符白名单与分类诊断 | `intelligence/services/finance_query.py:1832,1838`、`episode_tools.py:1999`；实现零增量，去掉纯格式差异。原测试直接读取 runner 的 observation 已过时，改查结构化 diagnostics，仍禁止任意散文/路径/数字泄漏。 |
| 3. 原 Episode 收到反馈后继续 | `8e79893729da` 含诊断通道与原循环交付，不新增重试或工具额度 | `intelligence/tests/test_finance_query_repair_feedback.py:169`、`test_agent_episode_progress.py:385`；产品零增量，保留真实 parser/loop、先有证据后缺历史参数、取消和工具额度回归。 |
| 4. 冻结 Mapping 可记进展 | `8e79893729da` 含 `0b688c368` 的 JSON Mapping 投影 | `intelligence/runtime/research_progress.py:73`；实现零增量，与固定 main 字节一致。保留主干四状态测试和原分支未知对象拒绝断言。 |
| 5. 历史分页绝对行身份 | #863 已有投影与窗口绑定，但每页 enumerate 从零开始，无 offset/next_offset | `intelligence/services/historical_research/episode.py:205,364,771`；仍增量：绝对 sample、分页游标、末页截断标记。保留主干“保持所选窗口”及先构造投影后登记成功的次序，新增投影失败不得记成功测试。 |
| 6. 删条件后的悬空计数 | #863 有数字删句，但无该局部清理函数及真实出口接线 | `intelligence/services/episode_semantic_verifier.py:3720,5697`；仍增量：只清本轮确删且无幸存定义的计数，保留其他观察、列表及换行，不放宽数字判据。 |

最终产品差异仅 `episode_semantic_verifier.py` 与 `historical_research/episode.py`。`research_progress.py`、`episode_protocol.py`、`episode_tools.py`、`finance_query.py` 对固定 main 字节一致。原工单“14 个文件”是合并前差集，不能作为本次增量分母。

## 六处冲突处理

- `docs/agent-product-door.md`：并存本分支两段与主干恢复/发布/RAG 边界，不删任何主干说明。
- `episode_semantic_verifier.py`：数字候选处理保留主干；局部清理函数及修复出口保留 #832。
- `finance_query.py`：语义相同，采用主干字节，消除零增量。
- `historical_research/episode.py`：合并绝对分页与固定窗口；`_result(..., offset=offset)` 成功后才 append history_results。
- `test_agent_episode_progress.py`：保留双方的结构化拒参和真实历史缺参测试。
- `test_research_progress.py`：保留主干四种失败状态和分支精确 TypeError 断言。

## 验证台账

- 首轮作者定向：371P/3F；三红是旧测试仍读 observation，主干已将控制反馈分离到 diagnostics。失败收据 `20260923T124921Z-0888ea98-b87b6620571d.json` 留在全机收据目录，脏树迭代读数不当准入。
- 修正测试消费者并新增分页失败回归后：1797P/8S，涵盖原七文件、`tests/test_history_*`、`tests/test_research_*`、`intelligence/tests/test_episode_*` 等。收据 `20260923T125235Z-0888ea98-2436b27ed768.json` 同为迭代证据。
- 九组内存撤保护全部被实际断言捕获，基线 37P，零 collection error；源码未写。复用既有 `docs/verification/2026-09-21-react-trace-qc/mutate_seams_v2.py.txt`，输出 `mutations/summary.json`。真实出口 `repair_wiring` 的红证人是 `test_repair_is_delivered_through_semantic_verifier_and_records_real_deletion`。
- 固定候选全仓 Ruff 通过，提交钩子通过；`git merge-tree --write-tree --name-only 626d8a508 d1b30e1a0` exit 0。
- 本次前向比旧 main `f2c3e9e1a` 有 250 个非 docs/非 Markdown 路径漂移；不能沿用 a140 的旧收据。
- Python 全量：运行中，`python-gate.log` 与 `receipts/gate-RaovaPhZ/pytest.json`；未出完整收据前不算通过。
- 前端首轮：install/lint/typecheck/120 单测/build 均通过；E2E 31P/3F/2S，`frontend/frontend.json` 首尾同 SHA 且干净，整叶 exit 1。三红在刷新后 5 秒可见等待（tablet/mobile `workbench.spec.ts:232`、tablet `:310`）；失败快照里已有消息。负载从开跑 25 升至 290，但未做低负载对照，不能直接归为设施噪声。原件 `frontend/test-results/`（含 trace.zip）已外部保全。端口 19381/19384，未碰 8792。
- 前端第二轮：同头、同命令和超时，install/lint/typecheck/120 单测/build 通过，E2E 32P/2F/2S（9.5 分钟），tablet/mobile 刷新恢复仍在 `workbench.spec.ts:232` 超时；`frontend-retry/frontend.json` exit 1，首尾同 SHA/clean，现场另存 `frontend-retry/test-results/`。不再重跑取绿、不改测试阈值。工程四叶未通过，#832 保持 WIP。
- registry 五项：固定候选均 exit 0，首尾同 SHA/clean，`registry.json`；crosswalk 保留既有反向 98 行 warning，不是全方向零告警。

## 旧独立审查与剩余边界

工单和 #832 旧正文遗漏了 09-22 后续终稿：`/Users/a77/.finance-runtime/reviews/react-trace-k3-20260922/STATUS.md` 及 `k3-session-03-report/work/REPORT.md`。它对旧 `a14005fc9` 给 Spec/Quality PASS_WITH_LIMITS，48 自造探针 + 356 作者相关测试；单审查者三会话，不是双盲，也没有全量/真实金融验收。原 09-21 的 600 秒超时记录仍真，后续终稿不抹掉它。本轮不重跑旧审查、不将其移签 d1b30e1a0。

新候选登记 #75；自然金融按 #76 另行授权，旧 not_passed 不变。特别是 225/25、候选数值显式引用与判官消费不能由离线绿代替。

`fix/react-trace-runtime-0921@dda5895aa` 是 #832 原头的祖先（`merge-base --is-ancestor` exit 0，`git cherry` 空），没有待补推的独有提交。但其现有工作树有两项他人删除（`.code-review-graph/.gitignore`、`wiki-steering.json`），本轮不强删工作树或分支；不再开重复占位 PR。
