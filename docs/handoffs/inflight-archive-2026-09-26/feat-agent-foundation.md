# feat/agent-foundation

## 这个分支做什么

Agent开发基线与六图确定性纠错。代码候选03af215e092c已通过Gitea #907快进合入main，未部署。
本页来自#908归档分支，接替代码枝原先过期交接；历史过程见日期快照。

## 决策与被否方案

沿用pip/pnpm锁和既有门禁，否升级共享venv/全量容器化：控制副作用。
开发锁与CI同源，否临时补包：新环境要能复现。
经Gitea API快进合并，否额外生成合并SHA后沿用旧收据：让入主干的提交就是受测提交。
细节见 `docs/handoffs/2026-09-24-agent-foundation-merge.md`。

## 当前状态

用户原话“你按照最优推进，合并”，授权合入本批，不含部署。
#907已回读merged=true、main=03af215e092c；本地原脏主树未切换。
#908、Harness #16、Memory #4的实时状态查Gitea或worktree_board，不手抄在此。
本批合入回读原件在 `~/.finance-runtime/reviews/agent-foundation-0924/merge/`。
Node22来自独立npm缓存，代码树venv按开发锁安装；未替换全局工具链。

## 已验证

03af完整Python15363P/88S/2X、收集15453；Ruff、前端120P、E2E34P/2S、lint/typecheck/build及registry通过。
03af收据完整范围/同SHA/干净树/解释器/依赖核对通过；#907快进后main与受测SHA相同。
原件归档 `docs/verification/2026-09-24-agent-foundation-gates/`，仅证03af，不签后续文档SHA。

## 未验证 / 已知边界

新提交的门禁读最新 `~/.finance-runtime/reviews/agent-foundation-0924/merge/acceptance/` 收据，以存在、完成、exit0、同SHA为准；没有这些条件就不是通过。
未验真实模型研究质量、生产数据/效果、新机器整栈、六图全文语义。ledger反向既有warning不等于修复。

## 下一步

核对Gitea回读和main精确收据；不再沿用旧交接的Node26阻塞结论。部署需另行授权。

## 踩过的坑

坏本地环境不得静默借共享环境；代码dirty不能报地图ready；检索满额也要留符号别名容量。
收据版本变化不是文字改名；只快进且主干未变时才能保持受测SHA。复用既有工具，未新增执行框架。
