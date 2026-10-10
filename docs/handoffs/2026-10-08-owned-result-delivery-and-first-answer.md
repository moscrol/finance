# 同源结果文字所有权：发布与唯一首答

> 历史保全：来自 #81 `7c86d613f`，正文记录 #80 的部署与首答时点；后续 #82 不翻案原首答 `NOT_PASSED`。当前合集仅保全文档，生产已非 bd66，范围见 [第二批记录](2026-10-11-release-wave2-integration.md)。

## 背景与选择

用户要求先优化上线再对比、harness比Pi更全面且简洁、持续查根因。上一批真实首答的免疫治疗349.327/strict false已到实际模型，seq44仍写true、有效修订保留；完整原件走真实核验仍原样passed。输入、计算、模型理解和核验必须分开，不能继续加数据或改错句。

| 方案 | 评价及结果 |
|---|---|
| 更多提醒、错句词表 | 正确false已经交付，不能切断自由改写；不采用 |
| 作者另填真假/kind/basis | 标签合法不证明正文蕴含，旧修订只改basis未改错句；不采用 |
| 更清楚的ResultView | 同源表示有价值，但不能签自然正文；作为结果目录复用 |
| 程序持有结果文字 | 采用有限保证：作者选opaque refs与自由文档块，程序渲染选定片段；free始终未评 |

仅支持D4已批准同日板块的canonical严格双红、本地规则定义、本表主题与预览覆盖。没有为全市场唯一、完整最高、指数贡献生成资格；没有新judge、预算、IO或第二引擎。设计与实施见 `docs/superpowers/specs/2026-10-08-owned-result-delivery-design.md` 和同名plan。

## 按发现顺序的实施与验证

1. 原型通过13组控制/24实际信号后，源writer逐步实现投影、实际ACK、ordinary `answer_parts`单正文、native finish/repair/carry/finalizer/source-only恢复、精确owned数字区间与最终公开coverage。source-only恢复不能补EvidenceLedger/floor；所有旧None与自由正文不自动获证。
2. 精确040clean的1218相关caller通过。Task2的295旧收据实际dirty（下一未收集测试WIP），原字段保留，不再称clean；所有定向收据都不冒充全仓。
3. 固定7b3独立Spec发现最终只比owner，撤mainline/cutoff收窄仍faithful。275修为不可变原receipt在最终coverage前复用原来源准入，当前context重编译；节点已删也重核。原反例不改断言转绿，Spec/Standards通过。
4. 275完整收集21205=21124P/1F/0E/78S/2X，失败抓新拒收字符串绕过统一view。停止发布并保存完整原红。1c310将两原因接到已有verification_incomplete视图，只登记真实新caller，允许函数表和文本出口表未扩；必要602caller通过，增量双审通过。
5. GitHub PR80正常合入，actual main `bd66de25085ea73c9c62bc7d5472371785f27e33`，parents e3+1c310、tree `ff3b0b5aaa66cc4c14083ae359ae10599688424d`，没有其它队列混入。head/main各自完整收集21207：head21127P/78S/2X、main21129P/76S/2X，均0F0E、无遮筛、未绕依赖、首尾clean/source稳定；前端六项、registry五项、各五CI全绿。两项由skip转pass是环境差异，不能只报一个混合读数。
6. 固定snapshot `~/.finance-runtime/finance-workspace-bd66de25085e` 用locked venv；既有helper正常切8792。实际full40、clean/code matches、1333模块及loaded=repo fingerprint `bc4dcd75649465d82d5b7616b705092ae553f42e64cd48de946cc9f36a4a071e`、13ready/idle0、canonical strict full40 switch/startup账本通过。备份success985refs，两端main同bd66。

部署state `~/.finance-runtime/answer-evidence-quality-1007/owned-delivery-1008/release-state.json` SHA `6ca97135be4df201b1974343f0fcd37c46c3ec9b8cad2b8485d2af3f8bf38a9c`；新release包 `release-execution-1c310178/release-proof-index.json`含384原件。旧275全仓红包不删除，不用旧green补新版本。

## 唯一新首答及整篇裁决

实际Workbench唯一run `run_20261008_221011_445118`、conv `conv_97d78a1c58394e8cac86baebfd690f09`、assistant `msg_60a904ac717a477eb7089e09740e9cd1`。原题Q+LF SHA `cf97c9489d474813910306416faca7ddb0975d4ee5699c2ab3ef15a2ad22496b`，user `probe-owned-result-delivery-1008-first-01`。worker900/env900/initial600/fuse120/client960原装配；无新Pi、无重抽、无truth注入。

