# Session handoff — 验收台首跑基线 + 三轴架构 + 三刀修复（2026-08-01c）

**上一段**：`2026-08-01b-claude-session-continuation.md`（断线续聊）。
本段从「高频/长尾探针」起，一路做到 A 组验收基线跑通并修了三处真缺陷。

---

## 0. 一句话现状

**28 道验收题的 A 组（日常主力）第一次跑出基线：起点是 7/10 题根本没产出答案，
根因是一条路由正则；修完降级桩和假拒答归零、正常完成 4→7。但发现验收台自身有
LLM 波动，单次运行读不出细粒度结论——这是下一段的第一优先。**

---

## 1. ⚠️ 先看这个：787 行改动全部未提交

```
分支 fix/exposure-ranking-truncation @ 881efc3c（HEAD 没动）
11 files changed, 787 insertions(+), 24 deletions(-)  ← 全部 working tree
```

| 文件 | 改了什么 |
|---|---|
| `intelligence/services/query_understanding.py` | **路由修复**：带日期的盘面细分题进 daily-review |
| `intelligence/workbench_skills/daily_review.py` | **按问题选章节** `select_review_sections` |
| `intelligence/adapters/knowledge.py` | `evidence_coverage_index()` + 暴露返回 `evidence_coverage` |
| `intelligence/services/ask.py` | `_exposure_coverage_summary()` → trace |
| `intelligence/eval/acceptance_verdict.py` | **判官修复**：别名未命中判不可判 + 中文方向词符号 |
| `intelligence/eval/cases/acceptance_verdict_contracts.json` | A1 别名补 `较上一交易日` 等 |
| 4 个 `intelligence/tests/test_*.py` | 16 条新测试，全部做过突变验证 |
| `docs/verification/2026-08-01-*.md` ×3 | 探针 / 架构 / A 组基线（未跟踪）|
| `intelligence/eval/runs/*.json` ×4 | 四次真实运行的 trace（未跟踪）|

**没提交是因为用户没要求。续聊第一件事建议先 commit 保住这 787 行**——
它现在只存在于这台机器的一个 `tmp/` 工作树里。

回归基线（每一刀后都跑过）：**3911 passed / 12 failed / 3 skipped，ruff 165**。
12 条红是既有的（8 `test_subconscious` + 3 `test_userspace` 环境依赖 + 1 待办 K），
**同名同数**，零回归。

---

## 2. 运行时状态

| 角色 | 值 |
|---|---|
| 工作 clone | `/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17` |
| 线上 8792 | cwd = `.finance-runtime/finance-workspace-751ef706`（**旧快照，本段改动全部没上线**）|
| 旁路 canary 8793 | PID 81260，cwd = 工作 clone，启动脚本 `/tmp/start-canary-8793.sh`，日志 `/tmp/canary-8793.log` |
| runtime 软链 | → `finance-workspace-751ef706`（没动）|

**canary 还开着**，B/C 组要用。不用了就 `kill $(lsof -ti tcp:8793 -sTCP:LISTEN)`。
起 canary 的四条防坑检查（每次重启都跑过，全绿）见 §7。

> ⚠️ **改了 server 侧代码必须重启 canary**，Python 在 import 时装载。
> 本段第二次复跑就是忘了这条差点误判——`acceptance_verdict` 是 CLI 侧不用重启，
> `query_understanding` / `daily_review` 是 server 侧必须重启。

---

## 3. 本段已完成（可当已交付）

### 3.1 高频/长尾探针（`docs/verification/2026-08-01-frequency-longtail-probe.md`）

- `mention_frequency.json` **否决**：题材粒度无公司维度、只覆盖 2.6% 概念、
  **固态电池根本不在那 115 个题材里**。
  → 上一段 handoff 写的「没用它＝信息没送到」**要撤回**：送到也没用。
- `evidence_index` join **可行**：按 `(concept, company)` 命中 77/86（90%）。
  **跨概念总数不能用**（宁德时代 42 / 中材科技 39，是知名度代理不是相关性）。
- 落地为**只读 telemetry**（不进排序、不进正文）：`graph_exposure.evidence_coverage`
  的 shown/pool 中位数。实测 `pool_size=86, shown_median=2.0, pool_median=1.0`。
- 对照 knevo：它的检索是纯关键词，**根本没有「高频/长尾识别层」**，无差距可追。

### 3.2 三轴架构（`docs/verification/2026-08-01-three-harness-architecture.md`）

**答案价值 = 送达率 × 信息量 × 可信度**，三份 harness 是正交轴不是加法：

| 轴 | 供给方 | 单独强的下场 |
|---|---|---|
| 送达率 | 通用 harness（马书/十原则/CC 文档）| 稳但空 |
| 信息量 | knevo | 深但不敢用 |
| 可信度 | 我们自己 | 可信但没信息量 |

已有实测落在乘法两端：Q4（PQC）我们信息量 0、Q6（数据安全）knevo 可信度 0。
**信息量之前没有归层**——既不是通用层的格式合法性、也不是领域层的事实正确性，
这是架构补的第三格。

