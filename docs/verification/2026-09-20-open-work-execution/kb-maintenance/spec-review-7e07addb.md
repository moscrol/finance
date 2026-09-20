# KB guarded maintenance — 7e07addb 静态 Spec 增量复核

**结论：静态增量复核通过，未发现八项合同回退或新的 Spec 阻断项。** 此补丁补齐成功路径落盘前的 writer 身份重检，符合原规格的单写者和故障恢复要求，可用于最终文档的 Spec 结论。

范围固定为 `1bd5e1dc8d48f59461c79f35ea553e1cda71a6ec → 7e07addb466385085e21ccaf3d06bf23c6e4b0a1`。本次仅阅读 Git 固定对象差异、仓内新增正式测试与已有日志 / 收据，并核对收据引用日志的 SHA256。**没有运行测试、独立动态探针或故障注入，也没有转交他人重跑被中断的动态路径。** 独立动态签署仍只归此前 [1bd5e1dc 报告](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/spec-review-1bd5e1dc.md)及更早固定提交；本报告不将其冒用为 7e07addb 的独立动态结果。

## 差异判定

源码改动保持既有语义，在明确副作用前增加 `assert_writer()`：

- `activate` 在已批准 manifest 解析后、替换单一 current 前检查；`approve` 在验证后及计算批准回执后、创建审批目录和写回执前检查。
- `prepare` 在独立消费者返回后、写消费回执前，以及 seal 后、写最终 validated 回执前检查；原有异常失权后不落盘的规则保留。
- publisher 在验证后创建 publication 目录前、以及远端元数据回读后创建本地下载目录前检查。若失权，保留最后一个已经合法写入的 running / remote_may_exist 回执，不写伪成功或越权失败回执。
- request 仍使用自己的短锁，在最终请求落盘前再次检查，不重新成为索引写入入口。

八项映射：第 2 项单写者、第 7 项故障恢复得到直接补强；第 1 项仅排队 / 无默认旧树写入，第 3 项双索引与代码 / 源身份，第 4 项独立分母，第 5 项本地发布门，第 6 项单 manifest 与热 worker 绑定均未被放宽；第 8 项整代发布、远端回读、最终精确 tag 身份校验保留。新增测试不改变旧测试判据，分别在根或锁身份替换后断言未知根 / 锁保持不变、旧 current 保留、审批 / validated / 消费回执不存在，并对 publisher 断言不创建目录、不下载、不修改失权后的记录。

## 现成正式收据核对

[精确 SHA 验收收据](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/acceptance-7e07addb466385085e21ccaf3d06bf23c6e4b0a1.json)绑定 `7e07addb466385085e21ccaf3d06bf23c6e4b0a1`；其四项日志的 SHA256 与文件实际字节一致。

- [最终定向日志](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/success-control-final-focused.log)：**80 passed in 46.25s**。
- [精确提交全量日志](/Users/a77/.finance-runtime/open-work-execution-20260920/kb-maintenance/full-7e07addb4.log)：**911 passed in 56.03s，0 failed，0 skipped**；正式收据记录工作树 clean，真实金融测试来源为 `4ace5ec2e9b7735d90eb15bc2351fa193c1120b8`。
- strict-vocab / tracked-file-size / quality gate 的收据 exit code 均为 0；strict-vocab 仍有 2 项告警，quality gate 的准确结论为 **“无回归，仍有历史债务”**，不是整体质量良好。
- 初始 **8 failed / 2 passed** 与第一次修复 **1 failed / 77 passed** 的日志仍保留。文件名 `success-control-boundaries-green.log` 实际属于后一个失败窗口；本报告的 80 项通过引用 `success-control-final-focused.log`，没有误认旧文件名。

本次不涉及源码修改、生产索引 / `uchg` / hooks / 8792 操作或真实远端资产发布。八项合同保持成立的结论来自此前独立 Spec 验收、上述有界静态差异和本次核实的正式收据，三者证据层次已明确分开。
