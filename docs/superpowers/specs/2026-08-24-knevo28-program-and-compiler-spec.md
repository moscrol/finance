# knevo28 规格恢复索引：ResearchProgram 与统一公开出口

> 2026-09-23 恢复失联引用；这是历史规格的入口，不是重新授权施工的计划。
> 08-24 的 P0-A / P0-B 已有后续实现。不能因规格未进主干就推断功能未实现。

## 原件与版本取舍

| 原件 | 内容 | 本轮处置 |
|---|---|---|
| `8a125aefc` 中同名文件 | v1：新建 PublicAnswerCompiler / ClaimKind | 保留 Git 原件，不恢复为现役方案；已有统一出口，另建会重复 |
| `73d2af5ca` 中同名文件 | v2：加深已有 `session_projection.view`，输入编译放 `research_contract`；不把手工组件臂分数当产品目标 | 逐段审读并采纳上述收窄；原提交是未审 WIP 封存，不整枝搬入 |
| `73d2af5ca` 的 prediction-ledger / inflight | 当时 D0/D1 及在途记录 | 不复制旧状态、不把旧收据当当前版本验收 |

完整原件可用 `git show <上述提交>:docs/superpowers/specs/2026-08-24-knevo28-program-and-compiler-spec.md` 读取。
本轮没有改写原件里的历史分数或新增预注册号。需要恢复旧实验时先核
`~/.finance-runtime/knevo28-four-arm-20260824/artifact-receipt.json` 与矿文件，不能只抄规格的统计表。

## 已有承载（本轮以代码和 Git 历史核对）

- **P0-A**：PR #354（`e8ed9e116`）已加深 `session_projection.view(TerminalFacts)`；
  当前 `intelligence/services/session_projection.py` 有 `verification_incomplete` 成因。
  核验没完成与证据没有是两件事，不新增第二个公开稿编译器。
- **P0-B**：PR #355（`48601e08c`；实现 `5216decd2`）已将
  `compile_research_program` 放进 `intelligence/services/research_contract.py`，
  接到 ask / Episode / market_watch_pack；回归入口
  `intelligence/tests/test_research_program_compiler.py`。
- 本轮只是来源与现状对账，不重做以上修复；发现下游缺陷须用当前真实入口复现。
  `docs/agent-product-door.md` 是当前产品合同，不以这份历史索引覆盖它。

## 仍未据此关闭的项

1. v2 §4 的 2×2 消融、§6 的逐缺陷同题验收，不能由“实现存在”补签完成。
2. 组件臂是逐题人工研究程序，不是可部署泛化基线；历史各臂不同配置不支持模型优劣归因。
3. 租用循环的工具缝停探索、三 runner 同 program、P1 的题材包与可靠性须分别找当前消费者和收据，
   本轮未对这些项重新做全面审计。
4. 不用 knevo28 的收据关 SPT 缺陷；不将本轮揭盲材料回归并入冻结28题。

全量材料处置与剩余工作见 [Knevo 收口报告](../../learning/knevo-distill/final-report.md)。
