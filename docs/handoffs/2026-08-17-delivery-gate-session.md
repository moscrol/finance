# 交接（会话快照）：交付门禁这一轮——做了什么、为什么、否掉了什么

- 日期：2026-08-17
- 树：`/Users/a77/fwp-wt-delivery-gate`
- 起点：复核 PR #144（当时 open），终点：#144 已合 + 两个新 PR 待批
- 相关 spec：`2026-08-17-delivery-gate-soften-design.md`、`2026-08-17-claim-tiering-and-revision-design.md`

## 0. 一段话背景（不读这段会误判后面每一个决定）

#144 的动机是对的：**旧规矩把「格式不合规」和「内容造假」判同一个刑**——都整答退稿。
模型写了一篇内容没问题的答案，只因没按格式标注引用就整篇被扔，用户拿到模板。
#144 把 6 个绑定类码 + 2 个术语泄漏码从 `error` 降成 `warning`。

**方向对，但降级只做了一半**：降 severity 会把决定权移交给下游，而下游没人接。
本轮补的三件事全部源于这一句。

## 1. 做了什么（按发现顺序，不是按重要性）

### 1.1 展示层抠空能发空白答卷（已随 #144 合入 `96446a93`）

绑定/术语降为 warning 后，退稿的决定权实际交给了展示层——它丢无效 claim ID 行、
丢含内部术语的行。**实测**两种输入被抠成空串：marker 的 claim ID 全无效；单段散文
里出现一个内部词。改前这两种是 `error` → 退稿 → 落确定性答卷；改后 blocking 为空，
空串直接写进 `result.synthesis` 并标 `accepted/validated`。

补了下限守卫（`ask_synthesis` 旧链主路 + `ask.py` WARN 回灌两处），并新增
`presented_lines_dropped` 遥测让「抠掉几行」可读。

> **为什么这算 bug 而不是「更宽容」**：原来的失败模式有确定性兜底，新的失败模式
> 是**盖着 validated 章的空白**。宽容的反面不是严格，是**静默**。

### 1.2 账实错误：`llm_added_number` 这个闸不存在（PR #145）

#144 的 spec 与交接页都写着「`llm_added_number` 仍是 error 的 fail-closed」，并据此
论证「只放松形式闸、事实闸还兜着」。`ast` 逐个数下来：该 code 最后出现在 `c516c62c`
（07-12），被 `53754507`「refactor workbench research contracts」（07-15）删掉，
**#144 落笔时已消失一个多月**。

真实闸况：

| 出口 | 事实闸（编数字/日期/公司、升格成事实） | 形式闸 |
|---|---|---|
| `validate_grounded_composer_answer`（**生产默认**） | 7 条，全 `error` | 全 `error` |
| `validate_llm_answer`（旧链 fallback） | **一条也没有** | 7 条本次全降 warning |

所以那句论证**在旧合成链上是假的**。

### 1.3 修订轮失联 + 一条内容闸被误归类（PR #146）

- `claim_binding_revision`（把问题喂回模型改一轮）触发条件是「有 error」。降级后恒不
  触发 → 从「退稿前先让模型改一次」退化成「不扔也不改，带病放行」。**中间那档被顺手
  关掉了，没人发现。**
- `llm_fact_only_superseded_evidence`（事实只绑了已被取代/已证伪的证据）**不是形式
  问题**，被 #144 归进「claim 绑定」一起降了。

### 1.4 修订轮不带草稿（PR #146）

修订 prompt 写着「保留原有自然措辞，只修复门禁指出的绑定」，而发过去的 messages 是
最初的 system+证据，**不含上一版**。让模型修一份它看不见的稿子。同仓 `ask.py` 那条
WARN 回灌走 `synthesis_messages`（含 assistant 草稿），做对了——两条修订路本该同形。

### 1.5 根因：这条链的 claim 契约从没下达过（PR #146）

带上草稿后第二发 live 仍未改好，继续挖：旧链 `_SYNTHESIS_SYSTEM_PROMPT`（388 字）
只说「事实句必须绑定合法 EvidenceAtom」「claim marker 只用于机器核验」，
但**全文 `claim_id` 0 次、`<!--` 0 次**，`build_synthesis_messages` 也不注入 registry。
**模型拿不到 marker 语法和合法 ID，不可能合规**——#144 那发它写出的 9 处短式
`claim_id=` 是在猜语法。对照 Grounded 那条自洽（prompt 明写 `claim_ids=` 复数，
正则也认复数）；旧链正则要单数 `claim_id=`，**那条方言没有任何 prompt 教过**。

## 2. 决策与被否方案

### 2.1 绑定闸怎么处置

| 方案 | 评价 | 结果 |
|---|---|---|
| A. 维持现状（继续报 warning） | 每答必报、把修订轮拖起来空跑 30.2s、两发 live 都未采纳 | 否 |
| B. 把 prompt 补全（教语法 + 注入 registry） | 治本，但旧链是 **fallback 路**（生产默认走 Grounded），为一条降级路补一套 claim 契约投入产出不划算 | **押后**，用户拍板 |
| C. 直接删掉这道闸 | 便宜，但删了**再也回不来**；哪天补了 prompt 也没人记得把闸加回去 | 否 |
| **D. 契约没下达就不问罪** | 判据从 prompt 自身算：prompt 开始教语法，闸自己回来 | **选中** |

用户在 B/C 之间选了「先做便宜那半」，我把 C 改良成 D 再执行——**同样便宜，但可逆**。

### 2.2 判据放哪层（这里错过一次）