首prepare因动态RAG环境未捕获，在0turn/0clone/批未建时停止；外部helper改为白名单观察当前serving PID字段并用实际deployed capture_generation验证，保留原失败/diff。没执行整个launcher、没落完整进程环境或凭据。native clonefile/0400源首尾 `f89785e21319563523d753719f693185ea986facaa1aeb5cbcd3685bd6e064f5`；不同旧100f，RAG generation/manifest不变，不签严格同输入A/B。

5唯一成功physical actual reported glm-5.3-flash、663准入0、unknown/未证分支0；39native事件/5model_intent对应5完整prefix、无引用child。Trace与Episode同五次不能相加；9candidate/repair记录不是9model。Trace无usage但native5条均有，input227303/output4970；费用/cache未知，不填0。

首稿seq24因basis格式拒收；seq29调整后finish，再一次数字backfill40秒，seq37修订/seq39接纳。公稿1753字、4427bytes SHA `22dff80f58fec68df40f263260f81d0e41f45d2b31b81c200827f64a4090f290`，仅比末稿多确定性待核标注。批 `owned-delivery-1008/prod-first-01/frozen-index.json` SHA `ebe4e5bf53d5ac5f5b370d300a5cfbe4095930c8cf1568e3e1cf816f9c5d6efe`，88文件hash/bytes/0400；旧118件保持。

独立 `content-review-first-01/report.md` SHA `08a0df743cce45867dbdde4346203e2b8991018599d31b13d503e07d8ed0aa79`；intakePASS、整篇NOT_PASSED，28claim为10PASS/7PARTIAL/11NOT_PASSED，不当正确率。

| 面 | 可签事实 |
|---|---|
| 有效部分 | 当日广度/日频/三条strict true正确，四主题/68行/24预览/44省略实际送达，公稿范围说明较旧更准 |
| 存活主错 | seq24开始，医药presence2天被写连续3天/最佳（电力4）；重叠主题成员次数30/52被当去重集中度（前50主题和222>52）；量价推指数贡献；节后观察推翻9/30、权重解释不加权家数 |
| 次要验证问题 | 任一成立识成一成，已交付500规则/E3九家被标无出处；部分slot binding范围不完整，存在与资格分账 |
| Programme采用 | seq12提供26refs，后四prefix均保留；三份终止JSON都无answer_parts，receipt0/coverage空。只证明已提供未采用，不判主观拒用 |
| 真实成稿合同 | system各prefix仍给旧status/draft/gaps/bindings模板，tool才说明answer_parts。模型合同未统一是可观测接缝；其对非采用的因果尚未证明，且统一格式不代签四类free错误 |
| 知识与记忆 | 七baseline、五ReadingRule与量价定义实际送达；量价定义被用。KB/RAG/wiki/图谱、个人memory、River未调用；D4历史聚合不是River。没有证明知识全消费或长期记忆增益 |

第一次市场query parse_error已自修，未传播，不当内容PRIMARY。正确producer/projection后seq24自由合成错是PRIMARY；格式/数字处理未拦且新增误报是SECONDARY。Root不把更短/更少调用或免疫错句缺席读成纠正同命题、代码因果或整体胜Pi。

## 后续与工具沉淀

先统一实际system/schema/finish表示的owner；日期集合与连续性、题材union/分母、指数贡献资格、反证目标时间另需同源可证对象，不能通过格式接口或数池给free默认发证。判官off、预算、现有权限及简洁表达仍是约束；Pi仍负责独立history生产对象，不双写其脏树。

生产纯计算owner已进services、真实门洞已有负控；发布复用规范gates/collector/admission入口。外部本轮取证脚本含固定batch/唯一身份，保留证据而不包装第二通用工具清单；跨项目可迁移的是“身份不等于当前权限”和“schema支持不等于实际模型合同已消费”，写共享知识层。`~/harness-reference/BUILD.md`发现他人dirty，未改KIT/BUILD。

本枝仅事实文档；生产仍是已核bd66。未来实现另从最新origin/main认领，先设计与离线反例，不重抽当前已冻结首答，不修改这两张NOT_PASSED判定。
