# FinArena 遗留功能保全与待验收项

本 PR 只为保全与归属交接，不是合入申请，也不授权生产或公众试运行。

## 已做

- 固定来源 `feat/finance-arena@7162a6cb`，原树 `/Users/a77/fwp-wt-finance-arena` 在核查时干净。
- 2026-09-21 将该固定提交推送到 Gitea 并回读 SHA；此前远端不存在该分支。
- 有真实新增功能，不因 8816 预览服务仍运行就认定有作者正在推进。
- 保留原分支中的 `docs/finance-arena.md`、试运行记录和 8792 探针失败原件。没有向榜单写票，没有接入新参赛方，没有改 8792。

## 不成立的结论

原交接记载的 Arena 后端 32P、前端 110P、Arena E2E 8P 是历史来源的读数，本轮未重跑，不能移签到当前 main。8792 三轮自然问答均 partial，不能叫业务通过。预览服务和干净 Git 状态都不是独立验收。

## 下一步

1. 基于届时最新 `gitea/main` 独立整合，只保留 Arena 的真实新增文件与入口，不带回旧 Workbench 代码。
2. 独立核对邀请、匿名比较、投票归属与发布合同，保持公众 Arena 与私人 Workbench 数据隔离。
3. 固定整合 SHA，补 Python、前端、两套 E2E、registry 与独立 Spec/Quality；任何叶子失败或无结论都不合。
4. 真实参赛、付费模型、正式榜单发布、公网治理与生产部署另行确认。

归属盘点与后续协调：`ops/worktree-ownership-closeout-0921` 的 `docs/verification/2026-09-21-worktree-ownership/decisions.json`。原树和本 PR 都不应因“已保全”而直接删除或合并。
