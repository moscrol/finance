# 在途交接：#58/#59 门禁证据收口

## 这个分支做什么
区分历史 SHA 收据与 main 验收快照，保留未完成项；本分支只含文档。

## 决策与被否方案
- 用观察时间 + SHA，不再为文档自身 merge SHA 反复开合文档。
- 四叶缺失则 WIP；不借旧收据、不杀他人测试、不再无限轮询。
- 展开见 `docs/handoffs/2026-09-23-main-tip-gate-bbd5.md`。

## 当前状态
文档已提交 `91eacae93` 并推送，PR #886 为 WIP，未合。15:40 CST 最终回读远程 main 已推进到 `27ca084f9ffc`（#856）；本轮未测该 SHA，下面 bbd5 也只作历史证据，续跑先核最新 tip。
本轮固定 `bbd53487f4ce`（09-23 15:32 CST 的远程 main），Python full 与 frontend/E2E 因 load1=15.13 未启动，不能放行合并。文档树在证据根目录 `trees/finance-workspace-private-5f35`，已前向到 bbd5；目录名不代表 HEAD。独占 bbd5 定向测试树已正常移除，树外证据保留。
#881 已留评论 6183 后关闭重复入口；API closed/merged=false，Git merge `4315d9d5` 事实另有核验，不再合一次。

## 已验证
- 文档 `diff --check`、pre-commit 全部适用检查通过；不是四叶。
- bbd5：registry 5/5、定向 74P，正确 SHA exit 0 / 错误 SHA exit 1；归档探针先红、删除后绿。
- 历史 5f35：正式 frontend 六步绿（Vitest 120P、E2E 34P/2S）、registry 5/5；不覆盖 bbd5。
- 证据根 `~/.finance-runtime/reviews/gate-closeout-qc-20260923/`，bbd5 日志在 `main-bbd5/`；74P 收据 `~/.finance-runtime/test-receipts/20260923T063034Z-bbd53487-d68615dd4b96.json`。

## 未验证 / 已知边界
bbd5 没有全量 Python 或 frontend/E2E 收据；74P 只覆盖显式测试路径。文档提交也未跑四叶，保持 WIP。

## 下一步
核远程 main 后建独占树。按 #59 准入（load1 <= 8、空闲 >= 8 GiB、pytest <= 2）运行正式 runner；Python 无 ignore/子集，树外 basetemp 与独立收据目录。明确收据路径校验 `--expect-revision --require-full-scope --base-drift-max 5`，核 target 为仓根，再做错误 SHA 对照。齐绿后才改完成状态。

## 踩过的坑
`main-4315/targeted-guards.log` 的 11P 实属 2439ca8a。5f35 手工 frontend 摘要无效，只认正式 runner。不要读共享 latest.json；不要动主检出和其他会话工作树。本轮复用既有工具，未新增通用脚本。
