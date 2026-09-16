# 研究进化 06 · 第三轮返修复审（第四轮 QC）

日期：2026-09-14。候选 `b481804c`，代码提交 `957e83f4`；与 `0c275716` 比较本轮修复。
独立审查树 `/private/tmp/re06-qc-957e83f4`，分支 `docs/qc-re06-957e83f4`。

## 结论：退修，暂不放行（3 P1 + 1 P2）

既有研究进化套件及前两轮探针 **110 passed**；但新增四条正确合同探针连续两次 **4 failed**。未改候选运行代码、未合并、未部署。主检出目录及执行方工作树均未动。

本轮不否认已修好的单请求快速失败、旧回调直接折回、首轮来源落盘、总结排序和锁初始化清理；问题在修复的边界与身份链。以下 U1/U3 是本轮补丁引入的行为，U2/U4 是 T1/T2 仍未消除的边界。

## U1 · P1：唯一待复核项不是当前消息的因果证明，普通聊天会被自动认领

定位：`intelligence/services/research_evolution/facade.py:1160–1188`；入口 `intelligence/api/app.py:2988–3001`。

`bind_pending_rejudge_run` 只核对“本会话当前只有一条待复核”，既不看消息内容、continuation，也不看已登记的目标 run。所有 `POST messages` 都调用它，所以非复核消息也会被登记到这条请求上。

真实 API 复现：先发起复核，随后发普通消息“先不处理制冷剂复核。请解释市盈率是什么。”，不带任何复核坐标。快速失败执行器结束该消息后：

- run_links 多出该普通消息的关联，携带待复核请求的 request_event_id；
- 维护项从 `rejudgment_requested` 变为 `open`，revision **1→2**；
- 根本没有针对这条维护项发起研究，却被当成它的失败结果。

同一会话的另一个标签页、尚待人工收尾的复核之后继续聊天，都可以落进这个范围；不需要伪造客户端字段。T1 修复把“同会话就行”的弱证明搬到了自动登记侧，后面的代际核验于是会信任一条本不该存在的关联。

**建议**：消息接受时必须核验明确的维护项/请求身份，服务端校验后持久化，再启动执行器；不要根据待办数量推断意图。初轮没有 origin run，不等于没有可用的动作身份。普通聊天应不产生 run_links，不迁移维护状态；合法复核仍需覆盖执行器立即失败/完成的顺序。

探针：`test_plain_message_does_not_claim_pending_maintenance`。

## U2 · P1：同会话两条待复核时，“等显式 link_run”并不能恢复快速终态

定位：`facade.py:1175–1176`；终态拒收 `facade.py:939–959`；调用端 `intelligence/webapp/src/App.tsx:793–823`。

多候选返回 None 本身是谨慎的，但后续恢复并不成立：App 必须等 messages 返回 run_id 才能显式 link_run，终态闸又要求“运行中已登记”。

本轮使用仓内真实 01 fixture，加现有 `CONDITION_DOWNGRADE` 条件，就产出了至少两条不同的 open 维护项（证据变化与条件触发），不需要 mock `_current_items`。对两项分别发起复核，再用第二项动作返回的 full_prompt 按 App 分支发送：

`messages 202 → run failed → 显式 link_run 400 run_binding_mismatch`。

所选项仍在 requested，已失败的这次合法研究不能挂接。handoff 的“夹具世界只产一条维护项”不能作为该分支未测的前提；现成 fixture 已能构造。

**建议**：接受消息侧携带并核验精确请求身份，不能依赖全会话唯一候选；或者设计真实可补偿的可信登记机制，让终态先到也能补偿。不要删关联闸，也不要靠延迟执行器等浏览器。至少用两个真实项覆盖“目标正确、另一个项不变、终态先到仍可收尾”。

探针：`test_two_pending_items_fast_terminal_can_reconcile_selected_item`。

## U3 · P2：终态全局重放跳过了会话范围核验

定位：`facade.py:756–766`。

