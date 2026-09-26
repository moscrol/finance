# docs/knevo-distill-closeout-0916

## 这个分支做什么
Knevo 资料炼化对账的收口（纯文档 + 一个未接线的候选 JSON）。上游 PR #749 已把三支 knevo 文档分支
合入 main（`8bb20aa9`），本分支处理审计查出的残项。全景与未闭合清单见 README §九。

## 决策与被否方案
| 选了 | 否了 | 为什么 |
|---|---|---|
| B 线**暂停**（ab-ledger「W4 裁决建议」，待拍板） | 废弃 / 攒够 25 条 | 废弃丢掉三条样本作 `answer_lint` 红样本的用途；它截止纪律两次失守，再攒也不是双盲 |
| q15 只收结构进 position-framework §6，阈值进 Q-002 #7–#11 | 落成代码 / 整条不吸收 | 指标本仓多数有数据源，但阈值全是它拍的；各层仓位区间属实盘指令，触红线 |
| q18 写独立候选文件 `eval/cases/knevo_q18_candidate_cases.json` | 并进 `acceptance_cases.json` | 28 题是冻结基准；q18 是它知情被测下连发作答的，写死期望值＝把它的答法当金标准 |
| AB-003 第 3 条计 miss | 按字面判 unverifiable | 冻结口径要「涨 >2% 且放量」才算证伪，实际 +3.09 但缩量；字面判会把明确判错洗成不可判 |

## 当前状态
六个提交，树干净。风远94 对账台账已落（`fengyuan94-corpus-dedup-2026-09-16.md`）：66 张卡判已有 18 /
部分 25 / 新增 22 / 不吸收 1，**原「编号零引用=未炼化」被推翻**（画像与卡同源、两条编译路径）。

## 下一步
1. **候选料只在 `/tmp/fengyuan94-new-cards-2026-09-16.md`（67KB，不进 git，重启即失）**。要吸收就尽快走
   `perspective-distill` 第 2–4 步；六条优先项见台账 §5。对账只判去留，**一条都没写进画像**。
2. 用户裁决三件：W4 是否暂停 B 线；q15 / q18 表态；三处 vault 矛盾（清单在 agent-memory
   `10_knowledge/knevo-44turn-rounds15-36-distill-2026-09-16.md` §4）。
3. 若暂停 B 线，`question-bank.md` §五两行改终态，`final-report.md` 只写「它真正领先的 top3」。

## 踩过的坑
- **主树落后 729 提交**，`knevo-distill/` 里看不到 q16–q18 / absorption-plan / recheck；在主树上盘点会把
  「已炼化」判成「没做」。先 `git ls-tree gitea/main` + `git branch -a --list '*<topic>*'`。
- 主树还躺着 E-008 的 untracked 旧草稿与 README 散落改动，与分支版不同——**第二副本永远是漂的那个**，已删。
- 派给子代理的输出路径写在一棵随后被合并删除的工作树里。长跑任务的输出目录要选本轮不回收的树。
- 血统对账六步法已归位 agent-memory `10_knowledge/distillation-provenance-audit.md`。

## 未验证 / 已知边界
- 对账的**去重判定是语义比对**，不是机械匹配：判「已有」意味着我认为画像某条覆盖了它，复核请直接看
  台账里给的字段与条目号。判「新增」的 grep 范围只有画像 + `reading_baseline.py` 两处。
- AB-003 判分是**自评**（本地答卷本系统产出、本次本系统打分），判据取纯客观涨跌幅但偏差仍在。
- q15 / q18 表态与 W4 建议都是 agent 起草、**用户未确认**，两处文档均已明写。
- 44 轮原文第 15–28 轮只做重叠审计，**8 项未覆盖**；三处与 vault 矛盾的结论**原文未改**。

## 已验证
**合并预览门禁全绿**：`git merge-tree`+`commit-tree` 造 `cb938b42`（本分支 ⊕ main `801d0fc2`）后跑
`run_main_gate.sh` → ruff 绿、pytest **10952P / 0F / 81S / 2x**，收据 target 是预览树。AB-003 数据从生产库
只读复算（`ab/AB-003-local.md` §5 两条 SQL）；候选 JSON 合法，无测试扫 `cases/` 顶层。
