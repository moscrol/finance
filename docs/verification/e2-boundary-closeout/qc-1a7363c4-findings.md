**不放行到 P2。** 固定提交仍有 6 项可复现的合同偏差：3 项 P1 级、3 项 P2 级。这里的严重性编号与实施阶段 P1–P7 无关。

审查版本：`1a7363c46b35bbb612a91bbbfafde22e3a7aac86`。所有命令均在 `/Users/a77/fwp-wt-e2-closeout-qc` 执行；前后 `git status --short` 均为空。解释器为指定的 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，版本 3.12.13。

已读取 AGENTS.md、指定设计 D1/D2 和验收条款、上版报告及修复 diff。执行证据：

- 原样探针：**46 passed / 0 failed，exit 0**；与上版审查树脚本逐字节一致，SHA256：`aab24c20e6b11277a3358640dbba1da6afcd384683dbced8dbae086cf6ba8eb6`。
- 指定三个测试文件：**67 passed / 4 skipped，exit 0**。使用 `FWP_TEST_RECEIPT=0`、`PYTHONDONTWRITEBYTECODE=1` 和 `-p no:cacheprovider`，避免写宿主收据及缓存。
- 独立补充配对断言：**13 项，7 通过、6 失败**。以下实际结果均来自纯分类器执行。

| 旧问题 | 本轮状态 |
|---|---|
| F1 强保护互相干扰 | 原反例通过；反向容器嵌套仍失败，见新 N1 |
| F2 长文复核绕过 | 原反例通过；编号开头的长文仍绕过，见 N2 |
| F3 前提识别遗漏 | 原 A8、虚构声明通过；相邻形式仍遗漏，见 N3/N4 |
| F4 未闭合引号同句禁令 | 原禁令、续轮、假设及闭合对照通过 |
| F5 完整题文丢失 | 原长续行、引用续行通过；引用内部空行仍失败，见 N5 |
| F6 引导块独立指令终点 | 原无“请”的三种状态指令通过 |

以下输入用 JSON 字符串表示，`\n` 表示真实换行；均为完整输入。

1. **N1 · P1：闭合引号内的围栏破坏外层保护，引用中的放宽被确认为消息指令。**

   输入：`"「\n```\nx\n```\n\n可以查真实数据。\n\n」"`

   实际：`constraint_confirmed`，产生 message 级 `constraint_b("可以查真实数据")`，无歧义原因。预期：`no_constraint_confirmed`、零指令，符合 D1 强保护及 A2/A17。去掉内部围栏即通过。原因是围栏屏障无条件清空外层引号栈：[user_task.py:605](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/user_task.py:605)。

2. **N2 · P1：编号材料标题含“说明”即可跳过长文复核。**

   输入：`"1. 行业空间说明\n甲公司去年总收入20亿元，相关业务收入2亿元，处于行业扩产周期。\n不要联网。\n2. 风险说明\n客户验收周期不确定。"`

   实际：`constraint_confirmed`，两道伪子题，禁令归 `q1`。预期：长文候选中的状态操作归属不明，应 `boundary_uncertain`，不能确认为题内指令。依据 D1 内容复核及 A13；标题里的“说明”不足以证明这是提问。移除首行编号并改为“行业空间”即正确复核。跳过位置：[user_task.py:729](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/user_task.py:729)。

3. **N3 · P1：内容复核漏掉带“本轮”前缀的明确禁令。**

   输入：`"材料如下：\n本轮不要联网。"`

   实际：`no_constraint_confirmed`、零指令、零原因。预期：`boundary_uncertain`；D1/A17 要求候选材料中的疑似禁令进入复核失败分支。删除“本轮”即正确。共享检测器只接受有限句首，导致复核与指令识别一起漏判：[user_task.py:544](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/user_task.py:544)。

4. **N4 · P2：假设词后的普通空格导致 A8 前提消失。**

   输入：`"假设 甲公司明年订单翻倍，结合当前行情分析。"`

   实际：`constraint_confirmed`，但只有 B 轴放宽片段；假设完全不在指令输出中。预期：同时保留 message 级 `premise_declaration` 和 `constraint_b`，依据 D2/A8。删除该空格即通过。根因是要求“假设”之后立刻为非空白字符：[user_task.py:492](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/user_task.py:492)。

5. **N5 · P2：题内闭合引用中的空行使整个题组消失。**

   输入：`"1. 请计算比例。\n「总收入10亿元。\n\n业务收入2亿元。」\n\n2. 哪些风险未确认？"`

   实际：`sub_questions=()`。预期：两题，第一题完整保留引用及内部空行，符合 D1/A1；只删除引用内部空行即可恢复两题。续行扫描把保护容器内部空行当成题目结束，随后连续编号验证失败：[user_task.py:772](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/user_task.py:772)。

6. **N6 · P2：题级 B 轴短语直接得到已确认分类。**

   输入：`"1. 请不要联网。"`

   实际：`constraint_confirmed`，`constraint_b` 的 scope 为 `q1`。预期：`boundary_uncertain`。D2 明定题级 B 短语进入歧义态；此输入没有 §3.7.3 所述“消息级已 material_only”的例外条件。题级片段最终无区别触发确认：[user_task.py:853](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/user_task.py:853)。这是分类结果偏差，不是要求本阶段实现权限执行。

另已检查同类/异类引号、反斜杠奇偶转义、长续行、状态短语的材料/引用/消息/题内角色及同句 A/B。对“单个片段同时含 A/B，但原文仍完整保留”的情况，尚不能证明后续必然遗漏，因此未列 finding。

未修改实现或探针，未提交、推送、合并、部署，未调用其他 agent、金融推理或外部数据 API，未接触生产用户目录。**旧回归已绿，但上述 D1 合同偏差仍阻止放行；不对 P2–P7 产品行为作结论。**