# 2026-09-18：历史表达边界与测试夹具生命周期

## 背景：两种失败不能混为一谈

目标仍是同一段 Workbench 对话完成市场阶段→历史参照→当时强势对象→启动/峰值→接力→各自启动特征比较。唯一主链保持 Workbench/Episode/history_query/canonical DuckDB/RunStore，不新增事实库或研究引擎。

之前 ba281381 已把接力状态、观察日数、原因做成同卡交付，工程通过但真实四题仍失败。第二题从历史强弱分析偏向公司优先级/收入利润传导；第三题误读未成熟；第四题未按各自启动对齐。此片只处理**错误前向表达合同**，其工程复验又暴露**测试后台任务越过夹具生命周期**，两个问题分别修、分别记。

代码节点：

- `f9afb4a0029224ed13dd3b3bb16d0a76e7c0f2e8`：表达边界，9文件。
- `672abcc504b3466a2ddd24dfa450c55703265c70`：测试生命周期，5文件；不改生产关闭或LLM行为。

裁决：672abcc5 作者侧四叶通过；没有新真实模型验收、独立人员QC或方法认证。WIP #783，不合并、不部署。

## 发现与实施顺序

### 1. 从标签线索追到实际输入与修复要求

只读旧 fbd8 四轮 durable `prompt_assembled` 和 `continuous-episode.json`，核 system/user hash 与源字节。第二题确实带持续跟踪和公司优先级模板，终态还追讨 `track_next_watch`、`ranking_flip_conditions`。因此不是仅凭 `comparison_analog` 标签推测；但这只确证一个冲突路径，不能说它是异窗排名、个股启动混淆或整组失败的唯一原因。

### 2. 同一可信用途贯通四个消费者

`track_contract.py`、`ranking_contract.py` 的 parser/guidance/rules/missing/merge/receipt/writer 接可选 `history_intent`。非空历史状态抑制前向表达合同；默认 None 保旧入口兼容。

接入 `episode_protocol` 实际提示、`continuous_turn_adapter` 缺项修复与收据、`conversation_orchestrator` 两条收尾及外层写门。历史写门在解析用户路径之前返回，两共享writer也有边界。保真正 structural missing/issues、日期与权限、历史 finish/publication 门，不让助手正文决定任务用途。

正反控覆盖普通前向题、前向题里的历史类比、用户显式停止历史任务、助手自称历史不能降合同、可登记正文的writer与真实run_turn。未传状态的standalone legacy CLI不猜用途，仍保持旧行为，产品门与词表已明示覆盖范围。

先保留测试设置红，再改设置得到真实模板消费3F，修后142P→244P→1041P/4S。expression套件8项变异守接线，旧diagnostics4/succession7集合不变。

### 3. f9冻结全量红，没有用定向绿抵消

f9干净全量11575P/1F，前端/浏览器/registry绿。唯一失败为`test_receipt_covers_calls_and_reuses_outer_budget`：公共HTTP替身计数被旧线程抢占，应收到503的位置返回了body。

先核LLM complete/预算/CLI链，单跑1P；单跑绿不能否定全套红。保持原收集与执行前缀，在HTTP替身内记录请求身份、线程和栈，复现原失败。未保存正文、header、key、raw query。

再给RunSupervisor提交标记拥有者，在无fixture替身时阻断真实_run_ask进入provider/DB：记录quota一次、admission两次逃逸；credits等teardown也仍active。插桩前缀1331P只作归因，不是正式CI。

### 4. 修任务拥有者，分离测试和生产关闭策略

三个fixture原状态：quota没有回收；credits/admission调用的生产shutdown不等待正在运行的任务。旧线程可在monkeypatch撤销后才解析runner，继而跑进真实研究或下一测试的全局HTTP替身。

新增测试helper `drain_test_client`：生产shutdown取消排队/请求停止，再对测试私有执行器`shutdown(wait=True, cancel_futures=True)`，最后close client。admission先放行gate。try/finally保证所有client退出早于替身撤销；join包括完成回调与积分结算。

新参数化测试从真实fixture入口起任务，在真实_execute前放屏障，只有wait-join才释放。退出fixture后核join发生、fake恰执行一次、active为0；即使故意变异失败，finally仍收拾线程。不是延长sleep赌调度。

定向84P。第一次内存变异丢了future annotations，NameError不计caught；修工装后删join，三个owner都命中生命周期断言。仅测试设施访问私有执行器，没有改生产shutdown、重试、预算、HTTP计数或收据逻辑。

### 5. 新冻结版本重新检查，不复用前一提交签名

确认提交672abcc5与clean，新目录跑完整四叶；期间不改源码。Python11579P/81S/2X/17warnings，890.75s；前端107P及三构建检查、浏览器34P/2S、registry五项0/98warning。正式收据八项通过，revision/dirty/解释器/依赖/日志hash/基座无漂移均核。

