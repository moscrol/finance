# feat/adaptive-research-loop

## 这个分支做什么
让模型自定研究视角、随取证修订；复用 PLAN/进展账，不写死股票池。工作树 `~/finance-worktrees/adaptive-research-loop`。

## 决策与被否方案
- 默认 `WORKBENCH_ADAPTIVE_RESEARCH=off`；否固定池/必查表，避免把单题分叉变成通用路径。
- 复用 PLAN；否另建 ResearchState 真本。deep/max 首批后无视角时只请求一次计划复核，原预算不增。
- 兼容单个 JSON 对象/代码框及普通尾部说明；对象字段、权限仍严验，不提取前置文字中的对象。
- 自报 supported 不授完成；引用诊断按提交时冻结，否事后追认。
- 展开与失败原件指针：`docs/handoffs/2026-09-20-adaptive-research-loop.md`。

## 当前状态
业务已提交 `469ba766`。未 push/PR/合 main/部署，默认关；8792 健康且仍为 bf662e93。本任务旁车与兼容代理均已关闭。没有其他人的代码改动混入此树。

## 已验证
干净业务提交完整 Python：11970 passed / 85 skipped / 2 xfailed；收据 `~/.finance-runtime/test-receipts/20260920T150621Z-469ba766.json`。Ruff 与全部提交门禁过。
3 组 K3 off/on + 1 次 on-only：前三组未接收 PLAN；最终单臂接收5视角并回传，0 非法动作、4模型/7工具、333.47秒。只有 revision=1。
原件 `~/.finance-runtime/adaptive-research-20260920/`，262文件封存；单臂指纹与业务提交相同。compare/inspect 已入 scripts。

## 未验证 / 已知边界
同一开发题、每版 n=1、作者自审、数据未冻结；最后单臂没有同版本 baseline，不证明质量/速度改善。未见观察后 revision=2 改向；公开稿仍漏内部部分未核验边界。max 档简单事实题也可能多一轮。
四道留出题、独立 Spec/Quality、前端/E2E 与合流验收未跑，不可合入。

## 下一步
先跑 `adaptive-perspectives.questions.json` 留出题，独立审实际改向、反证及公开缺口；同 revision 重复并交替双臂顺序。合并/更新8792须用户确认及全套门禁，勿用旧 baseline 配最终单臂。

## 踩过的坑
可选 PLAN 被忽略；代码框、引用数组超限、尾部说明各自造成拒收。字段约束必须送给模型，包装兼容不能放宽对象权限。用私有 durable events 看首失效点，公开投影不含完整提示词。旧失败不改判，不代写答案、不补名单。
可迁移经验已回共享闭环笔记；harness-reference 脏，本轮未动。
