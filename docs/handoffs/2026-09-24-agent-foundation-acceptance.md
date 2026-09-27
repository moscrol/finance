# Agent 开发基线：前向同步与完整工程验收

## 背景与顺序

用户授权继续推进，目标是补齐上一轮缺失的合入前工程证据，不包含合主干和部署授权。
原代码候选df9f7bee0已定向通过，但落后主干21个提交，前端Node26不符合同22。

1. 三个候选树均干净。Finance把gitea/main@4cc15e703f81合进候选，产生a4878b130，保留主干新加入的完整pytest日志机制。
2. Memory同步主干；项目交接索引发生并发插入冲突，核对双方提交后保留所有记录，不涉及行为取舍。Harness基座未落后。
3. 通过npm独立缓存准备Node22.23.3，沿用pnpm10.12.1；未改全局Node26。安装冻结前端依赖与对应Playwright Chromium。
4. 原最小开发锁全量收集出现10处缺包错误（numpy/pandas/Markdown），不是测试断言失败。按现有全仓测试使用版本补数据变换、渲染及传递依赖，不装实时采集客户端。
5. CI Python/E2E原本仍单独装DuckDB1.4.3等；改为共用requirements-dev.lock，新增解析YAML的契约测试，避免二次漂移。85项入口/门禁相关回归通过，pip check通过。
6. 固定03af215e092cf0da25f3c7e8f60256cb60c2836e，独占代码树执行完整门禁；清理launcher变量、不传模型凭证，前端使用独立端口19881/19884与夹具数据。
7. 完整Python15363P/88S/2X、零失败/错误；前端组件120P、E2E34P/2S；Ruff、前端lint/typecheck/build、注册表、ledger正向及runtime目录通过。ledger反向98条既有warning保留。
8. Python收据再次以require-full-scope、expect-revision和base-drift-max=0验证通过。收尾fetch后代码基座仍未落后。两项离线smoke在03af再次通过，doctor含前端ready。
9. 推送代码与两个共享文档分支，建立Finance #907、Harness #16、Memory #4，保留WIP保护。为不移动受测代码头，归档另开docs/agent-foundation-closeout。

## 取舍

| 选择 | 否决的替代方案 | 理由 |
|---|---|---|
| 合并主干进入候选 | 重写上一轮提交 | 保留已有验证历史与图谱固定提交引用 |
| 完整开发锁与CI共用 | 只往本机venv临时补包 | 下一棵新树和CI也须能复现 |
| Node22独立缓存 | 替换全局Node | 不影响其他agent、服务和工作树 |
| 固定代码SHA，交接单独分支 | 文档提交后仍称旧收据证明当前HEAD | 版本身份是收据合同的一部分；另分支显式保留边界 |
| WIP待用户裁决 | 工程绿即合并/部署 | 没有授权，工程证据也不等于生产效果 |

## 证据与后续

完整原件映射、哈希与校验命令在 `docs/verification/2026-09-24-agent-foundation-gates/README.md`。
原件根 `~/.finance-runtime/reviews/agent-foundation-0924/round-01/`；Python完整门禁约23分31秒，没缩面或拼接定向结果。
本归档分支没有完整工程签字；不得拿03af收据签后来合并版本。用户确认后固定实际合并预览，按门禁规程复验再合入。
真实模型、新机器整栈、生产库准确性、线上效果以及六图全文语义审计未做。
本轮未新增通用执行工具；复用workspace、run_main_gate、run_frontend_gate与原有审计器。开发锁及CI同源模式已在共享工具包登记，不另建清单。