clean复跑历史19变异，fixture删join三owner断言红，源码未改、故意失败禁写通用pytest收据。原序诊断前缀修后1334P/3S/1X，无逃逸事件；这是有拦截的诊断，不能代上面的未插桩全量。

另按原四题保存离线controller/Harness/缺项/收据消费快照，无前向标题且证据缺口保留。空registry/脚本缺证据稿，不是新自然模型会话。

## 方案对比与选择

| 问题 | 方案 | 判断 / 结果 |
|---|---|---|
| 历史与前向混淆 | 按“历史/排名/追踪”词面全局关闭模板 | 否；普通前向题也可能做历史类比，助手正文更不是授权 |
| 同上 | 只删初始prompt模板 | 否；repair、receipt、writer还会恢复错误义务 |
| 同上 | 同一可信HistoryIntent贯通四个消费者 | 选；用途单源，提示/检查/副作用一致；只去不适用义务 |
| 证据不足 | 为避免partial放宽历史finish或删真正缺件 | 否；偏题修复不是证据资格升级 |
| 兼容入口 | 新增可选keyword-only状态，默认None | 选；Workbench明确接线，旧CLI覆盖不足公开保留，不暗猜 |
| 全量单条失败 | 重跑单测绿就忽略、改HTTP计数或过滤后台请求 | 否；掩盖前一任务越过依赖生命周期 |
| 同上 | 改生产shutdown为永远等待慢IO | 否；会改变线上响应/退出语义，问题属于测试拥有者 |
| 同上 | 测试先放行、join完成，再撤替身 | 选；受控有界任务局部回收，保生产策略 |
| 竞态回归 | 长sleep/随机重复抽测 | 否；不能稳定证伪，消耗高且可能假绿 |
| 同上 | 真实入口+确定性屏障+删join反证 | 选；验证依赖生命周期次序，不认证时延分布 |
| 原四题质量 | 现在盲跑同题直到绿 | 否；已知同窗/启动/原件消费尚未修，不能靠重抽掩盖 |

## 验证入口与证明边界

入口：[672abcc5验收](../verification/history-market-anatomy/672abcc5/acceptance.md)；manifest含95份来源/副本、34源码hash、8份未改旧原件身份。固定结果、f9正常红、单测对照、诊断插桩、开发dirty、故意变异、工装设置错误分目录，不合算“通过率”。

原始运行根：`~/.finance-runtime/history-expression-672abcc5-checks/`；原f9根保留。当前代码的全量收据是`20260918T125515Z-672abcc5.json`，不是全局latest；随后文档提交不自动取得新SHA全量签名。旧接力开发同秒JSON覆盖没有补造，通用命名修复仍另案。

测试框架的裸assert可打印`E assert ...`而无字面AssertionError；一次人工检查器因此误判，保真实FAILED且无setup/import ERROR为证，不修改产品凑检查器。

没有新的DB补数、行情写入、生产画像/台账改动、每日链或生产服务部署。定向测试/插桩/脚本Episode/原件算术/semantic通过均不能代真实研究正确。

## 可迁移沉淀与工具盘点

- 用途贯通消费者原则补既有 vault `contract-vs-delivery-mismatch.md`；后台任务生命周期补 `terminal-signal-scope-and-projection-waits.md`，不建平行原则表。
- 可复用expression变异已在仓内既有`history_diagnostic_mutations.py`；fixture helper与确定性回归在测试基础设施，非只有文档提醒。
- harness自有`docs/history-query-probe`树核clean且底不旧后更新KIT/TOOLKIT，`c0a4d0cd8244a9541b45a49e844e36bf71ea5ced`已推未合；check_refs退出0，候选引用仍按分支/冻结源码核，不误称全都已在main。共享BUILD与保护镜像未改。
- 固定SHA四叶runner、保存样本提取、原执行前缀插桩、归档打包器只针对本次样本，保runtime及归档`.py.txt`，不伪装成泛用研究或业务判官；迁移的是生命周期/消费端不变量，任务归属与断言要重写。

## 接手者应继续什么

1. 同一参照窗内的全市场板块/股票与成员排名合同；不能为拿到非空结果偷偷缩窗或更换参照。
2. 板块信号日成员路径与个股自身启动分开；各自启动日对齐特征，并保留未启动/失败/缺数/未成熟对照，不把筛选条件当新规律。
3. 跨轮主动消费旧原件，不依赖旧助手错答；继续核实际菜单、调用、投影、引用、最终正文。
4. 已知片修完再跑原四题、原窗，新隔离users/conversation/instance与显式EpisodeStore，保存health前后。仍不强制工具或换题刷绿。
5. analogues独立排序审计、人员QC/真实浏览器研究交付、完整方法前向认证、每日水位/代码根、收据唯一命名与vault存量lint另列，不混入本片结论。

合并和部署分别等授权。当前真实四题失败仍是返修输入，不是已完成的能力。
