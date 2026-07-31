# Session handoff — 暴露取舍治理落地 + 密封夹具的不可重建风险（2026-08-01）

**先读** `docs/handoffs/2026-07-31-harness-goal-and-references.md`（Start Here，总入口）。
这份只记本段发生的事、留下的风险和验收口径。上一段是
`docs/handoffs/2026-07-31b-cutover-and-controller-observability.md`。

---

## 1. 最终目标（本项目所有 harness 改动的第一原则）

来自用户判断，原文在 Start Here §1：

> **把通用 harness 补齐到「不拖领域 harness 后腿」，领域 harness 保持严格。**

拆成两句可判定的：

- **通用层（宽容）**——标题措辞、句子编号、解析格式、重试、路由、**截断与取舍**。
  它无法知道内容对不对，只能保证「格式合法、不夹带未绑定的断言」。这一层拦错了是纯损失。
- **领域层（严格）**——数字/公司/日期有没有出处、必需输出有没有覆盖、证据够不够硬。
  这一层是产品价值所在，**一条都不能为了绿灯而放宽**。

归层判据：问「这条规则需要理解 A 股才能写吗？」需要就是领域层。

**不做什么**（别再重新论证，已有实据）：不为了过门禁而放宽门禁；不迁 Agent SDK /
Managed Agents。

### 本段做的事落在哪一层

暴露取舍（谁进正文）是**通用层**：它不判断某家公司对不对，只决定「候选装不下配额时留谁」。
所以本段的改动方向是「补齐能力 + 说清口径」，不是收紧判据——符合第一原则。

---

## 2. 当前状态

```
线上 8792     751ef706（已切，healthy）
              属主 launchd com.a77.finance-workbench（KeepAlive）
指针          /Users/a77/finance-workspace-runtime → finance-workspace-751ef706
本地分支      fix/exposure-ranking-truncation @ 751ef706（工作区干净）
工作 clone    /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
              ⚠️ 独立 clone、没有 origin；推送要经数据仓
GitHub        origin/fix/exposure-ranking-truncation = 751ef706（已推，635 commits）
              origin/main 仍 = 0430d544，一动没动
测试基线      仓根全量 3896 passed / 11 failed / 3 skipped；ruff 165
              11 条失败是既有环境依赖（test_subconscious、test_userspace 解析
              /Users/a77/agent-memory 路径），与代码改动无关，历次一致
```

**回滚**（旧快照都在）：

```bash
# 退到只有确定性排序、无选择器的版本
ln -sfn /Users/a77/.finance-runtime/finance-workspace-2634d6efa8c7e3a9183b3c4993152c1a1ee3fbaa \
        /Users/a77/finance-workspace-runtime
launchctl kickstart -k "gui/$(id -u)/com.a77.finance-workbench"

# 退到本轮之前（无任何暴露取舍改动）
#   → finance-workspace-610feb213b29cb40e40f1690b3e1918014647b56
```

**不重启的软回滚**：`ASK_EXPOSURE_SELECTOR=off` 只关掉模型选择器，保留确定性排序
和截断留证。但它要写进启动脚本 `/Users/a77/.local/bin/start-finance-workbench` 再
kickstart 才生效。

---

## 3. 本段做完的（3 个 commit，全部已上线）

起因：用工作台跑「固态电池产业链现在走到哪一步了，谁最受益」，答案里「产业链映射」
列了 12 家，严格按字序到「中」为止。查下去是图谱 86 家候选**分数完全并列（都是 20）**，
排序键 `(-score, company)` 的 tiebreaker 落到公司名——**决定谁进正文的是中文字典序**。
core 的先导智能/当升科技/赣锋锂业、high 置信的宁德时代全被挤到配额外，留下的却有
strength 空着的行。而且这一刀是**静默**的：正文写「另有 3 家仅有概念关联、9 家仅有
间接证据」，3+9=12，读者会把 12 当成全集。

