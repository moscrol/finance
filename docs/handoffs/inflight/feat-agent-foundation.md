# feat/agent-foundation

## 这个分支做什么

可重复的 Agent 开发基线与六图确定性纠错。代码树 `~/fwp-wt-agent-foundation`。
本更新在独立 `docs/agent-foundation-closeout` 文档分支，避免移动已验代码候选；代码PR内旧交接由本页接替。

## 决策与被否方案

沿用 pip/pnpm 锁与既有门禁，否升级共享 venv/全量容器化：限制副作用。
开发锁补全仓测试依赖，CI共用；否临时补包装环境齐全。
代码候选固定，验收归档另分支；否用旧SHA收据给新文档/合并SHA签字。
详见 `docs/handoffs/2026-09-24-agent-foundation-acceptance.md`。

## 当前状态

Finance PR #907，代码固定 `03af215e092c`，包含主干 `4cc15e703f81`，四叶工程绿。
Harness #16 / Memory #4 共享文档候选。均 WIP，未合入/未部署；原有脏工作树未动。
Node22使用独立npm缓存，未替换全局Node26。新树venv使用完整开发锁。

## 已验证

Python完整门禁15363P/88S/2X，收集15453，零失败/错误；Ruff通过。
前端安装/lint/typecheck/build通过，组件120P，E2E34P/2S（桌面/平板/手机）。
注册表四项、ledger正向、runtime目录通过；ledger反向98条既有warning保留。
收据确认干净树、同提交/解释器/依赖、全范围，收尾fetch后基座漂移0。
代码图已建；doctor含前端ready、两项离线smoke通过。
原件 `~/.finance-runtime/reviews/agent-foundation-0924/round-01/`；本分支 `docs/verification/2026-09-24-agent-foundation-gates/` 有原件副本与哈希。

## 未验证 / 已知边界

收据仅证明03af215e092c；归档分支及后来合并版本没有完整门禁签字。
未验真实模型/生产效果/新机器整栈/六图全文语义，不能从工程绿升级。

## 下一步

用户确认合入范围；重新fetch并固定合并预览，在该版本跑完整门禁再合入。不得自动去WIP或部署。
接手先读归档README，校验收据revision，不用旧交接数字代替。

## 踩过的坑

新环境收集测试缺numpy/pandas/Markdown，已补锁并接CI。
daily-full字面检索填满结果曾挤掉符号别名，真实建图才暴露，已修。
共享索引并发插入只合并双方记录，不覆盖他人交接。无新运行工具；复用既有门禁/收据。
