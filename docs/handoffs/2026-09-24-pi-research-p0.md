# Pi 式研究兑现：P0 合同与机制验收

## 背景与决定

用户先比较 8792 与当前 Pi 的研究限制，随后要求“落一份 spec 然后推进”。主树有他人在途改动，创建独立 `feat/pi-research-loop`，路径 `~/fwp-wt-pi-research`，基线 `4cc15e703f81`。本轮未动主树、生产快照或现有自主研究 owner 的文件。

先前问答借旧树与历史设计判断能力；新基线已经有 web_fetch、子研究、派生计算、研究进展反馈、收件箱和金融 Harness。本轮决定不为“Pi 式”标签再搬一套 Loop，而是把可观察行为写成合同，并验证现有生产 Runtime 装配是否允许这些行为。

| 方案 | 结果与理由 |
| --- | --- |
| 现有 Episode + FinanceResearchHarness，接续 #868 | 采用。保留权限、证据和生命周期，实际效果另做真实入口验收 |
| 参考 Loop 直接转生产 | 否。其生产持久化、生命周期覆盖不足，不能凭代码短替换 |
| 嵌入 Pi/dsh 或开放宿主 Shell | 否。本次目标是研究行为，不是换运行时或扩大宿主权限 |
| 重写自主视角 / 传输截止 / 修订发布 | 否。PR #868 / 工单 #72/#75/#76 有 owner，不双改生产模块 |
| 抬额度或把离线绿算质量完成 | 否。调用预算与真实研究质量分别有验收合同 |

总 spec：`../superpowers/specs/2026-09-24-pi-style-research-delivery-design.md`。

## 实施与读数

提交 `03453614b19017936cadebe51c08ddba4dbe0f07`：总 spec + `intelligence/tests/conformance/test_research_chain.py`，没有 Runtime 行为改动。

使用真实 `GLMAgentRuntime.start()`、默认 `FinanceResearchHarness`、注册表、预算及取消机制，只替换模型和数据源。模型替身读取上一轮观察，决定下一工具实参；正常完成从模型可见 E 编号绑定回真实 source hash。

12 项新增测试包括：两组不同线索传递；空结果、工具异常后换路；越权拒绝后合法取证；假引用不得交付；额度耗尽保留已有证据；观察后取消不派新工具；四个变异对照（改错线索、菜单泄露、宿主洗引用、漏扣预算）。变异只用 pytest monkeypatch，测试退出恢复，不修改生产文件。

首次扩展变异时发现两个夹具问题：改 authorized_specs 会先被授权快照结构校验拦住，不是菜单泄露；hard cap 与已授额度都设 1 时，另一道总次数帽会掩盖漏扣账变异。修正为菜单投影点注入，以及已授 1/hard cap 4 的未授 headroom 对照。中间红不算产品缺陷，原收据仍留在本机 test-receipts。

在已提交干净树执行：

```bash
$PY -m pytest -q -rsx intelligence/tests/conformance intelligence/tests/test_glm_agent_runtime.py intelligence/tests/test_research_progress.py
$PY -m ruff check intelligence/tests/conformance/test_research_chain.py
```

`$PY` 为主树 `.venv-workbench/bin/python`。结果 **175 passed / 3 skipped / 1 xfailed**，收集 179，16.34 秒；ruff 通过。

收据：`~/.finance-runtime/test-receipts/20260924T131215Z-03453614-66f9369f56b2.json`。`check_test_receipt.py --expect-revision 03453614b19017936cadebe51c08ddba4dbe0f07 --require-target intelligence/tests/conformance` 校验通过，dirty=false。这是定向范围，不是全仓门禁。最后文档提交不移签测试 revision。

3 个 skip 均为非生产参照 backend 声明的不适用部分；唯一 xfail 是已有 codex_headless 修复缺席收据基线，不是本次新增测试。本轮全部提交钩子通过，含真实装配工具可达性与运行目录保鲜；它们也不证明自然模型会用对工具。

## 在途依赖与后续

最初读到 #868 原分支交接的 131/152；随后共享项目笔记指向更晚原件，已经订正 spec。最新读取的是 `~/.finance-runtime/reviews/pr868-glm-qc-20260924-1405/STATE.md`：候选 `ce2a2713121a`，工程四叶绿，spec/execute 因漏 `complete: true` 被 schema 拒收并封存；累计 166/209、剩 43，不足原计划完整新批 78。未分类探针观察不能代签产品发现。新额度/方案由原 owner 确认，旧批不能续跑。

下一步是接续确切自主研究候选的独审，再按 #76 的授权协议做真实 Workbench 入口验收；候选组合须复跑本套测试。不得把本分支的离线绿移签给 #868，亦不得因模型/运行时风格近似而宣称自然研究效果相同。

未跑：真实模型调用、HTTP 会话入口、真实数据/网页/子研究链、语义判官与公开稿一致性、前端/全仓门禁、独立复审、8792 探针。未合 main、未 push、未部署。只读 runtime 软链仍指向 `finance-workspace-3b7e473575b0`，不替代活进程身份核验。

工具沉淀：新量具已在 pytest 常规收集面，没有留在 /tmp 的脚本或后台任务。本次复用已有符合性与变异方法，未发明新的跨项目机制，不重复写 harness-reference 清单。项目记忆只留一行指针。
