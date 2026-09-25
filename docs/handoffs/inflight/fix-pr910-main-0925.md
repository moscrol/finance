## 这个分支做什么
#910前向main并补离线门禁；发布fix/pr868-delivery-validation-0924，保持WIP。

## 决策与被否方案
- 运行时漂移重新冻结 / 旧绿灯移签：#930同时改变请求体与预算选择。
- 只停自有等待 / 并发叠加：准入不预约资源，不动外部进程。
- 两PR分账 / 合计通过数：不同SHA与分母不能互代。
展开：`docs/handoffs/2026-09-25-pr910-main643-engineering.md`。

## 当前状态
代码候选a8cea541422d006c1aa0c022db8a652a2792886e，基座643a2888ea14079035bc8b080129e3e4145d5685；无冲突吸收#930四文件，未手改产品逻辑。后续文档HEAD另计。

## 已验证
新候选doctor/Ruff/registry四项/crosswalk/PR diff-check过，地图已刷新。原件`docs/verification/2026-09-25-pr910-main643-static/`。
历史干净4e4d93a55（基座64847b7a）作者74P；全仓16232P/0F/0E/75S/2X，collected=16309，完整范围/版本收据通过；内层C3各3P、C7各66P仅作者回归、不重复计数。旧结果封存`2026-09-25-pr910-main648-engineering/`，0a6444ba1的142文件Git哈希核验通过，不移签。

## 未验证 / 已知边界
a8cea无pytest/前端/E2E收据。10:07:29 UTC资源因外部pytest4484/18495拒绝，动态未启动。旧批自有监督已退出，无后台。付费授权/请求0；独审、自然金融质量、真实来源、自主子研究、反证修订、L6、8792均未新增验证，未合main或部署。

## 下一步
资源允许后另根冻结当时干净HEAD，先核对main运行时漂移，再完整沙箱套件、Python、前端/浏览器。固定`/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`，依赖66726d345bf37ce5。工程齐后另申请独审额度，不恢复旧撤销批。

## 踩过的坑
Gitea mergeable=false可能来自WIP，不证明冲突。归档文档提交不继承代码SHA收据；资源拒绝是未执行，不是PASS或产品失败。
