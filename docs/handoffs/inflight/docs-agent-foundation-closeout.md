# docs/agent-foundation-closeout

## 这个分支做什么

归档 Agent 开发基线固定候选的完整工程验收，接替旧交接；不移动受测代码分支。

## 决策与被否方案

代码候选固定03af215e092c、文档另分支；否把交接提交后的HEAD冒充原收据版本。
归档原件与SHA-256，而非仅转述通过数字；使用既有门禁，没有新增运行框架。

## 当前状态

基于Finance #907受测代码03af215e092c。新增验收快照与证据，更新该代码分支的交接副本。
代码/共享文档PR #907、Harness #16、Memory #4均WIP，未合主干、未部署。
背景见 `docs/handoffs/2026-09-24-agent-foundation-acceptance.md`。

## 已验证

受测代码完整Python15363P/88S/2X、Ruff通过；前端120P、E2E34P/2S、lint/typecheck/build及注册表通过。
收据仅对代码03af215e092c成立；证据及哈希见 `docs/verification/2026-09-24-agent-foundation-gates/README.md`。
本分支只做文档/原件归档检查，不把代码收据改成此分支SHA。

## 未验证 / 已知边界

本分支及未来合并版本没有完整四叶签字；真实模型、生产数据/效果、新机器整栈未验。
旧主树detached且有他人改动，不要切回主树验或覆盖其文件。

## 下一步

用户确认合入范围后，对固定合并预览版本跑门禁再合入；WIP保护暂保留。
代码树 `~/fwp-wt-agent-foundation` 保持干净、代码SHA不移动；此树 `~/fwp-wt-agent-foundation-closeout` 仅交接。

## 踩过的坑

文档提交也是新SHA；运行代码相同不等于旧收据验证过新提交。
全量日志已保留，临时pytest目录由既有门禁在成功后清理。没有待跑进程。
