# 追问输出身份：候选有界通过，内容红灯阻塞

## 这个分支做什么
从发布2aea独立修复已有目标槽位时的重复direct_answer；不接管PR16比较器或R18预算线。

## 当前状态
代码/测试已提交4cba44a63，基座2aea7c27e。只改TaskFrame编译与runtime别名共享，终稿校验未改。**相关632P/1F，禁止合入/发布**；无新模型/推送/部署。
普通红例：`test_owner_output_identity.py::test_boundary_only_prose_must_not_stand_in_for_the_direct_answer`。旧基座同样1F，不豁免。

## 决策与被否方案
| 选 / 否 / 原因 |
|---|
| 生产端条件去重 / 否终稿放宽 / 各消费者应见同一合同 |
| 保留独立要求与旧frame / 否全表归一、历史迁移 / 避免吞要求及改身份 |
| 保留正常红测试 / 否xfail、逐字照抄门 / 不藏内容错误或误杀改写 |
展开：[日期快照](../2026-10-02-owner-output-identity.md)。

## 已验证
固定4cba锁环境13文件632P/1F、收据适用性过；新身份24例、5/5变异捕获且还原。三问ASGI回放合同complete，保存intent/frame/owner/gate集合及hash一致；不认证全文。
前端125P，浏览器40P/2既有S：原三视口及新增两问六断言均过；lint/type/build/Ruff过。独立19071/19074服务已退出，临时基座/变异树已清。

## 未验证 / 已知边界
词元重合仍让boundary-only正文冒充直接判断，answer_spans可写入未显示claim。正文仍有ONTOLOGY摘要冒作判断、重复及模板内容。原句仍走concept_definition；无目标时旧ID刻意保留。
未跑全仓Python、前端重新安装、新远端CI、独立review或自然模型全文验收；作者自验不能移签历史独审。共享httpx有漂移；锁环境633例不替代全量。浏览器只做Python外网guard，非OS沙箱。

## 下一步
1. 独立审2aea→4cba；另立正文见证修复，保留本红例与合法改写对照。
2. 红灯解除后在最终组合SHA跑全量/前端默认链/registry/CI，再独立全文验收；当前不签发布。
3. R18预算由原owner负责，R17已结案不重跑。

## 踩过的坑
变异restored-full仅所选24例；中间443P/1X已失效。API消息DTO没turn_intent，查持久化messages.jsonl最后同ID记录。前端未install，只独立克隆依赖。
证据`~/.finance-runtime/reviews/owner-output-contract-20261002T100000Z/`；[报告](../../verification/2026-10-02-owner-output-identity.md)含解释器/范围。最终文档HEAD不冒充被测SHA，见closeout。
