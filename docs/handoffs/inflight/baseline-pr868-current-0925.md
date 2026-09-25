## 这个分支做什么
保留fb41历史组合证据；当前#910/#911已拆开前向main，本树仅协调索引，不再作为最终代码候选。

## 决策与被否方案
| 选择 / 否掉 | 理由 |
| --- | --- |
| 各PR前向main / 整包重审 | #868由owner独立合入1751e21e0 |
| 实测新候选 / fb41收据移签 | 基座与组合范围已变 |
| 保留已撤销批 / 恢复旧78次计划 | 当前无明确新增付费授权 |
旧快照：`docs/handoffs/2026-09-25-pr910-911-review-preparation.md`及`2026-09-25-pr868-current-base-offline.md`。

## 当前状态
#910/#911 base=main且仍WIP。新基座9d5b9800a5500e6f64875432f8df3a06713d6f52。
#910代码167c9ffac1b428164e7906861438eb1757895dc5，树`~/fwp-wt-pr910-main-0925`，在途`docs/handoffs/inflight/fix-pr910-main-0925.md`。唯一测试夹具冲突保留双方意图，未手改产品实现。
#911代码8dec2a856b76cec21fae6daae1ed7505fb838dcc，树`~/fwp-wt-pr911-main-0925`，在途`docs/handoffs/inflight/test-pr911-main-0925.md`，无冲突、源码树与预览相同。

## 已验证
新候选doctor/Ruff/diff/registry四项/crosswalk过，尚无新pytest收据。#910合并前7P为未提交树诊断；旧4ad2的4P与86da的56P不移签。固定解释器`/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`。原根`~/.finance-runtime/reviews/pr910-911-main9d5-20260925/`，各树快照`docs/handoffs/2026-09-25-pr<号>-main9d5-gates.md`。

## 未验证 / 已知边界
全仓/前端/E2E及#910完整沙箱套件未进入。十分钟21次资源采样被外部pytest阻挡，RESOURCE_WAIT_EXPIRED；attempt02未建立，自有监督均已退出，无后台续跑。不补独审/自然金融/L6/8792证据。
旧fb41完整工程及原日志空白仅属旧批；旧停批根pr910-911-qc-20260925-01继续INVALIDATED_NOT_AUTHORIZED，五入口拒续跑，错误授权原件与评论7080更正保留。本轮模型请求0。

## 下一步
沿两棵新树补完整工程门禁；main继续前进则重评绑定。之后明确申请独审额度，另根准入。不要动owner分支/恢复停批/解除WIP/自动合main或部署。

## 踩过的坑
助手自写approved=true不证明用户批准；资源偶然挡住副作用不补授权门。不同SHA/轴/目标集的通过数不得相加或移签。