| commit | 内容 |
|---|---|
| `2634d6ef` | 排序键加入 strength/confidence；`get_exposure_matches` 返回 `total_matched`/`truncated`，截断进 warnings；落成 gap line + `AskResult.graph_exposure_telemetry` + trace 的 `graph_exposure` |
| `4404db41` | `exposure_selector` 按问题意图挑，失败 fail-closed 回退确定性排序 |
| `751ef706` | 留证文案按实际路径分叉（选择器跑通了还说「按名称排序」＝留证说假话） |

> ⚠️ **命名冲突提醒**：`4404db41` 的 commit 消息里写的「待办 C」指的是**本段临时
> 编号**（当时给了 A0/A/B/C 三个修法选项，C = 让模型选）。它**不是** Start Here §4
> 的待办 C（那个是 stall 阈值，仍未做）。commit 已推，改不了消息，在此挑明。

### 关键实现点

- **排序键**（`intelligence/adapters/knowledge.py`）：`(-score, strength_rank,
  confidence_rank, company)`。标注缺失落 `_EXPOSURE_RANK_UNKNOWN=9` 排最后，
  不让「字典里查不到」白捡高位。公司名保留在末位但只作确定性兜底。
- **选择器**（`intelligence/services/exposure_selector.py`）：候选池 60 家，
  模型按问题意图挑 `top_companies` 家；选不满用确定性排序补齐并记 `backfilled`。
  开关 `ASK_EXPOSURE_SELECTOR=off`，模型可选 `ASK_EXPOSURE_SELECTOR_MODEL`。
- **接线**（`intelligence/services/evidence_providers.py`）：`focus_entities`
  永远置顶，选择器负责剩下的槽位，**截断统一挪到最后做**。

### 线上实测

```
graph_exposure : {"matched": 86, "shown": 12, "truncated": true,
                  "selector": {"mode":"llm","candidate_count":60,
                               "llm_selected":12,"backfilled":0,
                               "hallucinated":0,"elapsed_ms":1454}}
留证           : 「图谱共匹配 86 家公司，本轮由模型从 60 家候选中按问题意图挑出
                 12 家写入正文；其余 74 家未展示，不代表不存在」
LLM 调用       : 4 次 → 5 次（chat 1→2），正好 +1；总耗时 54.7s → 27.1s
degrade_count  : 1（与切换前持平）
```

离线在真实图谱上（打桩模型）验证：确定性前 12 全是名字靠前的 core，选择后
宁德时代/赣锋锂业/当升科技进前三，其余 7 槽由确定性补齐。

### 刻意没做的

- **没有把留证塞进 LLM 合成的 `answer.md`。** 留证进了 `分歧反证` 模块和 trace，
  但 composer 是否引用由它自己决定。要强制进正文有现成先例可循
  （`ask_synthesis.py:1814` 的 `ensure_chain_mapping_section`：composer 不写就
  确定性补上）。属改行为，留给你定。
- **没有动 `top_companies=12` 这个配额。** 十原则 9.5「上下文是工作记忆，优化目标
  是可治理不是更多」——把 limit 调大是「更多」不是「可治理」。

---

## 4. 本段的两个决定（已执行）

### ① GitHub：推成分支，没动 main

摸下来和上一份 handoff 记的不一样：**本地线比 GitHub 领先 635 个 commit**（不是 26），
数据仓 main 只领先 6 个（夜跑调度/market-deviation 运维类），分叉点都是 `0430d544`。

推之前扫过这 635 个 commit 的红线文件：唯一命中的两个是**读**钥匙串的源码
（`keychain_credentials.py`），无明文密钥、无 `.env`/`.duckdb`/PDF/config。

选「推分支」的理由：真正不可逆的风险是「635 个 commit 只存在于这台机器的一个
`tmp/` 子目录」，推分支完全解决；快进 main 会把数据仓 main 变 diverged（它压着
137 个未提交改动），**花代价买一个当前没有消费者的东西**——运行时是从
`.finance-runtime` 快照部署的，不经 GitHub。

**主分支并法仍未决**，但没有任何东西依赖它。

### ② `.finance-runtime`：27G → 17G

- 删了 103 个 `continuous-canary` 快照（7-24 的，8 天前），其中 58 个走
  `git worktree remove`；剩 45 个不是工作树而是运行结果目录（共 51M），留着。
