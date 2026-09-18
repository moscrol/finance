# 8792 修复版真实复验：仍未通过

**固定 live revision：`c481272e0d0198a44e028497a66c21d6d1d82973`；业务代码与工程全过的 `9655b16d` 相同。四题首发、零重发、零澄清续答，整体 `not_passed`，不可晋级。**

API 运行状态四题均 `completed`，不等于四份合格研究：实际为三份研究正文＋一份错误澄清。按预注册的完整任务、证据、日期和写入组合要求，**0/4 全项通过**；这是本组验收读数，不是可靠性估计。旧 `3faf64fb` 的 3 completed / 1 failed、`not_passed` 保留不改。

- 私有原件 **R3**：`~/.finance-runtime/reviews/8792-boundary-retest-20260918/`。
- [机器摘要](results.json) · [决策与限制](../../handoffs/2026-09-18-8792-boundary-retest.md) · [在途交接](../../handoffs/inflight/fix-8792-boundary-integration.md)。
- [前轮工程修复](../2026-09-18-8792-boundary-repairs/README.md)；工程全量收据只签 `9655b16d`，不冒称本次再次全量。

## 四题实况

| 案例（执行顺序） | run / report | 观察到的有效行为 | 未通过原因 | 客户端观察秒数 |
|---|---|---|---|---:|
| F1 不登记 | completed / completed | 财务研究正文保留；checkpoint 与 judgment 均 0；清单结构检查无缺件 | 最近两期跳过已有 Q1；无对应绑定支持的 08-24 巨潮披露断言仍公开；10-22 复查与 10-17 到期待复核自相矛盾 | 275.662 |
| F3 格式化财务题 | completed / partial | 未误当用户材料；有正文、缺件提示；不登记；自然进入同 session 的零工具表达修复 | 列表中的坏阈值被删，但表格/区分变量里同类 `≥50%`、`<0.2` 仍公开；最近两期仍跳 Q1；补全未成功 | 280.661 |
| F2 未来计划＋引用 | completed / completed | 未写 checkpoint/judgment；按协议未追问或重发 | “请自行检索…这份真实证据”触发缺材料澄清；只有 64 字追问，没有研究、真实引用或未来复查计划 | 5.118 |
| 阳性：授权登记 | completed / partial | **实际写 1 条** `track_next_watch`，精确绑定 run，due=`2026-10-22`；判断账 0 | 正文说已登记，补全提示却说清单缺件；条件依赖正文承认无法计算的两期净现比基线；仍跳 Q1 | 160.360 |

不把“有正文”签成正文全部可靠，也不把诚实 partial 签成必需任务完成。耗时仅单次观测；未以同题/同冻结外部数据配对，不能据此算提速。

### 可追溯身份

| 案例 | run_id | assistant_message_id |
|---|---|---|
| F1 | `run_20260918_124232_344866` | `msg_a5cc49ae73ad4864b1f133485d8207ac` |
| F3 | `run_20260918_124708_106592` | `msg_9341f0142eba41669cc656a2ca71aaef` |
| F2 | `run_20260918_125148_844859` | `msg_0716e5107ac043e08ce4ea7cd73cdf1d` |
| 阳性 | `run_20260918_125154_030490` | `msg_d9014e97080e466dba184948869e7e12` |

每题 `cases/<case>/receipt.json` 含准确 user/conversation/run/assistant 身份、答案 hash、完整工件清单。`public-message.json`、`artifacts/answer.md` 已逐一相等；不是凭最后一条消息猜归属。

## 新暴露的边界与已核机制

1. **条件句门只覆盖部分表达形状。** F3 最终列表两句在 preflight 因 `novel_numeric_condition` 删除；相同阈值在“区分变量”和改判表的三句仍在。原数据投影到生产纯函数后，最终稿数字门拒绝集为空；三句均未命中条件触发词，而 `50%`、`0.2` 不被绑定数量集支持。离线诊断没有调判官或改答案。下一轮应核最终断言及等价表达，不能只补这三句白名单。
2. **判官拒绝不等于公开删除，也不等于判官理由必真。** F1/F3/阳性分别有 3/2/3 句 `demoted_to_issue` 仍在公开稿。`_plan_repair_indexes` 对必需块保留正文、理由进 issues，`_project_semantic_quality_marks` 不把质检条投到正文。F1 审计机构实际上在 E54 搜索片段出现，但未绑定、未被该句引用；不能写成“全证据池没有”。F3/阳性的计算编号是计算工具明确要求展示的，判官却指为内部标识泄露，这是合同冲突，不是自动成立的密钥泄漏。
3. **请求中的指代不等于用户提交了材料。** F2 原问题零材料，`references_material` 却匹配“这份”。真实 controller 走 `clarify`，未创建 ContinuousEpisode；本题没有到日期/引用门，不能将失败归为日期门误删。
4. **清单整体完成度与合法单项登记不相同，但提示必须准确。** 阳性真实写口提取一个事项；完整性扫描又把“本条已登记为长期跟踪”当成第二个无效条目。F3 还把括号期限、尾部说明算作条目。F1 机械 due 取到报告期 `2026-09-30`，不是指定复查日；因本题退出登记，**没有实际误写这一日期**。
5. **选期与时点仍未签收。** 三份研究均已有 Q1 2026 证据 E6，却取年报＋中报。三份 research_context 都是 `runtime_default=2026-09-18`，不是 route 的 09-16/17。F3 九份被引证据 metadata 的 source_date=09-18，但 E54 正文有 08-24；已证时点元数据冲突，尚不能断言真实使用了截止日后才出现的信息。不能从 URL 自补发布日期。

