# 8792 撤独立 Grok 判官、改 K3 自审（已切生产并验收）

## 这个分支做什么
执行 knevo 三轮 intake 清单第 4 项：撤掉独立 Grok 判官，保留 K3 自审，小样确认当前出口正常。
生产配置已改并 kickstart，小样已跑通。**代码快照未动**（仍 2efdff46），是干净的单变量切换。

## 决策与被否方案
| 选了 | 否了 | 理由 |
|---|---|---|
| 直接切生产 8792 | 旁路实例先验 | 本机 16G 旁路要关 RAG worker，检索面不等价，验不了「工具调用正常」这一条 |
| 判官在线但不独立 | 保留 Grok 独立判官 | grok 侧是慢性病：08-28 余额 402、09-02 沙箱拒启、09-09 下载件被自动更新清掉，三次都以 judge unavailable → fail-closed → 公开稿降级收场。挂掉是全站降级，不独立只是少一层交叉校验 |
| 四个 LLM_JUDGE_* 一起注掉 | 只注 BACKEND | 见下「踩过的坑」，只注 BACKEND 会炸 |
| 用 `scripts/workbench_probe.py` 打生产 | `intelligence/eval/live_probe.py` | 后者明说「Does not touch production 8792」，起的是一次性 sidecar 且走 marker lane，验不了生产出口本身 |

## 当前状态
- 启动器 `~/.local/bin/start-finance-workbench` 已改：144/159/160/161 四行注掉，带 09-12 说明段与回滚锚。
- 回滚锚：`~/.local/bin/start-finance-workbench.bak-20260912-pre-nogrok`（切前 cp -p，SHA-256 与原件一致）。
  回滚 = `cp` 回去 + `launchctl kickstart -k gui/$UID/com.a77.finance-workbench`。
- 8792 已 kickstart，新 PID 30830（原 67794）。`ASK_EVIDENCE_JUDGE=auto` 保持不变。

## 已验证（本次实测）
- 进程 env 中四个 `LLM_JUDGE_*` 全部消失；写手 `FORESIGHT_BUILTIN_LLM_MODEL=kimi-k3`、
  `RESEARCH_TIER=max`、`TOOL_AUTHORIZATION=all` 均未变。
- health：`source_revision=2efdff46e251…`、`code_matches_repo=true`、
  `loaded_tree_fingerprint == repo_tree_fingerprint`、依赖 7/7 true → 只换配置没换代码。
- 切前预检：8080 网关 http=200、Codex 钥匙可读、**kimi-k3 一次真实 chat 调用返回 `ok`**
  （health 200 不等于推理能通，这条踩过）。
- 小样 run `run_20260912_231328_111964`（user `nogrok-smoke-0912`，约 5.5 分钟）：
  - **判官真跑了**：`judge_status=repaired`、`correlated_judge=true`、`timeout_asked=75.0`、
    `judge_attempt_index=0`、`judge_unavailable_count=0`、`exc_class=null`、`http_status=null`。
  - **不是橡皮图章**：自审抓到两处具体错误 —— ①第12句把 E104 日期写成 2026-08-21，
    而该证据注册 `source_date=2026-09-11`；②第19句引用 E14/E23 越出 counterpoint 的
    evidence_ids。修复后正文确实收窄成「未见**本轮检索到的**正式订单公告」。
  - **修复没塌缩**：`repair_withheld=false`、`repair_collapsed_to_stub=false`、
    `rejected_claim_indexes=[]`、`content_degraded_count=0`、`degrade_class=null`。
  - 出口正常：`run.status=completed`、`degrades=[]`、`error=None`、answer.md 3126 字节，
    「复核服务不可用」等降级串 0 次。
  - 工具面：trace 里 **21 次真实 `tool_result`**，覆盖 memory/evidence/kb/L3/graph/
    financial_data/news/web_fetch/market_data/沙箱计算。
- 读码证实回落路径：`judge_provider()` 返 None 后，检索闸 `evidence_judge.py:95` 走主链；
  终稿判官 `episode_semantic_verifier.py:1816` 链空落 `_primary_judge`（`api/app.py:470`
  传的就是 composer client）→ `correlated=True` 而非 `unavailable`。
  `correlated_judge` 只出现在 `gate_receipt.py` 与 `eval/`，**发布路径零引用**，不是运行时闸门。

## 未验证 / 已知边界
- **只有一发小样，且是检索题**。方法论题、材料题、弃权题在 K3 自审下的表现未测。
- 自审的**长期质量**未测：本发抓到两个错，不证明它不会漏掉「同一模型的系统性偏差」那类错
  —— 那正是独立判官存在的理由（`llm_refine.py:247`）。建议后续按题型抽查 overturn 率。
- 收据 `correlated_judge=true` / `independent_n=0` → `eval/variance_baseline.py` 的独立性分桶
  会归零，**判官结果不能再当独立验证用**。历史对照数据跨这条线不可直接比。
- 运行时仍落后 `gitea/main` **80 个提交**（是祖先，无分叉）。情景树/历史重放/三值逻辑那六张
  PR 仍未部署 —— 本次刻意没动，保持单变量。
- 判官对 E104 提的是**日期不符**，修复采取的是加限定（「页面所载」「来自媒体转述」）而非改日期。
  值得follow：这是修对了还是绕过了。
- 行情：`tool_hunger.jsonl` 有一条 `stock_daily` 08-10..09-10 `row_count=0` 的
  `window_uncovered`，但同一 run 的正文引用了 09-03/09-04/09-08/09-10 真实行情，
  **所以那是某种查询形状的零行，不是月级空洞**，别据此扩大 09-11 缺口的结论。
  DuckDB 当时被 `market_feature_store` 写入进程（PID 45254，23:17 起）持锁，未能独立复核。

## 下一步
1. 复验第二、三轮材料题（不依赖行情补齐），标「揭盲后复验」。
2. 清单第 2 项补 09-11 数据；第 3 项对齐那 80 个提交 —— 两者都会改变基线，
   做之前先把本次这发小样收据留作「配置切换后、代码未动」的锚点。

## 踩过的坑
**撤一个可选组件时，它的从属配置变量必须一起撤。** 只注掉 `LLM_JUDGE_BACKEND` 而留着
`LLM_JUDGE_MODEL="grok-4.6"`，会掉进 `llm_refine.py:285` 的 `if model:` 分支 —— 它拿主
provider 换个模型名，变成向本机 8080 网关要 grok-4.6；网关没这个模型 → judge unavailable
→ fail-closed → 公开稿全降级。**跟 09-09 那次是同一个降级形状，只是换了个触发口。**
配置面的「半关」比「没关」更危险：没关至少行为已知。
