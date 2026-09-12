# 600f2aa9 独立质检：修复通过，发布准备待补

## 结论与范围

审查 `d0d59220` / `7ea9d958` / `600f2aa9`，未合并、未推送、未切 8792、未发真实模型题。本轮只读生产 health/readiness，离线测试使用主树 `.venv-workbench/bin/python`。

**T2 的 disclosure_scan 误判在被审提交上已修好，回归锁有效；不能将此等同于“可把整枝部署”或“T2 已能完整作答”。** 发布前须补探针身份绑定、在正确基线形成发布候选，再走真实产品验收。

## 独立证据

- 干净 `600f2aa9`：定向 **124 passed / 1 xfailed**；最终 `intelligence/tests` **7002 passed / 14 skipped / 2 xfailed**。
- 全量收据：`~/.finance-runtime/test-receipts/20260912T164818Z-600f2aa9.json`。在被审提交上执行 `scripts/check_test_receipt.py <该路径> --expect-revision 600f2aa9` **exit 0**。
- 原收据 `20260912T162655Z-1b9944dd.json` 确实记载 7002P，但 `dirty=true`，包含三份路由代码、新测试和 probe；无脏文件内容指纹，不能由 revision 还原。旧收据校验 exit 1，本轮干净重跑替代，不指控旧数字造假。
- 五个触碰 Python 文件定向 Ruff 通过，三提交 `git diff --check` 通过。**未跑全仓 pytest、前端、E2E、registry 合流门禁，非 merge-ready 收据。**
- T2 嵌入串与 `t2-question.txt` 字节一致，T2/T3 去尾 LF 后均是 `docs/knevo-20260911-intake` 冻结原文的精确子串。文件原始 SHA 与去尾 LF 的 SHA 不同；README 的短 SHA 实际是后者，比较时须标明归一化方式。
- 两次内存变异：放开 query_understanding 闸，事故用例 1 红；放开家族闸，事故用例 2 红。补丁没有“测试绿但删闸仍绿”的问题。变异不落盘，其自动测试收据不是未变异代码的发布证据（同秒收据还会同名覆盖），只采本段输出与最终未变异全量收据。

## 发现 1（P1）：续问探针仍能认错轮，失败也 exit 0

位置：`scripts/workbench_probe.py:103–122`。

API `intelligence/api/app.py:2701–2811` 提交消息时已经返回 `assistant_message_id` / `run_id`；脚本丢弃返回值，仅用非空 assistant 数量增长决定完成，再取最后一条。计数不是请求身份。

用 `_call` 的离线替身运行真实 `main()`，复现：

| 发问前 → 轮询 | 实际结果 |
|---|---|
| 1 条旧完整答案；另一旧 pending 未计数 → 旧 pending 完成，本轮仍 pending | 打印迟到旧答案，exit 0 |
| 1 条旧答案 → 本轮新增非空 `status=failed` 存根 | 打印“任务执行失败，请稍后重试”，exit 0 |
| 1 条旧答案 → 本轮 completed | 正常输出，exit 0 |

第二种是实际运行路径支持的消息形状，`conversation_orchestrator.py:4045–4068` 明确会把失败文本写为 assistant/failed。第一种可发生在前一次 probe 超时后用户续问时，不要求同时有两个执行者占同一用户槽。

**下一步**：保留 POST 返回值，只接收同 `assistant_message_id` 且同 `run_id` 的终态消息；pending/running 继续等，failed/cancelled 非零退出（partial 单列，不算质量通过）；输出精确 run_id，后续凭它取工件。新增旧 pending 迟到、别轮抢先完成、本轮 failed、本轮成功、超时等测试。消息完成也不等于工件已全部落盘，检查工件须另等所需文件就绪。

## 发现 2（P1）：被审分支不是当前生产的前向候选

只读生产实测：`runtime.source_revision=2efdff46e2510a2f87f5bc245b524fb94724741a`、`source_dirty=false`、`code_matches_repo=true`；runtime symlink 同 SHA，模型 `kimi-k3`，readiness 全 true。

fetch 后 `gitea/main=883e3d36a42e…`，生产到 main **86** 个提交，不再是 80。更重要的是：

- `git rev-list --left-right --count 2efdff46...600f2aa9` = **551 / 4**。
- `gitea/main...600f2aa9` = **637 / 4**。
- 生产到被审 tip 的三份路由文件 diff 为 **78 加 / 280 删**，会撤销现有材料拆分、日期解析等后续改动。直接部署整枝或覆盖整文件不是“最小修复”。

### 离线试移植揭出的行为差异

