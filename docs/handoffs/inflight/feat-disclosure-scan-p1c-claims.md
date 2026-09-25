# feat/disclosure-scan-p1c-claims（已收口：#401–#407 已合、8792=`fbdbbfd2`、母稿 P1 R5 于 26e 切后首次真过）

> 2026-08-26 质检后重写过三处结论。**「当前状态」里带 ⚠️ 的那段务必先读**——
> 初版把 registry 预算说反了；随后又把「残差上场 + 名单零回归」误写成母稿 R5 达成。

## 这个分支做什么

修 P1-① 残差写手被有据呈现器必然拒收的根因：`prepare_disclosure_residual_answer`
此前走通用 builder（claim 被 `[:8]` 截断），shadow 有据链输入完全从 answer_spec
生成，#395 预置的完整包与残差契约进不了这条链。两件事：①
`build_disclosure_residual_answer_spec` 全行 VERIFIED claim + 聚合统计 claims；
② 残差契约经 `spec.prompt_constraints` 进 shadow 链 required_outputs 槽。

## 当前状态

**代码已收口、母稿 R5 于 26e 切后才过（2026-08-26 12:28）。** 时间线不要并成一天：

| 时点 | 合入 / 切码 | 公开稿实际交付 |
|---|---|---|
| 26 凌晨 #401 `fe657cbc` | 全行 claim 集 | 残差被有据拒收，公开稿 = P0 纯包（安全空转） |
| 26 凌晨 #402 `6876a6e7` | judge CLI transport | 残差首次上场；名单零回归。**弱化 R5**（残差上场≠尾段解读） |
| 26 上午 #404 `7cc947f2` | 部分引文不得吞驳回 | 名单侧过；尾段仍只有计数+回购截断。该探针未走 #404 目标分支 |
| 26 中午 #405+#406+#407 `fbdbbfd2` | 收据脏判定 / registry 保留席 / 生产态 shadow trace | **母稿 P1 R5 首次真过**（见下） |

> ⚠️ **本节初版有三处错，别按旧说法走。**
>
> **错 1：「registry 64 条全装下无截断注」——说反了。** 64 是 `verified_facts`
> 的**长度**，不是进 prompt 的行数。`fe657cbc` 上忠实重建：68 条 claim、12k
> 预算只装下 18 条 + 1 条截断注；`disc:excl` 0、`disc:counter` 0。直接证据是
> 模型正文「另有部分结果**因窗口预算未纳入**」——该措辞全仓只出现在
> `answer_model.py` 那条截断注里，初版错归给了 `disc:gap:budget`。
>
> **错 2：护栏测过但没护住。** `test_residual_registry_holds_all_rows_within_budget`
> 一直是绿的，因为 fixture 11 行、生产 61 行。金样本把理想写进了断言。
>
> **错 3：「R5 判据达成」在 #402 切后就写上了——口径弱化了。** 母稿计划 §6 R5
> 锁的是公开稿**尾段**出现集采双重性/反证解读，不是包里的 `【集采中选】` /
> `## 反证` 标签，也不是「残差上场 + 名单零回归」。`run_20260826_092339_978777`
> （#404 切后）尾段只有计数 + 回购截断；模型 raw 写过解读，裁判/闸删掉后
> 公开稿没有。真过的时点是 `run_20260826_122832_875134`（`fbdbbfd2`）。

### 母稿 P1 R5 真读数（`run_20260826_122832_875134`）

对话入口、用户 `probe-registry-trace-0826`、8792=`fbdbbfd298f4`。

| R5 子句 | 读数 |
|---|---|
| 名单在顶 | 过。pack 21/39/1 |
| 名单零增删 | 过。21/21 公告号在稿、越界六位码 0、骨架关键词 0 |
| 尾段集采双重性 | **过（首次）**。「集采中选（如中关村盐酸曲马多注射液）因量价对冲不默认利好，未计入」 |
| 尾段反证解读 | **过（首次）**。「华北制药 8-22…同日公告撤回一项药品注册申请…削弱其整体利好判断」 |
| 边界诚实 | 过。临床≠上市、回购截断「不能表述为没有」 |

shadow `status=repaired`，judge rejected=[3] 已删（raw 1604 → repaired 1160 → presented 395），`degrades=[]`。

#407 生产 trace 首见：`grounded_composer_shadow`、`source=primary_grounded_presenter`、
`judge_reported=[3] == applied=[3]`、`judge_provider=grok-cli-judge` 与 composer `provider=zhipu` 分列。
本轮是单条带引文路径，**不是** #404「多条 issue、部分无引号」的 live 样本。

切流正文 `docs/handoffs/2026-08-26e-disclosure-406-407-cutover.md`（运行时副本
`~/.finance-runtime/cutover-20260826e-8792.md`）。回滚锚
`~/.finance-runtime/cutover-20260826e-rollback-8792.txt`（未动用）。

