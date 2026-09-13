# docs/qc-re06-957e83f4 · 2026-09-14 · 第四轮质检退修

## 这个分支做什么

独立复审 RE06 第三轮返修：候选 b481804c（代码 957e83f4）。只加质检证据，不改运行代码。

## 决策与被否方案

- 退修：U1 普通聊天误认领、U2 两待复核快速终态无法挂接、U4 旧判断被新请求误用（3 P1）；U3 全局终态重放绕会话闸（P2）。
- 否了“唯一待办=消息意图”：唯一性不是因果证明；否了“显式 link_run 可恢复”：终态后实际上 400。
- 保留执行前登记、代际隔离和版本闸前重放方向，但身份要穿过消息、run、成果、重放全部接缝。
- 全文 `docs/verification/re06-957e83f4/REVIEW.md`；决策快照 `docs/handoffs/2026-09-14-re06-round4-qc.md`。

## 当前状态

- 证据已提交 `4b09d38a`。工作树 `/private/tmp/re06-qc-957e83f4`。
- 未改执行方树或主检出目录；未合并、未部署。等待执行方返修 U1–U4。

## 已验证

- 既有研究进化套件+两轮探针 110 passed（干净 b481804c 收据 `20260913T190008Z-b481804c.json`）。
- 新正确合同四探针重复两次 4 failed，详见 `probes*.txt`。
- 全仓 Ruff；前端 lint/typecheck/build 通过；Vitest 90 passed；全套 E2E 31 passed/2 skipped。
- 注册表四检查绿；台账对账 exit 0（96 个既有反向 warning）。原始日志都在 REVIEW 同目录。

## 未验证 / 已知边界

- 本轮不跑全仓 pytest；执行方 10034 收据是 dirty=true 且忽略 test_codex_sandbox.py，不可称本轮干净提交全量。
- API 探针为合成用户+确定性执行器；旧判断由真实 writer 模拟 A 晚写，未跑真实模型输出质量。跨会话重放仅同 owner、零新增迁移，非跨用户泄漏。
- 真绑定 E2E 只跑 desktop，两跳过为既有非 desktop 配置。

## 下一步

将 REVIEW 的 U1–U4 与 test_review_round4.py 交执行方。修后四针应绿，原 110 条不得回退，再验干净候选组合门禁；需用户确认才合。

## 踩过的坑

- 多维护项可用现有 CONDITION_DOWNGRADE + 证据变化直接造，不必 mock 域函数。
- 自定义 E2E 端口同时设 RE06_E2E_PORT 与 RE06_E2E_URL；首轮漏 URL 的连接失败已保留，纠正后全套重跑。
- 上轮 test_review_contracts.py 在 `~/.finance-runtime/reviews/research-evolution-06-ba10747d/`，不在候选 docs 下。
