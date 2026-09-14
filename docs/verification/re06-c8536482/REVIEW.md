# 研究进化 06 · 第五轮返修复审（第六轮 QC）

日期：2026-09-14。被审候选 `42e8f4ee`，应用代码 `c8536482`；修前 `99d6e193`。
独立审查树 `/private/tmp/re06-qc-c8536482`，分支 `docs/qc-re06-c8536482`。

## 结论：退修，暂不放行（2 P1 + 1 P2）

请求实例坐标替代文本身份是正确方向，V1–V4 原四针及既有组合 **127 passed**。但坐标校验没有覆盖显式 running 登记；成果认领仍把「当前唯一」当成因果证明。新增后端三针连续两次 **3 failed**，新增前端状态转换针连续两次 **1 failed**，移入标准前端测试入口另复现 **1 failed**。均为业务断言失败，不是启动/依赖错误。

主检出树有他人改动且停在另一 revision，未使用；所有正式门禁在独立固定候选、净环境运行。未改应用代码、未合并、未部署。执行方树仍干净。

## F1 · P1：显式运行中登记仍可绕过完整请求身份（W1、W2）

定位：`intelligence/services/research_evolution/facade.py:940–975`，尤其 **949–950** 与 **961–971**；后续观察器选择 `1164–1167`。

新旧代检查只查 `find_run_link(item_id=目标项, run_id=run)`：

1. 看不到该 run 已属于**另一个项**；
2. 没有登记行时，不读取源消息已携带的 `maintenance_launch`，直接把当前 request_event_id 写上。

因此消息接受侧拒绝/确认的身份，能被另一条写入口改掉。

### W1：跨项重新认领

真实绑定两个不同原判断 A/B，各发起复核。通过真实 messages API 发送 A 的完整启动坐标，接受侧已登记 run A→项 A。run 暂停在运行中时，拿 B 当前版本显式 link 同一个 run。

- 返回 **200 registered / link_created=true**；
- 同一个 run 出现 A/B 两条不同请求坐标的登记；
- 释放 run A 使其失败，观察器取最后登记行，B **rejudgment_requested→open，revision 1→2**。

这不是让单 run 合法完成多个关联任务的请求：源消息明确点名的是 A，新增登记与该来源矛盾。

### W2：未登记的陈旧坐标被改贴当前代

同一项请求 A→取消 A→请求 B；之后才发送保存的 A 坐标。接受侧正确拒绝自动登记（断言 run_links 为空）。趁该 run 仍在运行，拿 B 最新版本显式 link。

- 返回 **200 registered**，把旧 A 消息的 run 登记成 B；
- run 失败后 B **rejudgment_requested→open，revision 3→4**。

V4 原针只覆盖「旧 run 已有本项旧代登记」；本针覆盖「陈旧输入被拒绝，所以根本没有登记」。缺少行不等于没有矛盾身份。

**修复要求**：所有登记入口在写入前遵守同一个完整规则：按 run 查既有归属，而非先按目标项过滤；若源消息存在结构化启动坐标，必须验证 owner/会话/项/当前请求一致，已知冲突或陈旧坐标不能回退到裸登记。当前同坐标幂等复用可以保留。

**不要求破坏 R7**：无消息、无既有归属的 running run 可按现有显式登记合同保留。两个新探针均是有源消息、且源坐标可核验的 run；不能用 R7 为已知冲突的来源豁免。更不能用延迟执行器或扩大时间窗修复。

探针：`test_review_round6.py::test_w1_running_run_cannot_be_claimed_by_another_item`、`test_w2_rejected_stale_message_cannot_gain_current_identity_while_running`。

## F2 · P1：取消别项后，其未消费迟到成果仍能自动关闭剩余项（W3）

定位：`intelligence/services/research_evolution/facade.py:1030–1058`，尤其 **1031–1032**。

新闸只数当前 `rejudgment_requested`，已取消/退出 pending 的请求从候选生产者中消失；`consumed` 只能排除已成功闭环消费的判断，排除不了取消项新写的未消费判断。

复现沿 V3 的真实两原判断、两绑定、两项场景：A/B 首次复核并登记各自 run→取消 A→原 writer 写 A 的迟到判断→A 完成→B 无自身判断也完成。此时只有 B pending、B attempts=1、A 判断未被消费，全部通过新闸。