- 顺手 `git worktree prune` 掉 2 条失效注册项。注册数 132 → 73。
- `app-server-ceiling` 17G → 11G：删了 4 个无引用的构建尝试（见 §5）。

---

## 5. ⚠️ 新增风险：密封夹具不可精确重建（本段发现，未解决）

清理时查明 `.finance-runtime/app-server-ceiling` 的性质，顺带发现一个**阻塞在途实验**
的问题。这条是本段最重要的遗留。

### 它是什么

**App Server Ceiling 基准实验**的密封夹具。要比较 headless 跑法和 App Server 跑法
哪个天花板高，必须保证两边吃到完全一样的输入，否则差异说明不了问题。所以把
2026-07-24 冻成时点(PIT)快照：每个 component = `finance.duckdb` 590M +
`wiki` 576M + Hybrid `index` 394M + 指令导出，哈希密封，再配一份独立的
语义泄漏评审回执才算数。

设计与进度文档：
- `docs/superpowers/plans/2026-07-29-app-server-ceiling-sealed-fixture.md`
- `docs/superpowers/specs/2026-07-29-codex-app-server-ceiling-benchmark-design-v3.md`
- `docs/handoffs/2026-07-29-sealed-fixture-task-2-wip-handoff.md` ← **状态在这**

**状态：做了一半，停在 7-29。** WIP handoff 里还有 9 步（"Exact continuation order"），
当前闸门是红的——泄漏检测把「A股」「周度」这类通用词判成泄漏，等一个分类感知的规则。
**这是暂停的在途工作，不是做完的旧实验。**

### 风险：只能重建一半

| 组成 | 能否重建 | 依据 |
|---|---|---|
| finance DuckDB 的 PIT 部分 | **能** | 主库 append-only，2026-07-24 及之前数据完好（`fact_stock_daily` 194 万行、`fact_sector_daily` 9.5 万行、`fact_market_daily` 385 行）|
| Wiki cutoff 导出 + Hybrid 索引 | **不能** | WIP handoff 第 5 步钉死用 KB 代码版本 `9053b0c4`，而该 commit 在 `knowledge-base-private` 和 `finance-workspace-private` **都不存在**（`git cat-file -t 9053b0c4` → unknown revision）|

**后果**：当前密封的 `b0edcbcc07b05ac0` 一旦丢失，实验没法在原口径上继续；
换 KB 版本重新密封的话，**之前跑出来的对照结果全部不可比**。

### 建议的处置（未做，需要你定）

1. **先查 `9053b0c4` 到底是什么。** 可能是：(a) 未推送的本地 commit，被 gc 或
   分支删除回收了；(b) 别的仓的 revision；(c) 记录时写错。
   查法：`git -C /Users/a77/knowledge-base-private reflog --all | grep 9053b0c4`、
   翻 `.git/lost-found`、或在 WIP handoff / spec 里找它第一次出现的上下文。
2. **查不到就在 WIP handoff 里显式降级这条前置**：改成「以现存密封夹具为准，
   不再声称可从 KB 版本重建」，并把 `b0edcbcc07b05ac0` 标成**不可再生资产**
   （现在它只是只读，没有任何文档说它不可重建）。
3. **考虑给它做一份异地备份。** 1.5G，是整个实验唯一的活密封态。

### 当前 component 清单（清理后）

`.finance-runtime/app-server-ceiling/2026-07-24/`：

| component | 状态 | 处置 |
|---|---|---|
| `b0edcbcc07b05ac0` | **当前密封态**（`sealed-fixture.json` 指向），有评审回执 | 保留 |
| `9b5538e19229ee1d` | 曾密封，被 `superseded-da3f7753` 取代，有回执 | 保留 |
| `d202e62c50304a9b` | 曾密封，被 `superseded-3dca8b1a` 取代 | 保留 |
| `de23b0dd754d626c` | 有回执，无密封指向 | 保留 |
| ~~`8753653155f330a7`~~ ~~`a422c3079b062c2c`~~ ~~`a91f9254285d18d4`~~ ~~`ebc7cf44c12f865a`~~ | 无任何引用的构建尝试 | **已删（6G）** |

