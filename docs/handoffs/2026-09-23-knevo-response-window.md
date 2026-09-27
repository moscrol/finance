# Knevo 响应读取时限续修：交付仍失败

## 结论与版本

代码 `7cfc51d524681e2b9a8740e6b16e064a32006ed1` 修补工具聊天的响应体读取窗口，并保留材料审稿首层失败和阶段耗时。PR #877 保持 WIP；不合 main、不部署 8792、不回补、不写生产画像。

干净定向工程通过不等于交付通过。新隔离原题包1、包3均 failed，尚未进入材料判官；本轮不能签判官线上预算验收，更不能签八问语义通过。旧三包失败、旧 f1fd 0/12、冻结28题与七份原件均不改判、不改写。

证据根：`~/.finance-runtime/knevo-absorption-20260923/response-window-7cfc51d52/`，索引 `current.json`。

## 发现顺序

1. 刷新代码地图后沿 `SemanticEpisodeVerifier -> GLMModelClient -> chat_with_tools -> urllib` 检查。旧包1材料首层收到75秒，下一层150秒共享窗已归零；trace从开始核验到最终投影约224秒，但没有每次HTTP耗时，不能倒推出唯一网络故障。
2. 底层 `urlopen(timeout=...)` 是网络等待超时，不是响应体总耗时。用本机HTTP服务持续发送小块数据，初始6测5F/1P：旧实现会接受超过调用窗口的有效JSON或流式答案。这是独立复现，不是补造旧运行台账。
3. 新 `_tool_response_window` 沿本次请求开始时的绝对截止时间，响应头返回后只使用剩余时间；到点对现有连接 `shutdown`，唤醒阻塞读取，退出时取消并等待计时器。晚到结果拒收，异常仍按已有 TimeoutError 处理；流式已吐正文后继续禁止回退重播。不增加调用、重试槽或预算。
4. `_run_judge` 原来首层没有报告就直接返回，导致包3这类首层失败没有阶段明细。现在每个实际审稿阶段都保存原有诊断与 `elapsed_seconds`，包括首层失败/无需二次复核。`inspect_run` 只导出耗时数值，旧记录没有耗时仍为 null；私有原文仍不导出。
5. 固定干净7cfc版本后，经原 Workbench Conversation 入口跑包1、包3。两题各在写手首发和既有终局补写阶段流式失败，没有形成有效八问稿，也没有进入材料判官。不是改题、减问、关判官或重试后选优。

## Live 结果

配置身份为 `continuous_glm / glm-5.3-flash`，不是认证实际供应商模型身份。加载指纹 `5c99f8c73a180426f8fd61898d51d377475826d98bd3e3e2373f99681b1bade8`，health 中 revision一致、dirty=false、code_matches_repo=true。新用户目录、Episode和数据根；复用用户标签 `probe-knevo-0923`，不声称OS沙箱或身份认证测试。

| 原题 | run | 结果 | 事件时间差 |
|---|---|---|---|
| 包1 | `run_20260923_185629_765585` | failed / repair_model_unavailable，probe exit2 | 首发请求75秒、约75.013秒返回；终局补写请求39.995秒、约40.012秒返回 |
| 包3 | `run_20260923_185825_569313` | failed / repair_model_unavailable，probe exit2 | 首发请求75秒、约75.010秒返回；终局补写请求39.995秒、约40.014秒返回 |

时间差由 model_intent/model_turn 的持久事件时间计算，包含适配器开销，不是独立HTTP计时。错误已扁平为“流式已输出后失败、不回退”，没有底层异常类，不能凭时长宣布四次一定都是本次watchdog触发。可以断言这四次观测没有旧式长时间越窗，不能断言线上判官已修好或模型更快。

两题原题逐字相同、material_only、Episode工具请求0；不是所有前置IO为0。两题 `material_review_stages=null` 是未到该阶段，不是阶段通过。驱动仍 `semantic_verdict=not_evaluated`，作者结论为未交付、未接纳。包2、G1b、G2b、Q14、真实Q18本轮未重跑。owned sidecar已停止，8817无监听；生产8792未操作。

