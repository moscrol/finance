# feat/adaptive-research-loop 在途

## 这个分支做什么
#72/PR #868、#75双轴独审、#76 L6。不能合入；未push/合main/部署。

## 决策与被否方案
- 固定候选签收据，不将作者探针、复制测试或文档HEAD当独审/全量。
- 旧失败不续跑/倒写，不放宽0.8秒+0.2容差或离线检索120秒。
- 取消计时绑定真实响应头；正式入口在启动旁车前重算阶段覆盖与身份。否掉仅创建惰性context、仅查越时的判据。
- 方案理由见 `../2026-09-24-adaptive-joint-engineering-and-evidence.md`；原件归档 `docs/verification/2026-09-24-adaptive-c315-engineering/`。

## 当前状态
最新受测e7a6cb412，0326完整工程正在Python阶段，无自动付费后继。仅修完整日志/管道失败/收据临时区重叠，不宣称修复RAG或阶段覆盖。已联合main3bb81b963；文档归档HEAD不移签候选收据。
工程0205已结束RED：15383P/7F/85S/2X，完整收集15477；7F全在 `intelligence/tests/test_rag_worker_keepalive.py`。前端六步及五个registry/ledger叶均过。取消探针原红项本轮通过。
运行根在 `~/.finance-runtime/reviews/`：新 `pr868-merge-ready-20260924-0326/`、旧0205；QC `pr868-glm-qc-20260924-0208/` 已BLOCKED_NO_RETRY；L6 `pr868-l6-20260924-0210/` 已BLOCKED_PREFLIGHT。均因工程红未准入，新增模型0、自然题0，不得续批。

## 未验证 / 已知边界
RAG根因未定。旧全量没有7F堆栈；单文件9P、相邻114P、全收集后选9项绿不能改判。前缀选择9117项，实际7165P/1F/20S/2X后停，余1929未执行；未到RAG，先在判官共享窗出现两次尝试只收到一次请求的覆盖红。不可强行归同一根因。
旧QC0015+0024消费74/152，Spec证据不足、Quality CHANGES_REQUIRED不改；0145/0208均0新消费。旧L6覆盖缺口与自然NOT_PASSED保留；本轮严格准入/检索/旁车未执行，不宣称生产身份已比较。
整PR diff-check exit2：8份旧封存文本空白格式问题；未裁剪原件、未豁免。新归档自身检查过。

## 下一步
1. 读0326终态、唯一收据及完整pytest.log/XML，定位失败；不以一次新绿宣称旧7F已修。
2. 有实际修复后固定新候选、新QC/L6根，预算累计不得重置；独审两轴不代签。
3. 全工程/独审/正式准入满足后才逐题自然验收，精确Episode审计PASS才下一题；实际合main仍需授权。

## 已验证
c315五文件111P、取消正反对照、准入两层撤保护5F/1F及恢复25P。e7日志旧反例4F+位置2F、修后72P。均作者证据。历史208份/本轮51份原件可逆归档。

## 踩过的坑
复制测试不属原路径；沙箱只加metadata权限；修夹具不改reviewer原判。harness-reference/BUILD.md有他人改动，未碰。
