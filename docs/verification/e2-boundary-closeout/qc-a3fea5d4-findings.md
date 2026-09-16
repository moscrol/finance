固定 revision：`a3fea5d4f74d0c0f7031c56e3a250a8baa79a76d`。复审前后均 clean、detached HEAD；已审 `85a20eb2..HEAD`。**P2 仍不通过：发现 1 项已验证的同类残留。**

旧两项 finding：

1. **多轴丢失：部分修复，尚不能关闭。** 原输入已通过，但既有指令前缀与连接词组合仍丢失 B 轴，见下。
2. **坏状态恢复：关闭。** `state_unavailable` 携带任一非空轴均抛 `ValueError`；经 `TaskFrame.from_dict` 恢复返回 `None`；合法空轴恢复保持未知。实现见 [material_contract.py:67](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/material_contract.py:67)。

新增 verified finding（旧 finding 1 的残留，不重复计数）：

- **输入**：`假设甲公司订单翻倍成立且麻烦不要联网。`
- **实际**：`constraint_confirmed / fictional × full / data_scope_declared=False`。
- **预期**：`fictional × local_only / data_scope_declared=True`。
- **对照**：将“且”改为逗号，或删除“麻烦”，均正确。
- **原因/行号**：[user_task.py:493](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/user_task.py:493) 的连接词切分前缀遗漏“麻烦／烦请”，但既有 [指令前缀规则:530](/Users/a77/fwp-wt-e2-closeout-qc/intelligence/services/user_task.py:530) 接受它们，导致显式禁令未进入 B 轴解释。
- **条款**：v10 §3.1 D1 顶层限定指令识别、§3.2 D2 双轴独立及“不要联网 → local_only”映射。
- **复现范围**：5 种连接词 × 7 种前缀，35 例中 10 例失败，均为“麻烦／烦请”组合。

实际验证：

- 指定解释器、`FWP_TEST_RECEIPT=0`，指定 11 个测试文件：**297 passed，4 skipped，0 failed**。
- 原边界探针：**46 passed，0 failed**。
- 独立相邻探针：上述组合 **25 通过、10 失败**；另 **12 项对照全部通过**，覆盖引用屏障、坏状态恢复、原编号及完整题文与材料分离、序列化往返、显式权限与默认权限的投影区别。
- 纯条件推理的旧 `evidence_free` 路径保持可用，没有将默认 `full` 误判为必须外呼；普通研究追问不被 P2 强制转澄清的回归测试通过。

结论仅限 **P2 载体及投影**。未将后续未接线项列为缺陷，也不作产品安全放行：门页已明确本阶段材料题不能据此安全实跑。

全程只读，未修改应用、调用金融 API、操作生产用户态或其他 agent，未合并、推送、部署。报告正文供宿主 `-o` 保存。