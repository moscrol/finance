# 研究进化 06 · 第二轮返修复审（第三轮 QC）

日期：2026-09-14。候选：`0c275716`；代码提交 `089526ab`，后续仅文档变更。
审查树：`/private/tmp/re06-qc-0c275716`，分支 `docs/qc-re06-0c275716`。

## 结论：退修，暂不放行

原测试可以复绿，但不能据此关闭 Q2/Q3/Q7/Q8/Q9 全部边界。独立的五条正确合同探针在原候选上 **5 failed**。两个 P1 是复核闭环时序问题；另三个 P2 是来源、原件版本与异常清理问题。未改候选代码、未合并、未部署。

### T1 · P1：终态早于第二个 HTTP 请求，合法复核无法登记/收尾

定位：`intelligence/services/research_evolution/facade.py:899–928`；调用端 `intelligence/webapp/src/App.tsx:798–823`。

- 页面先 `POST messages`，收到新 run_id 后才 `POST actions(link_run)`；服务端在消息响应之前已经提交执行器。
- Q3 新闸仅在 run 未终态时允许创建 run_links；终态无登记一律 400。若模型立即失败、任务很快结束或浏览器第二个请求稍晚，观察器先查到“无关联”返回，后来的登记也被拒。
- 真 API + 确定性快速失败执行器复现：messages **202** → run **failed** → link_run **400 run_binding_mismatch** → 项仍 **rejudgment_requested**。不是缺新判断造成的拒绝：失败本应退回 open。
- 现有 `test_q2_terminal_auto_close_without_second_link` 用 `turn_gate.clear()` 暂停执行器，恰好排除了这条真实允许的顺序。

建议：在消息接受侧建立可信的 request→run 关联，再启动执行器；若采用可恢复分阶段提交，终态先到也必须可以用可信关联补偿。不要删除关联闸退回“同会话就行”，也不要靠 UI 加延时赌先后。至少覆盖登记前完成、登记前失败、登记期间终态三种交错。

### T2 · P1：关联缺少复核请求身份，旧 run 的迟到回调误收尾新请求

定位：`facade.py:903–915`（run_links 仅 item/run/session/time）；`facade.py:1008–1025`（仅查项当前为 rejudgment_requested）；同样影响 `_upgrade_registered_link`。

复现（真实动作 API + 注入实际 facade 回调的 ObservingRunStore）：

1. 请求 A 复核项 I，运行中登记 run A。
2. 调合法 `cancel_rejudge` 恢复 open；随后对同一 I 发起请求 B。
3. run A 迟到失败，观察器自动折回。
4. **请求 B 被退回 open，management_revision 增加**，last_failure 写成 A 的失败。

01 已有 `management.rejudgment.request_event_id`，但 06 登记、查找、折回均未绑定/比较这个值。它证明的是“曾关联过这个项”，不是“属于当前这一轮请求”。无需伪造 run、无需把无关旧 run 重新登记；合法取消/重试加异步迟到即可触发。因而 handoff 的“只剩恶意客户端主动两步操作、诚实性不受影响”不足以描述边界。

建议：关联行携带不可变 `request_event_id`（或等价 attempt identity）及必要版本；观察器/手动恢复/幂等升级统一核验当前请求身份。新判断也须匹配本轮成果边界。旧请求结果只留旧请求审计，不迁移新请求。不需要先引入密码学签名才能修掉这条缺陷。

### T3 · P2：新会话首轮选任务仍丢 source_refs / scope

定位：`intelligence/webapp/src/App.tsx:793–798`；`facade.py:1233–1235`；`intelligence/api/app.py:1509–1514`。

Q7 加 click_payload 字段只解决“已有 origin run_id”的分支。没有已完成轮次时服务端不填 run_id，App 把整条 continuation 置 undefined，只发题目文本；消息落盘 `continuation=None`，任务 ID、对象版本和 source_refs 都不在该消息上。

探针从有旧判断/任务、但尚无完成 run 的会话开始，按 App 的真实 payload 分支发 messages：202、可完成，但结构化来源为空。现有 Q7 回归特意先完成一轮才选择任务，未覆盖首轮。此探针是 API + 与 App 一致的载荷分支，不冒充浏览器 E2E。

建议：区分“已有 run 的延续坐标”与“首次任务启动上下文”，后者不要求伪造 origin run，仍需经过 owner/session/task 范围核验并随消息持久化。增加首轮和已有轮次两条端到端断言。

### T4 · P2：“无 id 读最新总结”实际读字典序最大的内容哈希

定位：`facade.py:1469–1472`；`store.py:212` 附近的 `sorted(folder.glob("*.json"))`。

