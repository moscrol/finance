# 续验勘误与证据边界

- 先前 handoff 提交 `4cf5a33ad0ea017da330533f1e284bc4d91041e8` 完成后磁盘恢复，本轮重新启动验证；旧 b1/f7 归档、资源阻塞和旧 K3 未通过记录不改。
- `4cf5a33ad` 全量 pytest 实际结果 12591 passed / 2 failed / 87 skipped / 2 xfailed，Ruff 0；精确收据 `20260921T181909Z-4cf5a33a.json`。失败不是两条既存红：开关板遗漏 local_market_snapshot 是本任务注册同步遗漏；代码地图空结果可由运行器缩窄 PATH 单独触发。
- 初次查看错误路径 `intelligence/eval/capability_switchboard.py` 和不存在的 `test_capability_switchboard_runner.py` 返回 rg exit 2；实际实现位于 services，测试见 test_capability_switchboard.py。没有把搜索失败当不存在的架构结论。
- 地图刷新后仍能在旧 PATH 复现 0 命中，PATH 中可见已安装 uvx 后为 20 命中；见 environment-probe.json。不是仅凭 stale 状态归因。运行器改用工作流规定的 PATH 白名单值，并记录 KNOWLEDGE_WIKI 是否传入；不继承所有宿主环境。
- 新增移除快照授权测试的首版只改 allowed_capabilities，未同步 required_outputs，合同正确拒绝，开发检查 1F/92P/3S。修正合法测试构造后 93P/3S。两份 JUnit 与精确脏树收据保留；不作为干净候选全量证据。
- `53054bfd4336bebd0d570273a58e92758fb623be` 只补开关板行、再生默认盒以及一个菜单撤授权测试，不更改前轮产品实现；新树 `2aa8e01864722bd6a659a672e9cd76813f398eeb`。
- “完整 Python 已启动”指运行器已启动，不代表 pytest 已启动：本轮启动时发现其他任务 pytest pid 18535/31128，resource-wait.jsonl 和 checks=[] 记录等待。未终止他人进程。
- 本轮 Spec / Quality 正式调用均 exit 1，usage limit，未生成 verdict.md；启动与模型身份信息不算审查结论。不改账号/计费策略绕过限制。
- 新撤授权测试额外反证分两份：switch_mutation.py 只撤装配条件，baseline/mutant 均 1P，caught=false；源码另有 local_only 返回前最终合同过滤，不能把存活算漏洞或捕获。switch_mutation_v2.py 在同函数进程内同时撤这两处，baseline 1P、mutant 1F、errors=0，最终菜单断言抓住越权。原24项结果独立保持24/24，不把这三类读数伪加总。
- 新 K3 未启动：独立审查没有完成，不能越过准入。没有访问或切换 8792；没有补采、回填、生产写库、push、PR 或合并。
- 私有 episode durable 日志可包含完整 prompt，后续真实验收须核实际写出的日志与 hash；本轮只读源码发现这一入口，不补签旧 K3 完整首轮 prompt 已采集。
