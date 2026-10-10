# 上线后的回答质量根因与陈述资格接口

> 历史保全：来自 #78 `a52bf2676`，正文状态属于 10-08；后续实现由 #80/#82 接替，当前合集仅保全文档，原首答 `NOT_PASSED` 不变。当前范围见 [第二批记录](2026-10-11-release-wave2-integration.md)。

本快照记录已经发生的发布、唯一首答、独立审查与离线实验。生产基础优化完成，全文质量仍未通过；下一轮生产合同尚未选定或实施。

## 发生顺序

1. 数据与时间合同候选755472a84经两轴独审后，通过准确head与实际main各自的完整门禁。GitHub PR76正常合入main e3f88f2974f8cce2a74af9fbb1c6d9037ade746a，8792切到同一干净固定快照，fingerprint一致、13项就绪及部署账本通过，备份main回读对齐。
2. 保持原问题、GLM-5.3-flash和900 worker/900 continuous/600 initial Episode/120 fuse配置，只发一次新用户首问。native clonefile冻结当前库100f、权限0400，受管RAG代际readiness-20260927-43430ddd首尾相同。clone回退被执行层护栏拒绝，未产生整库copy2。
3. 唯一run_20261008_132253_459354完成并公开。8个唯一物理attempt均成功、身份准入通过；Episode/Trace是同组的两种视图，不能加成16。全部8原生模型前缀复核一致，根Episode1/子分支0。物理账每attempt usage字段缺失，费用未知；native token合计388556/5661不能冒充完整逐次账。
4. 独立全文审查接收PASS、内容NOT_PASSED。4主题/68总行/24预览、组内非空与省略、方法原来源及9/30时间合同真实送达，新增电力设备和地产对照被采用。模型最早seq44将已算false的免疫治疗资格写成true；seq49只改反证basis，正文逐字不变。seq57有效修订仍保留该错误，并新增没有完整候选集支撑的“医药无高标”。行业涨幅/成交额也被升级为指数贡献和轮动原因。
5. Root以原contract和110个私有v5原卡回放finish parser：44因basis拒收，49/57正常准入；E999负控仍拒。随后无损重建完整outcome/frame/9trace/events/bindings/usage，调用真实structural与semantic verifier，保既有off模式。本地非过期时钟只用于离线接缝，不驱动adapter或整轮。结果仍completed/passed，公开字节精确与原A845相同且矛盾保留，网络/SQL/模型/子进程0。
6. 用户再次强调“不要打补丁式修补，多找根因”。Root即时写入canonical用户纠偏，并补共享方法笔记。核验缺口与模型首错分别归因，没有把结构parser本来的格式职责叫作源码bug，也没有改写原失败。
7. 三个独立设计比较最小接口、扩展性和常见调用者。所有方案都承认合法schema或自声明kind/basis不能证明自由正文含义。程序拥有结果文字的方案随后做一次离线可行性原型：13组控制、24个实际信号与canonical匹配，确定性片段局部GREEN；原稿和原公稿保持unassessed/内容NOT_PASSED。生产wire、持久化及最终公开出口尚未接线。

## 被否方案与理由

| 方案 | 评价 | 当前决定 |
|---|---|---|
| 给错误句子加提示、词表或特判 | 正确false已经送达；不能以更多提醒解释已发生的反向读取 | 不采用 |
| 同版多抽一轮挑好稿 | 不能检验根因，还会覆盖真实首发失败 | 不采用；新版本独立验收才发一次首答 |
| 补所有数字到StructuredObservation | 原110卡为空，但通用数池会把规则、历史基数和未来阈值混为一谈；R20已有负控 | 不作为修复 |
| 让作者填新声明schema | 结构命题可核，但作者可以填false而正文写true；合法字段不是蕴含证明 | 不以schema直接认证全文 |
| 更清楚的同源ResultView | 能集中对象/日期/单位/规则/集合，减调用者负担；不能单独证明任意散文 | 保留为设计候选，尚无自然收益结论 |
| 结果owner提供资格族与关系回执 | 可复用核验，仍需声明到正文的可信关系，接口和持久化成本较高 | 保留对照，不先造通用DSL |
| 程序拥有可计算结果的文字出口 | 原型已证明不可将获证false改为true；自由推断仍未认证，实际wire/恢复改动不小 | 局部可行；不是已选定生产方案或全文根治 |

