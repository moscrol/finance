# 2026-09-21 · #830 K3 / 无判官切换、首跑验收与回滚

## 结论与当前状态

**代码修复已合并，生产上线目标未完成。** #830 合并提交为
`f2c3e9e1a24f42ae9b1d5a8cb9e501ababd1330a`。该版曾在 8792 成功运行 K3，材料、行情各一次真实会话
证明写手及无判官统计接线成立；19:01 最终就绪检查出现新增 `rag_query_protocol=false`，
按“只允许既有行情数据红项”的守卫回滚。19:07 三读确认恢复：

- 运行代码 `adcda94b5e401158f1c3aa51f210e1e8d0f0b713`，源码干净，加载指纹匹配。
- 主写手 `glm-5.3-flash`；原启动器恢复，`ASK_SEMANTIC_JUDGE` 未设置（默认 llm），
  `ASK_EVIDENCE_JUDGE=auto`。**当前生产不是 K3，也不是无判官模式。**
- 19:07 就绪只剩行情日期红项；19:17 旧版本再次出现同样的 RAG 探测超时。
  所以回滚不是持久修复，也不证明超时由 K3 引入。
- 用户随后“继续”，本轮只追加有界只读诊断和收尾，不自动重切，不合其他队列。
  远端 main 后来前进到 `c097d712f9acfdd258709c7d0de054f978e0159c`，含其他夜跑工作；
  #830 的全量收据不迁移到该新 tip。

本交接区分**代码已实现、配置曾启用、真实请求跑通、整体部署接受、答案质量**，五者不能互相代签。
执行者在作者树与 QC 树自行核验，**没有外部独立 QC 签字**。

## 背景与改动

用户 09-17 已决定不用 LLM（大语言模型）判官；本轮执行授权原话“你执行，现在可以用 k3 当写手”。
寻找替代独立模型不是关闭判官的前置条件。此前“应先恢复独立模型才关闭”的建议已撤回，
纠偏记录 `ef9070deccb2`。审查原件在 `~/.finance-runtime/reviews/writer-judge-audit-20260921/`。

#830 作者提交 `abbc9b93e2d3` / `292bd55785d2`：

1. `gate_receipt.py` 优先识别私有 `judge_mode=deterministic/off`，公开 `correlated_judge=null`，
   不扩 schema v1 键集。无判官合成的 passed 不是独立审核。
2. `variance_baseline.py` 将该样本记入 `no_judge`，不进 `independent_n`；私有模式覆盖旧公开 false。
   JSON 与 Markdown 落盘都保留 `no_judge_rate`；旧记录模式不明时不补猜。
3. `llm_refine.py` 统一五条 Chat Completions 请求构造，仅精确 `kimi-k3` 不传 `temperature`。
   同请求带 temperature 的网关首测 400、去掉后 200；其他模型采样、工具、流式与 token 上限不变。
4. 常驻 K3 用 8080 既有持久 client key，不用 18788 短期 JWT；GLM 后备保留，去掉网关离线即拒启的
   硬检查，让后备有机会接住。**没有实测后备故障切换。** 凭证不进入仓库和报告。

## 按发生顺序留痕

### 工程门禁

| 固定版本 | Python | 前端 / E2E | registry |
|---|---|---|---|
| 作者 `292bd55785d2` | ruff 0；12480 passed / 87 skipped / 2 xfailed | 六步 exit 0；110 passed；34 passed / 2 skipped | 五项 exit 0 |
| 部署 `f2c3e9e1a24f` | ruff 0；12480 passed / 87 skipped / 2 xfailed | 六步 exit 0；110 passed；34 passed / 2 skipped | 五项 exit 0 |

两树独占、干净、首尾身份稳定。解释器均为主树 `.venv-workbench/bin/python`，环境净化、umask 022。
正确正式收据：

- `~/.finance-runtime/test-receipts/20260921T091631Z-292bd557.json`
- `~/.finance-runtime/test-receipts/20260921T093551Z-f2c3e9e1.json`

部署收据已由 `check_test_receipt.py --expect-revision <完整SHA>` 校验；13 份门禁步骤日志哈希重核吻合，
见 `main-gates-recheck.json`。JUnit 的 89 skipped 包含 2 xfailed，不能误报成普通 skip 增加。
另有最终固定作者头定向 127 passed、接线补测 42 passed、四保护逐个撤掉均红的变异证据。

**旧失败不覆盖：** 主体提交首轮全量 18 failed / 5 errors，以磁盘写满的 SQLite I/O 错误为主，
另有运行中删 code-map 缓存造成的一条失败。17 个失败 fixture 根目录封存并核哈希后，只回收本轮
已结束 PID 的 scratch；恢复地图，改专属 basetemp 后另跑。不能把首轮抹成未发生。

