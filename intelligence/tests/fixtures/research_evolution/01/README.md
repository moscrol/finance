# 研究进化 01 · 判断持续维护 · 合同夹具

合同版本 `judgment-maintenance/v1`（`intelligence/services/judgment_maintenance/contracts.py`）。
全部夹具 **synthetic**：只作工程验收，不得据此宣称任何真实用户效果、方法支持或付费状态。
04 用同一份 JSON 并行开发，06 用它做边界适配的合同测试；字段调整先改这里再改提供方 / 消费者。

| 目录 | 内容 | 覆盖的反向验收（spec 01 §8） |
|---|---|---|
| `complete/` | 三条依赖：哈希变（content_changed）、未变（不出项只计覆盖）、撤回后被替代（source_expired → source_corrected 项链）；两条确定性条件（true / false） | 1、3、5、6 |
| `missing_source/` | 一条依赖截止日无版本（ref_unresolved）、一条条件无观测（condition_unknown） | 4、5 |
| `legacy/` | 树只存 ref 无 hash（dependency_unbound）、存量判断无 id 且版本缺时间元数据（time_metadata_missing）、绑定晚于市场日（binding_not_yet_effective） | 2、8 |
| `actions/` | 在 `complete` 报告上按步执行命令与系统事件：重放、同键异载荷、旧 revision、旧源版本、核对关闭、终态拒绝、重判失败 / 跨 owner 关联 / 关联成功、snooze 到期恢复 | 9、10 |

每个目录 `input.json` 是 `assess()` 的完整入参（`actions/input.json` 是步骤脚本），`expected.json` 是冻结输出。
`expected.json` 由测试从真实函数生成后冻结，比对时忽略 `generated_at` 以外的任何字段都不允许漂移；
需要重新生成时（只在合同或判定规则**有意**变更后）：

```bash
JM_FIXTURES_UPDATE=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_judgment_maintenance_assess.py intelligence/tests/test_judgment_maintenance_actions.py
```

再把 diff 与规则变更一起送审——夹具漂了却没有对应的规则变更，就是回归。
