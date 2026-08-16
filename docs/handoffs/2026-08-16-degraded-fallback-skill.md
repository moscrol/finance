# handoff: 降级回答章法 skill（knevo 蒸馏落地）与输出兜底注入

- 日期：2026-08-16
- 分支：`feat/degraded-fallback-skill`（基于 `91e0b172`，即 #87 合入后的 main）
- 开关：`ASK_DEGRADED_FALLBACK`，**默认 off**；off 时 episode 指令与 gap 答案逐字节不变（测试钉住）

## 背景

观点题核验预算回归（2026-08-16 立案）里，L01 的公开答案只剩一句
「已取得 60 条证据，但未完成核验绑定，暂不能引用」。knevo 蒸馏语料对这类
场景有成套纪律，但本仓只落了一半：`_gap_answer` 已实现「缺 X → 仍可判 Y →
验证窗口 Z」（缺数三档中间档），q13「降级后必须保留的七项」里的
**尝试过什么、来源标注不降级**两项没有着落，且章法散在代码注释里，
没有 canonical skill 文件可供 prompt 侧对照。

## 蒸馏来源

- `agent-memory/10_knowledge/knevo-reverse-engineering.md` §3C.3（结论五元素、
  梯度输出）、§3C.5（缺数三档、「假设 × 可验证时点 × 推翻条件」统一范式）
- `docs/learning/knevo-distill/q13-拒答与降级纪律.md`：拒答只留两类（实盘操作、
  收益承诺），其余一律降级；降级 = 换源 + 加标注，不是删信息；降级后必须
  保留七项，缺一项即降级不合格；「可信度降低了，透明度必须提高」
- `docs/learning/knevo-distill/E-004-missing-data-downgrade.md`：诚实降级的
  行为验证（信息不足 + 最大可判层级 + 最小补数集），其分类语义反转部分
  **不回灌**

## 交付物

| 文件 | 作用 |
|---|---|
| `skills/finance-degraded-fallback/SKILL.md` | canonical 章法（prompt-only、routable:false）；洁净契约与长尾骨架同源：正文无阿拉伯数字、无板块名，判断词表逐字引 `ANALYTICAL_MARKERS` |
| `intelligence/services/degraded_fallback.py` | 开关、skill 装载与契约断言、`episode_rule`（prompt 注入）、`gap_transparency`（确定性渲染） |
| `episode_protocol.py` 挂钩 | 指令里紧随长尾骨架位注入章法块；静态契约指纹不受影响（f-string 无常量段） |
| `episode_semantic_verifier._gap_answer` 挂钩 | 在既有结构性兜底末尾追加透明段 |
| `skills.registry.json` / `CLAUDE.md` | 用 `build_registry` 自身函数生成，与 CI 重扫逐字节一致 |
| `intelligence/tests/test_degraded_fallback.py` | 契约、注入、红线、marker 闸静默 |

## q13 七项 → 本仓落点

| 七项 | 落点 |
|---|---|
| 尝试过什么 | **新增**：`gap_transparency` 的「本轮尝试：检索调用 N 次、模型调用 M 次（＋机械中断成因）」 |
| 缺口是什么 | 既有「仍需核验：…」＋新增 stop_reason 成因翻译 |
| 已核验与未核验分开 | 既有「本轮已核验（供参考…）/ 已取得 N 条证据」＋新增「未核验内容暂不引用」 |
| 来源标注不降级 | **新增**：「材料来源：X（截至 date）、…」，只取 source/source_date 两个结构性字段 |
| 最大可判层级 | prompt 侧章法（模型还能写时约束其分档），确定性路径不代写判断 |
| 待补证清单与验证窗口 | 既有「仍需核验 + 证据数据截至 + 缺口补齐后可复验」 |
| 推翻条件 | prompt 侧章法；确定性路径不代写 |

## 红线（与 `_gap_answer` 原红线同源，测试钉住）

- draft、证据 `title`/`detail` 一个字不进透明段——gap 出现的场合正是草稿被拒
  或未生成的场合，捞正文等于绕过语义门禁
- 不暴露内部工具名/provider/哈希（对齐 episode 协议表达边界）：只报调用计数
  与自然语言成因
- `_CLAIM_POLICY` 七闸、judge 词表、预算常量、5pp 口径全部未动

## 非目标

- **不是**预算回归（R-20260816-01…05）的修复：不改预算、不改核验路径，
  不满足十题窗闸 2（`budget_regression_landed`），该闸仍等 triage 处置
- 不改判断句被剥后的「证据缺口：…」路径（judge 剥句 gap），如需同样透明化
  另开小 PR

## 翻默认前置（预注册草案）

- 复用长尾 live A/B 的合规口径（`docs/verification/2026-08-16-longtail-baseline-live-ab.md` §0.2）
  跑一个小对照窗：on-arm 只看 gap/partial 槽位，主看点是透明段是否引发
  judge 剥句、marker 闸告警或用户可见指令泄漏；prompt 注入臂另计 token 增量
- 建议排期在预算回归修复落地之后，避免两个变量搅在同一窗口

## 验证记录

- 目标测试（degraded_fallback / gap_answer_middle_tier / longtail_baseline /
  episode_protocol / task_fulfillment）：81 passed
- ruff：All checks passed
- 全量 pytest：5182 passed / 34 failed，失败集与未改动 main 树（`773b3d7e`
  deploy 树同 venv 复跑）**逐字节相同**——本机环境既有失败（ceiling fixture /
  continuous turn adapter 四文件），与本改动无关，CI 为准