外层 `2026-07-24-{01e3d36a,545ed904,a2d22cec}/` 三个目录（各 1.5G）全部保留。
注意 `a91f9254285d18d4` 在 `2026-07-24/` 和 `2026-07-24-a2d22cec/` 各有一份**独立
inode**（不是硬链接），删的是前者，后者被 a2d22cec 自己的 `sealed-fixture.json`
指向，必须留。

删除后已复核：每个 `sealed-fixture.json` 指向的 component 都还在（5/5 ✓）。

**⚠️ 动这个目录的两个坑**（本段实测）：
1. 密封夹具是 `dr-xr-xr-x` + `-r--r--r--`，**文件系统级只读**。`rm -rf` 会删掉
   可写部分后停在只读子树上（1.5G→970M 的半截状态），要先 `chmod -R u+w`。
2. `for t in $VAR` 在 zsh 里**不做词分割**，只迭代一次。第一次删除因此是空操作，
   靠核对「8 个 component 还在、体积没变」才发现——只看 `rm` 退出码会以为成功了。

---

## 6. 待办（延续 Start Here §4，按性价比排序）

### 新增

**H. `9053b0c4` 不可重建** —— 见 §5，最高优先级，它阻塞的是一个已投入很多的在途实验。

**I. 选择器的分辨率验证** —— C 已上线但只跑过一个问题。要看的是：
换成「谁在扩产」「谁受益于降价」这类**不同意图**的问题，选出的 12 家会不会真的不同。
如果都一样，说明模型没在用意图、只是复述了标注顺序，那 C 的价值就没兑现。
判据在 trace 的 `graph_exposure.selector`：比较不同问题下的 `llm_selected` 名单。

**J. 留证进合成正文** —— 见 §3「刻意没做的」。

### 延续（原文见 Start Here §4）

- **G. synthesize 报降级却说不出原因**——和已完成的 A 同一形状。
  `status = "validated" if result.synthesis is not None else "fallback"`
  （`conversation_orchestrator.py:2637`）只说「是 None」，不说为什么。
  先查 `result.prepared_synthesis_messages` 为空时是不是整段被跳过——
  跳过和失败是两回事，现在共用一个 `None`。
  > 本段新数据点：走 `theme-research` owner 时 `status=validated`，走 generic owner
  > 时 `fallback`。**fallback 和 owner 路径相关**，定位 G 时从这里切。
- **B. 剩下 7 个工具的行为契约**——等实测依据，**没依据宁可留空**。
- **C. stall 阈值**——阻塞在跑量。`ch06b` 的 30s **不要照抄**（见上方命名冲突提醒，
  这个 C 才是 Start Here 的 C）。
- **E. 工具并发分区**——可延后，前置是 `ToolSpec` 补执行语义字段。
- **F. 运维**——蓝绿切换 ✅；GitHub 分支已推、main 并法未决；`.finance-runtime`
  已清到 17G，还想再清只剩 §5 那 11G（属审计证据，需你定）。

---

## 7. 怎么验收

### 7.1 验收本段改动是否还在生效（任何时候可跑，不烧配额）

```bash
cd /Users/a77/finance-workspace-runtime
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki \
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "
from intelligence.adapters.knowledge import KnowledgeAdapter
r = KnowledgeAdapter().get_exposure_matches('固态电池')
assert r['total_matched'] > len(r['items']), '截断没被识别'
assert r['truncated'] and r['warnings'], '截断没留证'
assert all(i['strength']=='core' for i in r['items']), '排序键没生效'
print('OK', r['total_matched'], '→', len(r['items']), '|', r['warnings'][0])
"
```

期望：`OK 86 → 12 | 图谱共 86 家匹配，本轮按暴露强度取前 12 家；未展示的不代表不存在`

### 7.2 验收一次真实问答（烧 1 次 LLM 配额）

```bash
cd /Users/a77/finance-workspace-runtime
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/smoke_workbench_self_use.py --base-url http://127.0.0.1:8792 \
  --user default --question "<你的问题>" --timeout 420 --output /tmp/v.json
```

