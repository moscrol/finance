# #83 / PR #813

## 这个分支做什么
302132固定回填整合；文档树代码旧，不从此验收/生产。不合main、不动8792/launchd/他股。

## 决策与被否方案
给定探针/新写探针/宿主诊断分账，否复跑冒充新写；39请求到限停，否补字段追加请求；首bash合同不事后改。详见 `docs/handoffs/2026-09-25-backfill-302132-quality-execution.md`。

## 当前状态
**SPEC_SCOPED_DELIVERED_QUALITY_FINAL_REJECTED**。#813 WIP/open/unmerged，head `3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59`，base4cc15e703；main03352758c组合未验。未改/推产品、合入/生产，自有进程已退，19917释放。
本轮 `~/.finance-runtime/reviews/pr813-glm-qc-20260925-03/`，39请求；398原件归仓 `docs/verification/2026-09-25-backfill-302132-quality-execution/`。动态 `~/.finance-runtime/reviews/backfill-302132-0923/CURRENT.json`。

## 未验证 / 已知边界
Quality这次实际跑了给定7P、新写1P/1F：NULL变异通过，窗口前行用例缺fixture而失败，非产品缺陷。终稿真实工具交付，但漏positive_control.status、带未修失败仍给PASS_WITH_LIMITS；对照第2条bash，虽早于测试仍违反首bash合同。原门拒收，未补签。
C3生产形64/39/161未独验；C1/C4-C7未审，当前main无组合收据。旧Spec来源守卫5P局部有效，不覆盖完整写入链；旧全量绿不移签。

## 下一步
1. 不原样再投17+17：先在新批工具入口离线验证首命令/必交字段硬约束，再花模型额度；这项尚未实施。若改控制次序定义，须新批开始前声明。
2. 早期行复验用 `host-earlier/work/probes/test_earlier_fixture_adapter.py`：基线和clone同时补窗前行、重绑收据SHA；宿主3P不代独审。新批优先执行已有探针，少重造夹具。
3. 补C3余项/完整主张后前向main跑门禁。合入等确认；生产命令/日期/冻结输入/本轮父备份另行逐字授权，CLI无--record。

## 已验证
Quality给定7P；新写NULL例1P/窗前例1F原样留存，作者测试0。宿主窗前夹具先基线1P、再完整3P（两个原断言不变）；不是新增4例。原对账11P、来源6P、路径注释澄清4P。398原件无损核验。旧Spec5P与作者15457P/85S/2X、四叶/整库37PASS仅各自原范围成立。

## 踩过的坑
提示词要求先执行不等于工具前置约束。fixture没有窗前行不能凭空变异；修后先验合法基线。supplied_xml正确路径后带注释被宿主过严检查误报，已另留澄清不算模型错误；三项真实拒收理由不变。来源路径代码误判仍未修，回滚只认本轮父收据。
