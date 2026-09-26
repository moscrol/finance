# H-02 可信历史读取上限继承返修

## 背景与范围

用户“执行”授权继续修 H-02、补正反例与变异验证，不重启独立审核、不合并、不部署。旧 #845/d91aff9d8 解决了受测 H-01 引文控制问题，但合法省略续问“那它们见顶后谁接力？”和“以前有没有类似，失败案例也看看”仍继承历史窗口/截止而丢 material_contract，授权面出现 web_search/web_fetch。旧红例包不覆盖。

本轮源码固定为 `fix/history-forward-boundary-0921@7c99f389e9c72668663449dedeacd7fe4830cbdd`，已推 #845。父为 d91aff9d8，原 #833 7edfe24e7 不动。文档和证据仍集中 #838，源码不因交接推进。整体历史仍 **CHANGES_REQUIRED**。

## 发现与实现顺序

1. 恢复时源码 clean；代码地图首次 refused_empty，按有界 full build 重建。结构层可查询，不把缺失 vault/doors 视为架构结论。
2. 沿 controller、TaskFrame、合同编译、用户消息回放和真实 run_turn 查到三处不同步：材料编译未认省略续问、回放下一轮把合同重置 full、真实入口未收集该类续问的 typed history。
3. 复用历史续接判断和逐轴材料编译器。ConversationMaterials 新增回放的 history_intent；compile_contract 在历史续接且链缺失/截断时移除可继承基底，编译为 state_unavailable。只有 completed 原始 user 消息恢复权限，assistant 只作上下文。
4. 控制器先编译合同，再进入正常路由；TaskFrame 随序列化冻结。入口在识别历史续问后送达 typed replay，备用控制器的宽权限旧 frame 要重新编译。通用指代回填也必须同步恢复合同，否则澄清。
5. 三条旧正例只传任务意图、不带用户原件，按新安全边界被拦；补原始用户链，不撤缺链反例。当前用户显式放宽仍通过原逐轴编译器。
6. 正常测试发现两条相邻输入边界反例：短“材料如下”段与未闭合中文引号中的省略句，分区器不标 uncertain，仍误续接历史。不是测试预期错误；独立保留并固定 SHA 重现，未改期望或 xfail。它们在新版本保 local_only、原窗口/截止，没有证明联网授权或实际工具执行。
7. 固定源码后四组回归及十种进程内变异重跑；旧收据不移签。新证据包 history-permission-repair-02 封存 58 成员加 manifest。

## 决策与取舍

| 方案 | 评价 | 结果 |
| --- | --- | --- |
| 直接复制 previous intent/旧助手答复中的权限 | 缺可信用户来源，且新任务/取消会受旧权限污染 | 否决 |
| 只补当前轮 material_contract | 下一次原始消息回放仍重置 full，真实入口也可能不传基底 | 否决 |
| 复用合同编译，增加确认后的历史续接输入 | 两轴仍由同一编译器处理；当前用户可显式变更 | 采用 |
| 未知或截断链默认 full | 将权限缺失等同允许，无法区分旧限制是否消失 | 否决，先澄清 |
| 扩写新引号/材料解析器顺带解决新反例 | 涉及共享来源分区，不能以本次读取继承修复替代专项边界验证 | 本轮不做，红例保留 |
| 给 770 定向绿签完整验收 | 仍有正常版红例、完整门禁与独立终审缺席 | 否决 |

通用指代的直接 controller 正例带可信 typed history；这不声明真实入口支持所有通用自然追问。真实入口未恢复该基底时保守澄清，后续可按体验需求扩支持，但不能先放宽读取。

## 固定验证

源码 7c99f389e 干净树：168 + 169 + 242 + 191 = **770 passed**。242 组包含 H-01 41 例与 H-02 新 49 例；另一次正常量具 90P 与其重叠，不加总。全仓 Ruff、diff-check 通过。完整 argv、时间和前后 HEAD/status 在包内 frozen-check-*/receipt.json。

H-01 变异 partition/history-infer/follow-up/resolution-hint/cutoff 各 24/15/6/1/4 断言失败；H-02 history-contract/replay/authority/delivery/backfill 各 42/2/17/3/1 失败。每种有真实 call 阶段 AssertionError，collection/setup/teardown 零错误、源码哈希前后一致。

H-01/H-02 夹具禁并计数 socket/DuckDB 连接；H-02 另禁并计数意外 llm_refine.complete 调用。外部工具 dispatch 反例在 runner 之前拒绝且 runner 尝试数为零。历史工具只登记，不执行。770 的其他回归包含临时 DB 测试，不能称全部零 DB。

新相邻正常反例 **2 failed**：见 `history-permission-repair-02/frozen-check-adjacent-unresolved/pytest.txt`；剩余工具为 memory_lookup/finance_query，history_query 仍错误登记。record_check 总 exit0 只说明预期红例复现，不能读成产品绿。

## 首错与量具边界

- 新测试首次裸模块导入失败；改成 tests.test_history_control_boundary 后执行。首 traceback 仅工具会话可见，不重造日志。
- 入口变异第一次误选 run_turn 包装函数，anchor 不唯一；没有有效收据。第二次 120 秒超时 exit124，保不完整日志，无 result.json，不能宣称该中断轮零模型/IO 尝试。
- 备用控制器在撤保护后绕过原截停点。补研究计划前截停和模型调用计数后，dirty 第三次及 frozen 入口变异都完成并产生断言红，确认无后台 probe 遗留。
- 一度误判 parts.regions 的存在性，临时条件已撤。对象始终存在，最终代码不含多余条件。
- 变异 runner 支持点分方法定位、dedent 与 AssertionError 计数；依然是本项目定向量具，不另造平台。跨项目原则复用既有 gate-covers-only-its-return-value：路由状态与权限必须同步，但来源不能靠路由对象自证。

## 接手与禁止事项

新包：`docs/verification/2026-09-21-research-tail-forward/history-permission-repair-02/README.md`。归档/发布的不可变提交校验在后续包外回执，本文不预填尚未完成的发布动作。旧四包 281/28/38/45 成员不得改写。

下一步先针对短材料及未闭合引号反例修共享来源分区，覆盖合法省略续问和现有材料/引用边界，不牺牲 local_only。再按授权补精确源码完整门禁、独立终审和自然四题。旧自然 not_passed 不翻案；新 main、#841、三领域联合树未验。无合并、8792 部署、夜跑装机、生产回填、清树或新付费审查授权；#814/#829 与邻线不接管。