正常同键重放在 740 附近核对 payload_digest 和 conversation_id；新加的全局终态分支只查 `link_run:{item}:{run}:terminal`，不核对该行的 conversation_id 就返回 accepted。`apply_action` 只证明 URL 上的会话属于当前 owner，不证明旧结果属于它。

复现：会话 A 的失败复核已被观察器折回；在同 owner 的会话 B 用一个新幂等键、A 的 item_id/run_id 调 link_run，得到 **200 / replayed=true / accepted / rejudgment_failed**。原会话闸本应拒绝这条请求。

**影响边界**：本探针没有跨 owner，也没有追加第二次迁移，不能夸大成跨用户泄漏；它是跨会话误报操作成功和范围合同回退。

**建议**：允许已落终态越过过期期望版本，但不能越过 owner、conversation、item/run/request 身份核验。幂等重放（重复调用返回原结果）是免重复执行，不是免授权。保留同会话迟到请求 200 的正向测试，增加跨会话重放拒绝测试。

探针：`test_terminal_global_replay_still_checks_conversation`。

## U4 · P1：请求代际只约束 run_links，迟到旧判断仍能关闭新请求

定位：`facade.py:970–982,993–1006`（本轮未修改的成果解析部分；T2 尚未贯通）。

T2 的原探针“旧 run A 迟到失败直接折回 B”已绿。但是成功路径自动挑新判断时仍只要求同 session 且 `ts >= B.requested_at`，并不知道是哪一轮的成果。

复现用真实动作 API、`ObservingRunStore` 与现役 `judgments.record_judgment` 写入者，不伪造文件结构：

1. 请求 A 登记 run A；合法 cancel_rejudge，然后发起 B 并登记 run B。
2. A 迟到产出一条判断（用真实 writer 模拟 A 的写入；时间晚于 B 请求），A 完成。旧回调正确不迁移 B。
3. B 完成，但没有写下自己的判断。
4. B 的观察器取到 A 的迟到判断，把 B 从 requested **关闭为 closed，revision 3→4**，closure.linked_judgment_ref 指向 A 的行。

当前 legacy writer 的判断行有 session_id/ts，没有可靠的 run/request 归属；这个事实应导致“无法证明属于 B”，而不是通过时间窗自动认领。此探针证明的是接受现役写入形状时自动归属会误判，不代表已跑真实模型输出质量或完整模型写入流程。

**建议**：新判断成果也需要可信 run/request 关联；若原写入者暂不支持，应保持待复核/要求可核验的显式成果确认，而非挑“同会话最新一条”。如涉及超出 06 白名单的 writer 合同，登记最小依赖交对应 owner；不要把管理动作伪装成判断写入。回归同时验 A 的回调与 A 的成果都不能迁移 B。

探针：`test_old_attempt_judgment_cannot_close_new_attempt`。

## 原 T1–T5 的复核口径

| 项 | 本轮裁决 |
|---|---|
| T1 | 单项快速失败已修；U1 新增误认领、U2 多项恢复仍阻塞，不能整体关闭 |
| T2 | 旧 run 的直接迟到回调已隔离；U4 成果归属尚未隔离，不能整体关闭 |
| T3 | 原首轮选择任务的结构化来源落消息探针通过；此结论不扩大为所有同标题/过期动作场景的唯一归属证明 |
| T4 | 原哈希字典序误选已修，单份遗留与多 protocol 拒绝回归通过；未额外声明所有非标准时间字符串都可排序 |
| T5 | os.open 失败后的进程锁回收探针通过；try_transaction 的外层清理结构正确 |

## 独立验证与证据边界

