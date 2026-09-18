# R6：固定 R5 候选的四题真实 Workbench 验收

## 结论

**4 首发、0 重发、0 澄清续答；整题 0/4，`not_passed`，不晋级。**
四个 run 都 completed 且有正文；这只证明运行交付，不证明金融断言和全部任务通过。
有依据的正文、正确计算与真实登记分别保留，不把局部错误说成整份数据无效。
旧 R3 仍是独立的四首发 0/4，不被本轮覆盖。

- 业务版本：`dfd7b4ff6c52f76f342b2abeecc24c9045589d79`（R5）。
- 文档分支：`baseline/8792-financial-r6`，从 R5 文档 `1fe2ead2` 起步；本轮无产品代码修改。
- 实际入口：`scripts/workbench_probe.py` → conversations/messages API，非 CLI ask、非浏览器点击验收。
- 模型：`continuous_glm` / `glm-5.3-flash`；所有 22 条有用量的 writer 回合均报告此模型。判官和预算沿托管配置，未换尺子。
- 本地原件根（下文 `R6/`）：`/Users/a77/.finance-runtime/reviews/8792-financial-live-r6-20260918/`。
- 冻结题目/hash/判据：`R6/protocol.json`；完整 28 项逐题判据对账：`R6/criteria-review.json`；全局事实规则裁决：`R6/quality-review.json`。

## 逐题结果

| 首发顺序 | run / message | probe 秒 | API / report | 整题 | 主要阻塞 |
|---|---|---:|---|---|---|
| F1 不登记 | `run_20260918_192028_523324` / `msg_f9863ae497564f4296999fe1c34d15f3` | 125.803 | completed / partial | 未过 | 已有完整关注事项，却又提示“未给出”；Q3累计覆盖率对比H1未作同长度调整 |
| F3 逐期计算 | `run_20260918_192234_472714` / `msg_bd242f911bc74406a530bbae54915412` | 160.562 | completed / partial | 未过 | 半年/全年称“同累计长度”；存货三个月变化写成半年；0.6阈值换成问句仍公开 |
| F2 日期与来源 | `run_20260918_192515_167746` / `msg_c79db4a58cdb43bfa3b76cd822dfbade` | 105.408 | completed / completed | 未过 | 只取得结构化财报行，未取得题目要求的公告/报告文档；承认缺原文不等于任务完成 |
| 授权登记阳性 | `run_20260918_192700_589553` / `msg_f30bbfaffe02435fac7d48425891dd60` | 140.391 | completed / completed | 未过 | 正文把18−33.68写成−15.66；全年对半年比率仍被用作恶化比较 |

不同题面、四个单样本且部分外部来源动态，**不据耗时或分数宣称稳定性/速度提升**。

### 已核实的局部能力

1. **日期进入上下文**：四题均 `source=requested`，截止依次为09-17、09-16、09-17、09-17。报告期、披露日、个人复查日分开核。
2. **已得候选中的最近两期**：三道适用题均为2026H1/Q1，未跳过已得Q1而拿2025年报冒充。候选始终 `universe_complete=false`，不签官方全集。
3. **实际计算**：F1 `6dd9cb7b8fd66e2d` 3行、F3 `0c64ed377ce5fd02` 3行、阳性 `98df5f9738cdaa83` 6行。共12行JSON/CSV输入和比值与独立Decimal复算一致；H1=18/136.51≈0.132，Q1=33.68/57.35≈0.587。重复期间不算12个独立金融样本。
   - F1/F3脚本使用字面输入，逐项与当次原始观察核对；依赖hash本身不证明脚本读取了输入。
   - 阳性另有一个0行表 `6f6c065fa3d3f923`，不算完成比值任务。
   - 12行比值正确不认证所有财务同比、公式外推、HTML视觉效果或正文其他算术。
4. **三题退出登记**：隔离用户checkpoint和judgment均0。不是只读正文“不登记”。
5. **阳性真实写入**：`financial-r6-positive-20260918/checkpoints.jsonl` 恰好1条 `ck-2026-09-18-1706a4`，`source=track_next_watch`、上述阳性run、due=`2026-10-22`，judgment=0。触发用实际2025Q3比值0.765，条件可人工复查；不是自动量化阈值解析器。
6. **F2入口与日期句**：不再误索要用户附件；未来复查句E1/E2均known/bound、source_date08-22。原文获取仍缺，不能因日期子项通过签整题。

### 必须保留的反例

