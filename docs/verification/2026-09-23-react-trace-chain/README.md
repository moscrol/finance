# #81 / #832 前向合流验收

最新结论（09-23 续轮）：固定候选的工程四叶保持 `ENGINEERING_PASS_WITH_E2E_TIMING_LIMITS`；用户「推进」后启动的一批 #75 独审为 `BLOCKED_HARNESS_AND_INCOMPLETE_REPORT`。共 49 次 GLM 请求，无重试；沙箱阻断与终稿结构错误使独审不能签字，未启动第二轴或自动加额。工程原两轮 E2E 红仍保留，不作稳定性认证；金融质量归 #76，#832 保持 WIP。续轮收口回读远端 main 为 `c9dd71dfd678`，本页工程收据只绑定候选及固定基线 `626d8a508c1c`，不证明与后来 main 的集成。

## 固定身份与范围

- 候选：`d1b30e1a068ccd0559f091f3c664ca2ca82f1e7c`，已普通推送至唯一产品载体 PR #832（`fix/react-trace-qc-0921`）。
- 双父：旧头 `0888ea98477bf07292f41336538d7b3b904b1248` + 本次 main `626d8a508c1c`（完整身份见 `git show --no-patch --format=raw d1b30e1a0`）。未合回 main。
- 固定检出：`/Users/a77/fwp-wt-react-trace-chain-0923`。本验收文档在独立 `docs/react-trace-chain-0923`，文档 PR #892；不得把候选收据移签文档头。
- 证据根：`/Users/a77/.finance-runtime/reviews/react-trace-chain-20260923/`。
- 解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
- #841 仍归 #68；工程收口轮没有真实模型请求。随后 #75 续轮使用既有 GLM 路由，边界见下节；始终无产品修改、生产写入、合入或部署。

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
- Python 全量：14710P/0F/0E/85S/2X，exit 0，5220.45 秒。原件 `python-gate.log` 与 `receipts/gate-RaovaPhZ/pytest.json`；仓内副本 `receipts/python.json`、`logs/python-gate.log.txt`。collected=14797 与读数对平，无 ignore/deselect/-k/-m/maxfail/last-failed 收窄，dirty=false、依赖门禁未绕过；`check_test_receipt.py ... --expect-revision d1b30e1a0 --require-full-scope` 与 `main_gate_receipt.py ... --pytest-exit 0` 均 exit 0。成功后门禁自动清理自有 basetemp。
- 前端首轮：install/lint/typecheck/120 单测/build 均通过；E2E 31P/3F/2S，`frontend/frontend.json` 首尾同 SHA 且干净，整叶 exit 1。三红在刷新后 5 秒可见等待（tablet/mobile `workbench.spec.ts:232`、tablet `:310`）；失败快照里已有消息。负载从开跑 25 升至 290，但未做低负载对照，不能直接归为设施噪声。原件 `frontend/test-results/`（含 trace.zip）已外部保全。端口 19381/19384，未碰 8792。
- 前端第二轮：同头、同命令和超时，install/lint/typecheck/120 单测/build 通过，E2E 32P/2F/2S（9.5 分钟），tablet/mobile 刷新恢复仍在 `workbench.spec.ts:232` 超时；`frontend-retry/frontend.json` exit 1，首尾同 SHA/clean，现场另存 `frontend-retry/test-results/`。该轮结束时停止无对照复跑，不改测试阈值；当时工程四叶未通过。后续获用户「继续推进」指示，补下节固定 main 对照。#832 仍因独立验收未完成保持 WIP。
- registry 五项：固定候选均 exit 0，首尾同 SHA/clean，`registry.json`；crosswalk 保留既有反向 98 行 warning，不是全方向零告警。

## E2E 失败分诊与封存

第二轮 `receipts/e2e-triage.json` 从 trace.zip 逐事件解析，带原件哈希及毫秒时序。tablet 的刷新后 `/api/workbench/bootstrap` 返回 200，但耗时 5418 ms；mobile 的同一请求在断言失败时仍未完成（trace 的 status=-1 不是 HTTP 错误码）。两例断言超时均为原 5000 ms，刷新前最后一次 messages 接口均返回 8 条。第二轮等待耗在初始化阶段，不能仅凭此定为数据丢失，也不能定为设施噪声。

