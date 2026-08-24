# feat/optional-forward-slots

## 这个分支做什么

R-20260824-20。问句带前瞻信号（`_OUTLOOK_JUDGMENT_RE`：你认为/怎么看/会怎么走…）但题型不在
`market_forecast` / `event_forecast` 时，装配层把三个前瞻槽以 `required=False` +
`grounding_mode=model_reasoning` + `evidence_types=()` 挂上契约，并把数值门的条件槽豁免
从「只认必选前瞻槽」放宽为「必选可选都认」——让模型提出的条件阈值有槽可落、机械门不再整句砍。

**不动 `numeric_unsupported` 删除权**：动的是 `_repair` 的上游（契约装配），不是删除权分流。
V8 结论与 `test_numeric_unsupported_sentence_is_still_deleted` 原样不改。

设计合同：`docs/superpowers/specs/2026-08-24-optional-forward-slots-addendum.md`
（正文在分支 `docs/optional-forward-slots-addendum`，已推 Gitea，尚未合 main）。

## 当前状态

三个 commit，基线 `gitea/main@ada882c6`：

| commit | 内容 | 可否独立回滚 |
|---|---|---|
| `a89584ef` | verifier 豁免去掉 `item.required and` | ✅ 对现存契约零行为变化 |
| `4e71851c` | factory 挂槽 + protocol 动态提示规则 | ⚠ 两者不可拆，见下 |
| `3802f3f8` | 钉 9 修正（变异 M3 暴露） | — |

**挂槽与动态提示规则必须同生共死**。`grounding_mode` 在**主循环**里到不了模型：
`generic_research_owner.py` 的 `required_outputs` 块只发
`id / description / evidence_types / required`。（**恢复器
`intelligence/runtime/episode_finalizer.py:175` 是发的**——所以准确说法是「主循环不给、
恢复路径给」，不是「压根不进提示词」。）而 `episode_protocol` 要求模型让 `basis` 与
`grounding_mode` 一致、`basis` 默认值又是 `evidence`。只挂槽不给提示规则 = 模型只能猜，
猜错就 `basis_mismatch` 整份拒、回灌重来。别把这两个 commit 拆开挑一个合。

## 未验证 / 已知边界

- **从未 live。** 台账 `R-20260824-20` 是 `pending`，只有离线腿。执行方不得自行标 confirmed。
- live 需要（设计 §8.3）：≥2 个挂槽样本 + 无前瞻槽对照 1 个 + **误触发样本 1 个** +
  `basis_mismatch` 拒次数（应为 0，非 0 说明提示规则没渲染到，属未收口）。
- **误触发那条腿是必做不是可选**：触发信号 `_OUTLOOK_JUDGMENT_RE` 命中面偏宽（「这个概念
  怎么看」也会中）。LLM 有「给了格就填」的倾向，而三槽是 model_reasoning、其条件句已获豁免
  ——误触发不只是多三个空格子，它同时小幅扩大了无据阈值能存活的面。这是「变错」不是「变笨」，
  贵的那一侧。没有这个样本就不知道宽信号的取舍成不成立。
- 触发面比 #72 **更宽**：#72 是 `output_id in _OUTLOOK_JUDGMENT_OUTPUTS and 正则`，本单只看
  正则，所以契约里没有判断槽的题也会被挂。有意为之（设计 §4.4）。若 live 显示噪声集中在无判断
  槽的题上，收窄时第一个该加的就是这个门。

## 下一步

1. 合 `docs/optional-forward-slots-addendum`（设计文档）与本分支——**要合就一起合**，
   否则 main 上会有实现没设计，或反之。合 main 需用户确认。