结果：B **rejudgment_requested→closed，revision 1→2**，closure.linked_judgment_ref 指向 A 的迟到成果。

**修复要求**：不能以当前状态集合的基数证明历史因果。判断 writer 暂无 run/request/object 身份时，无法核验的成果应等待显式确认；如保留自动路径，必须论证并验证其来源合同，不是再加「其他项当前处于某状态」的局部条件。自动路径的正例应携带可信来源，必要时升级旧 setup，而非把缺身份自动认领固化为产品承诺。

此针在修前 `99d6e193` 同样产生错误关闭：是 V3 修复未覆盖的旧边界，不称本轮新增回退。run 用现役 ObservingRunStore 建立，判断用现役 `judgments.record_judgment` 写入；不是模型质量评测。

探针：`test_review_round6.py::test_w3_cancelled_other_item_is_still_a_possible_late_judgment_producer`。

## F3 · P2：先打开确认表单再等 run 完成，选择状态不更新，按钮卡住（W4）

定位：`intelligence/webapp/src/components/ResearchEvolutionPanel.tsx:45–57`，尤其 **54–57**。

`useState(eligibleRuns[0]?.run_id ?? "")` 只在组件首次挂载时求初值。用户在 run 仍运行时打开「确认成果」，runId 初始化为空；run 完成后 App 刷新投影（`App.tsx::finalizeRun → loadConversationData`），组件仍挂载，eligibleRuns 变为一条，但 runId 不会重算。

真实组件 rerender 探针观测：下拉框显示并读出唯一选项 `run1`，用户选好成果判断后，「确认这条判断是本轮成果」**仍 disabled**。只有一个 run 时用户没有另一个选项可切换来触发 change；收起再展开会重新挂载，才能恢复。

**修复要求**：让有效选择随候选集合/请求代际变化保持一致，例如由当前合法选择和候选共同派生 effectiveRunId，或明确同步/reset；提交前同时验证 runId 仍在当前代 completed 集合里。不能只凭 `eligibleRuns.length > 0` 保证已选值合法。至少保留 running→completed 的组件状态转换测试，而非只测试首次渲染时已完成的静态快照。

探针：`confirm-outcome.test.tsx`。这是组件渲染/状态更新复现，不冒充完整真浏览器新增旅程；现有浏览器套件没有覆盖这条确认操作。

## 上轮修复保留的结论

- V1：旧普通终态聊天不能补挂当前请求，原针绿。
- V2：无坐标旧文本不会自动认领；结构化坐标已从 App 传入 Message，原针绿。W2 说明后续显式 running 写入口仍可改掉拒绝结果。
- V3：两个项同时 pending 时不再自动认领，原针绿；取消一个后的迟到成果仍见 W3。
- V4：同项已有旧代登记的 running run 不能直接转挂，原针绿；不同项已有登记/无登记但有陈旧源坐标分别见 W1/W2。
- 新确认入口确实存在，已完成初始快照的单测通过；不能据此覆盖挂载后候选变化（W4）。

## 独立验证与证据边界

| 检查 | 结果 | 证据/条件 |
|---|---|---|
| 固定候选/应用内容 | `42e8f4ee` 干净；应用代码为 `c8536482` | 门禁期间未改/新增被测源码；静态资源重建无 diff |
| 代码地图 | 本树 build 后 ready | 仅定位，结论来自源码与反例 |
| 既有 5 套件 + round2/3/4/5 探针 | **127 passed** | `existing-tests.txt`；收据 `20260914T034816Z-42e8f4ee` |
| 本轮后端 W1/W2/W3 | **3 failed，连续两次** | `probes.txt`、`probes-repeat.txt`；临时 synthetic 用户 |
| W3 修前重放 | **1 failed / 2 deselected** | `probes-before-w3.txt`；实际错误关闭 |
| 本轮 UI W4 | **1 failed，连续两次**；标准入口再 **1 failed** | `ui-probe*.txt`、`ui-portable.txt` |
| 全仓 Ruff | **通过** | `ruff.txt` |
| 前端 lint/typecheck/test/build | **通过；92 tests** | `frontend.txt` |
| 浏览器 E2E | **31 passed / 2 skipped** | `e2e.txt`；隔离端口 19891/19894；两 skip 沿用绑定用例基线 |
| 注册表四检查 | **通过** | `registry.txt`；本仓在场，跨仓项由脚本跳过 |
| 全仓 pytest（无 ignore / 无新增 skip） | **10047 passed / 2 failed / 79 skipped / 2 xfailed** | `full-pytest.txt`；收据 `20260914T035716Z-42e8f4ee.json`，dirty=false，exit=1 |
| 两条全仓失败定向复核 | 候选 **2 failed**；修前 **2 failed** | `isolation-repeat.txt`、`isolation-before.txt` |

