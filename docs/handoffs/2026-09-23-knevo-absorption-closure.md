# 2026-09-23 Knevo 吸收收口决策快照

## 背景与范围

本轮承接“继续”任务，目标不是再盘点材料，而是把 Knevo 原料放进「材料 → 吸收决定 → 实现/回归 → 验证证据」链。工作在独立树 `/Users/a77/fwp-wt-knevo-closure-0923`、分支 `feat/knevo-absorption-closure-0923` 完成；生产 8792、生产行情库和用户画像未触碰。原 28 题冻结不变，09-17 揭盲材料不进入盲测分母。

## 按发现顺序的关键决定

1. 09-17 三包沿用既有审读和原件哈希，三包映射为三个完整题包，不拆成 24 个样本；Knevo 原答不是金标，rubric 不进入模型题面。
2. Q18 先做八个材料代理题，验证解释纪律；真实台账、空集、权限错误、身份隔离和跨轮改判继续留为未接前置，不因代理题绿灯关闭候选。
3. Q14 只吸收事实/解读/情绪三层结构；否掉现场数值信源权重、情绪溢价公式和交易窗口。共享 guidance 是生成指导，不是权限器或语义审稿器。
4. R6/Q15 收窄为研究检查表和观察词表；B 线暂停新增而不废弃。没有回测、干净成对样本或盲审，不能报胜率、top3、稳定性或成本质量前沿。
5. 风远只恢复 ZIP、66 卡、40–44 轮原料和定位索引，不重灌画像；旧临时筛选稿原字节丢失，未来写入须重新确认 userspace 身份和人工审批。
6. 真实 Workbench 结果不能用“completed”代替语义通过：9 completed、3 failed，作者侧仅 G1c/G2a 满足代理规则的文本层，端到端接纳 0/12。G3b 越过不查库，pack2 越过仅用材料，Q14 丢到通用题型，多个题只剩降级/复核不可用。
7. 公开 `report.json` 的 frame 与私有 Episode 分层。`sanitize_user_visible_artifact_text()` 可复现 pack3 D 日标签缺失，因此确认的是公开工件脱敏/保真问题；没有清洗前私有记录，不能断言实际模型输入被删。缺 Episode audit 也不能记成零 IO。

## 合流后的工程证据

- 已无冲突整合 `gitea/main=bbd53487f4cefdae97eae90f7322394d36e65462`；实际合流提交 `11727a1a9`，之后文档提交 `2bdc62222`。本次勘误提交后固定候选运行门禁，完整 revision 以收据为准。
- 勘误：此前把 `git diff HEAD..gitea/main` 中本枝新增文件的 `D` 误写成主干删除。该端点比较不能证明删除历史。#879 的实际变化（`86d3e558e..9a0227986`）只有四份 claim-scope 文档；#876（`5f35da172..bbd53487f`）实际改动 13 个门禁/数据库快照及相关文件。本枝的 Knevo 实现、题面、观察文件未丢失。
- 历史固定候选 `537c4c4c4fbc8171b4480068cf9003891b27edf6`：Python 全仓 **14606 passed / 85 skipped / 2 xfailed / 0 failed**、定向 335P；前端六步通过（单元 120P、E2E 34P/2S）；registry 四项及 crosswalk 通过、98 条 warning。这些保留在 `final-closure/` 原路径，不覆盖、不改签给后续候选。
- 本次勘误后的证据放 `~/.finance-runtime/knevo-absorption-20260923/final-closure/runs/<完整revision>/`，逐步保留收据、原始日志与退出码；完成后由 `final-closure/current.json` 索引具体结果，缺文件不视作已跑。此处是运行前快照，不预写成功；后续结果和推送状态以该索引及 PR #877 回读为准，不再为了更新计数改动已测 tracked 文件。
- 主干再次移动只记录差异与 merge-tree 结果，不自动反复合流重跑。WIP 推送交付的是固定审查候选，不是合入批准；真正合 main 前仍须对届时的组合候选验全门禁。
- 状态来源勘误：runtime 根的 `execution.json` 是四条实际运行记录（`semantic_verdict=not_evaluated`）；`final-prepare-85bff6326.json` 才是 `prepared_not_run/cases=12`。后续语义判断来自仓内 `batches/2026-09-23-regression/observations.json`，不是准备包或执行退出码。

## 失败归因与重开顺序

先修 `split_user_message → material_contract → task_frame → registry` 的材料范围和早期预取，再修 Q14 最终题型投递，最后分桶处理 invalid finish、missing output、judge unavailable 与降级出稿。原题不改、不开审稿闸、不新建第二权限器。修后用同一正门复验，再做 Q18 真实前置和任何消融；在此以前不声称能力增益。

## 禁止误读

工程门禁绿不等于研究质量绿；准备成功、HTTP/消息交付成功、语义通过是三种状态。公开 frame 缺字段不等于模型输入损坏；恢复风远原料不等于批准画像；外部工具自述、UI 标签和单次回执不替后端真相。PR #877 保持 WIP；合 main、部署和画像写入另等确认。