**重要前提纠正**：评测台**早就建好了**（`intelligence/eval/`，28 题、
`reference_agents=[codex,knevo]`、22/28 份 knevo 快照已冻结、freeze CLI、泄漏规则）。
任务不是建评测，是让它跑出基线。

### 3.3 A 组基线 + 三刀修复（`docs/verification/2026-08-01-a-tier-baseline.md`）

**首跑 0/10，7 题没产出可用答案**：5 题返回 232 字降级桩、2 题谎称日期在未来。
根因实测（不是读正则推断）：

```
_DATED_MARKET_REVIEW_RE 对 10 道真实问题 0 命中
（要求「日期+市场/盘面+总结/复盘/回顾/梳理/分析」，没人这么说话）
而 market_review_requested_date 对其中 8 道已正确解析出日期，
只是被 and 到那条 0 命中的正则后面 —— 白解析了。
```

**第六次「信息在系统里但没送到」，距离只有一个 `and`。**
A6 谎称「2026-07-23 是未来」时，`2026-07-23-daily-review.md` 就在磁盘上，
里面「立新能源」出现 4 次。

三刀：

| # | 修了什么 | 效果 |
|---|---|---|
| 10 | 路由：日期解析成功 + 盘面主题词即路由 | 降级桩 5→0、假拒答 2→0、正常完成 4→6 |
| 11 | 判官：别名未命中判**不可判**不判失败；中文方向词带符号（「缩减 17.27%」= -17.27）| 失败 10→7，摘掉 3 条假红 |
| 12 | daily-review 按问题意图选章节（投影丢了 92%，UI 共用不能动，走附加式）| 正常完成 6→**7**；A6 逐条列出完整梯队 |

**16 条新测试，每一条都做过突变验证**（共 12 次突变，各自打红对应那条）。

---

## 4. 🔴 断在哪里：验收台自身有波动（新会话第一优先）

A1 是泛问、**不选任何章节**，三次运行输入完全相同：

```
run 20260801T025854Z：缩量 ✅  反弹阶段 ✅   （1012 字）
run 20260801T034001Z：缩量 ❌  反弹阶段 ✅   （ 405 字）
run 20260801T035325Z：缩量 ❌  反弹阶段 ❌   （ 669 字）
```

**输入没变，两条断言全翻。** 结论：

- 只有**结构性大变化**可信（降级桩 5→0、正常完成 4→7）；
- **细粒度 A/B 不可信**——单次 10 题跑不出「这一刀有没有用」；
- 三轴架构的判据造出来了，**但信噪比不够**。

**在解决它之前不要跑 B/C 组**：跑出来的数读不出结论，纯烧配额。

三条候选修法（**先算量纲再动手**）：

- (a) 每题重复 n≥3 取多数 —— 28 题 ×3 = **84 次调用，远超 5 小时滚动上限（约 15 次）**；
      可能只对高价值子集做。
- (b) 看板显式标注「单次运行不可用于细粒度比较」—— 最便宜，但不解决问题。
- (c) `must_mention` 这类**措辞**断言改语义判定 —— 波动主要出在措辞层
      （「缩量」这个词写不写），事实数字层反而稳。**看起来性价比最高，先验证这个假设。**

---

## 5. 待办总表

| ID | 内容 | 状态 | 谁定 |
|---|---|---|---|
| 10/11/12 | 路由 / 判官 / 选章节 | ✅ 本段完成 | — |
| **14** | **验收台波动，单次跑不出结论** | 🔴 **断线处，先做** | agent |
| 13 | A8 题目不可复现（相对时间题 + 冻结期望值）| 待做，便宜 | agent |
| 3 | 看板拆三轴三列（可信度/送达率机判，信息量用 knevo 快照做 few-shot 锚）| 待做 | agent |
| 5 | B 组 8 题基线 | **等 #14** | agent |
| 4 | C 组复跑（唯一实测 1/7 是 backend=sdk_gpt，今天是 glm-5.2）| **等 #14** | agent |
| 2 | knevo head-to-head | **等有真答案可比** | agent |
| 6 | 待办 I：选择器分辨率（现已可量化，用 evidence_coverage）| 待做 | agent |
| 7 | 待办 G：synthesize 说不出降级原因 | 待做 | agent |
| **8** | **待办 K：夜跑 sync 失败连带丢 L2** | 🔴 **阻塞 origin/main** | **用户定 a/b** |
| **9** | codex 快照 0/28（ChatGPT app sidecar 503/401，需重登）；knevo 缺 6 份；7-31 补数 | 🔴 | **用户** |
| J | 留证强制进正文 | 未做 | 用户 |
| B/C/E | 工具契约 / stall / 并发 | 延后 | — |

**A 组剩下 7 条失败的性质**（已分清，别再重新分类）：

