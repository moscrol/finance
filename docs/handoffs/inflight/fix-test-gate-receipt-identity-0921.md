# 调用级测试收据归属

## 这个分支做什么
#814阻止嵌套pytest把内层结果写进外层唯一收据。

## 决策与被否方案
- Config.stash记(PID,path)，环境PID隔离继承子进程；否PID/target单独判归属，同进程同文件也能重入。
- configure早注册cleanup覆盖配置失败；只释放自己认领的环境，保留原先缺失/空串差别。
- 新组合固定新收据，否复用旧绿或追着main改被测对象。
- 决策展开：协调树`docs/handoffs/2026-09-21-ownership-integration-v4.md`及前轮`2026-09-21-ownership-reentrant-repair.md`。

## 当前状态
源码a092a021c已推#814；之后仅本交接文档变化，不继承源码收据。O-K3-001作者修复已验证。
用户再“继续”后组合#812@8d955fc3/#813@5994230d/#814@ffc8e1a8，以当时main c615adbd冻结6eb12c1b8；已推`baseline/ownership-gates-v4-0921`，未另开组合PR。候选树`~/fwp-wt-ownership-gates-v4-0921`保持净且不改。
新证据82文件已封于协调树`docs/verification/2026-09-21-ownership-integration-v4/`；原件`~/.finance-runtime/reviews/ownership-integration-v4-20260921/`。

## 已验证
源码a092：相关71P、新增15例，精确旧源码11F/4P→修后15P；三变异均打红；精确源码/完整契约两类嵌套均正确外层1P。干净源码全量11963P/85S/2X、Ruff/gate绿。
新组合6eb12c1b8：Python12461P/85S/2X、Ruff绿；前端110P、E2E34P/2S；finance-only registry五项0；适用pre-commit通过。各叶首尾身份/源哈希不变，唯一收据/JUnit/终端一致，回读/兼容0。新组合收据`gates/python/receipts/gate-bVVRCApx/pytest.json`。

## 未验证 / 已知边界
没有新独立复审；旧v3 K3各40请求触帽未终审历史不改。07:12Z远端main已adcda94b，6eb12收据只签c615基线组合，不签后来main。真实完整副本302132发布恢复未演练。
归属标记不是恶意写者沙箱；首尾净不证明中间无改后还原；shell只留pytest末15行。

## 下一步
协调入口`~/fwp-wt-ownership-closeout-0921/docs/handoffs/inflight/ops-worktree-ownership-closeout-0921.md`。另定独立复审对象/有限预算与届时main合流范围；合并/部署/生产回填/删树分别确认，三单与组合不可重复合。

## 踩过的坑
latest只导航；配置失败也要cleanup；旧单分支/旧组合/新组合总数不能直接比增减。被冻结的候选及历史证据不补写。
