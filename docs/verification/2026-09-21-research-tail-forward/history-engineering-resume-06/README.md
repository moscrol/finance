# #845 完整 Python 预声明分组续验 06

## 身份与范围

源码固定`442476f7def1013f1fadebaf6594971921147edc`，源码工作树`fix/history-forward-boundary-0921`；不改产品代码、测试断言或原#833。上一轮05完整运行的12807P/2F/87S/2X、普通组exit1与RSS环境配对原件全部保留，本轮不覆盖、拼接或移签。

**整体CHANGES_REQUIRED / 未验收。** 本轮只补完整Python工程执行记录，不自动续独立模型审核，不合main、部署8792、生产回填、删除工作树或接管#814及邻线。

## 预先固定的计划

05用相同env证明外层macOS Seatbelt（操作系统进程隔离）阻止`/bin/ps`，使两条RSS（进程驻留内存）观察断言得到None；另五条自身启动系统沙箱，不适合再套同样的外层。06在启动前把七个精确测试ID固定在`coverage_plugin7.py`，`plan.json`绑定脚本/插件SHA256、源码HEAD、clean状态、Git索引指纹和资源限额。分组插件只选测试及记录结果，不修改断言、不新增skip。

- `environmental`：先运行三个指定模块中的七条，其他收集项明确deselected；无外层Seatbelt，保各测试自身沙箱。七条通过后才启动普通组。
- `ordinary`：从原完整收集面排除且仅排除这七条；保外网阻断（仅放localhost），禁止写主树与共享记忆。普通组最多2400秒，环境组120秒，磁盘低于2GiB停止，停止信号与原退出码单列。
- 两组都使用主树`.venv-workbench/bin/python`，清理继承环境，`FWP_TEST_RECEIPT=0`避免污染共享latest；外置记录器不是#814正式收据。
- 两个进程的环境、选择集与运行命令均保留。它不是一次未分组的原始`pytest -q`，不声称完全复现CI环境；04/05已记Node26与workflow Node22差异。

## 实际结果

06环境组：**7 passed / 49 deselected，exit 0，2.01秒**。普通组：**12802 passed / 87 skipped / 2 xfailed / 7 deselected，exit 0，1306.09秒**。普通组pytest日志为`12802 passed, 87 skipped, 7 deselected, 2 xfailed`；无失败、错误、收集错误或中止信号。

两组收集面精确对账：普通组收集12898项并选择12891项，环境组收集56项并选择7项；环境七ID与普通组deselected完全相同，选择集不重叠，并集覆盖全部12898项。与05相比收集ID、skip/xfail ID完全一致，只有两条RSS在06环境组通过。完整分组结果为**12809 passed / 87 skipped / 2 xfailed，failed=0**。

## 对账与自检

`analyze.py`交叉核对完整collection、selected/deselected集合、每ID的setup/call/teardown阶段、pytest会话退出码、runner原退出码及JUnit XML；两组均无collection/setup/teardown错误或XPASS，源码首尾身份一致。`check_analyzer.py`只改临时副本，正常七条记录先通过，再造漏报告、重复阶段、缺call、teardown失败、exit1、选择集不完整、日志变字节、JUnit错误八种坏记录，全部被拒绝。这是作者记录器自检，不是产品新增测试、独立审查或额外工程通过数。

`environment.json`在普通组运行期间采集解释器/系统/依赖元数据，明确不是启动前环境快照。启动前真正绑定的项目看plan/start记录，不倒填时序。

## 封存方式

新06包与旧八包分开。`.py`/`.log`归档改名为`.txt`，不改内容；逐阶段JSONL按完整行无损拆分，拼接字节必须等于原文件。`sources.json`记录来源、长度、SHA256及分片映射；临时数据库/用户态、缓存不入仓。包内清单绑定全部成员，提交后用仓内`check_evidence_archive.py`核Git对象，发布回执放包外。

## 验收边界与后续

同SHA的六组1014P/4S、十五有效变异、Ruff/registry/台账、前端lint/typecheck/110P/build在04；E2E34P/2S且0重试在05，06未重跑这些叶，不迁签到文档tip或后来main。完整Python分组通过即使成立，也只补作者工程层，不等于#814正式门禁或独立验收。

#814正式收据、三领域独立终审、历史原四自然题、财务R6/R3、runtime跨进程driver/lease/未知效果对账仍分账；旧not_passed不翻，新main/#841/联合树未签。后续优先按授权做正式门禁与独立/自然验收，不再把05两个环境失败当成本轮产品未修，也不自动重启付费审查。

## 工具沉淀

分组与对账脚本随证据归档，保可复跑版本；源码冻结，不向产品分支塞第二套正式门禁。长期唯一正式入口继续归#814。可迁移的方法是先固定分母和例外环境，再按实际ID与逐阶段结果证明覆盖；记录器也要用坏副本验证拒绝，不只观察它成功一次。沿用已有证据卫生/门禁方法，不另建通用框架。
