# RE06 第七轮复审：9266407f / 代码 f90e27c5

日期：2026-09-14。结论：**退修，2 个 P1；本轮前端 P2 可关闭。**

固定候选 `9266407fec9f9c3190a2d642dceff63342855f92`，独立树 `/private/tmp/re06-qc-9266407f`，审查分支 `docs/qc-re06-9266407f`。不使用主检出树的他人改动；未改应用、未合并、未部署。

核实：`abb668cd` 与 `9266407f` 均为交接/返修说明提交；相对 `f90e27c5` 只改三份 Markdown，应用内容一致。执行方给出的干净全量收据真实存在。原 W1–W3 转绿属实，但不等于归属合同已经收口。

## F1 · P1：会话史唯一复核仍能自动消费普通聊天的判断（X1）

位置：`intelligence/services/research_evolution/facade.py:1052–1056,1069–1082`。

新增历史计数只枚举 `ACTION_REJUDGE`，而同会话判断的生产者并不只限于复核。通过该计数后，仍按 session + requested_at 下界挑最后一条判断，未证明该判断由关联 run / 请求 / 原对象产生。

### 最小复现

1. 给制冷剂判断建立真实绑定，发起本会话历史上**唯一**一次 rejudge。
2. 在启动维护 run 之前，先通过真实 messages API 发一条不带维护坐标的普通消息；确定性执行器调用现役 `judgments.record_judgment` 写入银行观点，完成普通 run。
3. 断言普通 run 没有 run_links、rejudge 历史恰好一条、维护项仍 pending。
4. 发送正确维护坐标启动复核 run；它 completed，但**没有写任何判断成果**。
5. 观察器/幂等恢复自动关闭维护项：`rejudgment_requested/revision=1 → closed/revision=2`，`closure.linked_judgment_ref` 指向步骤 2 的银行判断。

不需要同时运行两条模型任务，不需要取消别项，不依赖时钟偏移：普通聊天在复核请求之后、维护 run 之前完成就足够。测试用真实 API、01 状态机、存储和原 writer；仅执行器是确定性替身，不宣称验证了模型写入质量。

**修复要求**：自动认领必须凭可信成果归属；无法核验的 legacy 判断走现有显式确认，不再以首次/历史次数/候选数量代理因果。不要再加“期间是否有普通消息”“再缩时间窗”等局部规则。

Q2 应保留“可信关联成果到达后，无需第二次 link 即自动收尾”的行为目标；旧 Q2 夹具只写 session/ts，并不是缺归属也必须自动关闭的授权。若坚持保留自动路径，需要先申请 `judgments.record_judgment` 及其调用链的最小范围扩展，再升级可信正例；若采用全显式过渡，应明确提交合同变更，而不是私自删除旧断言或继续绕规则。

## F2 · P1：登记顺序倒转后，接受侧仍能建立双归属（X2）

位置：`intelligence/services/research_evolution/facade.py:1305–1323`（接受侧直接 append）；相关 `944–946`（同代复用先返回）、`1004–1005`（终态信任已有 link）；公开可见窗口 `intelligence/api/app.py:2956–2988,3011–3016,3074–3078`。

W1 已覆盖“先 A 接受登记，后显式抢到 B”。本轮只给显式 running 分支加完整校验，反向顺序仍可绕过：`create_run` 已公开可查，而用户消息及其坐标尚未落盘，R7 的无来源兼容先把它收成 B；消息落盘后接受侧不查 run 既有归属，又登记成 A。锁只串行了写入，没统一两条写入口的业务约束。

### 最小复现

1. 两个不同原判断 A/B 各请求复核。
2. 真实 messages API 提交 A 坐标；用线程闸门暂停在用户消息 append **之前**，不篡改业务函数返回。
3. 另一调用通过公开 `GET /api/runs` 获取已创建 run_id（不是从测试内部偷 id），显式登记给 B，返回 200。
4. 放开原请求，用户消息落 A 坐标；接受侧又 append A link。
5. A run failed；同 run 的 `run_links` 现在有 A/B 两条。观察器先折回 A；再显式折回 B 返回 **200 rejudgment_failed**，B `revision 1→2`、`pending→open`。

两针最终版本在候选连续两次 **2 failed**，归档后标准入口再 **2 failed**；在修前 `42e8f4ee` 原样 **2 failed**。均为目标业务断言失败，不是 setup/依赖错误；属于上轮修复未覆盖，不称 f90e27c5 新引入。

**修复要求**：

