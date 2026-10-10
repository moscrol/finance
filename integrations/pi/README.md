# pi 消费市场历史镜头（显式启用）

这是**外部工具适配器**，不是第三条金融问答引擎，也不替代 Workbench。
选用 pi 原生扩展 + Python 子进程，复用 `market_history_context.market_history_blocks()`；
相较于另起 HTTP/MCP 服务，不需新服务或额外运行依赖。代价是每次调用启动 Python，
当前仅适合本机小样本消费验证，未做吞吐或性能承诺。

## 先验离线合同

需要项目锁定 Python 环境和 pi CLI。此扩展按 `@earendil-works/pi-coding-agent` **0.87.1** 验证。

```bash
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_history_context_consumers.py \
  intelligence/tests/test_pi_history_bridge.py
```

第一组从 Workbench HTTP 会话入口走真实装配，在模型接口用替身拦停，并检查公开业务报告仍为
`partial`。第二组启动真正的 pi CLI，**脚本 provider** 发原生工具调用，真实 Python 计算，
下一轮 provider 收到同一份完整工具结果。测试没有真实模型、没有外部 HTTP；合成库与会话均在临时目录。
未安装 pi 会明确 skip，不能把该环境的 pytest 绿当作 pi 已验证。

`tests/offline-provider.ts` 仅是测试夹具，绝不能带进真实 GLM 试跑；它的答案不是金融答案。

## 配置与工具合同

由操作人配置三个**绝对路径**，模型参数里不接受路径或 SQL：

```bash
export FINANCE_HISTORY_CODE_ROOT="$PWD"
export FINANCE_HISTORY_PYTHON="$PWD/.venv-workbench/bin/python"
export FINANCE_HISTORY_DB="/absolute/path/to/approved-market.duckdb"
```

单独检查传输层，不调用模型：

```bash
"$FINANCE_HISTORY_PYTHON" -m intelligence.history_context_cli \
  --db "$FINANCE_HISTORY_DB" --as-of 2025-04-10
```

- 唯一工具：`finance_market_history({"as_of":"YYYY-MM-DD"})`。日历非法或未明确的日期拒绝，不回落今天。
- 输出：`finance-history-context/v1`，明确截止日、`INFERRED` 等级、两个完整文本块及各块 SHA-256。
  哈希只证明内容身份，不证明来源真实或历史日当时已知。
- 不写数据库、画像或研究结论；不调用其他模型、不联网。无库不创建；缺表/缺历史逐块保留 `gap`。
  CLI 成功表示信封有效，**不表示两块都有可用读数**。
- 48,000 UTF-8 字节原子预算：超限整体拒绝，不向模型交付残表；Python 只读计算共享 30 秒启动预算，
  pi 子进程另设 35 秒超时和取消信号。底层 deadline 不硬中断已启动查询；子进程超时不等于全会话预算。
- Python 子进程仅继承必要环境变量，不继承 provider 密钥、画像路径等。错误不向模型泄漏命令、私有路径或异常原文。
- 这是可信扩展的接口约束，**不是操作系统沙箱**。操作人负责审核代码根、解释器和数据库；
  pi 本身仍有当前用户权限，也能读已配置凭证。不要加载不受信的其他扩展。

## 经授权后让 GLM 消费

先确认真实模型调用与数据发送范围。模型使用现有 GLM 系列，不修改用户默认模型、认证或生产部署。
以下只是启动配方，**不自动执行、不构成付费授权**；真实验证时按本轮授权配置监督边界并保留收据。
总费用/请求数上限与单次防卡死超时分开：用户明确不设预算上限时，不擅自恢复旧额度；仍记录实际消耗及异常终态。
选择本机 `pi --offline --list-models glm` 中已有的 GLM provider/model：

```bash
pi --offline --mode json --no-session \
  --no-extensions --no-skills --no-context-files \
  --no-prompt-templates --no-themes --no-approve \
  -e "$FINANCE_HISTORY_CODE_ROOT/integrations/pi/market-history.ts" \
  --tools finance_market_history \
  --provider '<已有GLM-provider>' --model '<已有GLM-model>' \
  --system-prompt '你是金融研究助手。按用户明确截止日使用工具取证；依据实际读数回答，保留来源、缺口与时间边界。' \
  '截至2025-04-10，当前行情与历史上哪些区间相似，像在哪、不像在哪？' \
  > '/approved/private/output/events.jsonl'
```