| 题 | 性质 |
|---|---|
| A6 断层、A2 证伪 | 表达层——数据到位了，没下结论/没给证伪条件 |
| A7 芯片概念 66、A10 新高 339 | 真缺口——章节选了但数没取到（A10 锚定日是 07-21，别拿 07-23 的导出核对）|
| A8 | **题目缺陷**不是产品缺陷（任务 #13）|
| A1 缩量/反弹阶段 | **波动**（任务 #14），不是回归 |
| A3/A4/A5 不可判 | 判据表达力，`acceptance_verdict_contracts.json` 里已声明 |

---

## 6. 验收命令

```bash
W=/Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python

# 回归（期望 3911 passed / 12 failed / 3 skipped，ruff 165）
cd $W && $PY -m pytest -q && $PY -m ruff check .

# 看板（不烧配额，从已存 run 重新评估）
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki \
  $PY -m intelligence.eval.acceptance board

# 跑题（烧配额，每题约 30s）
$PY -m intelligence.eval.acceptance run --tier high_freq \
  --base http://127.0.0.1:8793 --user default

# 路由判据实测（免费）
$PY -c "
from intelligence.services.query_understanding import is_dated_market_review, understand_query
q='2026-07-23 哪些板块是双红'
print(is_dated_market_review(q, understand_query(q)))   # 期望 True
"

# 选章节实测（免费）
$PY -c "
import pathlib
from intelligence.workbench_skills.daily_review import select_review_sections
md=pathlib.Path('/Users/a77/finance-workspace-private/market_feature_store/exports/2026-07-23-daily-review.md').read_text()
s,w=select_review_sections(md,'连板梯队什么情况，有没有断层')
print([x['heading'] for x in s], '立新能源' in s[0]['body'])   # 期望 ['11. 3板及以上个股'] True
"
```

---

## 7. 起 canary 的四条防坑检查（每次重启都要跑）

```bash
PID=$(lsof -ti tcp:8793 -sTCP:LISTEN | head -1)
grep -c 'address already in use' /tmp/canary-8793.log      # ① 必须 0
ps eww $PID | tr ' ' '\n' | grep '^PYTHONPATH='            # ② 你的快照
lsof -a -p $PID -d cwd -Fn | grep '^n' | sed 's/^n//'      # ③ 你的快照 ← 真正决定的
ps eww $PID | tr ' ' '\n' | grep -cE '^(RAG_|KB_RAG)'      # ④ 必须 4
```

canary 启动脚本是从 `/Users/a77/.local/bin/start-finance-workbench` 用 sed 改写的
（换 cwd/PYTHONPATH/端口），**这样不用把 API key 打到终端里**。

---

## 8. 刻意不要做的

- **不要在 #14 解决前跑 B/C 组**——单次运行读不出结论，纯烧配额。
- **不要用单次运行的通过数论证小改动的好坏**（包括本段这三刀；已验证的只有
  「降级桩/假拒答归零、正常完成 4→7」这个量级）。
- **不要动 `daily_projection_modules`**——工作台 UI（`api/app.py:1014`）共用它。
- **不要为了绿灯放宽判据**。`-17.27` vs「缩减 17.27%」是同一事实的两种合法中文
  表达，修判官是对的；但 A4 的 `pct_chg=6.65` 答案里确实没有，那条不能动。
- **不要把跨概念覆盖度当质量信号**（知名度代理，见探针 §2.3）。
- **不要为凑满 28 份 knevo 快照花 3200 积分**——它的权威在框架层不在报数层，
  `reference_plan.not_the_oracle_for` 已列清哪些不该问它。
- **不要在 K 未定前 push origin/main。**
- 不要忘了改 server 侧代码后重启 canary。

---

## 9. 本段新增的两条经验（值得记住）

1. **「只测组件不测送达」这次是自己踩的。** 章节正文放进 `items[].content`，
   测试断言 `json.dumps(output.modules)` 含关键词 → 绿；而序列化器只读
   `items[].title/summary`，模型收到的只有标题。**断言点必须是模型真正看到的
   那份文本**（`answer_contract.answer_spec.verified_facts`），不是原始结构。
2. **防过度路由的保护性测试当场抓到了我引入的真回归。** 加盘面主题词后
   「2026-07-23 美股涨停情况怎么样」被判成 `general_finance_qa` 而非
   `external_market`，主题词把它放进了只有 A 股数据的 daily-review。
   **写正向测试的同时写反向守卫，值回票价。**

---

## 10. 元数据

| | |
|---|---|
| 会话日期 | 2026-08-01 |
| 配额消耗 | 30 次（3 轮 ×10 题 A 组），探针与判官修复全程离线零消耗 |
| 四次 run trace | `intelligence/eval/runs/20260731T191636Z / 20260801T025854Z / 034001Z / 035325Z.json` |
| 三份 verification 文档 | `docs/verification/2026-08-01-{frequency-longtail-probe,three-harness-architecture,a-tier-baseline}.md` |
| 工作区 | **脏**，787 行未提交（见 §1）|
