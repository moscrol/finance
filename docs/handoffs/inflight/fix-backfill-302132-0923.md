# #83 / PR #813

## 这个分支做什么
302132固定回填整合；文档树代码旧，不从此验收/生产。不合main、不动8792/launchd/他股。

## 固定身份
- 候选 `3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59`
- 工程基线 `4cc15e703f81bce8abadee00f68caacdb0c72b4d`
- PR head未变；PR保持open/WIP/unmerged
- 07-08 main观测 `fe9fdbfd70a637efc5bcf0cfecf74080a8d6a90c`；09-10 main观测 `4db9a42b69b0d30bcf55b2eafb64151a6c1bb317`；均未做组合验收

## 当前状态
**SPEC_SCOPED_DELIVERED_QUALITY_PASS_WITH_LIMITS_C3_NOT_VERIFIED**。批10完成C3限定Quality终稿：gateway4、explore3、execute7、report1；首bash raw exit1且含 `intentional probe_bug`；供应探针10/10 passed、0 failed、0 errors；作者测试0；host evidence audit为 `EVIDENCE_COUNTS_VALID`；终稿 `PASS_WITH_LIMITS` 通过硬门。C3生产形64/39/161未直接观察，故C3 claim仍是`not_verified`，不是完整QC批准。

## 之前的失败批次
- 04-06共52请求：06供应10P但终稿schema被拒收，旧归档不改。
- 07共12请求：explore耗尽8请求无交付。
- 08共21请求：execute因漏复制两个fixture依赖，collection error。
- 09共21请求：execute因探针残留旧`/06/candidate`路径，沙箱拒绝，collection error。
所有批次无自动重试，原始收据均已归档。

## 证据归档
- 新归档：`docs/verification/2026-09-25-backfill-302132-quality-0710/`，795份、3,799,001字节，manifest SHA `b5443a4c4ac33df18d87efeb331c1eb37a63ea49ef786c9d23c91947bb265600`。
- 旧归档：`docs/verification/2026-09-25-backfill-302132-quality-continuation/`，保持不改。
- 最新批次：`/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/`
- 动态状态：`/Users/a77/.finance-runtime/reviews/backfill-302132-0923/CURRENT.json`

## 未验证 / 禁止动作
- C3生产形64/39/161未独验；C1/C2/C4-C7未审；最新main组合无工程收据。
- 供应10P是局部行为证据，不等于完整C3或完整QC。
- `merge_authorized=false`、`production_authorized=false`、`production_executed=false`。不要合入、不要执行生产回填；生产前必须逐字授权命令、日期、冻结输入和本轮父备份。

## 下一步
若继续，先重新核对CURRENT、PR head、main和归档；优先补验C3生产形数量与剩余数据契约，再针对届时最新main执行工程门禁。详见日期交接：`docs/handoffs/2026-09-25-backfill-302132-quality-continuation.md`。
