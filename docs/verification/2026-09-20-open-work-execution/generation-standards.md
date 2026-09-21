# Standards：生成根 387028b8

冻结树 `/Users/a77/fwp-wt-generation-root-guards-validation`：复核前后均干净，HEAD 为 `387028b846a21a1327d964af8c4b428367f88fcf`。

固定比较：`git diff 1fef3d276d0e251158803fc09d5a81e60d79241b...387028b846a21a1327d964af8c4b428367f88fcf`。提交依次为 `4fbc8c42`、`07d42891`、`2f82d4d3`、`0f6c2810`、`9b974691`、`387028b8`；覆盖全部 34 个差异文件。

规范源：冻结版本的 `AGENTS.md`、`docs/agent-product-door.md`、`test-environment.json`，以及用户附件。未找到额外 CONTRIBUTING/CODING_STANDARDS；Fowler smell 仅作启发式。

## 硬违规：1 项 P2

**S1：失败告警的既有写入目标漏过路径守卫。**

- 新增遗漏点：`intelligence/workflows/generation_paths.py:73` 的 `targets`（至 85 行）没有告警日志。
- 规范原句：`docs/agent-product-door.md:38`：“写入位置落进代码根时拒绝生成”；`:44`：“已有子目录/文件软链指入代码根也拒绝”。
- 静态证据：`intelligence/workflows/daily_review.py:404–419` 在默认启用告警时将 FAIL 传给 `send_alert`；`scripts/notify_ops.py:29,34–36` 对 `$HOME/.finance-runtime/alerts.log` 执行 `mkdir` 和追加。若启动前该日志软链已指向 CODE，其他已枚举路径合法时预检仍放行；随后一个普通质量门失败即可改写代码快照。`--no-alert` 测试不会触发此分支。
- 这是现有 writer 的静态路径遗漏，非运行期间换链，亦非新增写入或外部 KB 接收器；门页 46 行的边界声明不涵盖它。
- 建议：启用告警时在副作用前校验实际 `ALERT_LOG`，加入失败路径的原样反例，断言快照字节不变且告警开关仍有效。

## 启发式建议：0 项

未把独立脚本必要的 import 引导重复、已有合同或工具强制格式项报成 smell。计划档位、子进程代码根、摘要参数单次解析、用户态/episode/日期目录/增量输出的显式守卫及 L2 环境隔离已逐项静态核对。

本轴只做只读源码审查，未跑全量测试或生产调用；S1 的运行实证由根代理另行组织，不冒称已在生产发生。结论是守卫候选需要补此边界；保留唯一守卫源码线和 L2 独立根，不回滚到缺守卫的 main。
