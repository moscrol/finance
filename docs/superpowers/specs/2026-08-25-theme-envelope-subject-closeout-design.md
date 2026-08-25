# 设计：题材题信封主语收口（前瞻观点词形 × 板块后缀）

- 日期：2026-08-25
- 状态：**Draft v1**（未实施，未核稿。核稿重点见 §12——「联合题升不升 theme_analysis」刻意不在 P0）
- 来源：五臂对照报告结论「科技/医药没有被收成 theme_analysis，是五臂（除原生）共用的契约债」（`~/.finance-runtime/trace-diff-spt-tech-med-monday-20260823/one-page-report.md` §信封）+ 2026-08-25 生产 live 两发契约冻结 + `0325d829` 快照 `understand_query` 实测（本稿 §3）。
- 代码树：实施时从 `gitea/main` 开干净树 `fix/theme-envelope-subject`。**禁止**在主检出脏树改 runtime。**禁止**动 8792 / 8796 / 8802。
- 相邻稿（本单不重做、不抢合）：
  - `feat/verify-timepoint-forward-slot`（#377 已合已切）：A 刀只把「后续的?走势|后市」补进 `_OUTLOOK_JUDGMENT_RE`（**槽挂载**闸，不是信封主语）；本单不碰该正则。
  - `2026-08-25-substitute-observation-probe-design.md`（#371/#372/#373 已合已切）：探针触发用**库内主线∩双红缺口**，不用信封主语；本单不改探针。
  - `2026-08-24-knevo28-program-and-compiler-spec.md`：`ThemeResearchSpec`（`R-20260824-17` pending）是题型升级（方案 B）的前置，不是本单 P0 的前置。
  - `2026-08-20-market-cause-sector-routing-design.md`：market_cause 路由不碰。

## 0. 一句话

「X（和Y）板块 + 接下来/后续 + 怎么看/怎么走」这类前瞻观点词形的题材题，在信封层**全链落 0.4 兜底、subject=None**——检索种子退化成整句、stance pack 与 kb/graph 锚定失去主语。主语抽取现在只有两扇窄门：显式 cue（「分析下…」）或「联合板块 ∧ scenario_tree 算子」（只有「会怎么样」词形能触发）。本单把「板块后缀 × 前瞻观点词形」收进主语抽取；**题型升级（general_finance_qa → theme_analysis）刻意另立**。

**判别变量**（验收只锁这一条）：冻结句「站在spt视角下，科技和医药板块接下来的走势怎么看，需要观察哪些个股的反馈」的信封必须是 `subject_kind=theme`、`subject=科技、医药`；单题材冻结句「医药板块接下来的走势怎么看」必须 `subject=医药`。不是「答案更长」，不是「题型变 theme_analysis」，不是「置信度数字变化」。

人话：客人指着菜单上的两道菜问「这俩接下来还值得点吗」，点菜员现在把整句话当菜名记（谁都查不到）；本单让他先把菜名抄下来。至于这算「单点」还是「套餐」（题型），下一单再定。

## 1. 范围

### 1.1 做

- `intelligence/services/query_understanding.py` 信封主语抽取：
  - **单题材新路**：`X板块`（后缀窗口）× 前瞻观点词形（接下来/后续/往后 + 怎么看/怎么走/走势怎么看）→ `subject=X`、`subject_kind=theme`、题型**维持现状**（general_finance_qa）。X 过 `_GENERIC_EXPLICIT_SUBJECTS` / `_GENERIC_EXPLICIT_PREFIXES` / 长度 ≥2 过滤（与现有分支同一套，不另造）。
  - **联合门放宽一档**：`_joint_board_subject` 的算子门从「`len(operators)>=2 ∧ scenario_tree`」扩到「∨ 前瞻观点词形在句」。产出形状不变（`左、右`，同一套过滤）。
- 负样本锁死：大盘级词形不得被抢（「接下来大盘怎么走」「今天市场怎么样」照旧）；「下游/下跌」等 `_KEEP_XIA_COMPOUNDS` 复合词不误剥。
- 台账 `R-20260825-07` 预注册（§9）。

### 1.2 不做

- **不把任何题升 theme_analysis**——那是方案 B（§4），依赖 `ThemeResearchSpec`（`R-20260824-17`）与联合主语的单题材骨架适配，需要自己的验收与核稿。本单只填 subject。
- 不动 `_OUTLOOK_JUDGMENT_RE`（#377 的 A 刀）、不动前瞻槽挂载。
- 不动 `is_market_watch_query` / `is_market_forecast_query` / market_cause 判定与次序。
- 不动替补探针触发（库内缺口对齐，与信封无关）。
- 不加 LLM 分类兜底（§4 方案 C 否决）。
- 不改 route_table 行、不改 capabilities。

