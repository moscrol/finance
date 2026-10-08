# 联合验证收尾：文档 tip 的第二条红灯与日期依赖

这是 [10-08 联合消费者快照](2026-10-08-river-owned-joint-consumer.md) 的后续，不覆盖旧读数。时间按本地 Asia/Shanghai：收尾跨过午夜，证据根仍用原批次名 `~/.finance-runtime/reviews/river-joint-consumer-20261008/`（E）。**联合验收仍 NOT_PASSED；本轮没有修复准入或 Episode 协议，不合 main、不推送、不部署。**

## 发现顺序与固定身份

1. 代码/测试快照 `642b45358aadbc6ee2f98d11d08e4e349ff97c15` 在本地 10-08 的干净 68 文件读数为 2084P/1F，唯一红灯是 D4+D10 grounded 联合消费。原收据不改。
2. 文档提交 `ea8a5c1597a11042f0c940ca49b1bf83aaabedf8` 只改门页、日期交接、inflight 三个文档，代码与 642 相同。其自然时钟、干净树、同一 68 文件实跑是 **2083P/2F/0E/0S，97.33 秒**，不是预期的一红。收据 `20261008T162844Z-ea8a5c15-c626cc8658e9.json`，收集 2085、无筛选/xfail；收据校验 exit 0 只表示红读数来源有效。
3. 多出的失败是 `test_episode_protocol.py::test_absent_temporal_contract_first_model_messages_keep_exact_base_bytes`。单独五次均同一哈希，模块为 57P/1F；这不是按通过次数挑结果。最初“不是本轮代码漂移”的判断尚无根因，不能因 Codex 同期推进就归因于对方。
4. 第一次建 642 对照树后漏切 cwd，pytest exit 4、零测试；这是操作错误，E/`control-642-*.log` 保留，不能算基线结果。纠正后新建 detached 控制树，在 642 和干净 main `bd66de25085ea73c9c62bc7d5472371785f27e33` 分别运行同一测试，两者均得到相同失败。E/`clock-control-{642,main}.log` 留完整记录；控制树验 HEAD/detached/干净后正常移除，未强拆其他工作区。
5. 源码显示测试 `_context()` 明确设了 `today="2026-07-25"`、`latest_data_date="2026-07-24"`，却未设 `information_cutoff`；后者的 `InformationCutoff.runtime_default()` 使用宿主 `date.today()`。`runtime_date_context()` 将这个日期写入真实模型请求。业务语义中的 today 与信息截止日是两个字段，设前者并不能冻结后者。
6. E/`probe_protocol_clock.py` 只在内存中给现有测试夹具显式传 `InformationCutoff`，保持断言、生产时钟、授权核验和请求拼装不动，禁网络并在首次模型调用前捕获停止。`protocol-cutoff-ea8/summary.json` 精确验证两组请求只差 `/1/content/information_cutoff/as_of_date`：

| 截止日 | 首轮消息 SHA-256 | 原断言 |
|---|---|---|
| 2026-10-08 | `a412664e7d52aedb67df336ab914a32d010464457d41be738a22362e4afa8da5` | 通过 |
| 2026-10-09（也为当时自然值） | `300418917248e0d558e2b387b05e95c6dd0e458f15674ee359566efe1e89758d` | 失败 |

早期诊断尝试替换 date 类，被精确类型/恢复校验拒绝；`protocol-clock-*` 的错误与部分捕获保留，不冒充成功实验。最终采用显式夹具 cutoff，而非改生产校验或全局冻结时钟。

## 取舍与未修范围

| 方案 | 评价与结果 |
|---|---|
| 更新哈希成 9 日、跳过/xfail 测试 | 只让当日绿，下一次日期变化仍红；不做 |
| 改生产默认 cutoff 或接管 Episode protocol | 改了真实日期权限语义，也越过并行所有权；不做 |
| 重跑直到一红或只报告旧 642 读数 | 隐去自然时钟条件；不做 |
| 固定输入做诊断、自然时钟正式结果保留两红 | 已做，区分测试日期依赖与真实联合准入缺口；诊断通过不替换正式收据 |
| 由协议所有者显式固定该字节测试的截止日，并另测默认日期合同 | 接续建议，未在本树实施；哈希不应代替语义日期断言 |

联合消费红灯未变：D10 完整行 11228 字符，D4 三 fact 行全被准入省略；最短一条可以容纳，三条与 D10 已需 12943 字符。不能将“零事实”解释成“一条也装不下”，也不能说调排序就能保全集。main 原有 grounded metadata 缺口、DecisionBrief 悬空 ID 另按 10-08 快照交接，不接管 owned 交付引擎。新真实模型请求 0；旧 GLM 全文质量仍未过。

## 收尾证据与接续

- 后续本分支只提交本快照、inflight、门页说明，代码/测试不变。**最终 revision 的自然时钟 68 文件复跑，以 E/`completion.json`、对应收据和日志为准**；本文不预签其计数。封存是否已完成，以同级外部 `river-joint-consumer-20261008.seal-check.json` 的实际存在和哈希复核为准，文档指针本身不是封存证明。
- ea8 时已离线刷新地图并读回 `ready`、`head_matches_build=true`，查询命中真实 `_grounded_registry_for_synthesis`；仅 checkout/committed，production_verified=false，vault unavailable。不声称全部叙事或跨仓召回已验。最终 tip 的地图状态另留 E。
- Codex 在收尾时继续切换到 `codex/research-process-contract-1009`，并有研究工具路径脏改；原 river 仍固定 af1f64b9f。最终身份见 E/`coordination-final.json`，均是只读快照，不是锁或对方 ACK；未吸收其新代码。
- 量具归位：联合五证人已在正式测试；日期诊断保存为证据脚本，不升格生产工具。它只解释一个未固定 cutoff 的哈希测试；通用迁移点是“字节不变断言须显式固定动态输入”。本轮不扩张为全仓测试时钟治理。
- 下一步先协调 `AnswerSpec → registry 准入 → DecisionBrief / actual request` 的送达集合、元数据、引用闭合、溢出/反证合同。另将日期夹具缺口交协议所有者；未经该所有者修复及新收据，不把第二红扣掉。真实 GLM、真库与生产发布仍分阶段验收。
