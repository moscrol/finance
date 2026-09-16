# 揭盲后复验：T2/T3 材料题（无 Grok / K3 自审形态）

状态：**QC 收口进行中（2026-09-13）。** 路由修复随 `2ee664fae9c4` 部署生产，T2/T3 复验拿到实质答卷；独立质检（[QC-2026-09-13.md](QC-2026-09-13.md)）判「部分通过」，S1/N1/E3/S2 已于 `fix/8792-qc-closeout-0913` 修复（E3 含 12 天重算验证），E2 材料边界立设计任务，复验文档已按 QC 更正（[RESULTS-2026-09-13.md](RESULTS-2026-09-13.md)）。下面是 09-12 的事故原貌，保留供溯源。

历史状态（09-12）：T2 被生产路由缺陷挡住，复验未能开始；缺陷已定位、已复现、修复已在本分支验证但当时未部署。

## 运行条件（切换前后都记，便于后续对账）

| 项 | 值 |
|---|---|
| 入口 | 8792 Workbench 会话 API（`scripts/workbench_probe.py`），非 CLI `ask` |
| 代码 | `2efdff46e2510a2f87f5bc245b524fb94724741a`，`code_matches_repo=true` |
| 写手 | `kimi-k3`（`FORESIGHT_BUILTIN_LLM_MODEL`，链首） |
| 判官 | **无独立判官**，K3 自审（本日已撤 `LLM_JUDGE_BACKEND`/`_MODEL`/`_GROK_BIN`/`_GROK_SANDBOX`） |
| 检索闸 | `ASK_EVIDENCE_JUDGE=auto`（未动） |
| 档位 | `RESEARCH_TIER=max`、`TOOL_AUTHORIZATION=all` |
| 探针用户 | `recheck-t23-0912`（非主账号） |

题面取自冻结原题 `docs/learning/knevo-distill/batches/2026-09-12-three-turns/questions.md`
（在 `docs/knevo-20260911-intake` 分支上），本目录 `t2-question.txt` / `t3-question.txt`
与之 **SHA-256 逐字节一致**：T2 `4fbb588ee75d3912…`、T3 `ec8e287bcf3ec580…`。

## 发生了什么

T2 run `run_20260912_232710_911376`（`~/.local/share/finance-workbench/users/recheck-t23-0912/runs/`）：

- `answer.md` **183 字节**，内容是「【扫描结论】未执行全市场扫描。未指定板块，本扫描不做全市场」
- `llm.used = false` —— **模型一次都没被调用**
- `answer_status=complete`、`status=completed`、`transport_status=completed`、`warnings=[]`
- `gate_receipt.judge_status=not_applicable`、`correlated_judge=null`

**与本日的判官配置切换无关**：模型没跑，判官自然 `not_applicable`；Grok 开着结果一样。

### 责任链（逐步取自 `trace.jsonl`）

1. `turn_controller` 判 `question_type="disclosure_scan"`，置信度 **0.98**，
   理由「路由表命中 disclosure_scan：高置信词面命中细粒度路由」
2. `route_skills`：`router_skipped=true`、`selected=[]`、`fallback_to_ask=true`
3. `ask_retrieve_compose`：`citation_count=0`、`elapsed_ms=2`
4. `answer_synthesis`：`status="validated"`，但 `diagnostic.state="not_requested"`
   —— **合成压根没被请求**
5. `conversation_orchestrator.py:3209` `result.synthesis = disclosure_scan_pack.render()`
   把正文覆写成扫描存根
6. `budget`：「研究工具调用 0 次」

第 4 步是这条链里最值得记的一处：`status="validated"` 与 `state="not_requested"` 同时为真，
**「校验通过」被拿来描述一件根本没发生的事**。只看 status 的仪表永远绿。

## 根因与最小复现

`is_disclosure_scan_query()`（`intelligence/services/disclosure_scan_pack.py:218`）要求三个提示词
同时命中，但它对**整段去空白后的全文做无锚点子串匹配**，不要求三词相邻：

| 提示 | 命中 | 位置 | 来自 |
|---|---|---|---|
| `_SECTOR_HINT_RE` | `行业` | @64 | 小节标题「【行业材料】」 |
| `_DISCLOSURE_HINT_RE` | `公告` | @72 | 「客户 R 公告：未来 12 个月…」 |
| `_ROSTER_HINT_RE` | `哪些` | @437 | 第 1 题「还需要经过哪些环节」 |

三个词分散在 370+ 字符之外的三个不相干段落。短问句里三词共现说明同一个诉求；
长材料题里纯属巧合。

复现（生产快照上直接跑）：

```bash
cd /Users/a77/.finance-runtime/finance-workspace-2efdff46e251 && \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -c \
  "import sys;sys.path.insert(0,'.');from intelligence.services.disclosure_scan_pack import is_disclosure_scan_query;print(is_disclosure_scan_query(open('<t2-question.txt>').read()))"
```

