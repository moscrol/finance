# docs/knevo-e009-arch-delta · 在途交接（2026-09-10）

## 干什么
把用户转贴的 knevo 架构自白（所有权标签/记忆=prior/护城河论）沉淀进 knevo-distill，
并出 delta 工作清单。产出三个文件，已提交 `b8061ece`，pre-commit 全绿：

- `docs/learning/knevo-distill/E-009-architecture-self-disclosure.md`（矿+对照+防误抄清单）
- `docs/superpowers/specs/2026-09-10-knevo-arch-delta-worklist.md`（W1–W6 候选，待人过闸）
- README §八 索引

## 关键状态：分支嵌套
本分支**基于 `docs/knevo-m-probes-verification`（未合 main，E-008 所在）**，不是 gitea/main。
knevo-distill 系列当前裂在三条未合分支：main 到 §五 / `feat/event-pricing-slice1` 有 E-007+§六 /
`docs/knevo-m-probes-verification` 有 E-008+§七（无§六）。E-009 对 E-007 是前向引用。
**合并顺序：先 event-pricing-slice1 / knevo-m-probes，再本分支；README §六/§七/§八
在一处追加，合并时必有一次手工归并。**

## 对照核心结论（详见 E-009）
knevo 三机制我们都有同构（memory_gate 写侧 fail-closed / user_memory [M] 块级标签 + 胜率行 /
CR-04）；真 delta 只有逐条 ownership 颗粒度、读侧路由硬分离两处。它自承的三缺口里
事实校验闸门与可靠性雏形我们已领先。采信等级=声明面（E-008 教训：它声称的派单已被实测证伪）。

## 等用户裁决（spec 六项，均未动代码）
W1(P1) 读侧记忆=prior 断言测试；W2(P1) user_memory 渲染升条目级 ownership；
W3(P2) 召回降权闭环；W4(P2) AB 台账补 verdict 或宣判废弃（停在 2/25 样本、逾期两个月）；
W5(P2) G1a 建块解锁 SPT-A06（first_limit_time 14.9 万行非空已核，open_times 全 NULL 仍成立）；
W6(P3) E-007 P3/P4 × Polymarket 表（依赖 polymarket-macro-odds-impl 未合并分支）。

## 坑
- 主树（detached HEAD）混着至少两个 session 的未提交改动，E-008 在主树是 untracked——别以主树
  工作副本为准认 knevo-distill 的状态，以分支为准。
-  divergence-distill §4 红线：W1–W6 人未过闸不写回代码。
