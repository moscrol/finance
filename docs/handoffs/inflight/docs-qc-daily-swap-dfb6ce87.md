# daily-swap 七轮独立复审

## 这个分支做什么

审 `fix/daily-swap-lock-all-callers@dfb6ce87`，只留报告与临时库探针，不改施工代码。

## 当前状态

审查报告与探针已提交 `e8ad314b`。**原两处修补通过；公共链暂不放行**，新增 P2：开工探针见过旧库后删除，下一次 exists 把它当 bootstrap，重建缺历史库并报成功。旧码同红，不是六轮新回归。未合并、生产库未动。

## 决策与被否方案

- 修既有→缺失被降为首次初始化；否了再加末端 stat，分类前提必须向下传。
- 一般 clone IO 裸抛另列小提交；不误报成目标替换，也不混成数据覆盖 P1。
- 否了「三文件不变所以合并后门禁也绿」；依赖/测试集合已变，需整合候选重跑。
- 详情：`docs/handoffs/2026-09-13-daily-swap-round7-qc.md`。

## 下一步

1. 修 `sync_daily_full.py:514-520` 的初始存在性分类，迁入新红项并独立红→绿。
2. 删门禁外推断言，修六轮报告的跨分支链接；可迁入 link 非 EEXIST 三条绿。
3. 复审通过后由用户裁定完整 hithink 合并面；适用门禁全绿后，合并/生产操作分别授权。

## 已验证

干净 dfb6ce87：三文件 **71 passed / 9.51s**，全仓 Ruff passed。
独立探针 **8P/1F**（两绿只是 clone IO 旧债 characterization）；旧版新增红项 **1F**。
核验他方 a42cbc5c 原始收据：dirty=false、9517P/0F/77S、exit0，不冒充独立全量。
探针 `scripts/review_daily_swap_round7.py`，显式 pytest 调用；日志 `~/.finance-runtime/reviews/daily-swap-dfb6ce87/`。

## 未验证 / 已知边界

未独立重跑全量/sandbox/前端/E2E/registry-check，未重做 hithink 数据端到端对账。
main=631786ab，main 独有35 / tip独有18；merge-tree 唯一冲突 lessons，仅文本模拟。
已有库最终 identity-check→replace 仍按声明边界，不声称可防任意外部文件操作。

## 踩过的坑

旧文件由探针 unlink 删除，不能说是 link 覆盖掉它；缺陷是已观察缺失仍静默重建并报成功。
探针以安全断言表达，所以一红就是阻断证据，不得改成「证明缺陷存在所以绿」来冒充验收。
