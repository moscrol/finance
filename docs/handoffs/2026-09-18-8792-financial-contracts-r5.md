# 8792 R5：财报选期、截止与计算交付合同

## 身份与结论

- 唯一实现树：`/Users/a77/fwp-wt-8792-financial-contracts-r5`，分支 `fix/8792-financial-contracts-r5`。
- 业务提交 `dfd7b4ff6c52f76f342b2abeecc24c9045589d79`，父提交为 R4 文档封存 `068e2a4652d7b8e0250c9d046272e7889b15c5b9`。基线 `gitea/main=0a1cb8c44aaf2d19ae5f5809bf27119b709b8442`。
- 用户授权是“修一下，不要和别的 agent 冲突”。R5 独立实现和离线工程验证完成；没有新真实模型发题、push、合并、部署、判官开关变更。
- **旧 R3 固定四首题、零重发、零澄清续答，整题仍 0/4、not_passed。** 工程通过不翻旧判，也不证明自然修复效果。
- [工程收据](../verification/2026-09-18-8792-financial-contracts-r5/README.md)；[机器摘要](../verification/2026-09-18-8792-financial-contracts-r5/results.json)。本地证据根 `~/.finance-runtime/reviews/8792-financial-contracts-r5-20260918/`（以下 R5/）。后续仅文档提交不冒签新 HEAD 全量重跑。

## 背景：为什么必须继续修上游

R3 的三份研究稿已经取到 Q1，却把 FY25/H1 当最近两份；context 仍用运行日而不是用户截止日。计算反复失败，工具外壳却都是 `ok=true`，成功计算尚未落盘又不能在同一研究会话沿用。R4 修过材料归属、跨排版数字门、清单与日期角色，但没有解决这些财务合同。

总合同不变：确定性坏断言要拦，局部错误不连坐可信邻句；同会话、原权限与既有根预算内修复并复验，补不齐则保留可信正文、明确缺口。不能以工具成功、非空正文、API completed 或诚实 partial 代签整题完成。

## 按发现顺序：实现与反例

1. **先隔离所有权。** 从已封存 R4 开新树，反复读取三条并行线状态，不复制未提交实现。data-readiness 已提交的同批数据行预算/模型标签按限定范围借用，来源见下节。
2. **日期先认角色。** `honesty_gates.requested_information_cutoff()` 接明确截至/信息截止表述，显式与旧站立日回退共用用户可见指令边界；报告期、披露日、复查日、材料引用、代码块和否定表达不升级成截止。`target_report_end_from_query()` 将年份绑定邻近期别，保留原年度公司财务问法。
3. **两表同批交付。** 主表/现金流表按真实数据行给额度，表头不占；主体、报告期、披露日、指标累计口径在模型可见文本中标注并重算证据 hash。没有二次取数。
4. **分开选期与可用性。** 新 `financial_report_contract.py` 按报告期选最近 N 期，披露日另核截至可用性；旧期可供同比/还原，不偷换最近 N。缺披露日、较新无数值候选保留收据，不能让两份旧期掩盖不确定性，候选集一直 `universe_complete=False`。
5. **绑定不代替交付。** `verify_episode_outcome()` 只对 financial_analysis 的 metric_evidence 检查所选期指标绑定和正文期别列示。真实 `expand_episode_snapshot_bindings()` 自动全绑定的反例仍会检出漏 Q1；缺口只影响该槽，保留 hash、其他槽及 draft。
6. **失败观察必须交给下游。** derived 失败机器码/gap/可修提示同时进入模型与审计，telemetry 仍不进模型。empty lookup 与计算失败分开；table/chart 提示给真实可执行签名，不新增 title 别名，不改沙箱 prelude。
7. **同会话成功计算先复用内存。** `bind_derived_calculation_tool()` 用本次 bind 的闭包缓存成功记录，miss 再走既有用户 loader；新 bind 不继承。实测原 `base_calc_not_found` 因“只认已落盘”出现，修后无需再取数或先落盘。
8. **组合针先校准量具，再抓真实假完成。** 结构缺口在首次语义检查前修复，故观察真实 structural verifier，而不是硬凑两次 semantic。随后 repair=False 仍 completed 的真红定位到不可达降级：预算耗尽把 metric 必答改 optional。只在 `mandatory_satisfiability` 保护该财务槽，不改 runtime、不拆其他领域降级。成功修复 completed，失败 partial，两 judge 模式都保留可信正文且零新增工具额度。
9. **加新反例，不迎合旧例。** purpose 叫“净现比”但产物只有无关数字仍曾放行；改核实际 observation.metric，不信标题。同期完全重复行去重，冲突版本却排除并留 gap，不随意取第一/最后一份。三种等价净现比请求的真红补入同一有限句式；计算 ID 必须对应已绑定实际产物。
10. **固定版本再验。** 脏树定向 599P 后显式提交 12 文件；干净 dfd7 全量、前端、E2E、注册表、14 组 R5 与 16 组 R4 撤保护、旧 QC15、旧原文重放及 R3 只读诊断全部完成。没有为挑绿重发真实题目。

