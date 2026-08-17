# Handoff：实体概念袋不该当 `get_evidence` 的硬过滤键（#157 只豁免了锚定实体）

日期：2026-08-18
roadmap_ref：L1-8792
前序：#153（数字证据消失诊断单）→ 诊断 `docs/verification/2026-08-17-evidence-number-density-diagnosis.md`（H4 CONFIRMED）→ #157（锚定实体豁免，已合并 `a36051aa`）
性质：**设计 + 量化决策材料单**。默认不改代码；若量化结果指向明确且方案边界小，可附带一个独立代码 PR，但材料先行。

## 1. 背景：#157 修了症状最重的一处，病根还在

`collect_evidence_index`（`intelligence/services/evidence_providers.py`）对每个 target 调 `get_evidence(target, concept=company_evidence_concepts.get(target), ...)`。这个 `concept` 来自 `collect_graph` 收的**图谱暴露绑定**——是实体登记概念袋里的某一条（长电科技拿到的是 `1.6T CPO`），不是这条证据自己的题材标签。

已证实的失败模式（#153 诊断，一手复算）：

- `get_evidence('长电科技', limit=8)` → 8 条，含 286.69 亿硬数字
- `get_evidence('长电科技', concept='1.6T CPO')` → `found=False`，**整包滤空**
- `get_evidence('长电科技', concept='AI算力')` → 有数（说明数据在，键错了）

#157 的豁免条件是 `target == anchor.entity`，**只救了锚定实体**。以下 target 仍然带着图谱概念袋当硬过滤键进 `get_evidence`：

1. `matched_theme`（题材 target）
2. `options.query` 全文
3. **图谱扫出来的其他公司**（盘面候选，如 富信科技/工业富联 这些）

第 3 类和长电是同构风险：图谱把公司绑到概念袋第一条暴露，绑定概念 ≠ 证据 concept 标签时，该公司的证据整包 `found=False`，然后被别家占名额——只是这次受害者从锚定实体换成了盘面候选。

## 2. 说清楚再动手：concept 过滤本来是干什么的

它不是纯粹的历史包袱。合理用途：题材题（「光模块概念股怎么看」）里，用 concept 把某公司证据窄化到与题材相关的那部分，避免把公司全部证据灌进有限名额。所以「一刀切删掉过滤」不是默认答案——先量化，再挑方案。

## 3. 任务

### 3.1 量化封杀面（只读，照 #151 决策材料单的做法）

写只读扫描脚本（放 `docs/verification/`），对账本回答：

- 图谱概念袋里每个（公司, 绑定概念）对：`get_evidence(company, concept=bound)` 是否 `found=False`，而 `get_evidence(company)` 无过滤时有数？——这是「整包滤空」名单。
- 滤空名单里，有多少公司出现在近期真实题目的 targets 里（可用 R15 十八题 / 冻结三十题的 targets 抽样）？——区分理论风险和实际踩线。
- concept 命中时，过滤把平均可见条数从多少压到多少？——量化「窄化」的真实收益面。

### 3.2 方案矩阵（至少这四个，可加）

| 方案 | 形状 | 已知顾虑 |
|---|---|---|
| A 维持 | 只保留 #157 的锚定豁免 | 盘面候选仍可能整包滤空；同构 bug 再来一次 |
| B 空则回退 | `found=False` 时对同 target 重发一次无 concept 的 `get_evidence` | 名额语义变化最小；多一次 adapter 调用；题材题的窄化收益保留 |
| C 软排序 | concept 不过滤，改为命中者排前 | 检索语义改动最大，要动 adapter 排序；彻底消灭滤空 |
| D 修绑定源头 | `collect_graph` 不要拿「第一条暴露」当公司概念，改为不绑或绑证据侧真实 concept 众数 | 动图谱收集层；绑定语义要重新说清楚 |

每格填：滤空名单覆盖率（用 3.1 的数）、字符/名额成本、要动的文件与函数、回归测试形状。给推荐，但**裁决留给用户**（写进 roadmap 决策队列，owner=用户）。

### 3.3 若做代码（可选，材料先行）

- 只动 `collect_evidence_index` 或 `collect_graph` 的绑定/过滤逻辑，**不动** `AskOptions.max_evidence`、不动 stale 排序（那是 #151 的裁决域，别搅）。
- 回归测试双向：滤空公司修后有数；题材题窄化行为不回退（拿 #157 的 `CollectEvidenceIndexAnchorTests` 当模板，正反两面都要）。
- 合并门禁照旧：`umask 022` 四件套（ruff + 全量 pytest + `intelligence/webapp` 的 pnpm lint/typecheck/test/build）。注意跑 pytest 前把启动器变量摘干净、**只留 PATH 和 KNOWLEDGE_WIKI**（`PYTHONPATH` 指着运行时快照会混树导入，2026-08-17 夜里已踩过，假红 19 条那种就是它）。

## 4. 验收

1. `docs/verification/` 有扫描脚本 + 数据表；滤空名单一目了然，能回答「现网还有几个公司会被整包滤空」。
2. 方案矩阵四格全填，带推荐；roadmap 决策队列挂「材料就绪待裁决」。
3. 若附代码 PR：测试先红后绿，四件套绿，PR 里写清楚只动了哪两个函数。
4. 全程不切 8792（当前 `877e1f72`）；跑前确认 `/tmp/finance-8792-live.lock` 不存在。

## 5. 红线

- 不动生产 8792，不改 launcher。
- 不顺手动 `max_evidence` / stale 排序 / prompt——各有各的单。
- 结论必须落盘可复算（脚本 + 收据路径），不接受「跑过了，是好的」。
- 新活从 `gitea/main` 开分支；PR 走 Gitea API（token 在钥匙串 `gitea-local`）。