`list_immutable` 按文件名排序，`summaries[-1]` 不代表时间最新或 supersedes 链头。内容寻址 ID 没有时间顺序。探针先发布旧 `sum-ffff`，再发布 `sum-0000`（generated_at 更新、supersedes 指向旧件）；无 id 请求 **200 却返回旧 sum-ffff**。

显式 summary_id 读取和前端本轮兜底已修好，缺陷仅在新加的无 id fallback。但它能把过期结论当最新原件给调用者，不是显示小瑕疵。

建议：明确 pilot/protocol 范围后按版本链选择，遇多链/歧义要求显式 id；或取消无 id 的“最新”承诺。不能把哈希字典序当版本顺序。单个 owner 也会有同一试点的多版总结。

### T5 · P2：锁文件打开异常后，已取得的进程锁永久泄漏

定位：`intelligence/services/research_evolution/store.py:163–166,181–184`。

`lock.acquire()` 成功后先执行 `os.open()`，才进入负责 `lock.release()` 的 try/finally。权限变化、文件描述符耗尽等使 os.open 抛错时，进程锁不释放。观察器会吞成 stderr，但后续有界测量永远超时、普通 `transaction()` 则会一直等待，恢复文件条件也救不回，需重启进程。

故障注入只让一次锁文件 open 抛 PermissionError，恢复真实 os.open 后第二次 try_transaction 仍 StoreLockTimeout。不是磁盘错误本身阻塞，而是异常清理路径缺失。

建议：acquire 成功立刻进入外层 try/finally；fd 的 open/close 与 flock 的解锁各有自己的取得标志。补 open 失败后可再次取得事务的回归，不仅测正常持锁超时。

## 已认可的证据及其边界

| 检查 | 本轮结果 | 口径 |
|---|---|---|
| 候选树与提交差异 | 干净，089526ab→0c275716 仅文档 | 默认目录是另一棵脏树，本轮完全未动 |
| 候选已有研究进化后端 + 上轮独立探针 | **98 passed** | `test_research_evolution*.py` + 上轮 `test_review_contracts.py`；非全仓 |
| 本轮新增边界探针 | **5 failed** | 正确合同断言，见本目录 `test_review_round3.py` 与 `probes.txt` |
| 前端 lint / typecheck | 通过 | 本轮独立运行 |
| 前端 vitest | **90 passed** | 本轮独立运行；其中面板 14 |
| 真浏览器绑定 E2E | **1 passed，desktop** | 独立端口 18791/18794；真实 API/临时 DuckDB/临时用户态；输入 synthetic，不代表真实市场研究质量 |
| 定向 Ruff | 通过 | 本轮后端改动路径、research_evolution 包、本轮探针；非全仓 |
| 用户提供的全仓收据 | 核对 JSON 为 **10022 passed / 0 failed / 77 skipped**，revision=089526ab，dirty=false | `20260913T163415Z-089526ab.json`；交接明确命令含 `--ignore=test_codex_sandbox.py`；本轮未重跑全仓，不改写成我的全量结论 |
| 其余 build / 全套 E2E / registry | 本轮未重跑 | 既已有阻断，不以历史绿灯替代最终组合门禁 |

上轮探针中 `test_registered_pending_run_terminal_stays_unreconciled` 是诊断断言，手动构建的观察器没有注入 maintenance_folder，预期仍停在 requested。因此“旧探针 10/10”本身不是 Q2 自动收尾的正向证明；本轮认可仓内 Q2 正向测试的有限时序，不扩大它的覆盖。

## 重放

从候选仓根执行（Python 必须使用主树 .venv-workbench）：

```bash
PYTHONPATH="$PWD" /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -s docs/verification/re06-0c275716/test_review_round3.py
```

运行时仅替换执行器速度/终态与一次 os.open 失败；所有用户数据和锁均为 pytest 临时目录。预期原候选 5 failed，返修后应 5 passed；不得删断言、添加 gate 抹掉交错或降格成 xfail。

## 决策与后续

- 保留 Q1 真绑定、Q4 结构化作答和已有幂等修法，不要求推翻本轮全部工作。
- 否决“全测试绿即放行”：新增正确合同已证伪边界，不是基线环境失败。
- 否决“先上来源签名才能修”：request_event_id 与服务端执行前登记先能消除本轮两条 P1，签名是另一层信任/威胁模型问题。
- 下一步交执行者按 T1–T5 返修，补“先终态 / 迟到旧回调 / 首轮消息 / 多版原件 / 锁初始化失败”的测试，再检查用户可见恢复入口和最终组合门禁。
- 工具沉淀：五条探针落入版本化审查证据，未只留 /tmp 脚本。通用层保留身份/时序审查方法，不造统一静态 lint：哪些回调可作用到哪一轮请求需要领域合同。未修改已知脏的 harness-reference。