## 方案对比与取舍

| 决策 | 采用 | 被否方案 | 理由与剩余边界 |
|---|---|---|---|
| 日期来源 | 用户指令角色/归属优先 | 取全题首个日期、让 legacy 回退复活已排除日期 | 复查/期末不是信息截止；有限句式不等通用自然语言理解 |
| 最近 N 期 | 报告期排序＋披露可用性收据 | 按抓取/披露先后挑两条，或把旧年报当最近一期 | 排序与可用性是两个判断；仍非官方全集证明 |
| 历史未知项 | 保留明确缺口 | 缺披露日推“没有报告”，或跳过较新空壳 | 未知不等不存在；明确截止后披露不阻塞正确旧 pair |
| 重复版本 | 完全相同行去重，冲突不合并 | 任取首/末行、拼成一份可信报告 | 没版本证据就不能替供应商裁决 |
| 指标交付 | 核绑定＋正文期别 | snapshot 全绑即完成、全篇拒绝 | 仅局部槽缺失；列示仍不证明逐期分析/公式正确 |
| 预算耗尽 | 停取数，保留必答义务 | 自动把 metric 降可选；追加预算/另开研究 | 权限和完成判据不能互相代替 |
| 计算成功 | 产物指标＋有限值＋依赖/ID | purpose/标题、exit0、非空文件即成功 | 仍未证明数学正确性、逐期比值齐全或正文支持 |
| 非必要计算失败 | 不连坐独立事实 | 一次失败永久污染全轮 | 直接事实/定性比较无需强迫计算器；主动比值/计算ID仍受核查 |
| 同轮复用 | 本 bind 缓存成功记录 | 全局缓存、等落盘、重取同批数据 | 不跨会话/用户扩权，不加预算；不承诺沙箱完全无临时文件 |
| 错误反馈 | 模型与审计都见领域失败 | 仅 telemetry、抛成整个 tool batch 失败 | 传输成功与领域产物成功不同；empty 是独立状态 |
| 计算接口 | 精确 table/chart 契约与例子 | 修改 prelude 接口迎合错误 title 参数 | prelude 纯标准库和版本规则不动 |
| 组合测试 | 按真实阶段观察 | 为凑 verifier 次数改 runtime | R5 结构修复与 R4 语义删句修复所处阶段不同 |
| 验收 | 新 revision 自己签工程收据 | 借 R4 全量、用旧题重发挑绿、全拒答 | 反证包含 all_financial_answers_rejected，拒绝一切不能过门 |

## 并发与借用来源

本轮没有修改任何 `intelligence/runtime/`、沙箱 prelude、protocol 或 semantic verifier 文件。
共同 `research_harness.py` 只把投影中的固定 `ok=True` 改为 `observation.result_status_fields()`；非整文件接管。

限定借用 data-readiness 已提交来源：
- `a93b50c2ee69022e2b0106f825e6d6079a707afb`：两表真实数据行额度/失败观察思路；
- `a9a7ce9228661156da3054d67fd7ea33b83adf45`、`d77383acce048e58b1f8cce87ed0b5f5452282e4`：主体、报告期、指标文本标签；R5 另留披露日。

未整枝 cherry-pick，不引资金事实扩展或全部历史日期改动，不将借用冒称原创。