代码定位：`intelligence/api/app.py:3630` 的 bootstrap 会扫描 runs/产物并投影最近运行；`intelligence/webapp/src/App.tsx:525` 等 bootstrap，再并行取会话与各初始化面；`:227` 的 `loadConversationData` 又等所有 run bundles 后才 `setMessages`。故初始化或详情投影迟到都能造成「消息未在 5 秒内显示」，不能直接判消息丢失。本轮只读定位，未改产品、未拆并行加载、未加超时。完整 trace 与快照仍在外部 `frontend*/test-results/`，不把二进制 ZIP 提交到仓库。

同目录 `receipts/` 收录原样复制的迭代红绿、最终 Python、两轮前端、registry 和变异摘要；前端各六步日志与所属 frontend.json 同目录，12 份日志的长度/哈希均与收据一致。`logs/` 收录 Python 门禁和完整性校验日志；`MANIFEST.json` 给所选封存件逐文件哈希。`candidate-identity.json` 再验固定身份、零增量文件和 merge-tree。收据有效性、测试通过与独立质量验收是三个独立判定。

全量运行期间磁盘一度约 2.8 GB，停止检查开始时已恢复约 21 GB，未发中断信号；不能把资源波动直接当作 E2E 根因。测试进程与 19381/19384 测试服务已结束。

## 串行对照与最新工程收据

用户要求「继续推进」后，冻结候选与固定 main 均未移动。用同一 `run_frontend_gate.py`（SHA256 见对照摘要）、固定解释器、19381/19384 端口，main 先跑、候选后跑，每边一次完整六步。没有 -g、重试、跳过新增测试或扩大原 5000 ms 断言。

| 对象 | 完整前端门禁 | 单测 | E2E | E2E 耗时 |
|---|---|---|---|---|
| main `626d8a508c1c` | 六步 exit 0，同 SHA/clean | 120P | 34P/2S | 91.89 秒 |
| #832 `d1b30e1a068c` | 六步 exit 0，同 SHA/clean | 120P | 34P/2S | 79.06 秒 |

两次均在 10 核共享宿主上，每 5 秒记录负载和空闲磁盘：main 的一分钟负载范围 10.26–13.59，候选 8.94–13.79；可用磁盘最低约 21.57 GiB。区间重叠、串行且两次前端/API/门禁脚本源码字节一致，但 **n=1/侧、非随机、非隔离资源**，不能据耗时差声称性能改善，也不能据本次通过认定旧失败由负载造成。共同初始化链的尾延迟仍是残余风险。

- 原件：证据根 `frontend-control-continue/`；仓内原样封存 `receipts/frontend-control/`，每轮 receipt 与六步日志保持相对路径。
- `pair.json` 记录命令/身份/退出码；`*-resources.jsonl` 记录共享宿主采样；`check_control.py.txt` 校验两个收据的完整性、固定 SHA、干净树、原日志哈希与范围，输出 `control-summary.json`。解析 Vitest 彩色摘要前只在内存去 ANSI 控制序列，原日志不改。
- `python-recheck.log.txt` 对原全量 14710P 收据再核 revision、解释器、依赖指纹和完整收集面，exit 0；产品头不变，未重跑或移签 Python。原 Ruff / registry 仍绑定同候选。
- `MANIFEST.json` 保留原 23 件，新增对照与复核证据；旧 E2E 红不覆盖。测试进程及 19381/19384 服务已退出。

据此工程收据层齐绿；独立 QC、自然金融及合入授权仍是另外三道门。理由与被否方案见 `docs/handoffs/2026-09-23-react-trace-e2e-control.md`。

## #75 独审续轮与工具诊断

用户「推进」按本候选一批有限 #75 解读，未扩至 #76、合并或部署。复用既有 GLM 隔离运行器，Spec/Quality 两轴互不可读、每轴 explore/execute/report 独立会话；串行、整批最多 152 请求、每阶段 24 请求/600 秒、单请求 120 秒、重试 0。实际执行止于 Spec execute，未用完预算不等于可以自动续跑。

| 阶段 | 请求 | 实际结果 |
|---|---|---|
| Spec gateway | 4 | 小请求及真实读写往返 PASS，非 QC |
| Spec explore | 22 | 4 个自造探针文件，阶段交付完成；C1-C4 未深验 |
| Spec execute | 23 | 第 23 发为预留终稿；JSON 尾部多一个引号，结构校验失败，EXECUTE.md 未落盘 |
| Spec report / Quality 全部阶段 | 0 | NOT_STARTED，批次已停止 |