- F1 `parse_next_watch_items()`可提取完整单项；随后口径声明和“不登记/非建议”尾注却被整段完整性检查当坏事项，最终补全存根与正文矛盾。不能靠删完整性门解决。
- F3存货156.72→198.26差41.54亿元是03-31→06-30，半年从126.81起应为71.45。其“存货增速快于营收”未给共同窗口；H1同比存货约116.25%，低于营收182.49%。期末余额亦不单独证明现金流背离的主要原因。
- F3表格0.6/条件0.2被确定性门删掉，末尾“是否回到0.6以上”仍公开。离线原门复查也无拒集，说明有限表达覆盖漏检，不能据此宣布阈值安全。
- 判官先指出半年/全年不同，后续 guided rejudge 标 lifted，原错误句仍在。补证不可能改变期间长度；`repaired/lifted` 不等断言已经修好。仍保留V8纯语义异议不直接删句的合同，下一步修交付/确定性支持检查，不复活判官任意删除权。
- F2真实l3查询为空，结构化行能支持部分事实，但不是取得报告原文；也不能由空检索推出公司没有报告。
- 阳性正文差值应为−15.68而非−15.66；登记正确不能豁免。整体valid_until10-17和个人due10-22明示不同角色，仅凭日期不同不判冲突；全局TTL适宜性未签。

## 自然恢复与预算

阳性同一个Episode：`KeyError`→模型/审计均见 `ok=false, script_error`→空表→6行有效表；工具调用在原授权内，没有外部重发/加预算。不能把空表算成功任务，也不能让此前失败污染后续正确计算。

F1/F3各有一轮 `remaining_calls=0,reopen_tools=false` 的表达修复，后续工具请求均0。
F2/阳性则为 `remaining_calls=1,reopen_tools=false`，实际reentry `research_tools_open=true`，各派发1次finance_query；它们不是零工具表达轮。实际派发与遥测分开记录，未仅凭调用少就认证完整根预算账本。

自然未覆盖：`inputs_from_calc` 同会话缓存复用、非法URL/Mapping异常、安全旧稿异常恢复、预算耗尽时必答槽保留。这些仍只有既有工程证据，不能写成本轮live通过。

## 用量与隔离

- writer：611,778输入 / 12,205输出tokens，22个回合；provider attempts指标33、judge calls7，分母不同。judge tokens、完整账单费用均null。
- durable工具请求/结果均14；episode metrics仅12，差额是F2和阳性的各1次补查。不能挑小数作全量用量。
- 服务8838、自有PID23654及自有锁已关闭；生产8792未切。关闭时生产health六项身份相等，三个共享命名sink的bytes/mtime/hash不变，测试身份未出隔离用户根；非全机无副作用证明。
- 市场DB独立inode/只读副本，SHA256 `2d192a78205d94a1f7bcef9d90f82ed2d9ecee8b1e7a9d1e30dfe23da0eb6b89`；exports/snapshot清单不变。F10、网页、KB未冻结。
- 公共投影审计：保存的run/messages/trace/report共1253字符串，有限泄漏模式/字段检查0未决；计算编号是工具要求展示的用户产物引用，不因判官抱怨就当密钥。F2预取字段尾注为可读性问题，不是秘密泄露证据。
- 凭证初扫：210 UTF-8文本、6条精确Python模块语法命中均复核、0未决、5个二进制未扫。文档提交后最终扫描以 `R6/secret-scan-final.json` 为准；不签Git历史、二进制、外部缓存或全机。

## 收据与后续

- 每题 `cases/<id>/receipt.json` 绑定题目、user、run、message、公开正文及artifact hash；inspection与独立reconciliation均只读、网络阻断计数0，原件前后不变。
- 新文档不冒签R5全量：历史收据 `20260918T094440Z-dfd7b4ff.json` 仍只签dfd7（11929P/0F/0E/81S/2xfail），R6没有重跑Python/前端四叶。
- `R6/evidence-index.json` 是文档提交后主封印，`post-seal-index.json`验证主封印和新增收尾文件，避免自引用hash。当前提交身份、扫描及精确文件数见外部最终收据。
- 下一步先按样本与并行owner分配修复，再经授权组装干净组合候选、重跑适用工程门；不能借任一分支绿签整合。新live、push/PR、合main、部署/启用各自另行确认。
- 不重跑本轮prepare/launch/register/run/close/inspect/reconcile一次性脚本，不改原题/原稿/判决；不删除保留数据。