然后在 `~/.local/share/finance-workbench/users/default/runs/<run_id>/` 里查三处：

| 查什么 | 在哪 | 合格标准 |
|---|---|---|
| 截断被识别 | `trace.jsonl` 的 `graph_exposure` | `matched > shown` 时 `truncated=true` |
| 取舍口径被记录 | 同上的 `.selector` | `mode=llm` 且 `hallucinated=0`；回退时 `reason` 非空 |
| 留证送到用户 | `report.json` 的 `分歧反证` 模块 | 有「图谱共匹配 N 家」且**口径与 `.selector.mode` 一致** |
| 成本没超预期 | `trace.jsonl` 的 `llm_call_ledger` | 相对无选择器版本只 +1 次 |

**口径一致**这条是 `751ef706` 专门修的：`mode=llm` 就必须说「按问题意图」，
不得出现「按名称排序」。留证说假话比不留证更糟。

### 7.3 回归基线

```bash
cd <工作 clone>
.venv-workbench/bin/python -m pytest -q        # 期望 3896 passed / 11 failed / 3 skipped
.venv-workbench/bin/python -m ruff check .     # 期望 165
```

11 条失败必须是 `test_subconscious.py` + `test_userspace.py` 那一批**同名同数**；
出现别的名字就是真回归。

### 7.4 验收方法论（本项目反复被验证，别省）

1. **测试要先证明自己能抓 bug。** 写完测试先把修复摘掉（`git stash push -- <file>`
   或临时突变），确认变红再装回去。本段 4 次突变验证：摘 LLM 路径红 6 条、摘候选集
   校验红 1 条、摘补齐红 1 条、断开接线红 1 条。
2. **只测组件不测送达 = 没测。** 本段两次踩到：只钉 adapter 不钉 gap line、
   只钉选择器不钉接线。第二次接线测试直接红了，抓出「以为 `focus_entities` 非空就
   该跳过选择器」这个错误假设——实际那 4 家是 planner 推的、只占 12 槽里的 4 个。
3. **「核实」要拿实据，不是拍脑袋说风险低。** canary 的 `degrade_count` 从 2 涨到
   6 时，先怀疑自己的代码 → 冷启假说 → 暖机重跑仍是 7（假说被自己的数据推翻）→
   查 env 才找到真因。
4. **判断某个 degraded 是不是自己引入的：跑 A/B。** 同问题、同 env，分别打改动
   前后两个快照的旁路 server，比 `trace.jsonl` 里 `synthesize` 那步的
   `output_summary`。

---

## 8. 参考资料库：七份信息源

**全部冷存在本地，无需联网。** 根目录 `/Users/a77/agent-memory/10_knowledge/`。
总索引也在 agent 记忆 `harness-reference-library`；完整版在 Start Here §5。

### 清单与地址

| # | 来源 | 落盘位置 | 体量 |
|---|---|---|---|
| ① | **马书**《驾驭工程：从 Claude Code 到 AI Coding》 | `_sources/harness-engineering/chapters/`（**全 36 章**）+ `mashu-ch25-six-principles.md`、`mashu-toc-and-preface.md` | 1.3M |
| ② | **harness-books**（十原则） | `_sources/harness-engineering/harness-books-ch9-ten-principles.md`、`harness-books-readme-and-toc.md` | — |
| ③ | **Claude Code / Agent SDK 官方文档** | `_sources/claude-code-docs/`：`loop.md` `permissions.md` `hooks.md` `sdk.md` `overview.md` | 92K |
| ④ | **官方 Prompt Engineering** | `_sources/prompt-engineering/claude-prompting-best-practices.md`（59K）、`overview.md` | 64K |
| ⑤ | mal_shaik 源码解读 9 条 | `_sources/claude-code-source-reads/mal_shaik-9-takeaways.md` | — |
| ⑥ | 陈成：sourcemap 泄露始末 | `_sources/claude-code-source-reads/chencheng-sourcemap-leak.md` | 28K |
| ⑦ | YukerX 源码走读（**全文**，用户粘贴提供） | `_sources/claude-code-source-reads/yuker-source-walkthrough.md` | — |

