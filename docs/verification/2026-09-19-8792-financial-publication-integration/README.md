# R6 × 精确发布边界：固定版本收据

业务 **d06dc1e8d1adf6ba8b39bd02333af6299416dc1d**；从文档0b16bc03继续，旧业务d9657215。
仅移入49fd8d72发布片、在本树构建静态前端；非整枝保稿/RAG/runtime合流。
背景/取舍/首红与下一步见 [日期交接](../../handoffs/2026-09-19-8792-financial-publication-integration.md)。
文档提交不改变本包签署的业务SHA。

## 判决分账

- 固定干净Python **12198P/0F/86S/2X**，17 warnings；Ruff0；前端115P及lint/typecheck/build0；E2E34P/2S。
- **engineering.json.all_passed=false原样保留**：宿主旧KB导致registry红。固定finance d06＋KB91725ea9＋site9f60bef原生五项全0；不是把宿主红改绿。
- publication8、financial-delivery6、financial-r613、research-delivery13组，每组撤保护有断言失败、恢复通过；默认extraction35组是测试体失败→绿，28组含断言、7组仅异常型。各套分母不相加。
- 发布组还保留1条SSE缺事件ValueError。JUnit无type属性时，必须读message/正文，不按缺失属性猜失败类型。
- 四原件有限回放、12输入hash不变、连接尝试0、临时登记0/0/0/1；不是新Episode或最终公开答案。
- **本候选新live=0、独立QC未跑，旧R6/R3仍0/4 not_passed**。F2取回未修；published不清金融partial。未push/合main/部署/切8792。

## 证据怎么读

`pytest-receipt.json`来自完整pytest.log精确指向的20260918T170550Z-d06dc1e8收据；同SHA0执行收据不算覆盖。
`receipt-check.txt`八项条件通过，不重跑测试。`registry-pinned.json`记录三个实际输入及前后状态。
`*-mutations.json`记录同SHA基线、每处撤/恢复、全套恢复和源码指纹；XML/diff原件在外置根。
`mutation-failure-classification.json`逐组列真实失败种类，保留AssertionError与运行期异常的区别。

`transplant-baseline-red.txt`后端13F（7KeyError/1ValueError/5断言），`frontend-baseline-red.txt`8F/107P；
前端命令实际跑整套，并非过滤子集。`transplant-first.txt`4F/145P是新测试漏传必填字段，
`seams-fixed-fixture.txt`修后4P；`related-development.txt`417P只属开发态。
初次收据文件名写错exit2、无效JUnit type分类稿仅外置保留并标invalid，不冒充产品失败。

原始根：`~/.finance-runtime/reviews/8792-financial-publication-integration-20260919/`。
JSON逐字节复制；文本展示副本只去行尾空白与EOF多余空行，manifest分别记录原/副本hash、字节数及转换。
不改原始日志或旧封存包。`SHA256SUMS`覆盖本包除自身外所有文件，manifest不自哈希。
外置指纹只取证据目录直接文件，不遍历pytest临时数据、用户目录、worktree或软链。
有限秘密模式扫描零命中不是通用认证。graph_audit0只证符号/路径；vault仍20E/17W，工具包refs0有存量漂移。
