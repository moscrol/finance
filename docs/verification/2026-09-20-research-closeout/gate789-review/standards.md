规范轴通过：硬违规 0，需报的 possible smell 0。固定 `4ace5ec2...c8dbd387`。

依据 `AGENTS.md`「Git 与合并」、`acceptance-workflow.md` §1/§3、`test-environment.json`：身份失败、非零命令、脏树、提交变化及重复输出均拒绝通过。独立复验原测试 10P，新增离线边界 5P；抽核 #795/#796 首尾身份及 12 份日志哈希一致。未跑全量、未改候选。

非阻断边界：身份查询继承宿主 `GIT_DIR`，可与子进程所用树分离；文档 §1 已要求 `env -i`，故不列为合同内违规。直接启动须保持该前提，后续可在身份查询内清理 Git 环境变量。

详证：`standards-details.md`、`standards-probes/boundary-results.json`。
