# 在途：输入与底座验收（接手收尾 L3）
## 当前状态
已前向 gitea/main 34dd58468（#939 capital_data 与记忆授权冲突按意图两段保留）。接手复核 PASS_WITH_LIMITS：F1 开口记忆绕过截止日、F2 纠错门把追问写成纠偏，已由 7e6aa4bab 修，8760f8d9f 钉住「当前截止下无日期旧笔记仍交付」。PR 为 WIP，等协调者合并预览四叶。
## 运行时变化与默认
- 主体研究题自动授权 memory_lookup + 开口预取（有身份即默认开，1s/2槽）+ 可选 prior_recall；记忆只能绑 user_premise。
- Workbench 纠错写侧默认开（真实身份），写 corrections.jsonl。
- 视角实验字段 signal_match_rules 运行时拒收。
- daily ops ledger 缺清单记 WARN 不记 PASS。
## 下一步
1. 协调者合并预览跑四叶后去 WIP 合入。
2. 待用户拍板：记忆预取是否默认开/加长度上限；§5.2 独立「应该是/应为/不是A是B」是否要求否定词或指代；多用户前纠错写侧先鉴权。
## 已验证
6d9a22bed 定向 114 文件 3545P、宽定向 259 文件 7113P/10S；8760f8d9f 关键四文件 100P、ruff 绿；撤保护 13 条全红、恢复回绿。证据：~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/L3/（review.md、mutation-results.json、probe-*.txt）。
## 未验证
全仓 pytest、前端/e2e、live 8792/8796、真实模型采纳与金融质量；SPT/风远与 #76 仍归原 owner。
