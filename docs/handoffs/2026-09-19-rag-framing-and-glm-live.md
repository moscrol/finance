# RAG 读取已修，完整工程通过；一次 GLM 已交付但整体未过

## 裁决

用户在上轮RAG阻塞交接后说“执行”。本轮只在 `feat/research-answer-preservation` 继续：
修复 `20939b18bcb4a00f1eec9098dc52887ab1f71c02` → 干净完整门禁 → 冻结协议 → 隔离8849正式Workbench入口首发1、重发0、续问0 → 只读审查 → 停自己的服务。未push、合main、部署或切8792。

- 工程：**11703P / 81S / 2X**；前端115P，E2E34P/2S；ruff、lint/typecheck/build、四项registry均exit0。收据属于20939b18，不移绑后续文档提交。
- 新live `run_20260919_002806_645542`：completed + 精确published消息，2137字正文、公开报告/答案产物hash匹配；报告仍partial，未把研究不完整标完成。
- 真实14轮主模型 `glm-5.3-flash`；工具请求16＝结果11＋错误5，ID全部结算。参数错误没有升级成Mapping崩溃，错误前97条证据hash仍在最终122条里。
- 模型自行修正结束格式，但**系统保稿机制未获证明**：首稿JSON字符串含未转义换行，候选解析返回None，`retained_candidate_count=0`；不能把模型自行重写当保稿机制过关。
- 作者逐项原证据审查发现下限算错、终点收益外推区间路径、实体/来源口径未区分。**整体not_passed**；同源产品判官passed不是独立金融认证。
- 两个旧live仍not_passed；365627fd E2E红、49fd中止、7a9380bd RAG红均不改判。

[验收说明及机器收据](../verification/2026-09-19-rag-framing/README.md)。

## 1. 读取修复的选择与边界

上轮真消费者＋OS管道诊断证明：`TextIOWrapper.readline()`可预读旧、新两条响应；丢旧后select只看空内核管道，把已在用户态缓冲的新响应误判超时。另一方面，select只保证至少有字节，不保证完整一行；阻塞readline会越过截止时间。

| 方案 | 取舍 | 结果 |
|---|---|---|
| 增大timeout / 重跑原测试 | 不修双层缓冲，幸运调度也会绿 | 否 |
| 每字节read直到换行 | 可诊断预读差异，但低效，阻塞半行仍需处理 | 不用于生产 |
| 专门reader线程＋queue | 可行，但新增线程、停止/EOF/请求归属生命周期 | 本次不选 |
| 非阻塞`os.read`＋显式换行缓冲 | 一个消费者掌握已读字节和截止时间，批量读取，保持现有锁及单进程结构 | 采用 |

`intelligence/services/rag_worker.py`：
- stdout只有`os.read`读（最多65536字节一批）；既有text stdin写请求不变，不混用stdout的TextIO读取。
- 先消费完整缓存行再select；没整行才等待内核。按整行UTF-8解码，避免字符跨批被误判。
- 一条请求一个绝对截止时间；旧响应、半行、虚假可读都不续时。
- 暖进程首次超时保留半行与abandoned ID；第二次仍按原策略kill/自愈，不增加时间预算。
- 新进程清空旧半行/abandoned/连续超时并重置模型加载计数，冷进程不能继承“已经预热”。不修改检索算法、索引、KB写入或生产配置。
- 本次约束是**响应读取**；未另改排锁/请求写入的预算语义，也未加新消息大小策略。

新 `test_rag_worker_transport.py` 用真管道＋消费者验证合并行、半行跨放弃、UTF-8切片、长行、绝对截止、EOF、错误/重复ID、坏JSON/UTF-8、虚假可读；原测试另加真实子进程替换状态隔离。首次旧实现3F/1P，状态测试首次2F；修后定向69P。独立副本六组撤保护：等待先于缓存、丢半行、逐块续deadline、逐块解码、跳ID、继承暖状态，均exit1；恢复69P、树干净。非独立QC。

已有量具 `scripts/review_probes/replay_rag_buffered_late_response.py` 增 `--expect repaired`；默认仍期待旧失败。新候选正确期待exit0，反向期待exit1。原18c7诊断及老扫描收据未改。

## 2. 固定工程与一次性协议

私有根 `R=~/.finance-runtime/reviews/research-rag-framing-repair-20260919/`。
完整收据 `~/.finance-runtime/test-receipts/20260918T162610Z-20939b18.json`，UTC时间09-18/本地09-19。
全部叶子在同一干净revision开始/结束；前端静态产物与7a9380bd零差，build未弄脏树。

原历史缺end回放仍真parser拒绝、反馈返回、44证据/参数/原件不变，0模型/网络/DB；旧两次拒收保稿原件回放也过。都不是新live，也不改旧样本。

协议`R/protocol.json`：主zhipu/glm-5.3-flash、兜底名openai但模型glm-5.3（同智谱端点）；max40步/600s/60s综合保留，实际Episode llm_timeout75s；判官继承llm，同源非独立。900s服务窗、960s客户端、1020s监督窗。无额外试模型请求。