## 影响面（实测，非推断）

- 三轮原题里**只有 T2 中招**：T1 缺 `公告`、T3 缺 `板块/行业`，各差一个词。
- 仓内冻结题集 `outlook-ten-question-frozen-2026-08-16`（18 题）与 `knevo_bench6_v2`（6 题）
  **命中 0 题** —— 全是短问句。**这正是它一直没被发现的原因：评测语料里没有长材料题。**
- 不是 `disclosure_scan` 一条的毛病。`_fine_grained_route_row()` 下辖六条路由
  （disclosure_scan / trade_advice / kol_review / comparison_analog / theme_track / quick_fact）
  用的是同一种无锚点词面匹配，自带 examples 长度全部 **8–21 字**，却被无长度限制地
  套在任意长度输入上。
- `gitea/main`（领先生产 80 提交）上**缺陷依旧**，且 `turn_controller.py` /
  `disclosure_scan_pack.py` 在这 80 个提交里一行没动 —— **部署那六张 PR 不会顺带修好它。**

## 修复（本分支已实现并验证，未部署）

`intelligence/services/turn_controller.py`：给 `_fine_grained_route_row()` 加家族级长度闸
（阈值 SSOT `route_table.FINE_GRAINED_ROUTE_MAX_CHARS = 160`，去空白后）。

- 闸放在家族入口而不是只修 `disclosure_scan`：六条路由是同一个弱点。
- 同文件 meta 路由早有此 idiom（`len(cleaned) <= 64 and _META_PATTERN.search(...)`）。
- 阈值依据：实测语料里真实短意图问句最长约 69 字，材料题几百到上千字，两者无重叠区。
- **失败方向安全**：超长问句只是退回正常 lane 由模型判，仍会被完整回答；
  漏判的代价才是上面那个静默存根。

验证：
- T2 不再命中细粒度路由；六条路由自带 14 条 examples 中 13 条仍各归其位。
- 唯一未归位的 `kol_review` 例「但斌说茅台到顶了逻辑有没有漏洞」(15 字) 在**未改动的生产
  快照上同样返回 None**，是存量缺陷（route 的 example 与自己的 pattern 对不上），不是本次引入。
- `test_turn_control_core` / `test_disclosure_scan_pack` / `test_quick_fact_routing` /
  `test_market_forecast_rubric` 共 94 passed。

## 追记（2026-09-13）：第一版修复不完整，第二个调用点已补闸

**上面那版只闸了 `_fine_grained_route_row` 一个调用点，端到端没有修住。**
`is_disclosure_scan_query` 还有第二个调用点 `query_understanding.understand_query`
（产出 0.98 的 disclosure_scan envelope）：第一版修复后 `decide_turn(T2)` 仍判成
disclosure_scan——envelope 沿 `build_task_frame → project_task_frame` 流进
`_deterministic_decision` 末尾的兼容底分支（「明确金融研究对象或决策目标」，
subject_kind≠unknown 且置信≥0.7 即采信 `envelope.question_type`）。
上一轮的验证全部钉在被改的那一层（`_fine_grained_route_row` 返 None、13/14 归位、
94 passed），没跑端到端，所以漏过去了。

最终修复（仍为最小面）：

- 阈值与判定 helper 上移到 `route_table.py`（叶子模块，无 import 环）：
  `FINE_GRAINED_ROUTE_MAX_CHARS` / `fine_grained_route_length_ok()`。
- 两道闸同一阈值：`turn_controller._fine_grained_route_row`（家族入口，盖六条路由）
  与 `query_understanding.understand_query` 的 disclosure_scan 分支。

端到端复验（修复后）：`understand_query(T2)` → `comparison`(0.82)，
`decide_turn(T2)` → `comparison` / research lane /「交给通用研究闭环」——正是设计的
安全失败方向；160/161 边界两侧两个入口行为一致；13/13 examples 归位不变。

回归锁：`intelligence/tests/test_fine_grained_route_length_gate.py`（30 passed + 1 xfailed），
钉三层——裸匹配器仍命中、两个入口都退回、`decide_turn` 端到端不再判 disclosure_scan；
事故题逐字节嵌进测试并用 SHA-256 断言防漂移；存量 kol_review miss 记为 strict xfail。

**教训**（已入 `.claude/lessons_learned.md`）：改完词面匹配器先 grep 它的全部调用点；
验证要钉 `decide_turn` 端到端，不能只钉被改的那一层。

## 未做 / 待决策

复验要走完必须先部署修复到运行快照，那是生产变更，等用户拍板。可选：
只部署这一条修复（最小面），或与清单第 3 项「对齐 80 个提交」合并处理。
**在此之前 T2/T3 复验不具备条件**，本目录不放任何替代性答卷，以免被后续误当成复验结果。