## 收据与不能推导的结论

私有证据根为 `~/.finance-runtime/answer-evidence-quality-1007/round2-release/`：

- `release-state.json`及`release-execution-755472a84/release-proof-index.json`：准确发布、head/main各自门禁与备份。各自collected21149=21071P/76S/2X/0F/0E；fullscope校验与失败数分别核对。
- `prod-first-01/frozen-index.json`：118项冻结、模型/日期/库/RAG/原始稿与公开身份；SHA54d580a86a832d2c861a268bafab7cd7472b97840adeebad3a4d329e38457433。
- `first-answer-content-review-1008/report.md`和`machine.json`：17条claim与实际模型可见证据，全文NOT_PASSED；报告SHA36fedbd220947a518da32d8d0778f21e49171cad1cf64c75b60930aefb348919。
- `root-first-answer-triage/`：M1原件根因报告、0.095秒finish接缝控制/红证人、真实semantic接缝回放与独立确认。
- `qualification-designs/{minimal,flexible,caller}.md`：三案，全部是设计而非产品能力。
- `qualification-prototype/receipt-02.json`：唯一完成的13组控制；module225行、runner270行，只写原型目录。初次准备误把native/outcome/public字节等同，原错误和脚本完整保留。

原seq57和outcome draft均2072字，SHA8ec4bca68145b305665aa83e2dc465b3749056dbbad1b53cdbf989d7cfc620b0。公开2194字包括既有四处待核，SHAa84579530284e94c7898e2fb339e88f5cedd07c651327cc5378190ccce3f302c。便于读的first-public-answer.md精确追加一个LF，SHA09d3325c379bfa0e960f6da9dfbff4224df3b1f4071e070936281794927c4e66。身份差异有解释，不改原稿求绿。

原型source identity使用整份完成Episode摘要；实际合成前生成稳定ref、后续事件追加时不改绑的合同仍未实现。不能拿本地选择引用成功签真实Episode接线完成。

本题没有KB/RAG、个人memory、River专属投影、独立反方检索消费；可用环境不等于已消费。只观察到7条领域基线和5条带原来源指导。旧Pi05物理库45b与本批100f不同，只可比较具体答句，不能签严格受控A/B、整体赢Pi、成本速度或长期记忆收益。

## 接续工作与归属

Root负责结论支持关系的设计验证。下一步必须先确定自由正文的实际证明范围、同源结果和可认证文字的所有权、稳定ref身份及旧None/wire/finish/repair/carry/restore兼容，再写小而完整的实现计划。不得为消除unassessed而假称已检查正文，或把局部原型GREEN换成全文质量通过。新源码需独立两轴、准确完整门禁、合入部署后一次真实首答，原失败继续保留。

Pi正在`fwp-wt-river-consumer-pi`修历史结果定义/适用域/投影。Root只读核对其在途文件；e3与已提交18090fc76的merge-tree在ask_synthesis.py有内容冲突，未应用合流。PR75及Pi脏树不接管，联合消费者等其结果合同完成后另验。

共享harness-reference仍脏且落后gitea/main，本次不编辑SSOT工作树。新增离线脚本是一次性鉴别实验：原件/协议尚未收敛，不复制到生产scripts或公共工具箱；若接缝最终复用，应归并现有对象和核验测试，而非再叠一次检查器。共享能力图谱只更新已有Controller行，审计exit0但315条在途未核验，不能称整张图全面通过。
