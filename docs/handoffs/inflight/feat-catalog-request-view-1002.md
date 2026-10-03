# 目录去重交接（2026-10-02）

## 当前
- 独立树fwp-wt-catalog-request-view-1002，branch feat/catalog-request-view-1002。
- base PR16@75af45fc0，非main；产品fd65a3f48，预测ca754c3e5，结果961d4e6e3。
- Draft PR17 https://github.com/moscrol/finance/pull/17 ，base fix/resource-profile-contract-1002；GitHub/Gitea已推送。无合并部署。
- R13仅工程confirmed：新41项、相关271P、仓内6/6变异；模型0。默认off、评测专用，生产factory未接。

## R14已关，绝不重启
- 原批物理4，累计100；5逻辑不等于5物理。Mac旧PID55471已退出，process-exit0。
- control A/B各1请求、0工具；输入13246→11277（少14.865%），耗时8.9068→9.7158s，不能签净收益。
- B数值/日期正确；来源增加「含市场涨跌家数统计表」，未通过实施者严格来源审计。不是数字被换口径的证明，也不证明去重致错；原全文已公开供复核。
- retrieval-B：2请求/1工具，正文核对通过，但末回包越过批截止；retrieval-A：时间闸拒绝、0物理、准入2，不是模型败。
- 总体inconclusive；查询缺格，600s硬墙钟未落实。4次发包均在600s前，但尾回包604.25s、进程退出683.13s。
- driver仅拦晚发，未夹紧在途timeout和调度等待。502不证明模型失败或主机睡眠原因。
- 4响应均glm-5.3-flash准入；请求/收据/响应hash相符，DB前后相同。没有补跑。

## 证据
- docs/verification/2026-10-02-catalog-request-view-results.md
- docs/verification/2026-10-02-catalog-ab-plan.md（冻结勿改）
- docs/verification/2026-10-02-catalog-ab-results.md（含三份完整答案）
- 私有 ~/.finance-runtime/catalog-ab-20261002/：plan、cases、driver、live各格、closure-audit、acceptance-review、COMPLETE、STOPPED。open-x不覆盖。
- 评论5946656644。最后查961d4e6e3：registry/frontend成功，Python/E2E进行中；不是全绿。ca754旧E2E失败，PR16红不豁免。

## 下一步
1. 另取号、模型帽0，修通用评测时间预算；复用原生HTTP绝对deadline，覆盖等待、在途、晚回包、时钟跳变及整个批进程终止；先断网测试/变异。不改R14冻结driver，不追本题坏句加规则。
2. 若再实测，另冻新批与未调试题，旧两题只作已见诊断；保持信息足够控制、全文审计和逐物理核账。
3. 正式完整8792×薄ReAct四格仍未完成，先于240；本次核心Runtime/单GLM不替代。PR8/生产门未过。

共享httpx漂移与空code-map未修；不改共享venv/主树他人内容，不以局部工程绿转签行为收益。当前没有新模型批或下一号claim。
