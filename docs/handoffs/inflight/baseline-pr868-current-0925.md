## 这个分支做什么
保留fb41历史组合证据；#910/#911已拆开前向main，本树仅协调索引。

## 决策与被否方案
- 两PR单独分账 / 整包或旧绿灯移签：基座、源码和目标集均不同。
- #930运行时变化后前向 / 当作文档漂移：推理档影响请求体与预算。
- 只停自有等待 / 绕过准入：不干预他人pytest。

## 当前状态
两PR已无冲突前向main643a2888ea14079035bc8b080129e3e4145d5685。
#910代码a8cea5414、含文档推送HEAD d300cb305；树`~/fwp-wt-pr910-main-0925`，在途`docs/handoffs/inflight/fix-pr910-main-0925.md`。
#911代码eb59c4a2f、含文档推送HEAD 1a61be4e7；树`~/fwp-wt-pr911-main-0925`，在途`docs/handoffs/inflight/test-pr911-main-0925.md`。
PR评论7186/7187已readback，base=main、WIP/open/未合入。

## 已验证
新代码候选doctor/Ruff/registry四项/crosswalk/PR diff-check通过，地图刷新；main643静态归档各23文件Git哈希过。
历史main648：#910的4e4d93a55作者74P、全仓16232P/0F/0E/75S/2X，完整范围及精确版本收据过；C3各3P、C7各66P仅作者内层。不移签给main643。#911的a52a只有静态，没有pytest。旧归档分别142/28文件Git哈希过。
详情各树`docs/handoffs/2026-09-25-pr<号>-main643-engineering.md`。

## 未验证 / 已知边界
新候选动态测试未启动：10:07 UTC外部pytest4484/18495阻挡准入，无pytest/前端/E2E收据。自有监督26492/4406均已退出，无后台。付费授权/模型请求0；独审、自然金融质量、真实来源、自主子研究、反证修订、L6、8792、合main及部署未新增验证或执行。

## 下一步
资源允许另根冻结实际干净HEAD，复核main漂移后重跑两PR完整工程门禁，再另申请独审额度。固定`/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`，依赖66726d345bf37ce5。不动owner/19899/8792，不恢复pr910-911-qc-20260925-01撤销批。

## 踩过的坑
WIP可令Gitea mergeable=false，不等于代码冲突。文档HEAD不继承精确SHA测试收据；助手自写approved=true不证明用户授权。资源拒绝不是产品红也不是PASS。