第一版把判据做成 `answer_model` 里的全局标志。目标测试 4 个文件全绿，
**全量测试抓出两个误伤**：市场复盘散文契约（`test_p0_hardening`）和 followup 合并
（`test_workbench_research_owner_skills`）都**故意钉着这条码当观测信号**。

一个判据替三个消费方做决定——正是本轮刚诊断过的形状。收窄后：
`validate_llm_answer` **照报**（文本里确实没 marker，是事实，不粉饰）；
**「要不要拿它问罪」移到 `ask_synthesis`**，只有调用方知道自己是哪个契约。

### 2.3 已取代证据怎么处置

| 方案 | 评价 | 结果 |
|---|---|---|
| A. 维持 warning 不动 | 用户读到的仍是一句语气笃定的结论，警告只有工程师看得见 | 否 |
| B. 提回 `error` 整答退稿 | 改动最小，但退回了「一刀切刑罚」 | 否 |
| **C. 降桶标注** | 不退稿，但在**正文**标「（待核验：所据证据已被取代或证伪）」 | **选中** |

依据 knevo（`agent-memory/10_knowledge/knevo-reverse-engineering.md` §3.2）三桶分层：
结论桶 / 线索桶（「下一轮检索的燃料」）/ 丢弃桶，配「缺数据标 gap 而不是编造」。
**降级要让读答案的人看见才算降级。** 只借形状不借数字——knevo 文档自己列了
「不应直接复制的部分」（confidence 阈值、排序权重）。

### 2.4 修订轮采纳门槛

否掉「无 error 即采纳」这个原有规则在 warning 场景的直接沿用：`error` 触发时初稿
反正要退，不变差就值得换；**`warning` 触发时初稿本来能发**，必须绑定问题数**严格
减少**才配顶掉它。否则一次没改动的重写会白白替换掉能发的稿子。

## 3. 一个贯穿全场的判断（回答「形式闸有没有必要」）

**在 Grounded 那条上：必要，而且形式闸是事实闸的输入。** `grounded_composer_added_number`
的算法是「取这句话**自己绑定的**证据原子 → 抽出其中数字 → 不在集合里就是编的」
（`allowed_text` ← `bound_atoms`）。去掉绑定，比对集合为空 → **每个数字都判越界**，
不是放行而是全量误报。

**在旧链上：不必要，但理由不是「管得宽」，是它罚的契约从没下达过。**

同一个词在两条链上不是一回事。**别把这两条结论互相套用。**

## 4. 验证与收据

- 全量 `intelligence/tests` **4771 passed / 12 skipped / 0 failed**（clean tree `3cbdc245`）
- 七条守卫逐条变异证伪，**正反成对**（抽掉守卫红 / 写成无条件生效也红）
- 三发 live：`~/.finance-runtime/claim-tiering-20260817/`，跑法见同目录 `run_live.py`
  （环境从 `start-finance-workbench` 只取 export，代码由 cwd + PYTHONPATH 指向被测树；
  **验的是实际加载的文件路径，不是 PYTHONPATH**）

| 发 | trigger | 采纳 | 修订耗时 | 绑定类警告 |
|---|---|---|---|---|
| `live-retrieval` | `warning` | 否 | 30180ms | 1 条 |
| `live-retrieval-with-draft` | `warning` | 否 | 30.2s 级 | 1 条 |
| `live-contract-scoped`（最终） | **`null`** | — | **无该调用** | **0 条** |

**不读快慢**：三发总耗时 204.9 / 267.8 / 218.4s，被检索方差主导，n=1 读不出延迟结论。
能断言的只有结构性事实：那次修订调用没有发生。

## 5. 后续要做的

| # | 事 | 备注 |
|---|---|---|
| 1 | 批 #145、#146 | 都 open/mergeable，未合 |
| 2 | 造一发带 superseded 证据的题验降桶标注 | 三发 live 都没出结构化 claim，该路径**只有单测覆盖** |
| 3 | 决定旧链要不要真走 claim 契约（§2.1 方案 B） | 做了的话闸会自己回来，然后重跑 live 看绑定率 |
| 4 | 看 `claim_binding_issues_before/after` 台账再决定要不要给修订轮加开关 | 现在就定阈值是拍脑袋 |
| 5 | T-F：Handle + §9.2 失败注入 | 读数页已推（`docs/tf-subset-attach-readings` `40f4c517`，含一条更正） |

**不要做的**：不要开 900、不要切 8792；不要把 Grounded 那条的
`grounded_composer_added_number` / `_added_date` / `_added_company` / `_promoted_to_fact`
改成 warning（见 §3）；不要把 `llm_fact_only_superseded_evidence` 塞进
`_BINDING_ISSUE_CODES`（证据本身已被取代，重绑修不好，只会逼模型攀附别的证据）；
不要在没有 live 收据的情况下写「修订轮有效」。

## 6. 这一轮踩的坑（可迁移的已进 `10_knowledge/` 候选）

1. **变异测试前没先提交实现**——`git checkout --` 把实现连同变异一起还原了，重做一遍。
2. **目标测试全绿 ≠ 没坏**：4 个文件绿的时候全量是红的，误伤在没想到的消费方。
3. **`--timeout` 这仓没装插件**，且管道到 `tail` 会把 pytest 退出码吞成 0——第一次
   「全量 exit 0」是假的，测试根本没跑起来。
4. **降 severity 会顺手关掉修复路径**：有人把 `error` 当开关用（`if blocking_issues`），
   改 severity 时要一并 grep 谁在这么用。
5. **门禁和 prompt 是同一份契约的两半**，只改一半就是在罚一个没下达的要求，这时调
   severity（松或紧）全是空转。