## 2. 术语

| 词 | 本稿含义 | 不要当成 |
|---|---|---|
| **信封（envelope）** | `understand_query` 产出的 `QueryEnvelope`，`build_task_frame` 直接吃它的 `question_type`/`subject` | answer_orchestrator 的 `QuestionPlan`（另一条链，本单不动） |
| **前瞻观点词形** | 接下来/后续/往后 × 怎么看/怎么走/走势 的组合疑问 | `_OUTLOOK_JUDGMENT_RE`（槽挂载闸用，词表独立演化） |
| **0.4 兜底** | `understand_query` 末端 generic 分支：`general_finance_qa`/`unknown`/None | 「路由失败」——它是合法兜底，问题是**本可抽到主语的题**不该落进来 |
| **联合主语** | `左、右` 拼接（如 `科技、医药`），`subject_kind=theme` | 一个题材词表命中；theme_analysis 的单题材 subject |

## 3. 已核实事实（2026-08-25 对 `0325d829` 快照实测 + 生产 live，实施时不要再探一遍）

1. **[live×2]** 生产 8792（`83ef1bcc` 与 `6a01f96f` 各一发，`run_20260825_101512_555399` / `run_20260825_102340_250817`）：「站在spt视角下，科技和医药板块接下来的走势怎么看，需要观察哪些个股的反馈」→ `task_frame.question_type=general_finance_qa`、`subject=None`。收据 `~/.finance-runtime/substitute-probe-live-20260825/{pre,post}-377-*/continuous-episode.json`。
2. **[实测]** 同句离线 `understand_query` = `general_finance_qa / unknown / None / 0.4`（0.4 兜底）。词形改「会怎么样」即抽到 `科技、医药`（0.8）；词形是唯一变量。
3. **[实测]** 单题材全灭：「科技板块接下来怎么走」「医药板块接下来的走势怎么看」「科技板块后续怎么走」「科技板块后续的走势怎么看」「接下来医药板块怎么看」全部 0.4 兜底、subject=None。
4. **[实测]** 「分析下有色金属板块后续的走势」→ `theme_analysis / 有色金属 / 0.8`：靠 `_EXPLICIT_CUE_RE`（「分析下」），**不是**靠「后续」。单题材主语现在只有 cue 一扇门。
5. **[实测]** `_joint_board_subject`（query_understanding.py）门为 `len(operators)>=2 ∧ "scenario_tree" in operators`，注释「先窄……不查题材词表」；返回落点是 `general_finance_qa + subject_kind=theme`——**留在 general_finance_qa 是该分支的刻意设计**，不是 bug。
6. **[实测]** `frame.subject` 下游真实消费：`episode_tools.py` 六处（检索 query 种子 `{subject} {raw_question}`、工具参数 subject）、`conversation_orchestrator.py`（`primary_subject`、stance pack `subject=task_frame.subject`）。subject=None 时检索种子退化为整句、stance pack 无主语。
7. **[实测]** #377 只改 `episode_factory/episode_protocol/research_contract/task_fulfillment` + `_OUTLOOK_JUDGMENT_RE` 词形（槽挂载）；信封主语未动。
8. **[账]** `R-20260824-31`：「分析有色金属板块后续走势」仍 `theme_analysis`——cue 路是现役回归锁，本单不得碰坏。
9. **[账]** 台账 `R-20260825-01…06` 已占（探针三行 + hotfix + #377 两行）；本稿从 `-07` 起。

## 4. 方案对比

| 方案 | 做法 | 得 | 失 / 判 |
|---|---|---|---|
| **A. 主语抽取扩词形（P0，采用）** | 单题材新路 + 联合门放宽；题型不动 | 检索种子/stance pack 立刻有主语；改动局限一个文件；cue 路与 market 级判定零接触 | 题型仍是 general_finance_qa，theme 专属骨架/rubric 不生效（可接受：那是方案 B 的事） |
| B. 联合题升 theme_analysis | 信封直接改题型 | theme 骨架、route 行、rubric 全套生效 | 联合主语 `科技、医药` 会进单题材假设的 theme 检索/模块（`theme_modules.run_module(theme)` 形状）；`ThemeResearchSpec`（R-20260824-17）未落地；route capabilities 面大。**另立单，不与 P0 绑** |
| C. LLM 分类兜底 | 低置信走 LLM 混合分类 | 覆盖未知词形 | episode 信封链是词面判定 + 确定性构帧；加 LLM 层 = 在信封上游引入不可复现判定，违背「契约由上游确定性生成」纪律。否决 |

## 5. 目标态