行情独立副本3,692,572,672字节，SHA256 `2d192a78205d94a1f7bcef9d90f82ed2d9ecee8b1e7a9d1e30dfe23da0eb6b89`，截至09-17；与旧样本同数据，inode不同。KB/web/财务在线输入未冻结，**非严格A/B**。仅从已授权启动器的export行读配置到进程环境，不执行主体、不写凭据；候选Keychain禁用、users/episodes/cache/vault分根。

冻结后占用一次提交名额，再用`workbench_probe.py`走conversations/messages正式入口；只有GET观察，没有补提示、续问或恢复旧run。

## 3. 新样本逐层读数

- user=`probe-rag-framing-20260919`
- conversation=`conv_b1cf0368ed3f4a66ad0bb5f437f27f0a`
- run=`run_20260919_002806_645542`
- assistant=`msg_04f66e8b950242888b8703babe3317b6`
- 主Episode14响应、14 provider attempts；输入712209/输出6027 tokens。汇总provider attempts15、tool_calls15，判官1次；**两个口径不等同，不当全链计费**。
- 先缺entity_codes，随后补确切990026.FP并成功compute_history；find_analogues参考窗口4次失败，未自行解决，后改查历史窗口，结果值missing。原缺end未触发。
- 第13轮：前缀＋字符串含真实换行的JSON，`not_json_object`；第14轮正确转义后准入。候选保留数0，durable phase done、turn14。
- 只读诊断用`json.loads(strict=False)`检查**这一份原件**，不是拟投产宽松解析器：首draft2096字→终draft2094字，仅“今日→当日”“FY-A01→判读规则”；bindings/history refs不变。公开终稿完整以该2094字开头，再附43字历史未完成提示。正文自然延续，但不能证明换个模型重写也会保住。
- 报告partial，历史用途insufficient_evidence/research_only；同源判官passed，不能抵销结构未完成或作者发现的事实问题。
- RAG预热readiness成功，本次主Episode**无kb_search请求**：不能称真实查询压中了迟到双响应；该边界证据来自确定性回归/变异。

## 4. 金融质量拒收原因（作者复核，不是独立QC）

| 问题 | 原件对照 | 判断 |
|---|---|---|
| “相似窗口最低12个” | E1三段窗口双红均值12、13、8 | 明确下限算错 |
| “5–20日没有系统性下跌，涨停/连板/双红不收缩” | E1只给5/10/20日终点收益，不给区间最大回撤；首窗涨停62→54/56/57，第二60→60/59/59 | 终点外推路径，非收缩断言也过强 |
| PCB -1.19%与-2.42%；涨停3与0 | E18是PCB概念，E19/E100是PCB；E94题材热度与D4投影不同 | 未向用户区分实体及口径，不擅选一个当权威 |
| “胜率中等”、3–5家/≥10家阈值 | 没有概率校准或阈值验证结果 | 应明标待验证观察假设，不包装成已验证标准 |

有竞争解释、日期、三个历史窗口和缺口提示是实在的进步，但不抵销以上错误；不以末尾免责声明代替逐句对账。

## 5. 关闭与封存

服务PID34684已停，8849/8851/8852均无监听、所属锁移除。生产七项身份及启动器hash不变，仍`bf662e9310ff`，行情/exports未变，测试用户没有落共享用户根。检查范围是声明根，不是OS沙箱证明。

旧214/44/90/6/82/296/338/341包本轮前后逐项hash一致。新包423文件/17,991,204字节，manifest SHA256 `877af81dfbabec17eba778faa14f364aca22a801bdd958a614dbd7c6afe6b720`。
公开/episode/event扫描0命中；全包首次14个jwt词形命中均精确核销为源码模块名，未决0，**不称全包零命中或独立安全审查**。UTF-8及zip文本成员扫描，5个二进制只hash；代码/数据另按revision/manifest，后续closeout排除。

首版审查脚本误要求私有continuous-episode出现在公开artifact列表，assert exit1保留；改为核准确run私有原件＋公开answer/report hash，另记exit0。没有改服务合同以满足错误脚本。

## 下一步与不做

1. 针对本次第13轮安全文本保留范围单独设计：格式拒收与候选安全/身份校验继续分开；不要把诊断`strict=False`或任意截花括号直接放宽成生产准入。先用封存原件/恶意反例离线验证，再决定是否扩保留。
2. 历史查询窗口纠参、统计外推和同名板块多口径需分账处理，不靠删掉整篇稿解决质量问题，也不把同源judge通过当证据。
3. 新live需要新修复、新干净门禁和新的有界授权；本样本不再发、不resume。合main/部署/切8792仍另等确认。
4. 通用能力已进入生产回归和仓内量具；控制器/本次语义审查留实例根，不造第二产品入口。共享harness-reference的BUILD.md仍为他人脏改，不覆盖；可迁移教训回知识层。