自己整理的两份手册（读这两份比读原文快）：
`claude-code-architecture-manual.md`、`harness-engineering-principles.md`。

### 怎么参照：按问题查，不要通读

**碰到难点先检索这里看有没有现成解法，再自己想。** 这是用户明确要求的工作方式。

| 你在解决的问题 | 去看 |
|---|---|
| 重试 / 降级 / 超时 / 流卡住 | ①`ch06b.md` **全章**，最实用的一章 |
| 门禁太硬、一个错误作废整份产出 | ①`ch04.md`（三分层错误级联）、`ch27.md`（渐进式自主）|
| 权限 / 拒绝该怎么回灌 | ③`permissions.md`、①`ch16.md` `ch17.md` |
| 上下文预算 / 大结果 / **截断** | ①`ch12.md`、`ch10.md`、**`ch28.md` 不足四** |
| 提示词措辞怎么写才被遵守 | ①`ch06.md`、`ch08.md`（工具提示词=行为契约）|
| 长上下文 / 输入顺序 | ④`claude-prompting-best-practices.md` → `### Long context prompting` |
| 压缩 / 长会话 | ①`ch09.md`、`ch10.md` |
| **候选池超配额、要挑哪几个** | ①`ch24.md`（模式四：预算约束注入）、⑦（**小模型选，≤5 条，精确度优先于召回率**）|
| 多 agent / 子代理 | ①`ch20.md` `ch20b.md` `ch20c.md`、⑦（反递归提示词）|
| 缓存 / 成本 | ①`ch13.md` `ch14.md` `ch15.md`、`ch05.md` |
| **这套设计在哪失败** | ①`ch28.md` —— **动手前先读它对应的那一节** |
| 想把模式搬到自己的 agent | ①`ch30.md`（六层框架）|

### 检索命令

```bash
K=/Users/a77/agent-memory/10_knowledge/_sources/harness-engineering/chapters

grep -ln "熔断\|circuit" $K/*.md                    # 1. 按关键词定位在哪一章
grep -E "^#{2,3} \[" $K/ch06b.md | sed 's/\](.*//; s/^#* \[//'   # 2. 看骨架

# 3. 读正文但压掉长代码块（一章 40K 字符大半是 TS 源码）
cat > /tmp/cond.awk <<'AWK'
/^```/ { infence = !infence; if (infence) { n=0 }; print; next }
infence { n++; if (n<=8) print; else if (n==9) print "    …（代码略）"; next }
{ print }
AWK
awk -f /tmp/cond.awk $K/ch06b.md | grep -v "^$" | sed 's|(http[^)]*)||g'
```

> ⚠️ 章节页标题带 markdown 链接（`## [4.8 模式提炼](…)`），按 `^## 模式提炼`
> 精确匹配会**静默匹配不到**。先 `grep -n "模式提炼"` 看实际长什么样。

### 五条纪律（血的教训，用之前先读）

1. **⑤⑥⑦ 和马书是同一份泄露源码（v2.1.88）被读了两遍**，不是独立信源。
   两者一致 **≠** 交叉验证。
2. **二手与官方冲突时以官方为准。** 已发现一处：mal_shaik 说「5 个 subagent ≈
   1 个成本」，官方 prompt-caching 文档明确写「N 个前缀相同的并行请求全部全价」。
3. **常量不要照抄，先算我们自己的量纲。** 已踩两次：ch06b 的 stall 阈值 30s
   vs 我们单 phase 预算 31–45 秒（抄了永不触发）；10 次重试预算（CLI 场景）
   vs 我们 5 小时滚动配额（只抄退避不抄次数）。
4. **同名不同题，别照抄结论。** ch06b 的 `shouldRetry` 问「该不该重试」，
   我们的门禁问「被审对象是不是无辜的」——同一个 401，相反的答案。
5. **引用前确认那一页是否真读过。** 每份笔记都标了精读范围。

### 本段的实际参照记录（「资料给形状，量纲自己算」第五、六例）

动手前按纪律检索了全库，结论如实记录：

