固定复审 revision：`8d1b35735a128742f53c3114fd06baa46b182bdc`，工作树最终 clean。按 v10 设计稿 D1/D2/D3 复审，范围仅限 P2 载体/投影。

实际测试：

- 指定 11 个测试文件：`332 passed, 4 skipped, 0 failed`
- `scripts/e2_boundary_review_probe.py --repo .`：`46 passed, 0 failed`
- 独立 35 例（5 种连接词 × 7 种前缀）：`35/35` 通过
- 另测相邻顺序、空白变体、嵌套引用、内容复核反例：全部符合预期
- `state_unavailable` 携带伪造轴值被拒绝
- 原 T2/T3 八题题文完整保留并通过
- 显式 `结合当前行情` 得 `full + data_scope_declared=True`；无显式 B 约束的默认 full 保持 `False`

既有 finding：

1. “连接词 + 礼貌前缀导致 B 轴丢失”：**关闭**。35 例均正确得到 `fictional × local_only`，且 `data_scope_declared=True`。
2. `state_unavailable` 恢复为伪造 `real × full`：**关闭**。反序列化现明确拒绝 resolved axes。

新 verified finding：**无**。独立复核通过。

结论：**P2 载体及投影阶段通过**。本结论不延伸至尚未接入的 P3 授权预取注入与 P5 可信基底，也不构成产品安全放行。