## 下一步

1. ~~judge URLError~~ **已修已切**（#402 `6876a6e7`）。
2. ~~registry 把反证/缺口挤出 prompt~~ **已修已切**（#406 `ef3b76ac`）。atom 去重复 +
   `counter_evidence∪gaps` 保留席位 `max_chars//4`。遗留：主名单 600536 仍会被
   排除名单里含「医药/公告」的行按 query 加权挤掉——通用 ranker 分不出主名单与
   排除名单，要分得动 spec 的领域模型，**另开一轮**。
3. ~~judge 驳回被吃掉一半~~ **已修已切**（#404 `7cc947f2`）。证据是单元回归锚 +
   归档件字节级重放。live 尚未碰到「多条 issue、至少一条不带引号」。
4. ~~shadow 各阶段没有落 trace~~ **已修已切**（#407 `fbdbbfd2`）。生产态
   `grounded_presenter` 现在会发 `grounded_composer_shadow`。
5. ~~收据脏判定漏 porcelain 首行~~ **已修**（#405 `7054f995`，测试基建，未单独切码）。
6. deterministic_issues 的标题 warning（建议标题集合外）不阻塞；若要消除，把残差
   契约的建议标题集合与 composer 实际产出对齐。
7. P1-② 巨潮详情/PDF 抽品种金额、P1-③ 问句自定义窗口、P1-b 缺口分列：母稿分期未做。

## 踩过的坑

- `disclosure_scan_pack` 顶层 import `answer_model` 会循环，import 下沉函数内。
- `AnswerSpec.system_notices` 是必填位置参数。
- worktree 无 venv：用主树 `.venv-workbench/bin/python`，cwd 决定加载哪份代码。
- 账本 `record`/`check` 的 `--repo-root` 必须给**数据仓**（`$FINANCE_WS`），给快照
  会把 switch 行写进快照自己的 `state/`（误置账本），check 则读到 `~/.finance-runtime/`
  回退位的陈旧账。
- shadow 存证的 provider/model 字段是 **composer** 的，不是 judge 的——判 judge
  用哪个 provider 要看 `judge_provider()` + **活进程的 env**，不是抄启动器脚本。
  误标一次烧了三轮（写着 zhipu，实际跑 grok-cli）。#407 把两者分开存。
- 收据的脏判定会漏掉 porcelain **首行**：`_git` 对整段输出做 `.strip()`，未暂存
  改动行形如 `" M path"`，首行前导空格被吃掉后 `line[3:]` 多切一个字符。当它是
  唯一的脏代码文件时 `dirty` 记成 False。写方 `conftest.py` 与检方
  `scripts/check_test_receipt.py` 是同一份逻辑的两个拷贝。**#405 已合**，两边都补了，
  仍未抽成单一真本源。
- 别拿 `verified_facts` 的长度当「进了 prompt 的条数」。要知道模型实际看到什么，
  就用生产 pack 重建 `grounded_claim_registry_block`——registry block **没有归档**，
  事后只能重放。
- R5 探针必须走对话入口（`POST /api/conversations/{id}/messages`，`skill_mode=auto`）。
  裸 `POST /api/runs` 不建 task_frame、不走披露扫描包。`workbench_probe.py` 默认
  `skill_mode=manual`，冻结题必须显式 `--skill-mode auto`。

## 工具沉淀盘点

无新脚本。「组件写正文、模型只写边注」的补全应用：claim 集就是组件事实的完整
投影，投影缺行（[:8]）= 边注必然越界。

**可复用判据（换仓仍会发生，形状在 BUILD.md §3 事实投递 / §4 预算+声明式截断）：**

1. **「投影完整」要在模型实际读到的那一份上验，不是在生成它的那一份上验。**
   spec 层 64 条 ✓、prompt 边界砍到 18 条 = 机制只交付了约四分之一。同类形状：
   额度写进 telemetry 但下游没读。验法：拿生产 pack 重建 registry block 数行数。
2. **偶然的 fail-closed 会掩盖真正的 fail-open。** judge 因 URLError 从没跑起来时，
   残差一律回纯包，看起来很安全；transport 一修好，`resolve_judge_sentence_indexes`
   吞掉半个驳回立刻变成「judge 点名越界的句子照样出稿」。修好一个坏掉的组件之前，
   先想清楚它坏着的时候是谁在替它兜底、那个兜底是不是设计出来的。
3. **验收句要钉在用户看见的那一层。** 「残差上场」是管线状态；母稿 R5 锁的是公开稿
   尾段。包标签（`【集采中选】` / `## 反证`）是 P0 渲染，不是 P1 解读。
