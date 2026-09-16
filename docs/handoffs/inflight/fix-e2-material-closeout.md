# E2 材料整合在途

## 这个分支做什么
整合 P5/P6，收口单份正文、逐句来源与真实交付；仍不具备 D6/P7 验收结论。

## 当前状态
树 `/Users/a77/fwp-wt-e2-material-closeout`，代码 `be01127e` 已推 WIP PR #770。
运行时最后改动 `01376610`；后续仅修诊断记录器和两个测试。未合 main、未部署。
独立审查按用户决定关闭，不重试、不记通过。8826 已停止；8792 最后实读 healthy/clean/match@db2963d4，由其他线部署。

## 决策与被否方案
- 显式 render_from_claims 单份渲染；否双写模糊匹配，来源逐字校验不放宽。
- 冻结 JSON 模板送达作者；否自动补返回字段/basis，避免篡改合同。
- 判官逐条类型/锚点序号由程序核对；否只信理由文字。nonfactual 分类仍须语义验。
- 完整决策/各版本失败与收据：`docs/handoffs/2026-09-16-e2-claim-rendering-and-judge-receipts.md`。

## 未验证 / 已知边界
最新三次 U/U/N 均算对且无私有 ID，加粗正常；编号题 c8 无锚点的 12.5% 仍被判官标 nonfactual 放行并借 c3，不签验收。
固定判官四例：错/空锚点拒、正确锚点通过，纯声明因类型与序号矛盾 unavailable；3/4 非全绿。
先前“删计算只剩原始事实仍 completed”未证明修好；正式原始 T2→T3、自然跨轮五格、local_only 全读取面未验。

## 下一步
1. 冻结 nonfactual 漏判与核心答案删失反例，先定内容完整性判据，再改实现。
2. 修真实协议稳定性，不补字段、不放宽引用、不追加抽到绿。
3. P7 按新 Workbench 会话规程；合并/生产切换另等用户确认，合并候选重跑全部叶子。

## 已验证
干净 01376610：全仓11271P/83S/2xfail，Ruff/registry、前端107P+lint/typecheck/build、E2E34P/2S。
干净 be01127e：565P定向+Ruff/registry；应用源码与01376610无差异，但未重跑全仓/前端。
具体收据 `20260916T131707Z-01376610.json`、`20260916T131931Z-be01127e.json`，校验exit0；不把父收据当新头全量。
删保护变异：私有坐标5红、旧分句8红、锚点回执7红；预期红非正常门禁结果。

## 踩过的坑
工件根 `~/.finance-runtime/e2-material-closeout-f7950553/`，后缀区分版本；最新run尾号210901_879736/211030_271881/211133_260447，在users-01376610/probe-e2-receipt-0916/runs。
probe打印的默认users路径不适用。脚本原生ModelTurn必须to_dict，asdict会复制只读参数失败，旧四例已保留；记录0不等于零外呼。
不设FWP_TEST_RECEIPT_DIR，不取共享latest/零计数自检；全仓进程已结束。harness索引在docs/material-claim-receipts候选，未合。
