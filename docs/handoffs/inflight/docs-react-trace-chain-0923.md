# #81 / #832 在途交接

## 这个分支做什么
文档载体#892；唯一产品#832，仍WIP。产品固定d1b30e1a068ccd0559f091f3c664ca2ca82f1e7c，基线626d8a508；本轮未改产品。

## 当前状态
工程四叶齐绿（附旧E2E时延限制）。用户「推进」后#75有限GLM批49请求（准入4/探查22/执行23），无重试，结论BLOCKED_HARNESS_AND_INCOMPLETE_REPORT；Spec report/Quality未启动，模型及relay已停止。原件根 `~/.finance-runtime/reviews/pr832-glm-qc-20260923-2255/`。
候选原树 `/Users/a77/fwp-wt-react-trace-chain-0923` 和新审查树均同SHA/clean。收口回读远端main已到c9dd71dfd678，未追逐移动头。
文档入口 `docs/verification/2026-09-23-react-trace-chain/README.md`；保留44件工程原件，新增371件独审包及独立MANIFEST。

## 未验证 / 已知边界
执行日志5P/3F仅C5局部，3F止于SQLite夹具建库；C6/七个作者回归未跑，C1-C4未深验。正控与pytest被echo包装，工具exit0不等于子脚本exit1；终稿JSON多引号且EXECUTE.md缺失。不得补签独审。
#76自然金融另授权，旧not_passed不变；旧a140的K3终稿不移签。工程收据不证明与后来main集成。旧E2E3F/2F及尾延迟风险保留，单次main/候选双绿不是稳定性认证；#841归#68。

## 下一步
先把真实测试子进程退出值、结构交付、pytest/SQLite实际操作准入做成机械检查，再另授权新#75批；不自动续预算、不重复工程测试冒充独审。#76仍单独授权；产品头变化需重取工程收据，不合main/部署/生产写入。

## 决策与被否方案
停批后只做零模型工具对照：补两个父目录metadata，不放开内容/写入/网络；控制2P、SQLite成功、必红exit1，越界仍拒。原3探针字节不变宿主复放3P，只算工具诊断，不改原3F或补模型签字。原规则/报告不原地修。
详见 `docs/handoffs/2026-09-23-react-trace-qc-blocked.md`；此前工程对照见同目录 `2026-09-23-react-trace-e2e-control.md`。

## 已验证
同头Python14710P/85S/2X、Ruff/registry通过；固定main/候选前端六步均exit0、120P、E2E34P/2S。新批账本49请求与派发/完成对平，185阶段产物哈希已核。

## 踩过的坑
旧预检靶标不存在不能算权限拒绝；import/touch通过不保证pytest/SQLite可用。零模型控制v1的逃逸符号链接误放收集根也会阻断pytest，失败原件保留。Gitea写后需回读；共享脏树/8792/harness未动，配方只封存未推广。
