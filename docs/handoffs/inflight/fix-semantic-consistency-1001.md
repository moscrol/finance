# semantic-consistency / 2026-10-02

## 目标与授权
纠偏62498cc2e02b：通用harness放大弱强模型，不追坏例堆路由；固定逐句默认计划撤回。持续GLM开放授权preservation_e2e含必要修复；分批预注册、留全部失败、不选优。其它模型未授权。PR14 draft，默认off，不合main/部署/改生产模型。01~11均closed，累计96物理；无模型批在跑，12未占号。

## 实现与工程
产品f4c9a5dc6：evidence_read补本Episode已交付title/detail，flag+显式cap，不改地板/ASGI默认。新字符非新来源，E1不串缓存。
clean391P；7变异6杀1存活。f4c CI36910144597/36910144590五绿，19276P167S2xfail，等树非合并。f9/019e/af8后继CI成功；新文档另查。

## 已关闭结果
06/07各1HTTP401/0准入，inconclusive，私有shlex未展开shell，非证实key过期。08原生入口后11请求：B恢复2/2、全文1/2，refuted。09 flash10请求：B全文2/2，限定confirmed，非净收益。low未验证。旧报告evidence-reread-candidate，评论5938954693已发。
10 glm5.3：10请求/10准入，真实材料离线回放限定confirmed。长题补读2次，全文保真；短题B零补读/2请求，与A相同。总B27767/475 token、29.18秒；A13783/519、17.31秒。短题菜单仍多652输入token。
11 flash：10请求/10准入，refuted。长题核心答对却新增“港元貸款僅升0.4%”，原件0.4%是在香港使用贷款，不是币种港元贷款；短题B额外补读一次，3请求对A2。B26440/631、44.95秒；A13771/558、24.28秒。B全文1/2，low仍未验证。

## 下一机制（尚未实施）
实际初始交付[0,239)，两配置均首读[300,596)，留下61字符[239,300)；该段含0.4%的指标主语。10再读[0,300)补齐并保留原口径，11未补齐而换了口径。核对整份HTTP；next_offset=null仅当前页到末尾，不证明整篇已交付。不是n=1跨配置的语义因果证明。
已用原生EvidenceReadCoverage零模型影子复算区间准确，未接模型/产品。下一候选是有界交付区间反馈，不加金融词规则、不强制读全；须单因素对照及无需补读控制，不覆盖11失败。

## 文件/门槛
结案docs/verification/2026-10-02-evidence-reread-real-results.md；预注册real-materials逐字保留。10/11根evidence-reread-real-glm、evidence-reread-real-flash，共享evidence-reread-real-sources（均-20261002）：原HTML/冻结/所有回包、独立acceptance、integrity、model-admission、隔离后检及coverage-gap/feedback-shadow齐，raw summary不回填。唯一启动/完成与20物理记录齐，未重开。
10/11前后main/生产版本及模型/队列7521/hash/DB0444/hash一致。R18失败、R26仅接口、R25 off门、R19 955+11/旧exit2保留。04全文0/4，05焦点非全篇。真实用户/ASGI/完整review-repair、独立强模型、正式四格、PR8均未过；四格先于240。
