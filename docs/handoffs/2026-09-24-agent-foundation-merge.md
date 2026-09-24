# Agent开发基线：授权合入与精确版本策略

## 背景

用户在四张PR及完整工程验收汇报后原话授权：“你按照最优推进，合并”。范围为Finance #907/#908、Harness #16、Memory #4，不含生产部署。
上轮03af215e092c已有完整四叶证据；归档fd4e59b5e另分支，不能直接借旧收据合入。

## 已发生的动作

1. 重新fetch三个仓。Finance main仍4cc15e703f81，无新增运行代码；Harness无落后；Memory主干新增并发记录。
2. 复核03af的Python完整收据与前端/E2E/registry身份，全部成立。merge-tree无冲突，树与候选相同。
3. 实际Gitea仓配置允许fast-forward-only，当前swagger也列出该合并动作。不修改仓设置，不绕开API。
4. 用户授权后解除#907的WIP，调用现有gitea_pr.cmd_merge传平台原生fast-forward-only动作。回读merged=true、main=03af215e092c，正是受测SHA。分支未删除，保留后续堆叠单。
5. #908接替为main目标，更新活交接，保留上一轮归档原件不改。最终合入以固定候选的新门禁和API回读为准，不提前记为完成。

#907授权与回读原件已存在：`~/.finance-runtime/reviews/agent-foundation-0924/merge/finance-907.json`。
后续产物目录 `~/.finance-runtime/reviews/agent-foundation-0924/merge/acceptance/`；有文件不等于通过，要核完成、退出码、干净树与精确提交。

## 方案对比

| 方案 | 取舍 |
|---|---|
| 直接推main或绕过平台 | 否决；使用正式PR接口保留授权、预览与回读 |
| 默认merge产生新提交，再拿旧SHA收据签字 | 否决；提交身份不成立 |
| 平台fast-forward-only | 采用；主干必须是候选祖先，保留全部已有历史，主干直接指向受测提交，无强推 |
| 修改仓设置以强开快进 | 不需要且不做；已核现有配置允许 |
| #908沿用03af测试数字 | 否决；新提交单独全量验，结果以新收据为准 |
| 为每份事后状态再改受测HEAD | 不采用；活交接指向Gitea和树外机器记录，历史快照保留当时边界 |

快进不是跳过验证：若main在测试期间前进，原快进前提失效，必须重新同步/验收。
本地共享脏树不更新，不部署，不触发生产模型或数据写入。全叶通过也不能升级为真实业务效果结论。
