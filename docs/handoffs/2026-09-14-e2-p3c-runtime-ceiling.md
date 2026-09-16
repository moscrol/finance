# E2 P3c：运行期注册表消费者的读取上限

## 背景与冻结身份

开发树 `/Users/a77/fwp-wt-e2-boundary-closeout`，分支 `fix/e2-boundary-closeout`。
本轮承接 `812b4d46`（P3b 作者收据与独立阻塞）；应用冻结 **`b4ba6fb5aa1f6e4f27bac1fcc2db163fe74bacf0`**。
D1/P2/P3a此前已独立通过；P3b、P3c仍无有效独立报告，未推、未合、未部署。
设计权威仍是 `docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok/E2-DESIGN-material-contract-2026-09-13.md` v10 D4/A16。

## 按发现顺序

1. P3b 独立 Codex 重试在工具前 502/429；Claude 备用 503、零工具调用。没有有效代码裁决。
2. 仅准备同一 P3 内的可单独审查小片，不跨到 P4：发现 Scope 构造器只限制自己的注册表副本，Episode/adapter/batch 其他消费者仍持原 full 注册表。
3. 新测试捕获首轮真实模型请求：未知 IO 工具进菜单，外部预取哨兵进消息。Scope dispatch 拒绝不能撤销这种提前注入。
4. 增加 `ResearchToolRegistry.for_context()`，复用原有单调 `with_read_scope()`。在 adapter 消费预取升档/可满足性预检前；Episode 配置快照/工具绑定/提示词/账本播种前；批菜单/定义/执行前；内存修复续轮重新绑定。Scope 改用相同 helper。
5. 避免“同上限直接返回 self”的优化：受限对象字段可被晚注入预取/加载器，重新构造须重新清洗；相反 full 普通上下文保留对象身份，不扩大兼容破坏。
6. 新增15针：原始registry+受限context、陈旧菜单、有无Scope拒绝与事件、参数解析/runner尝试计数、修复续轮、晚注入、认证local runner仍能执行、不兼容注入registry在消费预取前失败。Episode车道用合成题固定；没有改原题/评分/46针。
7. 完成代码提交、干净冻结测试、独立请求、两次全仓测试后才写本快照。

## 方案对比

| 方案 | 评价 | 决定 |
|---|---|---|
| 只依赖Scope内部副本或dispatch拒绝 | 不约束原注册表的提示词/预取/菜单消费者 | 否 |
| 原地改调用方registry | 跨任务复用时可能污染full上下文 | 否 |
| 各消费者入口拿同源、只收窄副本 | 覆盖局部运行路径且保留调用方对象 | 采用 |
| 同scope短路返回原对象 | 晚注入prefetch/calc_loader不会重新清掉 | 否，保留受限构造语义 |
| 借本轮解决全部来源纯度/恢复/确定性旁路 | 大幅扩大未审范围，不能用小片绿测证明 | 留后续P3 |
| 把审查CLI启动成功或作者测试绿当独立通过 | 工具前服务失败，根本未审代码 | 否，保留阻塞 |

## 验证与收据

统一解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
归档目录 `docs/verification/e2-boundary-closeout/`：

- `p3c-before-812b4d46-tests.txt`：修补前应用+同一最终15针，**12 failed / 3 passed**。仅新增测试的临时树 `/tmp/e2-p3c-before-812b4d46`，不是干净基线全测。
- `frozen-b4ba6fb5-tests.txt`：干净代码提交，11个相邻文件 **439 passed**，exit0；机器收据 `20260914T135236Z-b4ba6fb5.json`。
- `full-b4ba6fb5-first-tests.txt`：干净全仓 **9776 passed / 1 failed / 83 skipped / 2 xfailed / 17 warnings**，exit1；机器收据 `20260914T135831Z-b4ba6fb5.json`。失败 `test_rag_worker.py::test_warm_worker_survives_first_timeout_and_drains_the_late_response`，next查询2秒超时。
- `rag-b4ba6fb5-rerun-tests.txt`：同revision单文件 **44 passed**。
- `rag-before-812b4d46-tests.txt`：修补前同一RAG测试10次均pass。相应应用/测试文件在本轮diff为空，**仍不能断言环境根因或已证实既有失败**。
- `full-b4ba6fb5-rerun-tests.txt`：未改代码/阈值/跳过集的同一干净提交完整复跑 **9777 passed / 83 skipped / 2 xfailed / 17 warnings**，exit0；机器收据 `20260914T140639Z-b4ba6fb5.json`。首跑红收据保留，不隐去不稳定性。
- Ruff、diff检查、全部提交钩子通过；代码地图 ready @b4ba6fb。
- `qc-b4ba6fb5-blocked.md` + prompt/log：独立树 `/tmp/e2-p3bc-qc-b4ba6fb5` clean，Codex工具前503，exit1。P3b/P3c均未独立放行。

机器收据均位于 `/Users/a77/.finance-runtime/test-receipts/`。全部新测试离线、临时资源/脚本模型；未做金融模型验收，未读写生产用户台账。前端/E2E本轮未跑，非合并收据。

## 未验证与下一步

- 先用归档prompt重做固定P3b/P3c独立审查；有效报告前不升阶段通过，不堆更多未审切片。
- 仍待P3：歧义/基底不可恢复预取前澄清；controller摘要/stance/project prior/视角；普通context来源过滤；压缩、崩溃恢复、子研究、非工具provider事实、确定性旁路与回落。helper不能撤销registry_factory内部已经发生的IO。
- local_only原题号槽/更多runner认证，以及P4逐题三态、P5可信继承/旧答身份、P6材料锚点纯度、P7原始全新T2→T3未完成。T3不得重贴禁令遮继承漏洞。
- 内存repair测试不是崩溃恢复纯度测试；保留local认证是假设可信Python装配，不是网络沙箱。
- RAG超时未稳定复现：后续若再红固定调度/IO证据分诊，不直接调大2秒或删测试。
- RE06 I14另线；重叠补丁6c7bea6e/413b7a07集成须写接替。合并/部署另获授权。

## 工具沉淀盘点

无新增通用CLI或/tmp专属工具；新行为探针已进正式测试文件，红基线已归档。可迁移原则归入共享记忆既有 `gate-covers-only-its-return-value.md`，不另建重复清单；本轮未修改harness通用搭建件。取消后空模型响应的续轮测试曾触发严格消息派生不一致；最终续轮用正常partial结束再repair，**不关闭派生门、不冒充覆盖取消恢复**。
