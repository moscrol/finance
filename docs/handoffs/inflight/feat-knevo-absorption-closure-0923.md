## 这个分支做什么
把 Knevo 原料按「材料→吸收决定→实现/回归→证据」收口；Q14/Q18/09-17 三包、44 轮和风远恢复索引已归档，真实入口失败照实留证。

## 决策与被否方案
- 用揭盲回归与 reviewer-only 判据；不把原答当金标、不改冻结 28 题，因无配对盲样本。
- Q14 只吸收事实/解读/情绪结构；否掉数值信源权重、情绪溢价公式、交易窗口，因未回测且越界。
- Q18 先测材料解释；不把代理升级真实存储、权限、身份隔离、跨轮能力，因真实前置未接。
- 公开 report 与私有 Episode 分证据；不把脱敏 D 日缺失写成模型输入损坏，因 sanitizer 可复现且 pack3 无私有轨迹。
- 保留失败、PR #877 保持 WIP；不关审稿闸/改题凑绿，因 completed 不等语义通过。

## 当前状态
- 最新 `gitea/main=5f35da17` 已无冲突整合；本次快照提交完成后的 HEAD 才是最终门禁候选。main 的 #879/#873/#881/#882 删除了同名旧材料并更新门禁指针，本枝保留本 PR 的实现与证据。
- 工程门禁与语义门禁分开：语义仍 **0/12**，不能宣称 Knevo 炼化、胜率/top3 增益或完整消融通过。
- 不合 main、不部署 8792、不回补行情、不写生产画像；主检出树有其他 agent 改动，不要接管。

## 已验证
- 较早合流候选 Python **14606P/85S/2X/0F**、Ruff、前端六步、registry 与 ledger/spec crosswalk 全通过；最终文档提交后必须按最终 revision 重跑。
- 最终收据统一放 `~/.finance-runtime/knevo-absorption-20260923/final-closure/`：Python 定向/全仓、前端、registry、diff-check；JSON `revision` 绑定才可采信。
- `execution.json` 仍为 `prepared_not_run`；live observations 仅为 9 completed/3 failed，作者文本层 G1c/G2a 有限满足，端到端 **0/12**。

## 未验证 / 下一步
- 本次快照提交后，以最终 revision 运行并留存完整 Python、定向 Python、前端六步、registry、diff-check 收据；收据写出后不再改 tracked 文件。
- 继续等待审查和用户确认；若 PR head/主干再变，重新 merge-tree 和全部门禁。
- 后续修复 `split_user_message → material_contract → task_frame → registry`，再修 Q14 路由、invalid finish/missing output/judge unavailable；原题不改、不放松门禁。

## 踩过的坑
- 目标树无本地 `.venv-workbench`，解释器是主树 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；必须同时看收据 `tree` 与 `revision`。
- `frame_source` 要区分 `private_episode`/`public_report`；缺 audit 不是零调用，共享 KB 可读也不是 OS 隔离。
- `run_main_gate.sh` 要从目标树 cwd 启动，否则会误判 dirty。

日期快照：`docs/handoffs/2026-09-23-knevo-absorption-closure.md`。