`--offline` 只停 pi 的自动更新/目录联网，**不会禁止模型请求**。
工具白名单避免模型转而用 bash/read 直接读库；`--no-extensions` 不阻止显式 `-e`。
`--no-session` 不保存 pi 会话，但命令的 JSONL 输出仍可能含私有研究材料，应留在授权的私有目录。
使用不同 provider 时记录实际 provider/model；不传明文密钥到命令参数或日志。

## 真实合成样本记录（2026-10-08）

用户授权不限预算后，净树 `8a29bcacd` 经 `zai-coding-cn/glm-5.3`、thinking=high 首发两例，
合计4次真实请求、2次原生工具调用，无重试；完整工具原文进入下一次模型请求，合成库哈希不变。
模型准确使用本轮日期、候选、逐维读数及7/7→5/6覆盖变化，并拒绝把不同第一名按名次嫁接。
**只通过该两例的传输与实际利用；金融解释质量未通过**：有相对/绝对量、终点频率/路径、候选范围越界，
并定位到旧D10把常量退出误标“无数据”、把晚记录时间写成“被重写”的上游问题。本轮未改业务逻辑。
完整边界与私有收据索引见[真实试跑快照](../../docs/handoffs/2026-10-08-river-glm-synthetic-trial.md)。
尚无pi真库消费、Workbench真实作者/判官或独立金融质量批准。

后续 `094797ed6` 修D10查询失败/无值/常量退出分类、当前窗覆盖及记录时间文案，未改排名/收益。
净树定向594P；保留原同字节合成库/问题/系统提示，再各一次真实GLM原生工具首发（4请求/2工具）：
识别修正原因与涨家数0/20、正确分开终点频率0/2和未来胜率，但全文仍因百分位/候选集合等解释错误未过。
旧首发不覆盖；本轮工具材料已变，不称同输入A/B。Codex在修D4与日期权限，窄修路径无交集，
两整枝仍有既存ask_synthesis冲突，未合流。见[修复与协作快照](../../docs/handoffs/2026-10-08-d10-semantics-and-codex-coordination.md)。

随后按用户要求暂停逐句补丁与第三轮模型试跑，在64624794a离线定位到方法/表示层：突出度有小候选集上限，
距离贡献「对齐」不等于方向相同，签名不保路径，百分位定义与候选选择范围未完整进入模型材料。
既有28项镜头测试仍绿、反例同时成立；诊断轮未实施修复，不把原因全归GLM，也不把换JSON当治本。
见[根因与修复方向](../../docs/handoffs/2026-10-08-river-root-cause-diagnosis.md)。

随后按[结果合同](../../docs/superpowers/specs/2026-10-08-history-comparison-result-contract.md)实施：
完整对象恢复窗口日期/选择范围/来源及覆盖，贡献等级与首尾段方向分列，撤下未校准突出类别。
模型块改为同源的具名列表JSON，外层v1信封与原子上限不变；局部引用由本块`windows`绑定日期。
这是声明范围的摘要投影，未交付首尾各自水平均值/逐日路径，不能称原件无损传输。
净产品`d3df048ae`定向641P（含完整Workbench两样本与真实pi离线循环），原两例数值对账不变。
第三轮原库/问题/系统/settings各一次GLM5.3 high首发：4请求/2工具，运输与实际利用成立，
但全文仍有unknown→0、近零→反向、摘要→路径，另有跨块来源归属含混，**金融质量未过**。
原稿全部保留，无追问/重抽；开发回归不签泛化，尚无pi真库、Workbench真实写手/判官或独立金融批准。
当时仍缺逐窗分母及签名准入披露；第三轮发现与裁决见[实施与复验](../../docs/handoffs/2026-10-08-history-result-contract-and-glm-regression.md)。

后续生产覆盖提交`ae80c725`补齐均值所用的逐窗非空计数（含退出签名但仍展示原值的维度），
并让签名计算与投影共用既有准入规则；`raw_summaries`只补签名中未完整重复的均值/分母，
`feature_observations`用默认值与逐特征例外压缩。12K字符registry与48,000字节工具上限均未提高。
该提交定向663项通过，含Workbench完整入口的模型替身及真实pi离线循环；原两库数值与哈希不变。
**该轮新模型请求为0**：不能据此宣称GLM质量改善。当时D10逐对方向类别仍缺；逐日路径、源日完整性及
正文消费失真仍有边界，pi试跑未启用正文命题核验器。见[覆盖续修与收据](../../docs/handoffs/2026-10-08-history-producer-coverage.md)。

