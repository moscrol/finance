# 2026-10-05 · Grounded 同行多标记绑定修复

## 背景与授权

用户要求继续推进，最后由用户统一合并。本轮继续 PR #52，不合并、不部署、不切生产 8792；#51 合入前不启动其 invocation directory 后续单，#53 仍等待 #49 合入后再换 base。

上一轮最终 `b0243e77a` 已通过本机完整 **20481P / 77S / 2X / 0F0E**，收据 `gate-OJ1x8DCS/pytest.json` 经原树 `--require-full-scope --expect-revision` 与 target==tree 核验，GitHub 五项全部绿。本轮新增代码不能继承这张旧收据。

## 发现顺序与更正

1. 逐字读取 D4 候选原件 `run_20261005_172109_317056/grounded_composer_shadow.json`，对照解析器，而不是只读它生成的错误消息。**原稿有 20 个完整 marker，旧 parser 只产生 7 个绑定单元**。
2. 根因：旧 parser 对每一物理行只 `.search()` 第一个 marker，却用 `.sub()` 删掉全部 marker 后把整行正文送去核验。故后续连板、涨停、知识库正文被错误地套在市场总量、主线名单、口径说明上。
3. **更正上一轮 PR/任务板里的“D4多段实际未引对应证据”**：这些原稿段落有显式后续引用，是解析器丢了，不是作者没引。模型确有别的内容错误，但不能用程序丢出的引用推断作者漏引。原冻结输入不改。
4. 建立回归后红：同行独立绑定、第二 marker 的未知 ID 被掩盖、无绑定尾文偷借前句证据、parser/repair 编号错位、主体改绑改到前句、公开整行删邻句、截断丢已完成句、判官所见编号不一致。
5. 在 `answer_model.normalize_grounded_binding_lines` 统一边界：每个完整 marker 是单元终点；同一 marker 前有多个自然句时不按标点猜拆。完整 marker 内换行只作折叠；无绑定尾文留为独立行继续拒收；空 marker 新报 `grounded_composer_empty_binding`。
6. parser、repair、旧主体改绑器、presenter、截断保留和 judge 消息 builder 共用此边界。旧 orphan marker 只接紧邻无绑定正文，不跨空行/标题；多余空 marker 不吞并。
7. 产品修复提交 `17948c1386ae4beb45bbe59fc3fb93f7bda5fd15`，在其干净树上跑入库量具消费同一 7 稿；输入原始字节哈希及问题逐条一致。

## 方案与取舍

| 选择 / 被否 | 理由 |
|---|---|
| 以完整 marker 为绑定边界 | 作者已提供明确出处，恢复协议即可，不替作者选来源 |
| 拒绝整行 union 所有证据 | 会让前句借用后句来源，掩盖错引和未知 ID |
| 拒绝先把所有物理行拼起来再按 marker 切 | 无出处上一行可能偷借下一行的 marker；正文换行仍是安全边界 |
| 不按句号/分号自动拆分 | 一个 marker 合法覆盖一段话；拆开后该怎么分证据并无确定答案 |
| 只修 parser 不修消费者：否 | repair / entity rebinder / presenter / judge 仍会错编号或连带删句 |
| 扩公司正则白名单把 D4 全保留：否 | 独立问题；同句还有证通电子→证证电子误写，不能以保留更多字作为质量目标 |
| 冻结同稿重放后再验新交付 | 重放便于归因，真实首发才能证明最终用户消息确实走通；二者分账 |

## 验证与证据

根：`~/.finance-runtime/pi-vs-8792-claude-review-1005/`。

- `binding-boundaries-red.log` 首轮21F/3P，其中两个消费者测试是fixture漏传必需字段；修fixture后 `binding-boundaries-red-02.log` 才是完整行为负例。
- `binding-boundaries-focused-01.log` 238P；`binding-boundaries-focused-02.log` 因误点不存在 `test_ask_synthesis.py` exit4，未跑测试；**最终 focused-03 是19文件367P**。ruff 全仓通过。
- 新文件 `intelligence/tests/test_grounded_binding_boundaries.py` 最终31条，含真实 `synthesize_shadow_grounded_answer` 消费者（mock provider，不是新模型答卷）、有错/无错首稿、判官off/llm两种路径。
- `scripts/review_probes/grounded_binding_mutations.json` 在17948c138上 **9/9 killed**，基线31P，逐个指定断言红、还原干净；`binding-mutation-summary.json` / `binding-mutation-logs/`。覆盖 parser、repair、无绑定尾文、空marker、主体改绑、presenter、截断、判官布局、跨行marker。
- `replay-binding-17948c138.json` 是新干净树7稿结果；对照 `replay-final-a472605e2.json`（上一轮工具版，其answer_model与b0243相同）。无新检索/生成/模型判官，没有补模板。

### 同稿保留读数

字符含空白与标题、不含marker；新增换行会贡献少量字符，因此另核去空白字符，不以长度判质量。

| 题/端 | 错误数 | 保留字符 | 去空白保留字符 |
|---|---:|---:|---:|
| D1frozen 基线 | 1→1 | 2107→2107 | 1989→1989 |
| D1frozen 候选 | 7→7 | 1416→1416 | 1317→1317 |
| D1v23 候选 | 3→3 | 1500→2113 | 1403→1981 |
| D4frozen 基线 | 3→1 | 1185→1551 | 1084→1433 |
| D4frozen 候选 | 7→2 | 352→1747 | 321→1643 |
| D6 基线 | 3→3 | 1208→1208 | 1113→1113 |
| D6 候选 | 2→2 | 940→940 | 855→855 |

D4基线剩余错误是没有marker的第一段结论，保持拒收。D4候选剩两条：公司短语被识别为“板梯队共进股份”、gap句只绑fact；前者是识别误报，后者来源资格仍有问题。未放开。

**恢复1747字不等于内容通过**：D4原稿将“证通电子”写为“证证电子”；严格双红源列表14项含重复“工业金属”，原稿列去重后13名却仍称14个；“资金聚集/最强”等概括也需语义判断。机械数字集合匹配不能发现所有这类错误。旧7题每端n=1，候选向量worker关闭，不能作性能或总体优劣结论。

## 后续与停止规则

- 最终文档提交后才跑干净HEAD完整门禁并推送；本机收据、最终CI、首发真实交付结果追加PR #52评论，不为写收据制造新HEAD。
- 计划在隔离旁路串行首发D4frozen与D1v23各一次；固定题面/代码/模型，保留第一稿，不为追绿重采样。模型身份不符、无非空原稿、接口失败均如实失败；有结果只说明对应交付，不证明相对旧端更好。
- 旁路用户态、Episode和启动账单独落树外；只读保护生产数据与配置，向量worker仍关，差异记账；不改判官生产配置、不把旁路当部署。
- 本轮复用已入库重放器与变异运行器；没有新增通用框架。公司命名/去重计数/语义验收是另项，不能悄悄放宽标准纳入本解析修复。
