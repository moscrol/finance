# 研究进化 06 · 第四轮返修复审（第五轮 QC）

日期：2026-09-14。候选 `99d6e193`，代码 `ecd90a3c`；比较基线 `b481804c`。
独立审查树 `/private/tmp/re06-qc-ecd90a3c`，分支 `docs/qc-re06-ecd90a3c`。

## 结论：退修，暂不放行（4 P1）

上轮及既有定向套件 **119 passed**（原 110 + 仓内新增 5 + U 四针 4）；U 四针另独立重跑 **4 passed**。但本轮新增四条正确合同探针最终版连续两次 **4 failed**。不是环境错误：均观测到实际错误登记或状态迁移。

未改应用代码、未合并、未部署；执行方工作树仍干净。审查不是要求推翻终态重放或恢复功能，而是要求请求身份在所有登记路径与成果读取中可验证，不能把“现在的身份”补贴到旧输入上。

## V1 · P1：终态补偿仅认同会话消息存在，旧普通聊天也能迁移新请求

定位：`intelligence/services/research_evolution/facade.py:1080–1105`（调用 `968–978`）。

`_compensate_terminal_link` 验的是 user message.role/run_id，而不是消息对应的维护请求；取当前 `request_event_id` 直接登记。最新管理修订只证明调用者看过当前状态，不证明旧 run 与该请求有因果关系。

真实 API 复现：先在会话发“请解释市盈率是什么。”，快速失败；随后才绑定判断、发起复核，用最新版本显式 `link_run` 指向那个旧普通聊天 run。

- 返回 **200 accepted / rejudgment_failed**；
- 新项 `rejudgment_requested → open`，revision **1→2**；
- `run_links` 把旧聊天登记成当前请求的执行。

同一探针在修前 `b481804c` **通过**（拒收），本候选 **失败**：这是本轮明确引入的回退。没有伪造 RunStore 行，旧 run 和用户消息均来自真实 messages API。

**建议**：补偿只能重建已有可信启动身份（item + request 实例 + run），不能把“有同会话用户消息”当充分条件。时钟不可比较时应以稳定请求坐标/服务端接受记录代替，不能删除因果校验。保留合法快速终态、改写文案的恢复，但改写文案也须带结构化请求身份。

探针：`test_old_ordinary_message_cannot_be_compensated_into_new_request`。

## V2 · P1：启动文本不是请求实例身份，A 的迟到消息会自动认领 B

定位：`facade.py:1270–1292`、`_continuation_payload:2010–2027`、`_rejudge_prompt:2035–2044`。

接受侧通过 item 坐标或当前请求的 full_prompt/label 匹配后，直接取当前 request_event_id。输入并没有携带供对照的请求代际。对同一项 A→取消→B，item_version 可以不变，`full_prompt` 也逐字相同；按钮 label 更不区分请求。只验证“这个项当前有一代待复核”不是验证“这个输入就是该代”。

真实 API 复现：保存 A 的 rejudge 响应；取消 A 并发起 B；模拟另一标签页迟到发送 A 响应中的 full_prompt（首轮无 origin run，与 App 同形）；执行器立即失败。

- 实测 A/B full_prompt **相等**；
- A 的迟到消息被登记成 B 的 request_event_id；
- B 被自动折回 `open`，revision **3→4**，无需再调用显式 link_run。

该缺陷修前也存在；本轮的文本匹配只缩小普通消息误绑面，未修好代际身份。不能称为新增回退，但 U1/T2 尚不能整体关闭。带 continuation 的分支同样只查 item 坐标，未验证请求代际；本探针实际覆盖首轮纯文本分支，不冒充已测全部 continuation 路径。

**建议**：rejudge 响应应带服务端生成的唯一请求坐标，messages 接受时回查 owner/conversation/item/request 当前代。首轮消息也要能携带，不应依赖已完成 origin run 才能表达请求身份。多代或不唯一的 legacy 文本不自动绑定。

**测试合同纠偏**：上轮 U3 setup 用裸“继续核查”后等待 open，只是测试前置，不是产品必须支持“通用文案=请求身份”的约束。可以把 setup 改为真实请求坐标，同时保留跨会话拒绝、同会话重放、快速终态可收尾的核心断言；不得为照顾 setup 增加不可靠授权/身份捷径。

探针：`test_cancelled_request_launch_text_cannot_claim_replacement_generation`。

## V3 · P1：attempts=1 只说明本项首次，排除不了同会话其他项的成果

定位：`facade.py:987–1009`。

U4 新闸只在“本项 attempts>1 或 last_failure”时阻止自动选判断；首轮仍按 session+时间窗挑最后一行。局部次数不是成果归属证明。

复现用两条**不同原判断**、真实绑定和真实 01 项，不 mock `_current_items`：A/B 同会话各首次复核，分别登记 run A/run B；现役 `judgments.record_judgment` 写下 A 的成果；A 完成，B 无任何自身成果也完成。