| 检查 | 本轮结果 | 证据/条件 |
|---|---|---|
| 候选状态 | b481804c 干净；957e83f4 后仅交接 | 新建隔离 worktree；代码地图在该树 build 后 ready |
| 研究进化套件 + 前两轮探针 | **110 passed** | `existing-tests.txt`；收据 `20260913T190008Z-b481804c.json` dirty=false |
| 新四条正确合同探针 | **4 failed，重复两次** | `probes.txt`、`probes-repeat.txt`；均为合同断言失败，不是环境错误 |
| 全仓 Ruff | **通过** | `.venv-workbench/bin/python -m ruff check .`，`ruff.txt` |
| 前端 lint / typecheck / build | **全部通过** | `frontend-*.txt`；构建未改变受版本控制的静态产物 |
| 前端 Vitest | **90 passed** | `frontend-test.txt` |
| 全套浏览器 E2E | **31 passed / 2 skipped** | `e2e.txt`；隔离端口 19791/19794；真绑定仅 desktop，其余两项目按既有配置跳过；合成数据不代表研究质量 |
| 注册表四检查 | **全部通过** | `registry.txt`；只本仓在场，跨仓项按脚本跳过 |
| ledger-spec-crosswalk | **exit 0** | `ledger-crosswalk.txt`；96 条既有反向 warning 未消除 |
| 本轮全仓 pytest | **未运行** | 已有业务阻断，不花全量运行替代定向反证；最终合并仍须干净候选组合门禁 |
| 执行方全仓收据 | 核对为 **10034 passed / 0 failed / 77 skipped** | `20260913T181836Z-0c275716.json` 标 dirty=true、四代码文件；日期快照明确命令 `--ignore=test_codex_sandbox.py`。收据无脏 diff 内容哈希，不能仅凭路径清单证明逐字等于 957e83f4；不冒充本轮独立全量 |

测试收据根：`~/.finance-runtime/test-receipts/`。首次自编探针误用了 record_judgment 参数，按真实签名修正后才取本报告的两次结果；初次旧探针路径不存在导致未收集，也未计入测试通过。浏览器首跑漏设 `RE06_E2E_URL`，绑定用例错误连接默认 8794（30 passed/1 failed/2 skipped）；补齐变量后**全套**重跑得到表中结果，未改应用代码或测试断言。保留 `e2e-initial.txt`。

## 重放命令

从候选仓根运行；本目录探针可复制到返修树再跑，不依赖审查树的应用改动：

```bash
PYTHONPATH="$PWD" /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -s docs/verification/re06-957e83f4/test_review_round4.py

# 既有 110 条（上轮独立探针位于审查目录，非当前分支自带文件）
PYTHONPATH="$PWD" /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_research_evolution*.py \
  /Users/a77/.finance-runtime/reviews/research-evolution-06-ba10747d/test_review_contracts.py \
  docs/verification/re06-0c275716/test_review_round3.py

cd intelligence/webapp
WORKBENCH_PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
WORKBENCH_E2E_PORT=19791 RE06_E2E_PORT=19794 RE06_E2E_URL=http://127.0.0.1:19794 \
pnpm test:e2e
```

正式读数用 `env -i PATH="$PATH" HOME="$HOME"` 和 `umask 022` 清理宿主变量；探针只用 pytest 临时用户目录，无模型外呼、无生产数据写入。新探针应在本候选上红、返修后绿，不删断言、不加 gate 避开被测交错、不改 xfail。

## 决策与后续

- 保留执行前登记的方向，但必须是精确请求关联，不接受“唯一待办所以就是它”。
- 保留旧 run 的代际隔离，要求成果归属也贯通；仅在 callback 入口加闸不是闭环。
- 保留终态重放早于版本冲突的设计，但范围核验不能一并跳过。
- 否决凭已有测试绿/恢复按钮存在放行：本轮四条反证已证实产品合同仍可违反。
- 交执行者修 U1–U4；不要求重做 T4/T5。修完重跑本轮与前两轮探针，再跑合并候选最终组合门禁；用户确认前不合、不部署。
- 工具沉淀：反例已版本化为可执行测试，不只留聊天。跨项目“归属不是因果、重放仍需权限、请求身份须贯穿成果”的方法可复用；统一静态 lint 无法判定业务因果，因此不另造通用检查器，未修改已知脏的 harness-reference。