在 `/private/tmp/route-gate-qc-production`（独立 `2efdff46` 副本，绝非生产目录）试应用四文件补丁：普通 `git apply --check` 在 query_understanding import 上因后续代码上下文不同失败；保留生产代码，仅插入 helper import 与长度判断，其余三文件原补丁应用。该树保留未提交试移植，**不可作部署候选**。

- 生产原文：`understand_query(T2)=general_finance_qa`，`decide_turn(T2)=disclosure_scan`。
- 最小试移植后：定向 **125 passed / 1 xfailed**，T2 `decide_turn=theme_analysis / research`，理由为确定性识别 theme-research owner。
- 被审旧枝上才是 `comparison / research / 通用研究闭环`。

`test_fine_grained_route_length_gate.py:116–120` 只锁 `!= disclosure_scan` + `lane == research`，故两者都绿。它充分证明“不会再掉扫描存根”，**没有证明“进通用 owner”或“八问得到完整回答”**。不要为了凑报告而机械硬断言 comparison；应在发布基线上验证材料身份、禁外部事实约束和实际回答路径。

**下一步**：推荐拆开发布变量。当前生产 SHA 上移植最小修复形成新候选（主干合入线另从最新 main 接入），不捆绑 86 提交。用户授权部署之前，用独立端口/探针用户走同款配置 T2→T3；若 theme_analysis 导致虚构主体被当真实体或触发不必要外查，先修这个候选的材料路由，不能用旧枝的 comparison 读数作担保。

## 发现 3（P2）：家族入口已挡六条，不代表整个家族所有消费点已挡

`answer_orchestrator.py:267`、`:590` 仍直接调用裸 `is_quick_fact_query`，没有共享长度闸。这不是此次新增缺陷，但说明“同族所有入口都已覆盖”的广义结论不成立。

独立 230 字课堂材料双任务：正文含“茅台现在股价多少”，同时要求解释记录的证据强弱与待核实项。实测：长度闸 False、裸匹配 True、`decide_turn=general_finance_qa/research`；`plan_answer_question(query, question_type_override=decision.question_type)=quick_fact`。合成前题型仍可被另一消费点降成取值。没有跑模型，所以不进一步声称真实答案一定漏项。

**下一步**：本次上线声明收窄为 T2/disclosure_scan 止血；quick_fact 另立小单补长短题对照与两条判定链一致性测试，再决定共享闸下到 matcher 还是每个消费者。不要偷偷扩大紧急发布范围。

## 验证环境的两次假红（均已解释并重跑）

1. 最初干净树在 `/private/tmp` 全量 7001P/1F，Codex isolation 测试失败。父提交 `1b9944dd` 同目录形态亦红。进一步 probe：公网/loopback/Unix socket 均 denied，`live_root_read=unexpected_success`。移到正常用户 worktree 后该测试通过；临时目录布局改变了 OS 沙箱的可读面。
2. `git worktree move` 保留了旧 `.pyc` 文件，其 source filename 仍指旧路径，`inspect.getsource` 失败。删除自己新树的 `__pycache__` 后该用例通过，再全量 7002P。一次并行导入碰上缓存清理导致目录删除竞争，随后改串行清理/测试；没有改测试或 skip。

最终收据只采迁到 `/Users/a77/fwp-wt-qc-route-600f2aa9`、清理缓存后的那份。

## 建议执行顺序与放行条件

1. 修 probe 请求身份/终态，补离线回归。
2. 当前生产 SHA 上形成干净最小候选；主干修复另走新 main 分支，拒绝旧分支整树覆盖。
3. 最终候选上的本机等价门禁全部有结论且全绿；旧枝 7002P 不能代替候选收据。
4. 隔离端口按生产模型/预算/判官配置跑原题 T2，再在同一新会话续 T3。保存题面 SHA、配置/代码 SHA、精确 conversation/message/run ID、答案和 trace。T2 八问逐项有实质答复、0.5/20=2.5% 与 0.5/2=25% 正确，订单/收入/利润不混同，不联网补虚构公司现实事实；T3 按原题验增量而非重答 T2。
5. 不只看 `completed`：核实模型确实执行、不是扫描存根；T2 自给材料题无需强求外部引用非零。判官策略仍是单独变量，不据两题宣布 K3 自审长期可靠。
6. 证据齐后申请用户确认切流；保留旧代码快照和当前启动配置作回滚锚，切后 health 三读 + 真入口小样，再安排生产到 main 的独立集成批次。

本轮未扩建新工具，复用 pytest、现有收据校验与隔离副本即可证伪；probe 缺陷留给执行单修复，不在质检分支混入实现。
