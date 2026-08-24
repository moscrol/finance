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
| `4e71851c` | factory 挂槽 + protocol 动态提示规则 | ✅ 两者可分（初版说不可拆，已撤，见下） |
| `3802f3f8` | 钉 9 修正（变异 M3 暴露） | — |

**挂槽与动态提示规则的关系（2026-08-24 三次更正后）**：两者**可以分开**。初版交接写的
「不可拆，否则模型被 basis_mismatch 整份拒」**是错的**，理由已撤——`grounding_mode` 本来
就在 episode 逐回合载荷里（`build_episode_input` 发 `contract.to_dict()`，`RequiredOutput`
走 `asdict`，实测一次载荷 8 处）。动态规则保留，但它的作用是**行为引导**：让模型敢在这三格
写具体可核验阈值而不是「以盘面为准」自保，并说明可选、不必硬凑。

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
3. **~~技术债~~ 已撤销（2026-08-24 三次更正）**：初版记的「把 `grounding_mode` 加进
   `generic_research_owner.py` 的契约渲染」**不需要做**。三条依据全部被实测推翻：

   - 生产逐回合载荷 `build_episode_input`（`codex_headless_runtime` / `openai_agents_runtime`
     都调）发 `research_contract.to_dict()`，`RequiredOutput` 走 `asdict`——**`grounding_mode`
     在里面**，实测一次 general_finance_qa 载荷出现 8 处；
   - `generic_research_owner.py` 是 **ownerless 长尾**那条路，不是 episode 主循环；该文件全文
     `basis` 出现 **0 次**、不走 `validate_episode_finish`——**没有 basis 闸，少这个字段不是缺陷**；
   - 2026-08-18 live 那两次 `basis_mismatch` 是模型**看得见字段却没照做**的普通 FORMAT 滑档，
     回灌自愈，证明不了投递缺口。

   基于该前提做出的 `harness-architecture-review` L1/L3 缺口判定与三筛判词一并作废
   （三筛方法没问题，是喂给它的事实错了）。

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
