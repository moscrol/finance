# semantic-consistency / 2026-10-02

## 授权与边界
PR14 draft，不合main、不部署、不改默认off。用户“glm无限用，额度够”，ask_user glm_open_budget_scope=preservation_e2e：持续GLM总额度开放，允许必要修复；分批预注册/保留全部失败，不选优，不再逐批问额度。其它模型不自动获授权。
旧R18/R21/R24/R26与本日三批均关闭，STARTED_ONCE严禁重启；当前累计43物理请求。新批要新计划与停止条件，但可沿用持续授权。

## 本日3批（源码8a2dddc068735821b03b28ea2f03cc16e9549e86）
正式号R-20261002-01：20零网预检；完整verify错→对各2HTTP，4/4响应/身份0，18.665/15.310s。错首判明确−17.24%缩量拒14、终稿去错句；对原句终稿保留。限定目标保真confirmed，非整篇通过。实际均只2轮，不能归因抬到3次上限；R18旧失败不洗绿。
-02：27预检；错原→错补→对补→对原，2/2/3/2请求=9，均身份0。两对实际首wire只差system补充段。补充臂删除字段越界句，但四臂都留下窗口误用与孤立“这些”；native最后都passed，内容0/4，联合假设refuted，不接入生产。
-03：32预检；逐句覆盖/证据短引文/新nonce绑定/原生core一致的函数原型。首请求50.122秒超时，1HTTP/0完整响应、身份实际2；后案停止。无有效语义结论，台账pending但本批已终结，不补跑/不抬窗口。缺证稿不算修复。
本日新增14HTTP/13完整响应；13回包low均未验证，超时无回包。模型身份仅自报准入，不是认证。

## 证据/下一步
报告docs/verification/2026-10-02-preservation-e2e.md。私有根preservation-e2e-20261002、evidence-scope-prompt-ab-20261002、sentence-coverage-e2e-20261002；完整plan/runner/preflight/live/acceptance/postcheck保留。
零模型用canonical只读renderer逐字复现E7：episode_tools.mainline_runner传snapshot source_date09-30；block_lines_to_evidence同历史行不传覆盖则取最大日期09-29，detail相同。只证明快照日期≠历史事实区间，未证明唯一因果；别直接清空/改早source_date破坏新鲜度。下一步先查结构化覆盖/当日成员事实的证据投影，再做小输出审查，不继续只堆提示词。

## 旧结果/门槛
R26仅2已知案函数/绑定/角色通过、core仍拒句，无全文放行；R24 refuted，R21 partially_confirmed。R25实现b4，clean996P/6变异；disabled专用控制门仍不允许已知forced-thinking组合，不因新enabled授权改门。R19保持955严格+11精确不适用/旧exit2。
8a CI36884906131/36884906341五绿，19241P167S2xfail/1607.31s；c8f49d3d与8a完整tree f54ae5bc同，非实际merge、不覆盖私有runner；后续docs CI另查。
生产默认接线、完整内容/保真稳定性、PR8内容、原四格先于240未解除。main3a2718c6、生产healthy@2c394978/match=true、队列7385/hash及DB hash/0444均未变。
