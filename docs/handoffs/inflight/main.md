# 在途交接 · main

更新：2026-08-13 · 夜间循环收口：5 PR 合并部署，R13–R15 全量验收 + knevo 对照完成

## 这个分支做什么

生产基线。夜间修复循环 + 验收对照已收口，快照见 `docs/handoffs/2026-08-13b-night-loop-and-r15-knevo-comparison.md`。

## 当前状态

- 8792 = `3b7158a8`（含 #301–#306 全部修复），clean，ready，RAG ready。
- 28 题全量：A 组 10/10（A3 经 #306 修复后 completed）、B 8/8、C 10/10。
- knevo 对比包已生成（Mac 私有仓 runs/ 未提交）。

## 下一步

1. **实体识别吞前缀**：「立新能源」→theme「新能源」，A3/B1 零证据共同上游，最高优先。
2. **交易日历判定**：C1 该答「周六休市」不是「证据不足」。
3. A7/A10 核验预算、governor 升档——设计评审。
4. C2/C4/C5 degrades=9~10 偏高，可看核验剪裁量。

## 未验证

- 对比包只生成未判分（information comparison 需评审员跑）。

## 踩过的坑

- 收据 `repair=0/0 stop=None` = 失败在修复层之前，别当饿死修。
- 结算已完成的工作不能 fail closed（#297/#306 两处现场，已归位 BUILD.md）。
- 切 8792 不要 `reset --hard`；预热期 2–3 分钟不监听。
- **RAG worker 查询超时后状态停在 failed 直到下次查询才懒恢复**，readiness 期间红着
  （R15 高负载后实测，kickstart 可救）。要不要加自愈探针属设计项。

## 已验证

- R14：A3 硬失败→completed（#306 生产判决）。
- R15：18/18 completed；5 次瞬态重试全按窗发放。
- 合并末态回归 192 passed + episode 套件 82 passed。
- 收尾核验：8792 ready（RAG 重预热 94.7s），8794/8797 已关，
  本循环 9 条已合并远端分支已删，BUILD/TOOLKIT/记忆底座回写已提交。