方向续修`39e6bc1c6`让D10与river共用原±0.3首尾差规则，D10候选保留未舍入值算出的逐对关系。
两块模型表的`direction_relation`现用“同向/反向/一方近零/双方近零”，null为未比较；完整对象仍用原英文类别。
`signatures.defaults`保存全表各行完全相同的计数列，须与columns/行值合读；不猜覆盖，例外与未知保留。
外层v1、INFERRED、哈希及原预算不变；原子拒发测试仍在。净产品27文件701项通过，6个撤实现负控均被拒绝；
两冻结库三截止的既有完整对象字段、解码后旧模型字段及库哈希不变。**该轮也没有新模型请求**，不签GLM质量。
本线未吸收Codex结果文字所有权，联合消费者另验。见[方向续修与收据](../../docs/handoffs/2026-10-08-history-direction-contract.md)。

## 显式启用历史陈述复核

`reviewed-history.ts` 是同一原生工具的**实验性、显式启用**复核适配器，替代本页启动命令中的 `market-history.ts`，不要同时加载两者。它不修改全局Pi配置或Workbench运行层。

**真实正反对照尚未通过，不建议用作金融结论放行门。** 已有机械协议/失败保护回归，但GLM复核仍可能漏掉类型错误、误报或不返回合法回执；具体失败见[本轮实现验收](../../docs/handoffs/2026-10-10-native-history-review-implementation.md)。

- 作者收到的工具正文与旧入口逐字节相同。额外类型读数来自同一次计算，只放tool details；复核不重新读库，也不把INFERRED升为事实。
- 共享 `history_answer_review` 为每个陈述和具名读数建立本次请求内的身份，核对完整回执、锚点索引及回答完整性；纯格式/非事实豁免还要在隔离上下文里复核。未送进实际作者请求的工具结果不获得复核许可。
- Pi使用当前模型与high思考档，把陈述固定分成最多12条的小批，保留整稿上下文及全部证据；每批必须完成，随后单独核查回答完整性。来源只存一次，各句用索引引用，防止重复大段数据撑爆回执。第一次拒绝会驱动一次完整修订并重审；反馈带原句和引用读数。相同问题/材料/草稿复用已得回执，不重新抽审求绿，也不是重复抽首稿。持续拒绝、坏JSON、取消或复核不可用时保留原稿，明确未确认，不伪装为通过，也不吞成占位答复。
- 流式文字在message_end之前仍是草稿；不能把尚未完成的stream delta当作已复核终稿。queued user消息会清除上一题的证据许可和修订计数，续问需重新取得本轮材料。
- `finance_history_review`自定义记录保留原稿、草稿/来源身份、逐句回执和每次复核usage。嵌套复核请求额外分账，**不包含在作者消息的usage里**；不能用Pi作者token数冒称总消耗。复核使用300秒单请求超时、零SDK重试。
- reviewed只表示该模型的本次复核通过，不是确定性蕴含证明、独立金融专家批准或样本外能力证明。真实金融质量仍须逐项验收。

离线真实Pi状态机测试：

```bash
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_history_review_transport.py \
  intelligence/tests/test_history_answer_review.py \
  intelligence/tests/test_pi_history_review.py
```

边界决定见[ADR](../../docs/adr/0007-native-history-review-boundary.md)。旧两题未通过的实答记录保持不变。

## 分层验收

1. **接线**：实际 tool call → tool result → 下一次模型请求。比对块哈希与完整内容，不能用手工贴结果替代。
2. **真实利用**：真实 GLM 终稿准确引用本轮截止日、候选区间及逐维读数，不仅重复工具描述里的免责声明。
3. **研究质量**：逐项复核金融解释、反例、覆盖分母和推断边界；一次好答案不足以证明普遍质量。

两组候选分开计算，不表示统计独立，不按排名嫁接收益。`trade_date_only` 与单 cutoff PIT（按一个截止时点筛选）
都不证明每个历史日逐日可知；镜头不是胜率、预测概率或已验证环境剧本。
教学 `tf.*`、用户判断台账和剧本命名/持久化仍未接入。

pi JSON 模式在模型失败时也可能退出 0；必须检查 `message_end` 的终止原因、工具错误和
`agent_settled`，再读实际答案。Workbench 的 `Run.status=completed` 也不能代签业务成功，
还需读 `report.status/business_status`、`llm.used`、degrades 与正文。
