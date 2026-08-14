# Episode Seam Ladder Verification

- 日期：2026-08-09
- 分支：`test/episode-seam-ladder`
- revision：`3b00c3fc`
- 范围：episode 接缝阶梯（逐层接入实验）的 runner、离线回归门与 opt-in live smoke
- 结论：离线阶梯与聚焦回归全部通过；live smoke **未执行**，因本机 preflight 三项均不满足（环境事实，非代码回归）

## 1. 交付内容

| 文件 | 作用 |
|---|---|
| `scripts/run_episode_seam_ladder.py` | 阶梯 runner：stage 定义、契约/registry 派生、离线真回路、live preflight 与 receipt |
| `intelligence/tests/fixtures/episode_seam_ladder_cases.json` | 3 题市场 fixture，锚定 `2026-08-07`，显式声明 stage floor |
| `intelligence/tests/test_episode_seam_ladder.py` | 44 条聚焦回归：能力面、floor 不变量、真回路闭环、失败归类、live 安全 |

## 2. 设计缺陷的订正（本轮最重要的一条）

规格初版把 S1 定为「只开 `market_data`」，并给它配了一道 `market_watch` 题。实测这一级 **100% 会在构造契约时抛错**：

`ResearchTaskContract.__post_init__` 要求 `evidence_plan` 的 mandatory capability 必须是 `allowed_capabilities` 的子集，否则抛 `ResearchContractError`——契约在**构造那一步**就非法，根本到不了模型或工具。

实测各题型的强制底盘（生产 `TurnControlCore` + `build_episode_context`，零网络零模型）：

| case | question_type | evidence plan mandatory | floor |
|---|---|---|---|
| `next-session-index` | `market_forecast` | `market_data` | S1 |
| `current-mainline` | `market_watch` | `market_data`, `mainline_context` | S2 |
| `weekly-market-cause` | `market_cause` | `market_data`, `news_search` | S3 |

`market_forecast` 是唯一强制底盘恰为单个 `market_data` 的市场题型，所以 S1 只能用它。另外，带「处于什么状态」这类措辞的题会被路由判成 `general_finance_qa`（授权仅 `kb_search`/`web_search`），S1 交集为空，同样不能用。

**stage floor 因此不是主观分配，而是由这条不变量推导出来的。换题面前必须重跑这张表，不要只改字符串。** `test_floor_is_the_lowest_stage_whose_contract_can_be_built` 与 `test_routing_and_mandatory_capabilities_stay_put` 把这两项事实钉住，防止路由漂移悄悄让某一级失去测试意义。

## 3. 两个会让读数失真的实现约束

1. **不能靠传窄 `capabilities` 来收窄 stage。** `build_episode_context` 会把 evidence plan 的强制能力**重新追加**回 authorized，所以唯一诚实的做法是先派生完整生产契约，再 `replace` 它的 `allowed_capabilities`。只过滤 tool schema 而不收窄契约，会留下一条「契约授权比该级暴露更多」的不真实越权路径。
2. **每一级必须自建 context。** `ResearchDeadline` 是绝对 monotonic 时刻，`root_budget` 是活注册台账。跨级复用一个 context 会让 S1 的工具调用吃掉 S3 的预算——S3 的失败就可能来自耗尽的预算而不是它新接入的组件。runner 为每级生成唯一 episode id 并在 `finally` 释放（`release_root_budget`），否则同一级重跑会死在 "root budget already exists"，读起来像运行时缺陷。

## 4. 离线阶梯（CI 回归门）

命令：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/run_episode_seam_ladder.py --output /tmp/episode-seam-ladder-offline.json
```

实际输出（exit=0）：

```text
S1 next-session-index:  status=completed structural=completed semantic=passed tools=1
S2 next-session-index:  status=completed structural=completed semantic=passed tools=2
S2 current-mainline:    status=completed structural=completed semantic=passed tools=2
S3 next-session-index:  status=completed structural=completed semantic=passed tools=3
S3 current-mainline:    status=completed structural=completed semantic=passed tools=4
S3 weekly-market-cause: status=completed structural=completed semantic=passed tools=3
```

receipt 事实：`artifact_kind=episode_seam_ladder`、`mode=offline`、`source_revision=3b00c3fc`、`runtime.provider=scripted`、`semantic_verifier=offline_deterministic`、fixture sha256 前缀 `cd7598a6ac3d9e45`、`as_of=['2026-08-07']`；S0 产 0 条结果（只冻结路由，不构造 runtime），S1/S2/S3 分别 1/2/3 条，能力数 1/2/4。

离线跑的是**真回路**：`GLMAgentRuntime → ContinuousAgentEpisode → tool definitions → 真实 registry.execute → FINAL_JSON → 结构 verifier`。只有模型和语义裁判是脚本化的，工具的对外取数换成固定本地样本。没有预造 `AgentOutcome`、没有替换 `registry.execute`、没有走 deterministic fast path。

一个实现细节值得记住：`market_data` 的 `query_scope="episode"`，参数 schema 是**空对象**且 `additionalProperties: false`。脚本模型最初一律传 `{"query": ...}`，被 `registry.execute` 判 `invalid_arguments`，连带每个 output 缺证据。修法是按每个工具自己的 schema 生成参数。这正是「保留真实 execute」才能抓到的东西。

离线语义 verifier 只在结构输出已完成时返回 passed，它证明 semantic seam 被正确调用，**不宣称验证了生产 LLM judge**。

## 5. Live smoke：未执行

命令（未运行）：

```bash
scripts/run_episode_seam_ladder.py --live \
  --output /Users/a77/.finance-runtime/seam-ladder/<UTC timestamp>-<revision>.json
```

本机 preflight 实测三项全部不满足：

```text
ready False
  - continuous_mode must be 'on' to run an episode; got 'unset'
  - provider_chain is empty: no LLM provider resolved
  - market_data_freshness: no market snapshot date available
```

这是环境事实，不是代码回归。preflight 失败时 runner 写一份可读 receipt 并以非零退出，`stages` 保持为空——不伪造任何 stage 结果。live 的判据与离线相同，但另记 `business_incomplete`（真实空证据、日期闸门拒绝旧数据、verifier 正常部分完成），它不等于装配失败。

live 安全性由测试保证而非约定：默认调用绝不解析 provider（`detect_providers`/`GLMModelClient`/`SemanticEpisodeVerifier` 被替换成抛异常的桩，默认路径仍通过）；`--live` 的 receipt 必须落在 `/Users/a77/.finance-runtime/seam-ladder/` 之下；preflight 只记录 provider name/model，测试断言 api_key 与 base_url 不出现在 receipt 里。

## 6. 最终验证

```text
pytest -q intelligence/tests/test_episode_seam_ladder.py   44 passed
ruff check (runner + test)                                 All checks passed
git diff --check                                           clean
scripts/layer_audit.py                                     ERROR 0 条 == 基线
```

临时探针脚本（`tmp/probe_*.py`，未跟踪）已删除。

## 7. 边界声明

S1→S3 **不是**「能力越多答案越好」的质量单调性承诺。这套阶梯的硬约束只有三条：不暴露未开放工具、不绕过 verifier、新 capability 不使固定控制链路异常。答案质量仍由既有 A/B 与 28 题验收另行判断。
