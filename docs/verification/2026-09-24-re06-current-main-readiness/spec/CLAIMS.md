# Current Candidate Claims

Revision `b027194f1039692b8c26cacf9310619d633c54b7`，base
`3bb81b9638f97b4773ce0f338df3a505b7c0162f`。
均为作者主张，不是通过结论；详细源码定位见[冻结输入](../archives/qc-k3-04/inputs/claims.md)。

| ID | 主张 | 当前独审状态 |
|---|---|---|
| C1 | local_only按原题号冻结answer_qN，来源绑定不掩盖缺答题正文 | not_verified |
| C2 | material_only零读取与legal_gap不放宽local_only义务 | not_verified |
| C3 | 旧契约恢复保护已有题号；未编号和full模式不强制改形 | not_verified |
| C4 | 读写共享折叠，保留无记录/参与者/坏时间戳差异 | not_verified |
| C5 | 同时刻撤回优先，未来记录不提前生效，按事件时刻复核 | not_verified |
| C6 | 锁内复核拦TOCTOU，门关闭不争锁，三类自动测量事件共用门 | not_verified |
| C7 | 计时授权/停止/切会话/离页使用activity-timer与v2，发布资产一致 | not_verified |
| C8 | 纯计时不是测量意愿，空/部分/混合scope不误回落默认 | not_verified |
| C9 | 旧v1仅完整原控件自用形状对称读取兼容 | not_verified |
| C10 | 重新计时不覆盖真实撤回，不授予试点测量，不改原事件/content_hash | not_verified |

Quality独立轴未评估。14文件语法、18事务点枚举和宿主边界预检不签上述主张。
