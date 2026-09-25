## 这个分支做什么
#911研究链测试前向main并补门禁；发布feat/pi-research-loop，保持WIP。

## 决策与被否方案
- 运行时漂移重冻结 / 旧56P移签：#930改变请求体与预算。
- 按PR分账 / 借#910全仓：组合与分母不同。
- 只停自有等待 / 放宽准入：不干预外部进程。
展开：`docs/handoffs/2026-09-25-pr911-main643-engineering.md`。

## 当前状态
代码候选eb59c4a2fb4dbe77a349bd8545b942aa4df8db14，基座643a2888ea14079035bc8b080129e3e4145d5685；无冲突吸收#930四文件，未手改源码。后续文档HEAD另计。

## 已验证
新候选doctor/Ruff/registry四项/crosswalk/PR diff-check过，地图已刷新。原件`docs/verification/2026-09-25-pr911-main643-static/`。
历史a52a3a975（main648）也只跑静态，没有pytest；原件`2026-09-25-pr911-main648-engineering/`，0767f60a8的28文件Git哈希核验通过。共有审计的#910全仓16232P不属本PR；旧56P不移签。

## 未验证 / 已知边界
eb59无定向/全仓Python/前端/E2E收据。10:07:40 UTC准入被外部pytest4484/18495拒绝，动态未启动。旧批自有监督已退出，无后台等待。付费授权/请求0，独审未做，未合main/L6/8792部署。

## 下一步
资源允许后另根冻结当时干净HEAD，先复核main漂移；跑`intelligence/tests/conformance/test_research_chain.py`与`intelligence/tests/test_workbench_research_chain.py`，再完整Python、前端/浏览器。固定`/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`，依赖66726d345bf37ce5。工程齐后明确申请独审额度，不恢复旧撤销批。

## 踩过的坑
模型/数据/判官脚本化，TestClient不证TCP/浏览器/8792或自然金融质量。真实来源、自主子研究、反证修订未验。WIP可能使mergeable=false，不能声称代码冲突；文档HEAD也不自动继承测试收据。