- B 的 attempts=1、last_failure=None；
- B **被关闭为 closed**，revision **1→2**；
- closure.linked_judgment_ref 指向 A 的新判断。

该形状修前也失败；本轮关闭了“同一项先前代际”那条 U4，却未隔离同容器其他对象。用现役 writer 模拟 A 的成果，不是声称测试过真实模型质量或完整模型写入流程。

**建议**：自动成果选择须有可核验的 run/request/object 归属。writer 尚不支持时，首次也不自动认领不明成果；可以保留显式确认，但要提供实际 Workbench 恢复入口，不能只在错误 hint 要 `new_judgment_ref`。本轮查到该字段只有后端动作模型，App 的 link_run 载荷未传，维护面板无判断选择；这点是修法必须收口的产品依赖，不额外冒充已测 UI 新缺陷。

探针：`test_first_attempt_cannot_consume_other_items_judgment`。

## V4 · P1：旧 run 尚运行时可重新登记成当前代，终态旧代闸被绕过

定位：`facade.py:924–945`，旧代拒收仅在后面的 `950–962`。

运行中分支只查当前代有无同 run 关联，没有则创建；“是否已属于上一代”的检查只在终态分支。于是相同旧 run 可以先登记到 B，之后观察器按 B 的有效登记折回。

真实 messages + actions API 复现：请求 A 的 run 暂停在运行中并已登记；cancel A→request B；用最新 B 版本、另一个幂等键把仍在跑的 run A 再 link 一次；释放执行器让 A 失败。

- 重登记 **200 registered / link_created=true**；
- A 失败后 B `rejudgment_requested → open`，revision **3→4**。

为排除“RunStore 旁路造 run”的争议，最终探针的 run 也来自真实 messages API。闸门只在此测试控制 A 晚失败的交错；V1/V2 快速终态探针不加延迟。修前同样失败，属于 T2 剩余边界，不归为本轮新增回退。

**建议**：所有登记路径在写入前统一校验既有 run 的请求归属，不论 running/terminal；已有 A 归属不能因 B 当前仍 pending 就转挂 B。尽可能共用一个精确身份验证器，而不是在三条登记入口各补一组局部条件。

探针：`test_running_old_request_cannot_be_reregistered_as_new_generation`。

## 旧修复保留的结论

- U1 原普通消息负例已绿；不足以证明启动文本具有唯一请求身份。
- U2 两项、选中 full_prompt、快速终态正例已绿；新补偿存在 V1 回退。
- U3 跨会话终态重放拒绝已绿，保留版本闸前重放的设计；本轮没有要求移回版本闸后。
- U4 同项 A 迟到成果不关 B 已绿；同会话别项仍见 V3。
- T2 已登记旧 run 的直接迟到 callback 已隔离；先重登记再 callback 仍见 V4。

## 验证与证据边界

| 检查 | 本轮结果 | 条件 / 证据 |
|---|---|---|
| 候选内容 | `99d6e193` 干净，应用代码等于 `ecd90a3c` | 所有组合门禁在复制新探针/写审查文档之前运行 |
| 代码地图 | 本树 build 后 ready | 只作入口定位，结论来自源码/动态反证 |
| 既有研究进化 + 前三轮探针 | **119 passed** | `existing-tests.txt`；收据 `20260914T013518Z-99d6e193`，dirty=false |
| 上轮 U 四针单独重跑 | **4 passed** | `round4-repeat.txt`；结合 119 那次共验证两次 |
| 本轮新四针最终版 | **4 failed，连续两次** | `probes-final.txt` / `probes-final-repeat.txt`；真实业务断言失败 |
| 新四针跑修前基线 | **1 passed / 3 failed** | `probes-before.txt`；V1 是本轮回退，V2/V3/V4 是旧边界未修好 |
| 全仓 Ruff | **通过** | `ruff.txt` |
| 前端 lint/typecheck/build | **全部通过** | `frontend-*.txt`；没有受版本控制静态产物变化 |
| 前端 Vitest | **90 passed** | `frontend-test.txt` |
| 全套浏览器 E2E | **31 passed / 2 skipped** | `e2e.txt`；独立端口 19791/19794；绑定链路只跑 desktop，另两 project 沿用基线跳过 |
| 注册表四检查 | **全部通过** | `registry.txt`；只本仓在场，跨仓项由脚本跳过 |
| ledger-spec-crosswalk | **exit 0** | `ledger-crosswalk.txt`；96 条既有反向 warning |
| 全仓 pytest（无 ignore / 无新增 skip） | **10038 passed / 3 failed / 79 skipped / 2 xfailed** | `full-pytest.txt`；收据 `20260914T014714Z-99d6e193`，dirty=false，exit=1 |
| 全仓失败文件定向复核 | **35 passed / 2 failed / 1 skipped** | 候选 `full-failures-recheck.txt`；修前 `full-failures-before.txt` 同读数 |

