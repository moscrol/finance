# 工作树归属与接管

## 这个分支做什么
协调#812看板/#813回填/#814收据，保护他人现场，固定对象留证。

## 决策与被否方案
- 再次“继续”只建新组合跑工程全叶；否自动加K3预算/合并/部署。
- 固定授权时main c615adbd；否测试中追着main换对象或移签收据。
- merge-tree真实合流+四父提交；适用hooks另跑，否手拷文件冒充组合。
- 展开：`docs/handoffs/2026-09-21-ownership-integration-v4.md`。

## 当前状态
新组合6eb12c1b8已推`baseline/ownership-gates-v4-0921`，树`~/fwp-wt-ownership-gates-v4-0921`保持净且冻结；父c615adbd+#812@8d955fc3/#813@5994230d/#814@ffc8e1a8（含a092收据归属修复）。未另开组合PR。
82文件封于`docs/verification/2026-09-21-ownership-integration-v4/`（含README不含manifest），2,600,457字节；证据c39e5bfd8已推，#812/#813/#814评论5294/5295/5296逐字回读一致。原件`~/.finance-runtime/reviews/ownership-integration-v4-20260921/`。#814仅交接续至790dc27a，源码未变。
旧47530e20及六档不动；旧K3双轴40请求触帽未终审历史保留。未新模型会话/合main/部署/生产回填/删真实树；Arena另线。

## 已验证
6eb12固定组合：Python12461P/85S/2X、Ruff绿、gate0；前端110P，E2E34P/2S，六命令全0；finance-only registry五项0；适用pre-commit通过。一次运行，各叶首尾净同SHA/tree/源哈希。唯一`gates/python/receipts/gate-bVVRCApx/pytest.json`与JUnit12548条/终端一致；回读/兼容均0。
a092修复既有证据115文件保留；旧六档30/30/86/26/450/115成员/哈希/冻结提交字节不变，旧三v3审查树净47530e20。

## 未验证 / 已知边界
没有新独立Spec/Quality终审。07:12Z远端main已adcda94b（他会话），本轮只签c615基线组合，不签后来main；十个范围路径零差不是全仓集成证据。真实完整副本302132父子发布恢复未演练。
首尾净不证明中间无改后还原；归属标记不是恶意写者沙箱；shell仅留pytest末15行，JUnit非全stdout。

## 下一步
另定独立复审对象/有限预算；若验届时main，重固定组合并跑新全叶。#812/#813/#814与组合不可重复合；合并/部署/回填/删树分别确认。发布和收尾复核记录`~/.finance-runtime/reviews/ownership-integration-v4-closeout-20260921/`。

## 踩过的坑
latest只导航；11963旧单分支/12068旧组合/12461新组合不直接比。show-ref缺ref退出码依--quiet变化，旧manifest用files非entries；设施错误原件均保留。