2. 验收方跑 live 探针 `probe-fwd-<mmdd>`，按 §8.3 四条腿回填台账。
3. **本单留下的技术债（不是可选优化，未立案）**：把 `grounding_mode` 加进
   `generic_research_owner.py` 的契约渲染，一次修好所有 model_reasoning 槽。

   **[实测]** 这事已在生产发生：`intelligence/eval/measurements/2026-08-18-frozen-thirty-live-3d30b2c5.json`
   里有两次 `grounding basis mismatch for direct_answer: expected evidence, got model_reasoning`
   → `stop_reason=invalid_model_finish` → 落恢复器。恢复器的提示词带 `grounding_mode`，
   所以第二轮就对——**系统在靠「先让你摔一跤，摔完再告诉你答案」工作，每次白烧一个来回。**
   猜错方向是反的（模型报 model_reasoning、契约签 evidence），方向随机正说明病因是
   「没告诉它」而不是「它偏好某一侧」。

   **架构判词**（`harness-architecture-review` C2 三筛）：约束「basis 必须匹配
   grounding_mode」本身是**真下限**，烂的是它被实现成**拦输出**（审已产出的 FINAL_JSON
   且拒整份）——判「**可改写成拦输入**」，正确动作是让约束由构造即满足，**不是**再加一条
   逐槽手写规则。本单加的那条规则是补丁；债在这里。修完之后，`_question_type_rules` 里
   凡是只为传达 `grounding_mode` 的手写规则（prior_recall 那条、本单这条）都可以删。

   仍未在本单做的理由：会动到所有任务的提示词，需单独立案 + 单独 live，**别搭本单车**。

## 踩过的坑

- **`evidence_types` 不能留给默认值**。`_required_output_evidence_types` 对不认识的 output_id
  会回**全量能力列表**；推理槽挂一串工具名等于暗示这格该去检索，正是 prior_recall 踩过的坑
  （`run_20260808_102708`：模型读不出哪个工具对应这格，把工具预算全投给别处）。钉 1 抓出来的。
- **钉不能随 bug 自适应**。钉 9 初版按 `if item.required` 生成绑定，变异 M3（挂槽时
  `required=True`）一改，测试就跟着把三槽也绑了，「模型不绑仍 completed」这个场景根本没被演
  出来 → M3 存活。改成按 output_id 排除前瞻槽后才击杀。**演「模型不绑」，绑定列表就不能跟着
  契约的错误状态走。**
- 测试里 `build_episode_context` 的 `task_id` 必须唯一，`research_contract` 按 episode 登记活跃
  根预算，重名直接抛 `root budget already exists`，与被测行为无关。
- 设计初稿的行号锚两天就烂了（main 前进 40 commit）。本分支开工时 main 又从 `34fcbaaa` 走到
  `ada882c6`，factory 里的锚再漂 4-5 行。**认符号不认数字。**
- **我自己也栽了一次同款**：断言「`episode_finalizer.py` 不存在」，实际它在
  `intelligence/runtime/` 下——我只 `git cat-file` 查了猜的那个 `intelligence/services/` 路径。
  由此连带把「grounding_mode 不进提示词」说重了（真相是主循环不给、恢复器给）。
  **查存在性要全树搜文件名，不要拿猜的目录去证伪。** 代码没受影响，错的是论证。

## 工具沉淀盘点

变异驱动脚本是一次性写的（`tmp_mutation_run.py`，跑完已删）。形状值得留意但**没抽成工具**：
样本只有这一次，抽早了会把偶然形状固化。若下一单还要跑变异，第二次重复时再抽
（放 `~/harness-reference/TOOLKIT.md` 审计那一件）。脚本要点：`PYTHONDONTWRITEBYTECODE=1`
跑，否则 .pyc 按 mtime+size 判缓存，同长度改动一秒内还原会伪造出「回归」。

## 已验证

- 离线钉 18 条全绿（`intelligence/tests/test_optional_forward_slots.py`）。
- 变异 §8.2 六条 **6/6 击杀**，含两条必杀：恢复 `item.required and` → 钉 6 红；
  删动态提示规则 → 钉 11 红。
- `intelligence/tests` 全量 **5699 passed / 11 skipped / 0 failed** @ `3802f3f8`
  （收据 `~/.finance-runtime/test-receipts/20260824T145518Z-3802f3f8.json`）。
  main 本身此刻也无存量红，无需比对。
- `ruff check intelligence/` 全绿；9 道 pre-commit 门禁全过。