- run 归属约束必须统一覆盖接受、显式、补偿和已有链接复用/终态信任，不是再复制一次局部检查。
- 区分“来源确实不存在的裸 run”与“来源尚在持久化中的已受理消息”。后者不能先当裸 run 登记，再把冲突坐标补进来；建立身份与对外可登记性需要明确顺序/原子边界。
- 仅接受侧检测冲突后返回 None 还不够：错误的 B link 若继续被终态信任，仍可迁移 B。必须同时保证已知源冲突不会驱动错误对象状态。
- 不要求破坏 R7 真裸 run；新测试未修改 RunStore/台账实现，只控制真实两请求的交错顺序。

## 本轮已修好的部分

- W1：已有 A 登记和消息坐标时，显式 running 抢 B 被拒。
- W2：已持久化陈旧消息坐标，显式 running 不再改贴新代。
- W3：取消同伴后的迟到成果不再关闭剩余项；但 F1 证明“历史唯一”仍不充分。
- P2：表单选择派生 + 代际 key 生效。原 round6 前端探针原样移入标准 src 入口 **1 passed**；仓内新增两条状态转换包含在 **94 passed** 中。原报告引用的 `confirm-outcome.test.tsx` 未进入候选提交，本次从上一轮审查树读取后重放，不冒充候选自带文件。

## 验证与证据边界

日志耐久目录：`~/.finance-runtime/reviews/re06-9266407f-evidence/`。新反例：本目录 `test_review_round7.py`。

| 检查 | 实际结果 | 证据 |
|---|---|---|
| 原 5 套件 + round2–6 全部探针 | **133 passed** | `existing.txt`；收据 `20260914T045531Z-9266407f.json` |
| X1/X2 候选最终探针重复 | **2 failed × 2** | `probes-repeat.txt`、`probes-final-repeat.txt` |
| X1/X2 修前原样 | **2 failed** | `probes-before.txt` |
| X1/X2 归档后重放 | **2 failed** | `probes-archived.txt` |
| 全仓 Ruff | **通过** | `static-and-isolation.txt`；归档新针另过 Ruff |
| 前端 lint / typecheck / test / build | **全通过，94 tests** | `frontend.txt`；重建静态资源与候选无 diff |
| 原 UI W4 探针 | **1 passed** | `ui-original.txt` |
| 浏览器 E2E | **31 passed / 2 skipped** | `e2e-final.txt`；19921/19924 隔离端口 |
| 注册表四检查 | **通过** | `registry.txt`；跨仓缺席项由脚本跳过 |
| 本次独立全量 pytest | **未得完整结论** | `/private/tmp` 那次 600s 超时停在约64%；home 重试主动停止在约9%，均不得统计作完整收据 |
| 执行方提交态全量收据核实 | **10057 passed / 0 failed / 77 skipped**，dirty=false | `~/.finance-runtime/test-receipts/20260914T043357Z-f90e27c5.json`；应用与本候选相同，但不是我本次独立全量绿 |

E2E 首次 30P/1F/2S 是审查命令只设 `RE06_E2E_PORT`，漏设用例独立读取的 `RE06_E2E_URL`，请求跑到默认8794；补齐环境、不改测试/应用后 31P/2S。首份错误日志保留，不算产品缺陷。

### 沙箱两红：更准确的环境裁决

不能把“评审环境红、执行环境绿”直接归因为嵌套沙箱。本轮同一 harness、同一提交、同一解释器、净环境命令，改变检出路径：

- `/private/tmp/re06-qc-9266407f`：两测试 **2 failed**，重复仍红；直接探针 `live_root_read=unexpected_success`，其余三项 denied。
- `~/.finance-runtime/reviews/re06-9266407f-home`：同提交干净树，两测试 **2 passed**；直接探针四项 denied、status=proven。收据 `20260914T051137Z-9266407f.json`。
- 二进制同为 `codex-cli 0.154.0-alpha.6.2`，与前轮报告里的0.153.4不同；完整对照见 `isolation-path-comparison.txt`。

因此可以支持**检出位置敏感、非此次 RE06 diff 所致**，不能支持“profile 在嵌套沙箱不生效”这个已定根因；本轮没有完整拆解 Codex 默认文件系统策略，不进一步猜测。原测试与隔离实现均未改。两份位置条件各自保留，建议最终合并门禁固定在符合实际隔离边界的非临时目录干净候选重跑，不加豁免。业务反例本身已足够阻断放行。

## 重放

```bash
# 在候选根目录；Python 原测试文件在本目录，无需修改应用。
env -i HOME="$HOME" PATH="$PATH" bash -c 'umask 022;
  PYTHONPATH="$PWD" /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -s \
  docs/verification/re06-9266407f/test_review_round7.py'
```

下一步：先决定成果归属合同/是否申请 writer 范围，再修 F1/F2；原 W1–W3、P2 与历史组合必须保留。所有应用补丁仍由执行分支承担；本审查分支只留报告与正确合同反例。
