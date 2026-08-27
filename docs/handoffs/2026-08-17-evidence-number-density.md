# Handoff：锚定实体的数字证据在 R 通道消失——「答得薄」的第一失分项

日期：2026-08-17 深夜
roadmap_ref：L1-8792
前序：#146 部署（8792=`877e1f72`）→ 长电靶 live 探针（收据 `~/.finance-runtime/claim-tiering-20260817/live-superseded-tiering.json`）→ #149 更正
关联单（读一遍再动手，别撞车）：《2026-08-17-live-probe-traceability.md》（探针 trace 化，能帮你拿一手上下文）、《2026-08-17-max-evidence-stale-quota-decision.md》（同在 R 通道但不同环节：那单管「一个 target 的 top-8 里 stale 边进不进」，本单管「锚定 target 的整包证据为什么没到出口」）
本单性质：**先诊断后修**——定位环节要证据齐全；修复走最小改动 + 四件套 + live 复验

## 0. 一句话

用户问「长电科技的营收规模怎么看」，知识库适配器层明明有「25 年前三季营收 286.69 亿(+18%)」这类硬数字（top-8 内、active 状态），最终答案却说「本轮证据给不出数字」。已定位到丢失发生在**检索出口之前的管线内部**（不是 KB 缺数、不是模型不敢用）：锚定实体自己的证据包整包没变成 evidence 行/引用。找到丢在哪一环，修掉，live 复验答案能给出带引用的硬数字。

## 1. 三层已验证事实（2026-08-17 晚实测，均可复算）

**层 1：适配器层有数。** `get_evidence('长电科技', limit=8)` 返回 8 条 active，其中 5 条带硬数字：

- `[[AI算力产业新格局与供应链深度研究报告]]`：**2025 年前三季度营收 286.69 亿元，同比增长 18%**，高端封装占比 42%
- `[[GPU产业新格局…]]`：HBM 封装良率 98.5%、2025H1 毛利率 13.2%、先进封装营收占比 38%
- `[[AI端侧…]]`：全球份额 10.40%→12.00%
- `[[AI应用…]]`：2025 Chiplet 营收预计破 50 亿
- （另 3 条为定性行）

**层 2：管线出口零命中。** 同题走生产装配路径（`use_llm=False`，检索段确定性）：

- `anchored_entity = EntityAnchor(entity='长电科技', ticker='600584', matched_by='name')`——**锚定正确**
- `found_graph=True`，citations 26 条
- 但 R 通道（`evidence_index`）的 6 条引用 target 全是**别的公司**：富信科技、工业富联、剑桥科技、汇绿生态、铭普光磁×2（形似盘面候选携带证据）
- 全部 26 条引用里 **不含 286.69**，不含上述任何一条数字富集边

**层 3：live 答案如实反映了输入贫血。** 那发收据的正文：「本轮证据只索引到这些文件的『存在』，没有提取任何金额、增速或利润率数据……营收规模判断目前是明确缺口」——W 通道给的是 `长电科技.md`/年报 baseline/逻辑跟踪这类文档级线索，L3 给的是巨潮披露文件存在性。模型行为是诚实的，料没到。

复算命令（层 1 与层 2）：

```sh
set -a; . <(grep '^export ' /Users/a77/.local/bin/start-finance-workbench | sed 's/^export //') >/dev/null 2>&1; set +a
cd ~/fwp-wt-deploy-main   # 或任一 gitea/main 检出
# 层 1
PYTHONPATH=$PWD /Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "
import os
from intelligence.adapters.knowledge import KnowledgeAdapter
ka = KnowledgeAdapter(os.environ['KNOWLEDGE_WIKI'])
for it in ka.get_evidence('长电科技', limit=8).get('items') or []:
    print(str(it.get('source'))[:30], '|', str(it.get('evidence'))[:90])
"
# 层 2
PYTHONPATH=$PWD WORKBENCH_GROUNDED_PRESENTER=0 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "
import os
from intelligence.services.ask import AskOptions, answer_query
r = answer_query(AskOptions(query='长电科技的营收规模和封测行业地位怎么看',
    kb_wiki=os.environ.get('KNOWLEDGE_WIKI'), use_modules=True, use_wiki_rag=True,
    use_llm=False, compose=False, clarify=False))
print(r.anchored_entity)
for c in r.citations or ():
    print(str(c)[:110])
print('286.69 present:', any('286.69' in str(c) for c in r.citations or ()))
"
```