**收据误选纠正：** `093625-f2c3e9e1` 是另一脏 worktree 的定向 1P/10F，不是本轮全量。
最初误选使 `&&` 后哈希循环未执行，后来手写的 `main-gates-verified.json` 不足以证明哈希已验。
后补的 `main-gates-recheck.json` 和 `main-receipt-check-correct-093551.log` 才是实际验证原件；
原失败日志 `main-receipt-check.log` 保留。**同 SHA 和 latest 都不足以唯一标识本轮测试。**

### 切换与真实首跑

首轮 bootout 后 bootstrap 报 `Bootstrap failed: 5: Input/output error`，恢复代码与启动器后验证旧身份。
第二轮保留已注册服务、用 `launchctl kickstart -k`，18:14 三次 health 均为新快照 / K3 / 干净匹配，
readiness 当时仅 `market_data_consistency=false`。EIO 的 launchd 时序解释只是猜测，不是定因。

随后走 **8792 的会话 HTTP 正门**（不是 legacy CLI、不只是直接模型请求），每题只提交一次：

| 题目 | run_id | 实际写手轮数 | 结果与边界 |
|---|---|---:|---|
| 材料三问 | `run_20260921_183219_280474` | K3 ×2 | 5%、约0.28倍正确；首 finish 因一个 claim 有两句被结构门拒，原会话第二轮修正；零工具 |
| 长电科技行情 | `run_20260921_183642_325351` | K3 ×5 | 实际读 fact_stock_daily / fact_sector_stock_daily / fact_sector_daily，并做派生计算；见下方质量问题 |

两题外层 Run 与内层 Episode 均 completed / model_finish，每轮 provider_attempts=1，无已记录的 fallback；
`report.llm.model` 与 `model_turn.served_model` 均为 `kimi-k3`。这是响应声明身份，不是上游模型的独立认证。
私有 judge_mode=deterministic，终稿 judge_usage.calls=0，材料模型 review 记录0，公开 correlated_judge=null。
最终 `evaluation.json` / `.md` 都是 independent_n=0、no_judge_rate=1。

**检索判官证据边界：** 进程环境 `ASK_EVIDENCE_JUDGE=off`，两题的完整工具序列没有知识库候选相关性
判官入口（行情为 market_data×1、finance_query×4、derived_calculation×1）。有候选时的 off 短路已离线
测试，但本次两题**不等于自然知识库检索路径也经过活体验收**。metrics.judge_usage 是终稿判官口径，
不能拿它充当全链通用调用计数。

原件冻结18个文件，SecretScanner（敏感信息形状扫描）扫描15388个字符串、0命中。
每题 n=1：不作质量改善、速度收益、方差或单PR因果结论。切前隔离两题属于 `abbc9b93e`，不冒充生产首跑。

### 数值复核与未通过的内容质量

只读 DuckDB 独立复算，没改行情事实、没新增模型调用：

- 库内最新日 09-18；长电收盘73元、涨7.75%、成交114.9025亿元；09-17为49.3146亿元，环比约+133%。
- 五个实际查询板块的涨幅、成交额及市场总量对账相符；本地归属名单有20个板块。
- **不能签答案全对：** “最近一个已收盘交易日”只能改成“库内最新可用日期”；只比5个板块不能说
  “跑赢所有归属板块”；成交额/边际量放大不直接证明净资金流入。
- 材料末句“未注明币种单位”混淆币种与单位：亿元已给出，币种未显式写明。两项计算绿不代签边界文案。
- 首笔裸代码600584查空，模型改600584.SH后取到值，不能说代码归一缺陷已修。
- 递归 data_dates 只抓到请求日期09-21；真实日期须看 evidence.source_date 和事实表，不能从这个摘要下结论。
- 隔离行情首答把未更新误说成“非交易日行情”，亦保留，不被生产首答覆盖。

### 最终回滚与续查

19:01 的 `final-readiness.json` 新增 rag_query_protocol=false，warning为“RAG CLI 能力探测超时”。
19:03 回滚前核 worker active/queued=0 时该项已自行恢复；仍按本轮守卫回滚，不能将随后恢复归功于回滚。
原启动器 SHA256 `b736771770e67e5d73d1c222c5e5658108628921b28bf8dc554808d9f603dda3` 恢复，
旧快照三读匹配；部署账本 switch/startup、check/homes 对账通过，未改用户旧会话。