## 方案与边界

| 方案 | 评价 | 结果 |
|---|---|---|
| 沿urllib在响应读取边界中断已有socket | 无新依赖，不遗留后台模型请求；局部修复可用真实慢流复现 | 采用 |
| 只在返回后检查时间 | 能拒收，但仍会吃光下一阶段预算 | 不单独采用 |
| Timer只调用response.close | 缓冲读取持锁时close可能等待，不能据此保证唤醒 | 不采用，改socket.shutdown并join计时器 |
| 新起线程等待超时后放弃 | HTTP仍运行、费用和副作用未结束 | 不采用 |
| 全面更换HTTP传输/强制解码器 | 超出此片，需单独验证兼容、重试与记账 | 未实施 |
| 加长75秒窗口、追加重试、少答八问 | 会改变本轮资源或交付合同 | 不做 |

明确剩余边界：此guard在urlopen返回后才安装，DNS、连接、响应头阻塞不能由它主动打断，不能宣传全网络硬截止。依赖CPython urllib的 `HTTPResponse.fp.raw._sock`；本地网络反证覆盖HTTP，未另跑本地TLS服务、慢响应头、DNS阻塞或其它HTTP实现。无socket替身只有返回后时间检查。`elapsed_seconds`是整个审稿阶段含已有重试的耗时，不等于单次HTTP耗时，不能拿它与最后一次timeout直接比较。

## 工程与反证

- 干净定向：`tests/gate-cXzT6C1o/pytest.json`，1768P/2S/1X/0F/0E，绑定完整7cfc revision与目标工作树；Ruff与收据验签通过。不是全仓/前端/组合main收据。
- 首次未修复测试：`~/.finance-runtime/test-receipts/20260923T104850Z-9ecc9384-612b1a79c589.json`，dirty-tree，5F/1P，不冒充干净基线。
- 进程内撤响应guard：`mutation-body-window.log` 两测均红；撤阶段记录：`mutation-stage-timing.log` 两测均红。磁盘源码不改。
- 撤保护后正向72P：`~/.finance-runtime/test-receipts/20260923T110027Z-7cfc51d5-b31c606c349e.json`。本地测试服务线程和截止计时器在成功/失败后均退出；流式已发布内容不得重播。
- 材料题面与原件哈希校验包含在既有 `test_knevo_regression.py`，七份冻结文件另按原manifest重新验签，`source-hash-check.txt`全过。旧完整工程收据不移签。
- 收据检查曾误用宿主Python3.14，因解释器/版本/依赖不一致被拒；改用生成收据的主树venv后通过（`receipt-check.log`），没有改测试结果或收据。

## 输入绑定复核与下一步

旧包1首层拒绝16句，其中14句完全没有本句锚点，另外2句仅绑定部分事实。计算、范围声明、研究卡中的重复数值仍需本句输入，不能从邻句借用。逐句补齐来源也不自动修内容：旧c40称“90仍高于基期100”，与材料直接矛盾；没有成本等输入也不能据量价直接签盈利方向。这些没有用正则或自动补引用“修掉”，本轮未改写手提示或正文。

1. 先解决完整八问稿在既有写手窗口内的生成可行性，同时保持逐句全部输入与原任务义务；不能靠恢复无限读取或减问题过关。
2. 可用有效终稿后再验材料首层/非事实复核，分开无剩余预算、服务超时和非法报告；保留单次调用与阶段总耗时的区别。
3. unsupported/nonfactual互斥、旧答认领、A/B改判自洽、Q14概率/因果漏判仍待处理。包1删句后八问完整性未通过。
4. 全网络绝对时限需另做DNS/响应头/TLS及传输替代验证；不以本片部分覆盖代签。
5. 未获合并授权，不追移动main、不部署、不回补。需合并时固定组合重新跑完整叶子门禁。

工具沉淀：真实慢流复现已进入仓内pytest，阶段诊断复用inspect_run，无第二套评分器。通用教训写入共享 `contract-vs-delivery-mismatch`；`harness-reference` 的 BUILD.md有他人改动且基线旧，未接管。