## 2. 诊断任务：丢在七环里的哪一环

链路：KB 原始边 → `get_evidence` → `collect_evidence_index`（`intelligence/services/evidence_providers.py:526`）targets 遍历 → evidence 行拼装 → 行预算/引用预算 → LLM 上下文 → 门禁/展示。层 1/层 2 已把丢失夹在**第 3~5 环之间**。至少验证这三个可证伪假设（各配探针，逐条标 CONFIRMED / REJECTED）：

- **H1 targets 错位**：运行时 `collect_evidence_index` 的 `ctx.anchor` 或 targets 列表里根本没有「长电科技」（虽然 `result.anchored_entity` 有）——探针：在该函数入口打印/断点 targets 实际值（临时插桩跑一发即可，不提交）。
- **H2 行建了但被挤掉**：锚定实体的行进了 `bundle.lines`，但行预算/引用预算把它们排到盘面候选携带证据之后裁掉——探针：打印 `bundle.lines` 全量与最终 citations 的差集；查预算/截断常量在哪。
- **H3 条件性 cite**：行进了 evidence_lines 但 `cite('R', …)` 只在某些分支执行，锚定实体分支没走到——探针：对照 `:526-635` 的分支逻辑与运行时路径。

若三个都 REJECTED，把新假设和证据写进诊断记录再继续；**不许在没定位的情况下盲调参数**。

## 3. 修复原则

- 最小改动。方向性建议（按诊断结果取舍）：锚定实体的证据在 R 通道应有**保底名额**，不被盘面候选携带证据整包挤出；但不要顺手重排整个通道的优先级——那影响所有题型。
- 不动 `max_evidence` 默认值、不动 stale 排序（分别是另两单的地盘）；若修复方案与《max-evidence-stale-quota-decision》的方案空间冲突，先在两单之间对齐再动。
- 带回归测试：至少一条「锚定实体证据必须出现在 R 引用中」的用例 + 一条对偶（无锚定题不受影响）。
- 四件套过（`GITEA-USAGE.md` 三行；pytest 必须 **umask 022**，077 会假红 16 个 ceiling 权限位审计，环境项）。

## 4. 验收（可判定）

1. 诊断记录：三假设逐条 CONFIRMED/REJECTED + 证据，落 `docs/verification/` 或本文件补节。
2. 修复后层 2 探针：R 引用含 target=长电科技 的条目，`286.69 present: True`（或当时 KB 的等价硬数字）。
3. live 复验一发同题（探针方法沿用《live-probe-traceability》交付物或 in-process+落盘双管）：答案正文能给出带引用的营收数字，收据落 `~/.finance-runtime/claim-tiering-20260817/live-number-density.json`。
4. 全量 pytest 绿（umask 022），无既有用例回归。
5. PR 合并走 Gitea（消息风格「标题 (#N)」）；台账：`docs/handoffs/inflight/main.md` 补一行。
6. **部署不在本单**：合并后是否切 8792 由用户决定，默认不追切。

## 5. 红线

- 不动 8792（launchd `com.a77.finance-workbench`，快照 `finance-workspace-877e1f721e05`）；探针全部旁路跑。避开 `/tmp/finance-8792-live.lock`。
- 临时插桩不许进提交；诊断跑完删干净（`git status` 干净再开修复分支）。
- 基线从 `gitea/main` 开（本机旧 `main` 落后几百提交）；`gh` 不可用，PR 走 Gitea API（token：`security find-generic-password -s gitea-local -a a77-token -w`）或网页 http://localhost:3300 。
- 密钥全在 Keychain，不落盘。
