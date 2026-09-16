固定 revision：`85a20eb25782ab0d94520b7a81d912a7b428d1ad`  
工作树：clean（`git status --short` 无输出），detached HEAD。  
解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，`FWP_TEST_RECEIPT=0`。

执行证据：

- `test_e2_material_contract.py`、原 D1 相关测试及 `test_task_frame`、`test_query_understanding`、`test_episode_factory`：`276 passed, 4 skipped, 0 failed`
- `scripts/e2_boundary_review_probe.py --repo ...`：`46 passed, 0 failed`
- 未调用金融 API、生产用户态；未修改文件、未提交或推送。

Findings：

1. **P2 双轴单片段没有完整解释，B 轴会丢失。**

   - 输入：`假设甲公司订单翻倍成立且不要联网。`
   - 实际：`authenticity=fictional, data_scope=full`
   - 预期：`fictional × local_only`
   - 条款：设计稿 §3.2 要求 A/B 轴独立；显式“不要联网”应设置 B=`local_only`。
   - 原因/行号：[user_task.py:562-569](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/user_task.py:562) 对单句只返回一种 `kind`；[material_contract.py:125-142](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/material_contract.py:125) 只按已生成的单一 instruction span 解释，因此同一片段中的第二个轴不会进入合同。

2. **`state_unavailable` 反序列化允许伪造已确定的 `real×full`，违反续轮保守语义。**

   - 输入：`MaterialContract.from_dict({"classification":"state_unavailable","authenticity":"real","data_scope":"full"})`
   - 实际：成功恢复该合同。
   - 预期：拒绝恢复，或强制两个轴均为 `None`；不可从不可用基底猜测默认权限。
   - 条款：设计稿 §3.2、§3.7 要求续轮基底不可恢复时保持 `state_unavailable`，禁止静默回 `real×full`。
   - 行号：[material_contract.py:61-66](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/material_contract.py:61) 仅对 confirmed 状态校验非空，未约束 `state_unavailable` 的轴值。

阶段结论：**P2 不通过，存在 2 个实现缺陷。** A8 的 `fictional×full` 反例、引用内虚构/放宽隔离、完整题组接 legacy question、普通问答旧 hash、材料与题文分离、反事实事实槽仍走 evidence 等检查均通过。