<!-- ownership-k3-v4-interrupted-6eb12-pr814 -->
## 无预算K3复审异常中断：BLOCKED，不是独立通过

a092修复的same-target同进程嵌套探针确实保住外层2P收据，但不等于全范围独立终审。源码未改，当前tip仅文档。

被审对象仍为 **6eb12c1b8a41071fd4af8bee343950fe0b85b221**（c615冻结基线），不签后来main。用户“不用给k3设置预算，随便用”已落实为执行器/授权/prompt全部无总时长、请求、token和强制收尾帽；旧v3触帽历史不改。

两路于08:07:40Z启动：Spec于08:40:39.231815Z、Quality于08:40:37.949713Z均exit1，各 **50准入/49完整assistant消息**，均无REPORT/verdict/completion。**50是实测数，不是新限额。** Spec stderr明确 `ENOSPC: no space left on device, write`；Quality stderr为空、几乎同时中断，原因仍未确证。未自动重启、增开会话或切付费路由。

operator QC：首尾及复核时净同SHA/tree/十二源哈希，冻结输入和原输出哈希匹配；75份shell记录完整。Quality现有定向测试 **210P/1S、真实pytest exit0**，receipt关闭、tail后日志非完整stdout；两轴自写探针只有部分覆盖，signal控制未全过。没有确立新的候选产品缺陷，也不能据此宣布无缺陷。原fixture失败/覆盖/删除、错误pipeline退出读数、Quality早期宽泛pkill后才改owned child PID等偏差如实保留；shell无OS沙箱，未作全机旁伤审计。

证据 **[47f80174d](http://127.0.0.1:3300/a77/finance-workspace-private/commit/47f80174d498794383b0f7edd1e73f7d55e1fabe)**：[README](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/47f80174d498794383b0f7edd1e73f7d55e1fabe/docs/verification/2026-09-21-ownership-k3-v4/README.md)、[operator QC](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/47f80174d498794383b0f7edd1e73f7d55e1fabe/docs/verification/2026-09-21-ownership-k3-v4/operator-qc/review-qc.md)、[manifest](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/47f80174d498794383b0f7edd1e73f7d55e1fabe/docs/verification/2026-09-21-ownership-k3-v4/manifest.json)。**819文件/33,027,503字节**（README算、manifest不算），events按原字节分片，拼接哈希一致；成员/原件/提交字节复核通过。首次发布66f848e46受通用tmp忽略规则漏220份文本，已在47f80174d补齐且保留初始失败，不amend原历史；[设施纠正](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/47f80174d498794383b0f7edd1e73f7d55e1fabe/docs/verification/2026-09-21-ownership-k3-v4-publication.md)。七档旧证据与v3/v4固定树不变。

下一步先核磁盘容量与待处理路径归属，再另行确认恢复审查；不得重跑旧launch/run覆盖本轮，也不重新加旧预算。没有合并、部署、生产回填、删除真实树或接管Arena。最新main集成/完整副本发布恢复另验；三单与组合不可重复合。
