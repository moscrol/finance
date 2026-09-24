# #813：Spec局部交付与C3宿主探针

状态 `SPEC_SCOPED_DELIVERED_QUALITY_BLOCKED`。固定候选3c5/base4cc，main033组合未验。无完整独审或合入/生产批准。

- 本轮65模型请求：Spec30，Quality35。先前本地端口冲突批0请求保留；没有停止占用19899的其它任务，改专用19913并重验沙箱。
- Spec独立5P，正式PASS_WITH_LIMITS，结构/计数校验通过；其内作者测试1F（.git被沙箱拒绝），宿主同一测试1P单列。
- Quality产品探针0，仅语法检查；首命令故意红已执行。报告200/exit0却只返回JSON文本，未调用deliver_stage，原门拒收，没有补签。
- 宿主运行原Quality探针7F，修正夹具的收据路径及他股日期后7P，断言不变。临时将验收器EXCEPT ALL改EXCEPT，重复行见证1F预期红；未改候选再跑7P。以上不计入独立Quality。
- 760份原件、4,846,099原始字节；manifest逐项记录原路径/编码/原字节和存储SHA。XML/日志等以Base64可逆存储，脚本为文本；排除候选树、凭据存储、临时数据库/用户目录和软链。旧失败批没有改写。

入口（`raw/pr813-glm-qc-20260925-02/` 下）：

1. `semantic-check.json`：证据范围、Spec深度限制、Quality缺口与宿主诊断分账。
2. `spec/report/parsed.json` / `spec/host-evidence-audit.json`：有效Spec原稿与XML计数对账。
3. `quality-report-diagnostic.json` / `quality-final-message.txt`：没有工具交付的原始文本，不能当有效终稿。
4. `host-c3/receipt.json` / `host-c3/set-mutation-control.json`：原7F、修夹具7P、去保护必红与原版复验。
5. `host-c3/work/probes/test_fixture_adapter.py.txt`：只修夹具、复用原断言的宿主适配器，可供新独立审查核对后复验，不可直接移签。
6. `host-countercheck/receipt.json`：作者定向对照1P；`host-tools-final.json`：对账装置11P与版本变更。
7. `report.json`：宿主封存总账，不是独立判官报告。

细节见 `../../handoffs/2026-09-25-backfill-302132-guard-qc-and-oracle-probes.md`。全部自有进程已退出；未改/推产品代码、未合main、未读写生产或动8792。
