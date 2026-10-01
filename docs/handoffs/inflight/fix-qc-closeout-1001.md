# fix/qc-closeout-1001

- 用户授权推进质检收口，未授权合 main 或切生产；PR #8 不动。
- 独立工作树基于 PR #10 的 `983590438`，包含另一会话新加的默认关闭语义记忆；不覆盖原 PR 分支。
- 已实现：模型准入递归父子、缺分支 fail closed、2×2 analyze 自动重算；A/B 重放失败/范围不齐不再 exit 0；报告勘误；7 条修复事后正式入账。
- 实测：952/966 份真实存证重放成功，14 失败；成功部分新增0/消失0，不得宣称全量 A/B 通过。
- 冒烟阻塞：旧 ReAct 控制台不调模型，抽样 session 无 served_model；未调用付费模型，未启动240次。
- 开发直接回归102过；最终提交的独立收据看 `~/.finance-runtime/qc-closeout-20261001/final-*`，不能引用旧/脏树读数当全量。
- 详细交接：`docs/handoffs/2026-10-01-qc-closeout-progress.md`。