```
understand_query(text)
  → …现有次序完全不动（company/ticker/估值/compositional/explicit_company/
     market_forecast/event_forecast/matched_theme/alias/quoted/explicit cue）…
  → [新] 单题材：板块后缀窗口 × 前瞻观点词形 → subject=X, kind=theme, 题型不变
  → _joint_board_subject：算子门 ∨ 前瞻观点词形 → subject=左、右（现状形状）
  → 仅当以上全空：0.4 兜底
```

新路插入位置必须在 `market_forecast/event_forecast` 判定**之后**、0.4 兜底**之前**（大盘级词形先走大盘判定，不被题材路抢）。

## 6. 契约

- 主语过滤三条与现役同源：长度 ≥2、`_GENERIC_EXPLICIT_SUBJECTS` 黑名单、`_GENERIC_EXPLICIT_PREFIXES` 前缀黑名单。不新建第二套黑名单。
- 联合主语拼接维持 `、` 分隔（消费方已按该形状吃）。
- 置信度：单题材新路 ≤ cue 路（0.8），建议 0.72–0.78 区间定一个并写死在实施 PR；联合路维持 0.8。
- `subject_source`（若信封带该字段）标 `suffix_window`，与 `explicit/alias/quoted` 区分，方便日后审计词形贡献。

## 7. 验收（离线红→绿；live 只做旁证不做门）

| # | 输入 | 必须 |
|---|---|---|
| 1 | 冻结句（judgment 变量原句） | `subject=科技、医药`、`kind=theme`、题型不变 |
| 2 | 「医药板块接下来的走势怎么看」 | `subject=医药`、`kind=theme` |
| 3 | 「科技板块后续怎么走」 | `subject=科技` |
| 4 | 「分析下有色金属板块后续的走势」 | **仍** `theme_analysis / 有色金属`（cue 路不被新路抢） |
| 5 | 「接下来大盘怎么走」 | 无 theme subject；市场级判定不变 |
| 6 | 「今天市场怎么样」/「2026-07-23 今天市场怎么样」 | 仍 `market_watch` 链路，零变化 |
| 7 | 「下游产业链怎么看」 | `_KEEP_XIA_COMPOUNDS` 不误剥、不误抽 |
| 8 | 「站在spt视角下，…会怎么样…」（五臂原句） | 联合路照旧 `科技、医药`（回归锁） |

变异：把新路插到 market_forecast 判定之前 → #5 必须红。删联合门放宽 → #1 红、#8 仍绿。

## 8. 落点与文件

| 文件 | 职责 |
|---|---|
| Modify: `intelligence/services/query_understanding.py` | 单题材后缀窗口新路 + `_joint_board_subject` 门放宽 |
| Test: `intelligence/tests/test_query_understanding_theme_subject.py`（或并入现有信封测试文件，实施时按就近原则定） | §7 全表 + 两个变异锁 |
| 收尾: `docs/prediction-ledger.md` | `R-20260825-07` |

## 9. 账本（预注册）

| ID | 现象 | 类型 | 验证 |
|---|---|---|---|
| `R-20260825-07` | 前瞻观点词形题材题信封 subject=None、0.4 兜底；检索种子退化整句、stance pack 无主语 | `HARNESS_FIX` | §7 #1–#8 红→绿；live 旁证：同冻结句生产契约 `subject` 非空 |

题型升级（方案 B）若立案，另占号、另写判别变量，不复用本行。

## 10. 实施顺序

1. 干净树 `fix/theme-envelope-subject`（基线 ≥ `0325d829`）。
2. §7 表全部写成失败测试（#4/#5/#6/#8 此刻应绿——它们是回归锁，先确认绿再动手）。
3. 单题材新路 → #2/#3/#7 绿。
4. 联合门放宽 → #1 绿、#8 仍绿。
5. 变异两锁跑一遍。全量 + ruff。
6. live 旁证一发（冻结句，产线通道），收据入 sidecar；合并等用户确认。

## 11. 合入关系

- 与 #377 线零文件冲突（它不动 query_understanding 主语路）。
- 与探针线零冲突（触发不读信封）。
- 方案 B 若开单，基线必须含本单（联合主语形状是它的输入）。

## 12. 自检 / 核稿重点

- 无 TBD；P0 只有一个文件的行为变更。
- 核稿必查三点：① 新路插入位置是否真的在 market/event forecast 之后（§5 次序）；② ~~后缀是否锁死~~ **[已实测]** `_JOINT_BOARD_SUFFIX_RE = (?:板块|题材)`、`_JOINT_BOARD_RE` 要求 `A(和|与|、)B` 各 2–6 个汉字紧贴后缀窗口——门放宽后无「板块/题材」后缀的句子仍进不来；③ 单题材窗口对「XX概念板块」「XX指数」这类复合后缀的行为。
- 「先窄」原则继承：新路只认「板块」后缀词形，不查题材词表、不做模糊匹配——宁可漏（落兜底，与现状同）不可错抢。
