# feat/adaptive-research-loop 在途

## 这个分支做什么
#72/PR #868、#75双轴独审、#76 L6。工程绿，独审/自然未闭合，尚不可合入。未push/合main/部署。

## 决策与被否方案
- 固定候选签证，文档HEAD不移签。旧失败不续跑/倒改；0.8秒+0.2容差及检索120秒不放宽。
- 否掉宿主修JSON补签旧Quality；对象交付仅新设施候选，不能替reviewer作结论。
- 余额不足原批准完整双轴方案，不启动半轮、不借L6额度。
- 背景/方案比较：`../2026-09-24-adaptive-e7-qc-budget-boundary.md`。

## 当前状态
受测e7a6cb412，基线main3bb81b963，末次远程复核未漂移。0326七叶全绿：15396P/85S/2X、collected15483，无筛选；前端六步及五个registry/ledger叶过。e7只修日志链，不宣称旧RAG/覆盖根因已修。
根均在 `~/.finance-runtime/reviews/`：工程 `pr868-merge-ready-20260924-0326/`，独审 `pr868-glm-qc-20260924-0415/`，均结束、无后台。收据为0326下 `python-receipts/gate-Pq59hxEb/pytest.json`，完整log/XML已存。
0415已封存BLOCKED：Spec PASS_WITH_LIMITS但C3/C7未验证；Quality执行交付内部JSON字符串语法错误，exit75、无report/最终verdict。两轴原路径作者各16P，不能补独立缺口。原始探针失败及解释均保留。
**模型总账131/152，剩21；不得从旧74重新起算。** 本批Spec30+Quality27=57，历史74；所有已起shim计数一致、active=0、shutdown_complete=true。原每轴4/17/17/1方案不能以21完成。保持完整新批78上限需总授权至少209，尚未获准，不自动启动。

## 未验证 / 已知边界
旧c315的7个RAG失败及前缀判官共享窗覆盖红根因仍未定，新绿不翻案。
0145/0208/0400零消费封存；0400原路径10P/6个git-init setup error后另起0415，只补父目录metadata，宿主16P各过。原exit120空日志原因未定，简单文件/管道对照均0。
新L6未准备/提交，旧0210零消费阻断、严格覆盖/检索失败及自然NOT_PASSED不改。生产身份未比较。
整PR diff-check仍exit2，8份旧封存文本空白问题；未裁剪/豁免。新归档自身检查不是整PR。

## 下一步
1. 先读0415的batch、host-evidence-audit与closure-current-turn；旧批不得续。
2. 待预算/方案确认，另建独审根。对象协议须新批验证，C3语义结果、C7身份/收据及探针签名/端点核对不能省。
3. 独审与正式准入均满足后才另建L6新根/新题；精确Episode审计PASS才下一题，重发/续问0。

## 已验证
e7日志修复72P、旧反例4F+2F；对象交付离线15项含注册工具通过，0模型、未启用，不算独审。新530工件可逆归档 `docs/verification/2026-09-24-adaptive-e7-qc-closeout/`；历史208/51份仍保留。

## 踩过的坑
模型HTTP200与阶段完成不等于有效终审。metadata可逐目录放行，正文不能跟着开放。harness-reference/BUILD.md有他人改动，未碰。
