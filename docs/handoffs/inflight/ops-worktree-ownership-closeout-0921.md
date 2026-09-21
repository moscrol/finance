# 工作树归属与接管

## 这个分支做什么
协调#812看板/#813回填/#814收据，保护他人现场，固定对象留证。

## 决策与被否方案
- 用户“继续”后只续#814修复；否决自动追加K3、合并或部署。
- Config调用级凭据+PID+cleanup；否决PID或target字符串单独判归属。
- 新码新收据，旧树/档不改；作者修复不冒充独立通过。
- 展开：`docs/handoffs/2026-09-21-ownership-reentrant-repair.md`。

## 当前状态
#814代码a092a021c已推，O-K3-001同进程pytest抢外层收据已作者修复验证。只改conftest.py及test_main_gate_receipt.py；后续文档尖不继承源码收据。
115文件封存`docs/verification/2026-09-21-ownership-reentrant-repair/`（含README不含manifest）。原件`~/.finance-runtime/reviews/ownership-reentrant-repair-20260921/`。
旧47530e20仍冻结；K3双轴40请求触帽无终审（Quality仅占位），旧代码CHANGES_REQUIRED/独立完成度BLOCKED历史保留。本次未加模型会话/扩额/合main/部署/生产回填/删真实树；Arena另线。

## 已验证
首批9例旧6F/3P→新9P；最终15例对精确旧hook11F/4P，修后15P；相关四模块71P。三变异各打红，还原15P；精确源码/完整契约复验两种嵌套均正确外层1P。
a092干净源码全量11963P/85S/2X、Ruff绿、gate0；唯一`clean-source-full/receipts/gate-QQdiL9Bn/pytest.json`，JUnit/终端/收据一致，回读/条件检查0。旧五档30/30/86/26/450逐字节不变；旧三审查树仍净47530e20。通用模式推harness PR14@9f1c80b。

## 未验证 / 已知边界
修复未独立复审；未建三单新组合/最新main集成，未跑修复frontend/E2E/registry叶。无真实完整副本302132父子发布恢复演练。调用标记不是恶意写者沙箱；首尾净不证明中途未改。shell只留pytest末15行，JUnit不是完整stdout。

## 下一步
06:02Z远端main已c615adbd（他会话变化）。先定基线、冻结新组合跑全叶，再另批独立审查会话/预算。#812/#813/#814与组合不可重复合；合并/部署/回填/删树分别确认。源分支交接在`~/fwp-wt-test-gate-receipt-identity-0921/docs/handoffs/inflight/fix-test-gate-receipt-identity-0921.md`。

## 踩过的坑
latest仅导航；PID不等于调用；cleanup必须覆盖configure失败；占位不等于终审。11963是单分支、12068是旧组合，不能直接比增减。旧失败原件不补写求绿。