## 真正覆盖了哪些失败/修复

- 40 条 `tool_result` 外层均 `ok=true`，但内含 **10 次“派生计算未产出”**：9 次 script_error、1 次 base_calc_not_found；分布 F1=4、F3=4、阳性=2。后续均有同 episode 的 finish。只数外层 error 会漏掉真实失败反馈；10 次为事件数，其中含重复尝试，不是十个独立故障。
- 阳性另有一次 `invalid_action/not_json_object`，随后继续完成；不与工具异常混计。
- F3、阳性自然进入 `remaining_calls=0 / reopen_tools=false` 表达修复，之后工具请求数为 0；但最终仍 partial，不能代签“自然补全成功”。
- 本轮没有自然触发非法 `file://` 的 mappingproxy 记账边界，也没有 `_recover_verified_delivery` 异常恢复路径。其证据仍仅来自前轮工程测试，不借本轮有正文升级。
- F2 没有 episode、report `llm.used=false`；不替它补造 judge/tool 用量。

## 用量与费用范围

| 案例 | writer 输入 / 输出 tokens | writer 调用 | 工具调用 | semantic judge 调用 |
|---|---:|---:|---:|---:|
| F1 | 592033 / 4952 | 16 | 16 | 2 |
| F3 | 698171 / 7645 | 17 | 17 | 2 |
| F2 | 无 writer usage 记录，llm.used=false | — | — | — |
| 阳性 | 265263 / 4283 | 9 | 7 | 2 |

三份 writer 台账与 durable `model_turn` 合计一致：输入 **1555467**、输出 **16880**，42 次 writer、40 次工具。六次判官 tokens 未知；总成本/套餐账单未知，不能用 writer 价目或缺失填零。

## 固定与隔离

真实 Workbench HTTP 会话：先建 conversation、再发 message，准确 user/run/message 绑定；不是 CLI ask，也不是浏览器点击验收。预注册 `protocol.json` 在首发前固定四题新措辞/新用户、每题 900s 服务预算/960s 客户端预算。实际 writer=`glm-5.3-flash`、backend=`continuous_glm`；semantic 默认 llm，evidence auto，未翻开关。

市场 DB 沿用旧 canonical 派生的冻结快照，SHA256=`2d192a78205d94a1f7bcef9d90f82ed2d9ecee8b1e7a9d1e30dfe23da0eb6b89`；独立 inode 的只读 clone，不是硬链接。exports、snapshot、users、episodes、部署账、rejudge、vault、L3 缓存均隔离。外部 disclosure package 还会写自身 SQLite/SSE UID 缓存，因此连相关工作源码/配置一起复制并用 SQLite backup 取一致初始库，实际解析路径核在 R3 内。外部源树脏，记录的是相关工作文件 hash，不声称 clean revision。

知识库/向量索引与 F10/网页仍是共享在线来源，非全数据冻结、非操作系统沙箱。缓存隔离不是取消网络访问。

## 收口与证据

- 自有 PID32155 已 SIGTERM 并确认 8828 无监听；自有锁移除，runner 已退出。没有杀生产或其他 agent 进程。
- 8792 报告的六项启动身份前后一致，仍 `bf662e93` healthy；这不是新的全文件系统完整性审计。
- 市场快照、exports/snapshot hash 不变；共享 rejudge index 与外部 SQLite/SSE UID 文件的大小/mtime/hash 不变；无测试身份目录落到已检查的生产用户根或 `.foresight`，共享 rejudge 无本轮 ID。不是“全生产用户文件零改动”的证明。
- 首次预注册量具读错 readiness 字段，发题前超时；当时模型提交 0。首次离线诊断漏将 observations 转为属性对象而 AttributeError；两份失败脚本/日志均保留，仅修量具，不重发题。
- `inspection.json` 是机械事实，`quality-review.json` 是人工判决，`closure.json` 是退出/隔离收据；封存索引与敏感扫描具体范围、数字见 `results.json`。hash 只证明身份，扫描未决 0 不证明全系统或 Git 历史安全。
- 前轮发现的旧疑似凭证已在当前 lessons 脱敏；真伪未验证、轮换未执行、Git 历史未清，本轮不扩大安全授权。

## 后续复现（无模型、无写口）

```sh
cd ~/fwp-wt-8792-boundary-integration
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/review_probes/inspect_boundary_retest.py \
  --live-root ~/.finance-runtime/reviews/8792-boundary-retest-20260918 \
  --output /tmp/new-boundary-diagnostic.json
```

新树无 venv 时用主树绝对解释器；输出须不存在且不在封存输入根。脚本拒 socket、只读原件、hash 前后相同；直接诊断 4 案、Ruff 和两个拒绝路径已验。**它是量具，不是修复或全量回归门**。四题失败需另轮代码授权后转成最小回归与变异验证；不得原样重跑本轮一次性 launcher/runner 或继续加题挑绿。