- 49 请求全部完成，账本与派发数一致，无 HTTP 失败、自动重试或墙钟超时。执行会话达到工具关闭/预留终稿阶段，不是 24 发硬帽越界，也不是供应商不可用。
- 原始工具日志显示 C5 纯函数 5P、registry 3F，后者都停在 SQLite 夹具建库；C6 与七个作者回归文件未运行。5P/3F 使用额外 `-c/--confcutdir`，不是原定入口的完整独审收据。
- `execute/commands/005-bash` 用 `; echo` 包装正控，工具整体 exit 0、输出中的子脚本 EXIT=1。报告的「真实 exit 1」不得解读为工具返回 1；pytest 包装也有同类问题。不能只采信摘要或包装退出码。
- 初版离线预检引用旧任务的缺失文件而失败，保留两轴 `sandbox-preflight-04` 原件；仅换成候选中真实存在的禁止读取文件，`-05` 才通过。这个预检仍漏掉真实 pytest/SQLite 操作所需的父目录元信息权限。
- 停批后零模型诊断：独立复制规则，仅允许批根与 candidate 父目录的 metadata。对照前 pytest exit 2、SQLite exit 1；后两项控制 2P、SQLite exit 0、必红对照真实 exit 1，越界读写/符号链接/外网/8792 仍拒绝。诊断 v1 的对照符号链接放在收集根造成额外 exit 4，也原样保留；v2 将它放入 tmp，仍实测拒绝越界。
- 原 3 个 registry 探针逐字节复制，在修补后的工具中由宿主执行 3P/exit 0，明确归 `HOST_TOOLING_DIAGNOSIS_NOT_REVIEWER_EXECUTION`。不替换原 3F，不补签模型执行或独立结论。原运行器、探针和执行收据未原地改写。
- 自造探针借用了作者夹具；C6 幸存定义测试含条件式断言，单看绿数不能证明该分支执行。这些限制须留给后续审查者，不冒充完整独立覆盖。

原件根 `/Users/a77/.finance-runtime/reviews/pr832-glm-qc-20260923-2255/`；仓内 `receipts/independent-qc/SUMMARY.json` 和 `MANIFEST.json` 封存 371 件（字节与哈希逐项见清单），包括完整工具请求、输出、退出码、原失败、探针与运行配方。流式 events 原件留外部，已按 execution.json 复核 185 个阶段产物哈希。原 44 件工程证据不变，工程 MANIFEST 另锚定独审清单。原日志仅改归档扩展名为 `.log.txt`，临时目录中的诊断源码映射到 `diagnostic-probes/`，不改字节。完整暂存差异 `git diff --cached --check` exit 2，60 处空白告警均在 9 份冻结原件；不修原件或加豁免来刷绿，手写文档检查通过。

下一轮需先落实退出码/交付结构的机械校验和真实执行准入，再单独授权新审查；不以宿主 3P、旧 a140 终稿或原工程全量替代独审。详见 `docs/handoffs/2026-09-23-react-trace-qc-blocked.md`。

## 旧独立审查与剩余边界

工单和 #832 旧正文遗漏了 09-22 后续终稿：`/Users/a77/.finance-runtime/reviews/react-trace-k3-20260922/STATUS.md` 及 `k3-session-03-report/work/REPORT.md`。它对旧 `a14005fc9` 给 Spec/Quality PASS_WITH_LIMITS，48 自造探针 + 356 作者相关测试；单审查者三会话，不是双盲，也没有全量/真实金融验收。原 09-21 的 600 秒超时记录仍真，后续终稿不抹掉它。本轮不重跑旧审查、不将其移签 d1b30e1a0。

新候选 #75 本批已执行并阻塞，不自动续预算；自然金融按 #76 另行授权，旧 not_passed 不变。特别是 225/25、候选数值显式引用与判官消费不能由离线绿代替。

`fix/react-trace-runtime-0921@dda5895aa` 是 #832 原头的祖先（`merge-base --is-ancestor` exit 0，`git cherry` 空），没有待补推的独有提交。但其现有工作树有两项他人删除（`.code-review-graph/.gitignore`、`wiki-steering.json`），本轮不强删工作树或分支；不再开重复占位 PR。