19:17 续查在旧版复现同样超时。新旧 `intelligence/api/app.py` / `services/kb_rag.py` 无差异：
每次 readiness 都运行 KB 的 `rag_index.py query --help`，默认5秒；它在解析参数前导入 rag/numpy。
19:18净化环境、19:20继承运行进程环境各一次 importtime 诊断为0.453/0.426秒，参数齐全。
当时负载和可用磁盘显著变化；**不能据此认定资源压力就是历史超时根因**。未改生产超时、未做负载注入，
未改有他人在途/冲突的知识库树，未修探针缓存或导入结构。
19:43收尾只读观察仍为旧GLM/干净匹配，原启动器哈希未变，RAG恢复、行情仍红；该新观察不翻原部署失败。

## 决策与被否方案

| 选择 | 被否方案 | 原因 |
|---|---|---|
| 无判官独立成桶，公开null | false即独立 / 删私有mode / 扩公开键集 | 避免把没审核当独立审核，并保持接口兼容 |
| 精确K3去temperature | 所有模型一并改采样 | 网关不兼容证据只覆盖该模型 |
| 生产首选持久key，GLM后备保留 | 固定短期JWT / 网关离线拒启 | 过期不可维持常驻，硬预检会堵死后备 |
| 新红项触发回滚并保留所有结果 | 重测至绿 / 将RAG超时追加白名单 | 本轮只授权继承行情滞后，不凭成功首答抹服务失败 |
| 新旧都复现后只诊断 | 宣称K3回归 / 回滚治好 / 直接加大timeout | 缺根因证据，改阈值不能证明修好 |
| 固定#830证据，不追新main | 沿用旧全量收据部署c097 | 新tip含其他任务，超本轮范围且收据不适用 |

## 证据、工具沉淀与后续

本轮证据根：`~/.finance-runtime/reviews/judge-mode-k3-20260921/`。
仓内选择性封存见 [verification索引](../verification/2026-09-21-judge-mode-k3/README.md)，不含启动器、密钥或数据库。
生产首跑登记在 `~/.finance-runtime/live-probe-traceability/20260921-post830-k3-first-runs-rolled-back.json`。
备份先因空闲跌至2.2GiB延期；空间回升后一次带6GiB余量守卫的备份于19:25完成，tar exit0，
`~/backups/gitea-20260921-post830-guarded.tar.gz` 为4465571840字节，SHA256
`9a5af3b3fecfae116033ed761beb9ad4c99d5d988462c0ca07f74f6e882c9fbd`。见
`post830-backup-result.json`；Gitea未停机，未做恢复演练，不声称在线事务一致性或可恢复性已验证。

后续顺序：先解决/隔离 RAG 探针间歇超时并冻结可验证候选；确认要继续固定#830还是另验最新主干；
再完整门禁与一次有界部署验收。两道判官off仍是已授权目标，不因回滚改成“用户要开启”。
行情数据恢复是另外的写入任务，本轮没做。#56默认翻转/退役与五交易日观察也没做。

归档前扫描发现首轮失败日志含JWT/secret assignment形状；未核实其凭证有效性，原日志仅留本机0600，
入库的是带原件哈希、替换计数的脱敏副本，其他选择来源逐字节复制。99份来源（含收尾观察）共约1.8MB，
扫描16511个字符串0命中；不把扫描当作绝对无泄漏认证。

统计缺陷已补正式测试与变异；首跑、回滚、导入诊断脚本以原件封存，未升级为通用部署器，
因它们钉死本机身份、两题和授权。可复用的“模式先于布尔标签”“恢复不证明因果”回写既有证据卫生笔记。
`~/harness-reference` 的 BUILD.md 有他人未提交修改，故未改共享工具总纲、也未另造第二份通用工具清单。

## 对旧交接的追加勘误（保留历史原件）

本节接替旧 `2026-09-21-8792-switch-adcda94b5e40.md` 的相关结论，不改写历史快照：

- 当时两次材料真实写手为 GLM，不是“K3自审”；同源判官passed不等于独立复核。
- 看门狗新旧各6/6通过只说明未复现，不能证明“不是回归”或“加压可诱发”；根因未定。
- 材料对照外层Run均completed，内层才是partial/invalid_model_finish→completed/model_finish。
  后者4 bindings、11 claims、10 anchored claims、13 anchor references，不是“10个锚点”。
  每臂n=1，切换还含#825等，不能归因单独#770或证明判官净收益。
- #819的FINANCE_RESEARCH_REASONING只管求证/推理提示，不控制所有判读基线、输入边界和旧证据恢复。
  #770/#819接缝只放行验证了原件与归属的旧证据；新读取仍受冻结范围约束。
- 旧feat-no-llm-judge-mode交接“开关未翻”是09-17时点；本轮曾翻off，但最终恢复原配置，
  应按此时间线解释，不能拿其中任何一行当永久生产状态。
