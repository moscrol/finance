## 这个分支做什么
把 Knevo 原料按「材料→吸收决定→实现/回归→证据」收口；真实入口失败照实留证，PR #877 保持 WIP。

## 决策与被否方案
- 揭盲材料只作回归，不当金标、不进盲测分母、不改冻结 28 题。
- Q14 只吸收事实/解读/情绪结构；未回测的信源权重、情绪溢价公式、交易窗口不采用。
- Q18 材料代理不证明真实台账、权限、身份隔离、跨轮能力；风远仅恢复原料，不写画像。
- 公开 report 与私有 Episode 分证据；脱敏 D 日缺失不证明实际模型输入损坏，缺 audit 不等于零调用。

## 当前状态
- 已无冲突整合 main `bbd53487f`（#876 含门禁/数据库快照代码）。本次勘误提交后固定候选，不继续追逐移动主干。
- 勘误：端点 diff 的 D 不是删除历史。#879 只改四份 claim-scope 文档，不能称它删除 Knevo 材料；本枝文件完整。
- 最新运行/推送状态查 PR #877 与 `~/.finance-runtime/knevo-absorption-20260923/final-closure/current.json`。本段是运行前快照，不预写成功；索引缺失不视作已完成。
- 不合 main、不部署 8792、不回补行情、不写生产画像；不接管主检出树或其他 agent 改动。

## 已验证
- 历史 `537c4c4c4`：全仓14606P/85S/2X/0F、定向335P、Ruff通过；前端六步120P/E2E34P2S，registry与crosswalk通过（98 warning）。收据仍只绑定该 revision。
- live observations：9 completed/3 failed，作者文本层仅 G1c/G2a 有限满足，端到端 **0/12**。
- runtime `execution.json` 是四条运行记录；`final-prepare-85bff6326.json` 才是 prepared_not_run。两者不替代 observations 的语义判定。

## 未验证 / 已知边界
材料范围约束、Q14 正门路由、出稿/判官失败处理、Q18 真前置未通过；不能宣称 Knevo 炼化、胜率/top3 增益或完整消融。

## 下一步
- 固定候选门禁写入 `final-closure/runs/<完整revision>/`，完成后生成 current.json 并更新 WIP PR；旧证据不覆盖、不移签。已测树不再改 tracked 文件。
- 主干漂移只记录差异及 merge-tree；真正合入前另验组合候选，等待审查和用户确认。
- 后续先修 `split_user_message → material_contract → task_frame → registry`，再修 Q14 路由和失败分桶，原题同正门复验。

## 踩过的坑
目标树无本地 venv；用主树 `.venv-workbench/bin/python`。`run_main_gate.sh` 必须从目标树 cwd 启动；同时核对 revision、tree、dirty 和全仓收集面。

日期快照：`docs/handoffs/2026-09-23-knevo-absorption-closure.md`。