全量红灯分诊：

1. `test_codex_headless_runtime.py::test_installed_codex_sandbox_denies_network_and_unix_socket[False/True]`：候选/修前均红。直接探针 `codex-isolation-receipt.json` 显示 `codex-cli 0.153.4`，网络/Unix socket 被拒，但 **live_root_read=unexpected_success**，故 isolation=unproven；不是模型外呼失败，不归因于本轮 RE06 diff，也不得豁免门禁。
2. `test_workbench_conversation_integration.py::test_real_conversation_round_trip_persists_skills_sse_and_three_turns`：全量中第三条 assistant 仍 pending，定向重跑通过。该测试 `_send` 只等 run 终态就读消息，文件已有 `_wait_message_terminal` 注释解释两次写入窗口，但本用例未使用；这支持时序窗口诊断，未做变异确定其唯一根因。没有把定向绿覆盖全量红，没有新增 ignore/xfail。

全量不含四条新探针：它们当时在树外，保留了候选 dirty=false。现在归档进审查树后会被下一次全量收集并失败，这是正确的退修探针，不是给候选声明全绿。

所有定向探针用临时 synthetic 用户与确定性执行器，不访问真实用户/模型/市场源。浏览器测合成绑定和接线，不证明真实研究质量。全量中 Codex 隔离测试会执行现役本地二进制的隔离探针。正式命令均用 `env -i PATH="$PATH" HOME="$HOME"`、`umask 022`，不继承宿主测试逃生变量。

日志与收据归档：本目录（`docs/verification/re06-ecd90a3c/`）；原始工作副本 `/private/tmp/re06-qc-ecd90a3c-evidence/`。

### 执行方收据指针纠正

交接称 `20260913T201520Z-b481804c` 是 10043 全量，实读该 JSON 为 **37 passed**，target=`intelligence/tests/test_research_evolution_rework.py`。真正的 **10043 passed / 0 failed / 77 skipped** 在 `20260913T202240Z-b481804c.json`。两者均 dirty=true；后者的 dirty_paths 是 **3 个**受跟踪代码文件、worktree_dirty_total=4，不是快照声称的“五文件”。全量结果确实存在，不应说它没跑；只是指针/条件记录错误，也不能凭路径清单推定脏 diff 逐字等于提交。本轮另跑固定干净候选，不冒用旧收据。

## 重放命令

从候选仓根运行；复制本目录探针到返修树即可，不依赖审查分支改应用：

```bash
# 新四针应在本候选上红、返修后绿；不得删合同断言或加 skip。
PYTHONPATH="$PWD" /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -s \
  docs/verification/re06-ecd90a3c/test_review_round5.py

# 本轮 119 条组合
PYTHONPATH="$PWD" /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_research_evolution*.py \
  /Users/a77/.finance-runtime/reviews/research-evolution-06-ba10747d/test_review_contracts.py \
  docs/verification/re06-0c275716/test_review_round3.py \
  docs/verification/re06-957e83f4/test_review_round4.py

# 全仓命令未排除任何测试
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check .
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q

cd intelligence/webapp
WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
WORKBENCH_E2E_PORT=19791 RE06_E2E_PORT=19794 RE06_E2E_URL=http://127.0.0.1:19794 pnpm test:e2e
```

正式重跑应再包前述净环境与 umask；端口先查无占用。探针可能需要随明确的新输入合同升级 setup，但被测负面状态/修订/归属断言不可删。

## 修复方向与取舍

| 选择 | 取舍 |
|---|---|
| 接受消息时绑定服务端请求实例坐标 | 推荐；不等执行器结束/浏览器第二次调用，也不依赖文案和墙钟 |
| 继续把 label 前缀或全文等同身份 | 否；同内容可以来自不同请求，测试已证 |
| 终态补偿仅凭“用户消息真实存在” | 否；真假 run 与因果归属是两个问题 |
| running/terminal 共用请求归属校验 | 推荐；否则提前 return 绕过后面的代际闸 |
| 只有多代才禁用自动挑判断 | 否；其他对象首次复核就能冲突 |
| writer 暂不能提供成果归属→显式确认 | 可接受保守过渡，但要有真实入口与可核验引用，不是假恢复按钮或报错提示 |
| 为保持旧 setup 绿而扩张身份推断 | 否；可以升级 fixture/输入合同，不能删核心拒绝/状态断言 |
| 用全量/端到端绿覆盖新反证 | 否；测试覆盖的是断言，不是未建模的因果关系 |

工具沉淀：四条反例已写成可移植 pytest，正文与最终版本进审查分支；共同失败形状补进 `~/agent-memory/10_knowledge/state-transition-identity-must-survive-dedup.md`，不另建重复清单。通用 lint 无法证明业务因果；所以保留动态探针，不改已知脏的 harness-reference。用户确认前不合并、不部署。
