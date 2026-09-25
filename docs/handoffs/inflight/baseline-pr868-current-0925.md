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
#910/#911 base均已改main，仍WIP。固定基座1751e21e0fd30642e0b223604b64b30e38c46f41。
#910代码4ad2cb42b0c58d9b3997a435568eea5e549bccdb，工作树`~/fwp-wt-pr910-main-0925`，在途`docs/handoffs/inflight/fix-pr910-main-0925.md`。
#911代码86da22fda1f8fa02c71cd5d8759ee55a65e6fd37，工作树`~/fwp-wt-pr911-main-0925`，在途`docs/handoffs/inflight/test-pr911-main-0925.md`。两树无冲突、源码树与merge-tree预览相同，未手改产品实现。

## 已验证
新候选分别静态门禁/registry五项/精确版本收据通过；#910仅四目标4P，#911两文件56P，不能合并成一个候选分母。解释器`/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`。原根`~/.finance-runtime/reviews/pr910-911-forward-20260925/`；各新树有27原件归档。

## 未验证 / 已知边界
全仓/前端/E2E未重跑；#910完整沙箱73例未重跑。共享宿主三套全量在跑，资源拒绝新全量；定向绿不替四叶/独审/自然金融/L6/8792。
旧fb41完整工程及原日志空白仅属旧批；旧停批根pr910-911-qc-20260925-01继续INVALIDATED_NOT_AUTHORIZED，五入口拒续跑，错误授权原件与评论7080更正保留。本轮模型请求0。

## 下一步
沿两棵新树补完整工程门禁；main继续前进则重评绑定。之后明确申请独审额度，另根准入。不要动owner分支/恢复停批/解除WIP/自动合main或部署。

## 踩过的坑
助手自写approved=true不证明用户批准；资源偶然挡住副作用不补授权门。不同SHA/轴/目标集的通过数不得相加或移签。
