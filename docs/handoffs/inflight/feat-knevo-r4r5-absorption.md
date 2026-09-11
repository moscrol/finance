# feat/knevo-r4r5-absorption

## 这个分支做什么
吸收 Knevo q16–q18：R4「按会不会改变判断筛材料」、R5「产业逻辑变强」与「已反映多少」
分开答；R7（谁有权改关键变量）只试用，仅单测。

## 决策与被否方案
| 选了 | 否了 | 为什么 |
|---|---|---|
| 受控材料包 + 三臂消融 | 真问句跑完整 episode | 召不回反证时两臂同输出，分不清「改动无效」还是「材料没反证」；选材与契约是两半活 |
| 正门形态不改，留用户定 | 直接补 `missing_outputs` 修复回路 | 强制字面标题会改所有 stock_deep_dive 的输出形态，是产品选择不是接线缺口 |

臂定义与实验全文：`docs/learning/knevo-distill/absorption-plan-2026-09-11.md`。

## 当前状态
4 提交（feat/test/docs/probe），基线 `c714eb60`，树干净，**未推送未开 PR**，合入等点头。

## 已验证
- ruff clean；定向 111 passed；全量 **9244 passed / 0 failed / 77 skipped / 1 xfailed**；`layer_audit` ERROR 0、路径字面量无新增（23/37）、`graph_audit` exit 0（7 断言 PENDING）、11 道 pre-commit 全过。
- 同题对照（`thinking:disabled` 同生产）：选材那半送达反证 **0/3→3/3**；契约那半表达缺件 **3→0**；定价二分缺件 **3→0（2/2）**，违例恒 0。
- 正门：契约五个标记**都在** `prepared_synthesis_messages` 里，`question_type='stock_deep_dive'`，契约 782 字占 prompt 2.5%–2.8%。

## 未验证 / 已知边界
- **正门答案无两段字面标题**，`missing_pricing_split_elements` 判两段皆缺；正文其实分了两段，只是用自己的小标题。占比问题，不是门没开。
- **台架 3/3、2/2 是上界**：台架 prompt 几百字、契约占比高一个量级，不能当正门遵从率用。
- 本机盘面停在 2026-07-15，定价那半输入本就缺，正门答的是「取不到」；换数据新鲜的机器结论可能不同。

## 下一步
1. 正门形态三选一（**需用户定**）：补 `missing_outputs` 修复回路 / 放宽判据认实质 / 契约前移。选完用 `scripts/probe_contract_in_prompt.py` 复量占比。
2. 开 PR 到 gitea，等确认再合。question-bank 回灌等形态定了再改，现在改会锁死错的那个。

## 踩过的坑
- **`cli ask` 默认 `compose=False`**，契约注入点在 `ask.py:4129` 的 `if options.compose:` 内；生产入口（`api/app.py:1455`、`conversation_orchestrator.py:2859`、`chat`/`agent`）全 True。只有 `cli ask` 关着，首次 e2e 恰好测了它，结论反了。
- `--llm-timeout` 默认 60 秒要在 brief/composer/judge 间分，合成抛 `LLMDeadlineExceeded` 降级模板；「超过共享截止时间」是**我们自己的** deadline，不是网关慢。
- 台架漏传 `thinking:{"type":"disabled"}` → 推理 token 吃光 `max_tokens` → 加契约的臂 `content` 全 0，读数反向。另：反证检测词用通用词会假阳，须用证据独有的数字。
