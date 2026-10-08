## 这个分支做什么
在隔离树验证river历史块与D4结果交付能否共存；只做本地测试快照，不合main、不推送、不部署。

## 决策与被否方案
| 选用 | 否决与理由 |
|---|---|
| D4拒未类型化事实，D10整块INFERRED并存 | 不择一覆盖；两个旧实现单独代入均被证人拒绝 |
| 保留正常红测试与实际请求 | 不删断言/改xfail、不抬12K/48KB或删历史边界 |
| 根因停在准入合同 | 不接管Codex的owned/finish/repair/carry/restore |
展开：[联合消费者快照](../2026-10-08-river-owned-joint-consumer.md)。

## 当前状态
树`~/fwp-wt-river-owned-joint-1008`。代码/测试`642b45358`为单父快照：`bd66de250`加river `af1f64b9f`整枝预览、两冲突解决及五个联合证人。联合验收NOT_PASSED；非可发布候选。证据根`~/.finance-runtime/reviews/river-joint-consumer-20261008/`，最终文档HEAD及对应复跑/封存看`completion.json`。原river不动；Codex持续前进，不自动吸收。

## 已验证
642净树68文件2084P/1F/0E/0S，收据`20261008T155827Z-642b4535-0ac3aa08fa33.json`可采信；Ruff/提交门过，非全仓。普通B、原生Episode联合证人过；grounded例稳定红。两冻结库三截止完整工具字节等于原river，库哈希不变；旧118/46/60包复核未改。

## 未验证 / 已知边界
grounded联合例D10行11228字符，反证/缺口占位后D4三事实送达0；D4-only送达3。最短一条本可容纳，三条加D10已12943，不能只调排序保全集。DecisionBrief仍列省略的ID。D4 query_basis从prepared到grounded丢失在干净main也复现。原生owned仅认证精确保留片段，whole_answer仍unassessed。
新真实模型0；旧GLM全文未过不翻案。无联合HTTP往返专项、全仓/前端、真库、Workbench真实写手判官、多轮及独立金融批准；历史路径/源版本未补。

## 下一步
先核本树/main/Codex的HEAD和脏路径，再协调既有AnswerSpec→registry准入→DecisionBrief的送达集合合同；补元数据、引用闭合及溢出/反证负控。修复保持当前红证人，固定新revision复跑；真实GLM另阶段、真库另授权。

## 踩过的坑
315P和最初2084P/1F是脏预览，不能签主干。收据校验exit0只证明读数适用，不会把1F变绿。12K是registry字符、48KB是工具UTF-8字节。快照非锁，私有权限非不可变。