| 命中 | 给了什么 | 我们改了什么 |
|---|---|---|
| ①`ch28.4`「截断告知不等于行动」 | 最接近的命名失败模式；三条改进建议（结构化预览/相关性提示/自动分页）| **同名不同题**：它的消费者是能回头读完整文件的**模型**，我们的是最终答案里的**人**，下游没有「再读一次」这个动作。所以光告知不够，必须同时把选择改对 |
| ①`ch24` 模式四「预算约束的记忆注入」 | 「截断时追加警告消息形成自修复闭环」+ 前置条件「截断后仍能提供有意义的信息」 | 直接适用，给了「必须加截断留证」的授权。我们原来两条都不满足 |
| ⑦ 记忆检索「小模型选 ≤5 条，精确度优先于召回率」 | 待办 C 的整个形状 | **三处量纲不同**：(a) CC 用 Haiku，本机只有 glm-5.2；(b) CC 每轮都选，我们只在截断真发生时选；(c) CC 宁缺毋滥，**我们不能缺**——12 个槽位是答案覆盖面，模型只选 3 家会让 `chain_mapping` 这个必需输出塌掉，所以选不满必须用确定性排序补齐 |
| ②十原则 9.5「优化目标是可治理不是更多」 | **反向命中** | 否掉了「把 limit 从 12 调大」这个懒办法 |

**没命中的**：全库检索 `同分|并列|tie-break|字典序|相关性排序` 只有一处无关命中
（ch30「权限模式按字母序排列」）。**七份信息源没有一份讨论「打分并列时用什么兜底」**
——这部分量纲完全自算。记下来是为了下次别再重复检索。

---

## 9. 环境提醒（每次动手前扫一眼）

1. **决定加载哪份代码的是进程 cwd，不是 PYTHONPATH。** `python -m uvicorn` 让
   `sys.path[0]=''` 排在 PYTHONPATH 前面，而数据根 `/Users/a77/finance-workspace-private`
   底下就有一个 `intelligence/` 包。
2. **cwd 在启动时解析符号链接** → 只切指针不重启完全无效。
3. **8792 属主是 launchd KeepAlive**，手工 `kill`+`nohup` 会被它抢走端口。
   重启用 `launchctl kickstart -k`。
4. **旁路 canary 起完必须验四件事**（`/api/health` 的 `source_revision` 报的是
   数据仓，判断不了代码版本）：

   ```bash
   grep -c "address already in use" <log>                  # ① 必须 0
   ps eww <pid> | tr ' ' '\n' | grep ^PYTHONPATH=           # ② 必须是你的快照
   lsof -a -p <pid> -d cwd -Fn | grep '^n' | sed 's/^n//'   # ③ 必须是你的快照 ← 真正决定的
   ps eww <pid> | tr ' ' '\n' | grep -cE '^(RAG_|KB_RAG)'   # ④ 必须 4，和 8792 一样
   ```

   第 ④ 条是本段新加的：`.env.workbench` 和 `/tmp/runtime-8792-env.txt` **都不含**
   RAG 四件套（只写在启动脚本里）。缺 `RAG_WORKER_ENABLED=1` 就没有常驻 worker，
   每次检索重载索引：**wiki latency 4.5s → 23s**，broad 超时、counter
   `budget_exhausted`，`degrade_count` 从 2 涨到 6~7。**症状跟代码回归一模一样，
   而前三条检查全绿。** 判据：`wiki_rag.latency_ms` 高一个数量级 + 告警全是
   「知识库检索：…」族，就先查 env 别查 diff。
5. **zsh 不对未加引号的变量做词分割**（`for t in $VAR` 只迭代一次），
   也**不对变量内容做 glob**（`du -sh $pat` 不展开通配符）。本段两处都踩到，
   一次让删除变成空操作，一次让分类统计全是 0。

---

## 10. 配额

LLM 是 **5 小时滚动上限**，约 15 次 canary 跑光。本段用掉 7 次
（1 次基线 + 3 次 canary 排障 + 1 次 A/B + 2 次上线验收）。

**能用离线复现台就别起 server**：直接调 `get_exposure_matches` 看排序、
打桩 `complete` 看选择器，都不烧配额（§7.1 就是这么写的）。
