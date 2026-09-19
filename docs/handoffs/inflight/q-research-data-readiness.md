# T3 值槽续检 · 2026-09-19

## 这个分支做什么
沿原q线修可信正文/引用误删与数值核验，不开热点平行线；工程、外审、自然答案分账。

## 当前状态
业务746b716ff95d40898697628e197fd266a9473bf6已推Gitea。原占位四例已4P，但新边界探针4P/12F，仍停合。
ARL-0004首调用本地Prompt too long无裁决；独占根补试返回PASS却有5项必需检查PARTIAL，被原门禁隔离为INVALID_VERDICT/failed_check_for_pass、authority none。不是外审通过，也不冒充第四份有效CR；旧三份CR未被有效覆盖。无后台续试。
未开PR/合main/部署；main末核b22ddf8b。见`docs/handoffs/2026-09-19-t3-ratio-scope-review.md`及`docs/verification/2026-09-19-t3-ratio-scope/`。

## 决策与被否方案
- 占位只消费自身值槽，后续/残余数字仍查；否整期continue、猜数或整句删除。
- 标记锚定期别，保原文坐标/Markdown；并列绑定对标记透明但不免检，必须重验第二次解析。
- 否手改外审PASS/PARTIAL或再试到绿；无效裁决只作反例线索，原样复现另记账。
- 正确但陌生措辞可保守unknown；不能把所有独立数字都当未知比率，当前仍有新误报。

## 未验证 / 已知边界
新回归：正确比率后接“行业排名第3”、金额“1,234.56亿元”或“2025中报的含金量为0.289”，均误降partial。
既有漏检：错值“1.587元/元”“158.7个百分点”、占位后分号“；实际为1.587”仍completed无缺口/续修。六类×off/成功替身12F，未继续修。
本轮自然金融会话0/取数0；旧not_passed不翻案。外审两次CLI另计：首次本地0API/token，补试opus-5报价$2.15684非结算，provider次数未知。
格式化旧标记/续修提示移除标记及任意归属词表仍待验。8792、夜跑、KB防写、他人树/shim及其他T线未动。

## 下一步
1. 主树venv原样跑`check_ratio_scope_boundaries.py`，精确746应4P12F；旧保真6P/逗号占位4P。红针非绿CI。
2. 六类接入既有出口/续修矩阵，成对保独立数字/单位/邻期；新冻SHA验全套+变异，再新独占根外审，保旧CR及invalid意见。
3. 原件根`~/.finance-runtime/convergence-20260919/retention-repair/`；本次review根`qc-repair-746b716f`和`qc-retry-746b716f-01`，不是全局同号队列。
4. 固定题/证据/GLM flash+5.3兜底/预算另验conversations。未来待合tip另出精确收据；切生产另授权。

## 已验证
746全量11988P/0F/0E/87S/2x，收据`20260919T085036Z-746b716f.json`；Ruff0，前端110P/lint/typecheck/build0，E2E34P2S，固定三仓五项0；36撤保护真检出/还原绿、首尾416P。外审机械预检1116P不是准入。

## 踩过的坑
正确值也不免检≠所有后续数字属于它。外审总PASS与必需项PARTIAL矛盾即无效。后置gate120秒无输出超时，无决策；直接裁决验证已明确invalid。原件不清洗，收据不移签。
