# feat/adaptive-research-loop 在途

## 目标与边界
#72/PR #868、#75双轴独审、#76 L6。尚不可合入；未push/合main/部署。固定候选签收据，文档HEAD不移签；作者探针/复制测试不算独审。旧失败不续跑、不倒改，0.8秒+0.2容差及离线检索120秒不放宽。

## 最新工程
受测e7a6cb412865fdd189cf51a17f93622fa3d4fe55，已联合main3bb81b963。0326七叶全绿：Python15396P/85S/2X，collected15483、无筛选，前端六步及五个registry/ledger叶均过。唯一收据 `python-receipts/gate-Pq59hxEb/pytest.json`，完整pytest.log/XML已留。仅修日志留存/管道失败/收据与basetemp重叠；不宣称修复旧RAG或阶段覆盖根因。
运行根前缀 `~/.finance-runtime/reviews/`：工程 `pr868-merge-ready-20260924-0326/`，干净detached候选在其candidate。

## 正在进行的独审
新批 `pr868-glm-qc-20260924-0415/`，绑定e7。控制器 `0326/run_qc_0415.py` 已启动，首查batch.json及各阶段controller/counts。目前执行Spec轴；阶段COMPLETE不是verdict PASS。
**历史74/152必须累加当前实耗及在途预占，不能把74当最新总账。** 本批上限78，阶段4/17/17/1，两轴串行；失败不重试。driver在副作用前记录预占，缺失消费数按预占保守扣账。
0400新批因两轴原路径测试各10P/6个git-init setup error零消费封存，不得续；0415只增批次父目录metadata后，宿主原路径16P/81 deselected各通过。security CLI仅help拒绝自测通过；两轴隔离预检PASS，均不算独审。

## 历史与未闭合项
c315工程0205仍RED：15383P/7F/85S/2X，7F全为RAG keepalive，原完整堆栈丢失。定向绿不改判；原序前缀实际7165P/1F/20S/2X，未到RAG先遇判官两尝试只收到一请求。新e7仅记录未复现，不归因为负载。
旧QC0015+0024的Spec证据不足、Quality CHANGES_REQUIRED不改；0145/0208/0400零消费封存。L60210因工程红零消费阻断；旧严格覆盖/检索失败与自然NOT_PASSED仍在。新自然题、检索、旁车尚未启动，不宣称比较过生产身份。
整PR diff-check仍exit2，8份旧封存文本空白问题；未裁剪或豁免。新归档自身检查与整PR不是同一范围。

## 下一步
1. 等0415终态，按原始命令/源码/退出码核算两轴覆盖与真实消费；宿主不代签。
2. 独审与正式准入均满足后，另建L6新根/新题；精确Episode审计PASS才下一题，不重发/续问。
3. 终态证据和交接再落盘，实际合main/部署仍等授权。

## 证据与方法
c315作者111P、准入两层撤保护5F/1F及恢复25P；e7日志旧反例4F+2F、修后72P。历史208份/本轮51份可逆归档：`docs/verification/2026-09-24-adaptive-merge-history/`、`2026-09-24-adaptive-c315-engineering/`，51份原件/本地/Git核对0差异。理由见 `../2026-09-24-adaptive-joint-engineering-and-evidence.md`。harness-reference/BUILD.md有他人改动，未碰。