### 全量红灯分诊

两条失败都是 `test_codex_headless_runtime.py::test_installed_codex_sandbox_denies_network_and_unix_socket[False/True]`。直接探针 `isolation-receipt.json`：codex-cli 0.153.4；public_tcp/loopback/unix_socket 均 denied，但 **live_root_read=unexpected_success**，故 status=unproven。

它们在修前也红，不归因于 RE06 diff；也不允许因此豁免合并门禁。位置/本机二进制等环境条件会影响探针，不能拿另一棵树的绿数覆盖本次干净候选的红数。

执行方 `20260914T033709Z-99d6e193.json` 确实记录 **10051 passed / 0 failed / 77 skipped**，不是虚构。其条件是执行方树、revision=99d6e193、dirty=true（14 个 dirty_paths，worktree_dirty_total=17），不能直接等同于本次干净提交。两份读数各自保留，不据路径清单推定脏 diff 完全相同。

全仓测试运行时，新四针仍在树外，因此 full-pytest 的 2 failed **不包含**本轮业务反例。现在归档三条 Python 反例后，未来全仓会额外收集它们，这是退修应保留的正确合同断言。

修前 W1/W2 不能原样运行：旧 continuation 没有 request_event_id，setup 会 KeyError，不能把它记成修前业务失败。未为凑修前回归结论改变候选探针；本报告只对 W3 给出动态修前对照。

正式命令统一使用 `env -i PATH="$PATH" HOME="$HOME"` + `umask 022`，解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。测试无模型调用、无真实用户写入；全仓包含现役 Codex 二进制隔离探针。未使用测试逃生变量。

## 重放命令

```bash
# 候选仓根：复制本目录到返修树，不修改应用。
env -i PATH="$PATH" HOME="$HOME" bash -c 'umask 022;
  PYTHONPATH="$PWD" /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -s \
  docs/verification/re06-c8536482/test_review_round6.py'

# 前端探针需位于标准 src 测试入口以复用同一 React/Vitest 解析；拒绝覆盖现有文件，退出移除。
env -i PATH="$PATH" HOME="$HOME" bash -c 'umask 022;
  p=intelligence/webapp/src/components/RE06Round6Probe.test.tsx
  test ! -e "$p" || exit 2
  cp docs/verification/re06-c8536482/confirm-outcome.test.tsx "$p"
  trap '\''rm -f "$p"'\'' EXIT
  (cd intelligence/webapp && pnpm exec vitest run src/components/RE06Round6Probe.test.tsx)'
```

## 决策与交付纪律

- 两条 running 绕闸反例合为一个 P1，因为缺的是同一登记入口的完整身份核验；不靠拆探针数量放大缺陷数。
- 保留 R7 裸 run 正例，不把「无来源」与「已知矛盾来源」混为一谈。
- 禁止再靠 pending 数/首次次数/未消费集合等代理变量证明因果；无法证明时走已提供的显式确认入口。
- 不要求换引擎、不触碰 judgments 唯一写入者；如果后续扩成果归属，先更新 writer 合同和正例。
- 反例落仓可机械重放；通用静态 lint 不能识别业务因果，不另造假通用门禁。跨任务教训补既有 `state-transition-identity-must-survive-dedup.md`，不改已知脏的 harness-reference。
- 下一步：修 F1/F2/F3 → 本轮四针绿且历史 127 保留 → 干净候选重跑门禁并解决/独立裁决隔离红灯 → 等用户确认合并。不得以旧套件绿覆盖新反例。