收尾快照 `R5/owners-closeout.txt`、`owner-shared-seams-closeout.txt`：
- answer-preservation 已从本轮最早 af9500ec 的脏状态前进到 `35ee8a5c` clean；FinishCandidate/steering/admission 改动当前不触及本轮投影段。
- runtime owner 从 `48823062` 前进到 `26dea412`，还有新一批未提交 runtime/持久化改动；共同 registry 当时新增 sub_research replay 属性，当前不触及 R5 ToolObservation/计算描述段。
- data-readiness `d77383ac`，其交接/lessons 仍在收尾。

这些只是读时状态，**独立 worktree 不消除未来整合冲突**。后续整合先刷新三线 owner diff，尤其 harness、registry、episode_tools/market_financials；重组干净候选再跑适用门禁。本轮没有组装它们的组合候选。

## 证据、首红与结论边界

干净 dfd7：Python **11929P / 0F / 0E / 81S / 2 xfailed / 17 warnings**，672.08s；Ruff 过，前端 lint/typecheck/build＋107P；fixture E2E **34P/2S**。收据 `20260918T094440Z-dfd7b4ff.json`，八项条件一致、base drift0。此耗时是单次执行，不做性能提升结论。

保留首红和修正复跑，不把量具/夹具加载失败当产品反证：不存在测试文件 exit4、pytest 保留参数名 request、错误 OutputBinding 名/缺 hash、tuple 当 JSON、purpose 缺失、deadline API 拼错、指标简称与 glossary 不同。真实缺陷反证是预算假 completed、purpose 伪产物、冲突版本、等价比值请求与同轮成功计算复用失败。详情见 verification README。

撤保护各组必须 exit1、tests>0、failures>0、errors0、源码不变；不是“所有错误都可接受”。旧原文57事件只重放解析与进度投影，不是完整 Episode 重放。旧 R3 原题截止解析为09-17/09-16/09-17/09-17，但旧 context/正文/评分不改；F2 没被新补答。

隔离 E2E 用8893/8895且客户端 RE06 URL显式一致、独立 users/DB/episodes/账本/rejudge/vault，测试服务已结束。新回归阻断 Python socket、脚本化 provider/model/judge；不能声称全仓或整个操作系统零网络/零写入，也不签生产当前 health 身份。

未签范围：官方报告全集、供应商历史窗口完整性、metadata/正文日期不一致的金融裁决、正文逐期分析/比值完整性、公式与依赖的真实数学使用、比较基线、全局到期日冲突、自然模型修复/真实金融质量、非法URL与旧稿恢复的新增自然覆盖。成本未知记 null，不把 writer tokens 当完整账单。

## 工具与记忆归位

- 重复排查固化为仓内 `scripts/review_probes/run_financial_contract_mutations.py`，docstring 写明失败形状；复用旧 QC/重放/诊断工具，不重建第二条 live 启动链。
- 本地 `prepare_closeout.py` 等仅一次性收据组装/扫描/封存，非通用产品工具，保留在证据根且不重跑 exclusive-create 步骤。
- 跨项目原则回写 `contract-vs-delivery-mismatch`；能力图谱新增分支符号，项目笔记仅一行索引及看板。共享 memory 有并发写者和自动同步，不能按整个文件认领他人新增行。
- 本轮新测 vault 基线 **20 errors / 17 warnings**，不是沿用 R4 的19/17；回写后同类问题未增，仅已超限项目笔记字节 warning 变化。图谱在共享并发下177→184断言无漂移，R5仅新增4个符号，其余3个属另一 agent 的数据链，不冒领。完整增量收据在 `docs-memory-validation.json`。
- `harness-reference` 仍有他人的 BUILD.md 脏改且工作树身份与远端不同；不覆盖、不顺手同步 KIT/TOOLKIT。若后续要推广通用 runner，再在干净最新基线登记；当前只在 finance 内承接这一领域反证套件。

## 接手顺序与禁止事项

1. 若要新自然复验，先另获授权，固定业务版本、题目/预算/判据与隔离写口；真实 Workbench 会话首发，正文/核验/登记分别对账，失败不重发挑绿。
2. 新 live 不等 push/合并/部署授权。整合其他分支后工程必须重跑，不能迁移单枝收据。
3. 不重跑 R/R3/R4 一次性 launcher/关闭脚本，不补答旧F2、不改旧评分、不恢复历史清理删除器。
4. 不顺手并入下游基线/全局期限、凭证历史治理、共享 vault 债务或其他 agent 在途代码。
