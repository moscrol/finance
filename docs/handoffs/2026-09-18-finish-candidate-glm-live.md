# 准入前保稿：GLM 隔离真实验收与历史查询记账异常

## 裁决

用户要求「按照最佳方案推进」后，在冻结的 `35ee8a5c05aa1a25498ab9c32cc548d0166bb5a7` 上，经真实 Workbench 会话入口提交原题 **1 次，0 重发、0 续问**。

**新 live = `not_passed`；旧 live 仍 `not_passed`。** GLM 凭据与响应链可用：Episode 持久事件记录 3 轮 `glm-5.3-flash` 响应。研究在首次 `history_query` 参数被拒后的进展记账处崩溃，尚未到 finish 或候选稿保留路径，不能签收「新版保稿生效」。公开仅 15 字失败提示，无金融答案可评。

本轮没有修改业务代码或生产运行配置，没有整合其他分支、push、合 main、部署或切换 8792。新增仓内原件重放量具及验收文档。后续修复整合、工程验证和新版本真实验收是独立动作，不能覆盖本次失败。

## 身份与原件

- 工作分支：`feat/research-answer-preservation`，树 `~/fwp-wt-research-answer-preservation`。
- live 代码：独立 detached `35ee8a5c`，不是文档 HEAD `69c056f6`。
- 归档根 **R**：`~/.finance-runtime/reviews/research-candidate-glm-live-20260918/`。
- 测试端口 `8849`；用户 `probe-candidate-glm-20260918`。
- conversation：`conv_d3f6dac2132f43dc92a510d2b93cef53`。
- run：`run_20260918_213933_397262`。
- assistant message：`msg_18e9ac951cd44153addc360fa573d2be`。
- 原题：「这里的行情哪个板块更有机会，历史上有相似的阶段吗」。
- 服务日志只含一次创建 conversation、一次提交 message。既有 `scripts/workbench_probe.py` exit **2**；202 Accepted 仅是受理，不是完成。
- [`验证索引`](../verification/2026-09-18-finish-candidate-glm-live/README.md)；私有 `artifact-index.json` 封存 **82 文件 / 623321 字节**。大库和源码副本不重复列入该包，身份由精确 revision、行情及导出清单锚定。

## 按发现顺序

1. **撤销人为凭据阻塞之后，不先烧一个“连通性题”。** 复用已授权智谱直连，密钥只由启动器 export 行进入子进程内存/环境，不执行生产启动器主体、不另落凭据文件。固定主模型 `zhipu / glm-5.3-flash`，兜底配置 provider 名 `openai`、model `glm-5.3`，均指 `https://open.bigmodel.cn/api/coding/paas/v4`。兼容后端名 `continuous_glm` 不作为实际模型证明。
2. **冻结代码、行情和写口。** 新建精确代码树并校验干净。既有全量收据 `20260918T101211Z-35ee8a5c.json` 条件复核 exit0，未重跑或移绑。沿用旧验收行情快照，数据至 09-17；DB 副本 3692572672 字节，hash一致、inode不同、文件只读。用户/会话/episode/vault/部署台账/待审/缓存根独立；未给候选 Keychain 读取。知识库、web、L3、财务在线输入未冻结，因此不是严格 A/B。
3. **首发前纠正量具预算口径。** `protocol.json` 最初用 CLI `ASK_RESEARCH_TIER` 默认值记成 standard/90s。Workbench 实际走 `WORKBENCH_RESEARCH_TIER=max`；在首发预占之前追加 `protocol-budget-amendment.json`，保留原文件，不改运行预算。初始 600s/40步/60s合成保留，turn LLM 熔断120、根工具帽60/600s；阶段缩放仍按未改代码。服务总时限900s、环境 LLM_TIMEOUT300s、探针960s；实际 Episode configure 的 llm_timeout=75s，不能把环境上限当实际授额。判官配置 llm，为同源产品自审而非独立验收；本 run 未到判官，记录0调用。
4. **只发一次并追准确 id。** 首发前写独占 `submission-reserved.json`，然后调用现成 probe。21:39:33受理，21:40:13 failed / `continuous_runtime_failed`，未重发。持久日志有3条model_turn、6条tool_request、4条tool_result；6请求不等于6成功执行。Episode记载输入102479/output1041 tokens，仅属这3轮的用量，不是全链计费。`report.llm.used=false`、失败 metrics.tool_calls=0与持久事件不一致，不能读成“没调模型、没用工具”。
5. **先保存再关闭。** 保存精确 run/report/trace/message 与 durable事件。公开提示「本轮连续研究未取得可公开答案。」；私有 failure为 mappingproxy JSON TypeError。8849仅自己的PID停掉、锁已释放；8792前后健康身份仍 `bf662e9310ff` 且一致，启动器hash未变，行情/导出hash未变，测试用户不在两处检查过的共享用户根。不是全OS沙箱或所有缓存无副作用的证明。
6. **不能把最后工具名当根因。** 原件没有stack，按第3轮真实请求重放：`history_query(find_analogues)` 缺 `end`，真实注册表 prepare正确拒绝为 `invalid_arguments: end requires ISO date`。随后 `_EpisodeToolAccumulator.consume → ToolCallDigest.__post_init__ → normalize_query → json.dumps(mappingproxy)` 抛异常，没来得及给模型错误反馈。其余同期 finance_query已有派发意图但未结算，不猜是否完成。先前4个工具结果里有44条唯一证据。
7. **复用已有修复，不另造。** 检索到 `fix/8792-boundary-integration` 的 `a969d30a` 已在 `research_progress.py` 增加 Mapping→新dict的JSON边界投影；原始冻结参数不改，任意未知对象仍拒绝。对其干净 `068e2a4652d7b8e0250c9d046272e7889b15c5b9` 用同一原件重放：缺end仍拒绝，但反馈正常生成、44证据与输入不变。相关两文件测试24P/0F；未修改该分支、未将整包修复合入本分支。这里只复现 parser→拒绝结果消费者，不是整轮重放、模型自然自修或终稿保留。
8. **量具也要能拒假结论。** 旧版硬要 feedback、修复版硬要 crash各exit1；写已存在输出exit2。两正确方向exit0。零网络连接尝试、零模型/数据库调用。仓内量具 `scripts/review_probes/replay_history_progress_failure.py`，不只留临时脚本。旧214/44/90/6文件包逐文件hash复核一致。

