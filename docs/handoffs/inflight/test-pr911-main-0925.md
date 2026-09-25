## 这个分支做什么
#911研究链测试前向最新main并补门禁；发布仍走feat/pi-research-loop，保持WIP。

## 决策与被否方案
| 选择 / 否掉 | 理由 |
| --- | --- |
| 新main前向后冻结 / 旧56P移签 | 基座新增启动归因、隔离及沙箱测试 |
| 两PR分账 / 整包数字拼接 | 候选对象不同 |
| 每叶复查、有限等待 / 放宽准入 | 即时采样不预约资源，不动他人进程 |
展开：`docs/handoffs/2026-09-25-pr911-main9d5-gates.md`。

## 当前状态
代码8dec2a856b76cec21fae6daae1ed7505fb838dcc，基座9d5b9800a5500e6f64875432f8df3a06713d6f52；预览/实际树32f55112相同，无冲突或手改源码。后续文档HEAD不自动继承收据。

## 已验证
固定Python=`/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`，依赖66726d345bf37ce5；干净8dec上doctor/Ruff/diff/registry四项/crosswalk均过，地图已刷新。
归档`docs/verification/2026-09-25-pr911-main9d5-gates/`；原根`~/.finance-runtime/reviews/pr910-911-main9d5-20260925/`。

## 未验证 / 已知边界
8dec没有新pytest读数/收据。串行计划在#910前置被外部pytest阻挡；十分钟21次采样拒绝，attempt02未创建，监督进程已退出。旧86da两文件56P不移签，共有归档的7P是#910合并前诊断而非本PR证据。全仓/前端/E2E与独审均缺。

## 下一步
资源允许另根重跑两文件和四叶；main漂移先重评。工程齐后明确申请独审额度。当前付费授权/请求0，旧撤销批不能恢复，不自动合main/解除WIP/部署。

## 踩过的坑
模型/数据/判官脚本化，TestClient不证TCP/浏览器/8792或自然金融质量。L6/真实来源、自主子研究、反证修订未验。资源拒绝不等于产品红，也不等于PASS。