## 方案取舍

| 选择 | 被否 | 原因 |
|---|---|---|
| 精确旧候选先完成一次验收 | 默默混入邻枝修复再发题 | 保持被测代码身份；不能事后替换样本分母 |
| 保存失败、离线原形状复现 | 原题重复直到成功 | 定位不需继续消耗模型，失败必须保留 |
| 已有Mapping投影修复作为整合依赖 | 全局解冻/default=str/关进展 | 不削弱不可变参数合同，不把异常对象伪装成合法文本 |
| 缺end回给模型修正 | 自动猜结束日期或放宽历史窗口 | 不替模型编研究范围，不降低历史边界 |
| 标保稿路径未触发 | 以工程绿或GLM可用签live通过 | 模型连通、局部容错、答案质量是不同结论 |

可迁移知识：**可恢复的输入错误必须以反馈回到同一流程；进度/审计记账不能把它升级为整轮崩溃。** 继承现有 `contract-vs-delivery-mismatch` 方法，不新建重复能力清单。

## 验证边界与仪器失败留痕

- 既有35ee工程收据仍是11664P/81S/2X，前端107P、E2E34P/2S；本轮只校验其适用条件。24P是已有修复分支的定向测试，不能拼成整合候选全量通过。
- 新增原件脚本 Ruff通过；正确方向2次exit0、错误期待2次exit1、拒覆写exit2。提交检查另见提交日志。
- 新 live 未到 finish，故准入前保留、同进程继续/恢复都未被本次自然路径检验；跨进程候选恢复仍未实现。
- public run failed，但durable state停在tools_pending，reserved为同期finance_query，last_sequence25而事件26；未调用resume，不宣称异常终态已对齐。
- 首封扫描exit1：六个词形未分类（5个文件/marker命中），为Python模块名、方法引用和 `SecretScanner()` 变量赋值。逐个以精确路径+marker+词形hash复核后未决0；`secret-scan.json` 与失败日志保留，复核另写 `secret-scan-reviewed.json`。不是“全包零命中”，二进制DB不在文字扫描范围。公开投影/事件扫描无命中，不代表独立安全认证。
- 代码地图empty/refused_empty，只沿精确路径和已有提交定位，没据空图得出“没有实现”。

## 下一步 / 不要做

1. 按本次原件将已有进展序列化修复纳入下一候选，保留其未知对象拒绝与真实loop回归；不要为这一个问题盲目合入整包邻枝业务修复。
2. 整合后在干净新revision跑应有工程门禁；失败用量及durable终态不一致单独登记，未修前仍unknown/不完整，不填零。
3. 需要新真实验收时另冻结版本、模型、数据、预算、协议并确认额度，作为新样本；本run和更早run永久保留not_passed。本轮不追加第二次。
4. 合main、部署和切8792仍需用户另行确认；GLM路线已证有实际响应，不再回到过期GPT Keychain前置。
