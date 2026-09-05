# feat/judge-token-usage

树 `/Users/a77/fwp-wt-judge-token-usage`，基座 `gitea/main`=`c6e702a6`（派单时；实施中 main 前移 10 个提交，
已 `2ac58896` 合入本分支，merge-tree 干净）。工单 `docs/superpowers/specs/2026-09-04-judge-token-usage-workorder.md`
（INDEX #23）。解释器 `.venv-workbench/bin/python`。PR **#593** `http://127.0.0.1:3300/a77/finance-workspace-private/pulls/593`。
**未合 main、未强推、未切流。**

## 这个分支做什么
把判官侧的 token 用量记进已有的 `LLMCallLedger`（不新开账本），让「单次研究全口径成本」能量出来：
① `LLMCallRecord` 增 `input_tokens / output_tokens / usage_source(api|cli|estimated) / purpose`，`summary()` 增合计 / 按 purpose 分组 / 估算占比；
② API 判官 `_post_chat` 读响应顶层 `usage`（双命名）；③ grok CLI 判官解析 payload 顶层 `usage`（探明：**有**），拿不到才字符估算并标 `estimated`；
④ `episode_semantic_verifier._run_judge` 用 `call_purpose("judge")` 给判官调用贴标签；⑤ `continuous_turn_adapter` 的 turn `metrics` 增 `judge_usage`；
⑥ 读者 `intelligence/eval/research_cost.py` + 价目表 `intelligence/eval/pricing/llm-prices.json` 出写手 / 判官 / 合计的中位 / 均值 / p90 与元/次；
⑦ `metric_field_contract` 登记、台账地图新行、测试 43 例、首份真实目录报表。

## 决策与被否方案
- **CLI 分支实现、估算留纯函数**：2026-09-05 真实判官调用一次（生产同款 grok 1.0.5 / grok-4.6 / read-only），stdout 顶层
  `usage={input_tokens:19326, cache_read_input_tokens:128, output_tokens:970, reasoning_tokens:858, total_tokens:20424}` +
  `modelUsage`（camelCase）+ `total_cost_usd=0.00757`。原始 stdout `~/.finance-runtime/judge-usage-probe-2026-09-05/raw.json`（不进仓）。
  按用户指令只接真正需要的 `cli` 分支；`estimated` 分支只在拿不到用量时回落（含既有测试把 `complete_grok_cli` 换成回裸 str 的替身）。
- **用量怎么从 CLI 路带出来**：`complete_grok_cli` 返回 `GrokCliText`（`str` 子类挂 `input_tokens/output_tokens/usage_source`），
  `_complete_cli_judge` 用 `getattr` 读后对外仍回纯 `str` / 否 改返回类型为 dataclass / `test_grok_cli_judge.py` 与
  `conformance_transport/transports.py` 都把 `complete_grok_cli` monkeypatch 成三参回 str 的函数，换返回类型或加 kwarg 全会破；
  否 ContextVar 侧信道 / 要 reset 纪律，替身不写会读到上一次的脏值。
- **双命名取值下沉到新模块 `services/llm_usage.py`** 而不是放 `llm_refine` / `grok_cli_judge` 也要用它，放 `llm_refine` 会形成
  `grok_cli_judge → llm_refine → (lazy) grok_cli_judge` 的循环味；runtime `_message_token_usage` 改为调用该纯函数，逻辑单源。
- **`purpose` 包在 `_run_judge` 内两处真正发请求的位置**（`llm_refine.complete` 与相关判官 `primary.complete`）/ 否 包三处
  `self._run_judge(...)` 调用点 / 三处都汇到 `_run_judge`，包内层一次即全覆盖，修复轮写手调用发生在方法之外不会被误标；
  否 `with (a, b):` 括号写法 / `ruff.toml` target py39，改为嵌套 `with`。
- **`judge_usage.usage_source` 合并规则**：任一 `estimated` → `estimated`（估算不得混进真实值而不注明）；全同源取该源；
  多真实来源（主判官 CLI + 备胎 API）→ `mixed`；无一条带用量 → None、token None（0 与「没记到」是两件事）。`mixed` 是工单
  三值之外的扩展，已写进 `metric_field_contract` 的落点说明。
- **快路径 metrics 不加 `judge_usage`**：`deterministic_fast_path` 没有任何 LLM 调用，两条既有测试对该 dict 全等断言；报表按
  `execution_kind`/写手 usage 为 0 归入 `writer_unrecorded_runs`，不会被误计成「判官未记账」。
- **`metric_field_contract` 不新增条目**：`test_no_declaration_without_spec_entry` 把 `spec_name` 钉在 spec §9.3；判官落点写进
  既有「input/output token 和每个阶段耗时」条目的 locator / note。
- **价目表 grok-4.6 行价格 null**：实施环境无外网检索，xAI 官方价核对不了，按工单「不猜数」；报表对无价模型显示「价目表未录」
  并列 `unpriced_models`。GLM-5 / GLM-4.6 官方给区间，取上界（与 BP §7.3「GLM-5 档均值约 0.33 元」算法一致）。
  **2026-09-05 收尾轮已填**（见「未验证 / 已知边界」）：判官默认取 **CLI 实付档**而不是 API list 档 / 否 默认 list、
  实付只写进 note / 否 两行都填但不动默认——用户拍板取第一种。理由：报表口径是「单次研究全口径成本」，生产判官走 grok CLI，
  按 list 算出来的判官成本是 xAI 实际计费的 5.9 倍（¥0.3019 vs ¥0.0513 每次判官调用），这个数要进 BP。
  代价是默认那档不是官方公示价而是反解值，用 `test_cli_selfreported_cost_reproduces_from_the_build_row` 把它钉在 CLI 自报成本上。
- **报表加 `--writer-price-model` what-if**：真实目录里 243/356 个 run 的 `report.json.llm.model` 是 `gpt-5.6-terra`（8 月中转期），
  按实际模型只能给 113 个 GLM run 定价；BP §7.3 的 0.34 元是「全按 GLM-5.2 档」的 what-if，加这个开关才能复现它。
- **报表以 `run.json.status=completed` 过滤**（缺 run.json 退到 `outcome.status`）——与 BP 的 356 个 run 口径一致
  （`outcome.status` 在 semantic repaired 的 run 上是 `partial`，用它会少算）。
- **测试文件复用 `test_episode_semantic_verifier._structural`** 做 verifier→complete→_post_chat 的真实链路断言，不另造夹具。
- 提交按逻辑层分 4 个（记账层 / 标签+metrics+契约 / 读者+价目+台账 / 测试）+ 报表基线 1 个，未按工单 §5.3 逐子步拆——
  `llm_refine.py` 的字段、API 解析、CLI 接线、ContextVar 互相引用，拆开需交互式部分暂存。

## 当前状态
代码尖 `80f6a01e`（全量门禁 revision）→ 其后只有 docs 提交（PR #593 head 以 `git log gitea/feat/judge-token-usage -1` 为准）。
提交：`d0121126` 记账层 → `af2a0c48` purpose / judge_usage / 契约 → `7f493e5a` research_cost + 价目表 + 台账地图 →
`a37f43fd` 测试 → `8361b7ac` 首份真实目录报表 → `2ac58896` merge main → docs → **`7cbe5af6` 落 grok 价目 + 默认判官取价改
CLI 实付档 → `80f6a01e` 报表按新价目表重出**。
改动面：`intelligence/services/{llm_refine,llm_usage(新),grok_cli_judge,episode_semantic_verifier}.py`、
`intelligence/runtime/{continuous_turn_adapter,glm_agent_runtime}.py`、`intelligence/eval/{research_cost(新),metric_field_contract}.py`、
`intelligence/eval/pricing/llm-prices.json`（新）、`intelligence/eval/measurements/research-cost-2026-09-05.{json,md}`（新）、
`intelligence/tests/{test_llm_call_ledger_usage(新),test_research_cost(新),test_continuous_turn_adapter}.py`、`docs/learning/ledger-map.md`。
前端零改动（未跑 pnpm）。探针目录 `~/.finance-runtime/judge-usage-probe-2026-09-05/`：`probe.py`、`raw.json`、`request-messages.json`、
`calibrate_k.py`、`calibration.json`、`pr-body.md`——都不进仓。

## 已验证（本树、`.venv-workbench`）
- **探明**：grok CLI stdout 顶层键 `modelUsage / num_turns / requestId / sessionId / stopReason / structuredOutput / text / thought /
  total_cost_usd / total_cost_usd_ticks / usage`；`usage.input_tokens=19326`（提示词只有 2951 字符≈估 1240 token，CLI 自带上下文
  占了 15.6 倍）、`output_tokens=970`（含 reasoning 858）、`cache_read 128`（`total = input + output + cache_read`，即 input 不含缓存命中）。
  单次调用 25.7s，`total_cost_usd=0.00757`。
- **K 校准**（`calibration.json`）：同一段提示词发 GLM API（服务端回 `glm-5.3`）`prompt_tokens=1222` → 2.415 字符/token；可见补全
  207 字符 / 106 可见 token；解得 K_cjk≈1.26、K_other≈5.7，取 1.3 / 5.0；回代：提示词估 1240 vs 实 1222（+1.5%），GLM 可见补全
  106 vs 106（0%），grok 可见输出 90 vs 112（−20%）。估算**看不见** reasoning（GLM 180 / grok 858）与 CLI 自带上下文——
  这就是 `estimated` 标记必须走完全程的原因。
- 定向：`test_llm_call_ledger_usage` 30 绿、`test_research_cost` 13 绿；`test_grok_cli_judge` + `conformance_transport` +
  `test_metric_field_contract` + `test_p1b_runtime` 98 绿；`test_episode_semantic_verifier` + `test_continuous_turn_adapter` 266 绿
  （后者 1 条全等断言补 `judge_usage` 后）；runtime/API 面 350 绿；合 main 后 HEAD `2ac58896` 上工单点名集合 **448 绿**
  （收据 `20260904T185159Z-2ac58896.json`）。
- **变异**：`_post_chat` 的 `token_usage_counts(...)` 改成 `(None, None)` → `test_llm_call_ledger_usage` **4 红**
  （`test_post_chat_records_usage_from_either_naming` ×2、`test_call_purpose_nesting_does_not_leak`、
  `test_verifier_judge_call_is_labelled_judge_end_to_end`），恢复后 30 绿。
- **合并点全量门禁（2026-09-05 收尾轮）** `bash scripts/run_main_gate.sh` @`80f6a01e` 干净树：**7760 passed / 0 failed /
  15 skipped / 1 xfailed**，335.7s；收据 `20260905T014007Z-80f6a01e.json`，`check_test_receipt.py --expect-revision
  $(git rev-parse HEAD) --base-drift-max 5` → **exit 0**（基座漂移 0：分支已含 `gitea/main` 全部提交）。
  同日先在 PR head `035c38cf`（填价前）跑过一轮：**7758 passed / 0 failed**，收据 `20260905T012327Z-035c38cf.json`，
  同样 exit 0；两轮 `same_red_set=True`、`passed_non_decreasing=True`，+2 是新增的两条价目表守门测试。
  **下面那轮 9 红已全部消失**——9 条里 7 条当时被归因为知识库仓解析态（`~/knowledge-base-private` 74 条未提交改动，
  今天仍是 74 条、HEAD 仍是 09-02 的 `e4c9a939`，但那些用例现在全绿），2 条本就判为 flaky。即：**那 9 条不是本分支的红，
  且现在整棵树 0 红**；结论「9 红与本单无关」成立，但当时给 7 条写的那个 KB 归因没有被今天的读数证实，只能算未证伪。
- 上一轮（填价前）读数留档：`bash scripts/run_main_gate.sh` @`8361b7ac` 干净树：**7744 passed / 9 failed / 15 skipped / 1 xfailed**，640.7s；
  收据 `~/.finance-runtime/test-receipts/20260904T182620Z-8361b7ac.json`；`check_test_receipt.py <收据> --expect-revision $(git rev-parse HEAD)
  --base-drift-max 5` → **exit 0**（revision / 解释器 / 依赖指纹 / 干净树 / 基座漂移 4≤5 全 ✓）。
  9 红逐条对待：**7 条在纯净基线 `c6e702a6`（临时 detached 检出树 `/tmp/fwp-baseline-c6e702a6`，用完已删）上同样红**——
  `test_ask_clarify_planner::test_parallel_and_serial_compose_identical`、`test_conversation_orchestrator::test_skill_answer_owner_bypasses_generic_ask_and_renders_its_contract`、
  `test_generic_research_owner::test_ask_owner_path_skips_fixed_answer_template`、`test_kb_search_coarse_pipe::test_jcet_replay_delivers_body_not_half_url_or_path_line`、
  `test_kb_selection_noise_filter::test_jcet_replay_noise_heads_drop_and_body_fronted`、`test_market_watch_delivery_gate::test_gate_liveness_signal_on_zero_drop`、
  `test_market_watch_delivery_gate::test_orchestrator_strips_owner_prose_threshold_clauses`（ask / kb_search / market_watch 一族，
  知识库仓 `~/knowledge-base-private` 74 条未提交改动、`wiki/entities` 09-04 18:01 被改，是「冻结集对 KB 解析态不封闭」的老形状，
  不碰本单任何文件）；**2 条隔离复跑绿**：`test_kb_search_coarse_pipe::test_same_query_delivery_chars_beat_legacy_800_cap`（基线过、本树全量红、
  本树单跑 3.4s 绿）、`test_workbench_conversation_integration::test_real_conversation_round_trip_persists_skills_sse_and_three_turns`
  （本树定向 350 绿那轮已过）。同时段其他树全量 0 红（如 `bd469fb2` 7725P @18:03Z），KB 改动发生在 18:01 之后。
- ruff 0（整仓）；`layer_audit.py` ERROR 0（@`2ac58896`）；`check_unread_fields.py` 无新增；pre-commit 10 道每次提交全过。
- **报表 · 合成 5 run**（3 新格式含 1 估算 + 2 旧格式；`test-judge` 10/50 元/M）：
  ```
  run 数：扫描 5，进统计 5；判官有记账 3（判官未调用 0），判官未记账（旧格式）2；估算记录占比 33.3%
  | 侧 | n | input tokens | output tokens |
  | 写手 | 5 | 40,000 / 40,000 / 56,000 | 1,500 / 1,600 / 2,600 |
  | 判官 | 3 | 20,000 / 20,333 / 36,000 | 1,000 / 1,033 / 1,800 |
  | 合计 | 3 | 60,000 / 60,333 / 68,000 | 2,100 / 2,533 / 3,220 |
  | 侧 | n | 元/次（中位 / 均值 / p90）**（含估算）** |
  | 写手 | 5 | 0.3480 / 0.3648 / 0.5208 |   ← glm-5.2 8/28：[0.174,0.282,0.348,0.456,0.564]
  | 判官 | 3 | 0.2500 / 0.2550 / 0.4500 |   ← [0.015,0.25,0.5]
  | 合计 | 3 | 0.5980 / 0.6170 / 0.7452 |   ← [0.471,0.598,0.782]
  ```
  全部手算对照（p90 线性插值）钉在 `test_research_cost.py`。
- **报表 · 真实旧 run 目录**（`linxiaoqi5111/runs`，`--since 2026-08-12`，已进仓 `intelligence/eval/measurements/research-cost-2026-09-05.{json,md}`）：
  扫描 495，进统计 **356**（与 BP §7.3 同一集合：均值 48,293 / 1,719 一致；中位 37,389 / 1,398、p90 79,860 / 2,898 与 BP 的
  37,504 / 1,403、79,988 / 2,930 差在分位算法），**判官有记账 0 / 判官未记账（旧格式）356**；写手按实际模型 113 个 GLM run
  0.2866 / 0.3265 / 0.6005 元/次，243 个 `gpt-5.6-terra` run 价目表未录；`--writer-price-model glm-5.2` what-if：
  **0.3393 / 0.4345 / 0.6979 元/次**（BP 0.34 / 0.43 / 0.72）。

## 未验证 / 已知边界
- **工单目标 9 / 验收最后一条（≥ 20 个新 run 真库读数 → 交接 + BP §7.3）本轮做不到**：依赖改动上线后积累数据。BP 未动，
  `【待填：Alpha 期含判官的全口径实测】` 原样。上线后：`python -m intelligence.eval.research_cost --runs-root $FORESIGHT_USERS_DIR/linxiaoqi5111/runs --since <上线日>`。
- **验收第一条「新 run 的 continuous-episode.json 里 metrics.judge_usage 存在、calls ≥ 1」**只在测试里验过（adapter 全等断言 +
  `_episode_metrics` 单测），没有真实新 run——同上，需上线。
- ~~**grok-4.6 价目为 null**~~ **已填（2026-09-05 收尾轮，`7cbe5af6`）**：官方页 `https://docs.x.ai/developers/grok-4-6` 今天可达，
  list = $2.00 / $6.00 每 M（同页 models 注册表 `promptTextTokenPrice=20000` / `completionTextTokenPrice=60000` /
  `cachedPromptTokenPrice=5000`，单位 1e-4 USD 每 M，与页面文字互证）。价目表现在两行：
  `grok-4.6-build*`（生产 CLI 实付档 $0.34 / $1.02 / $0.085）在前、`grok-4.6*`（API list）在后，顺序有语义——
  `grok-4.6*` 也 fnmatch 得上 `grok-4.6-build`。`DEFAULT_JUDGE_MODEL` 随之改成 `grok-4.6-build`（用户 2026-09-05 拍板：
  生产判官走 CLI，按 list 计价会把判官侧放大 5.9 倍）；API 备胎判官取价用 `--judge-model grok-4.6`。
  USD→CNY 走价目表新增的 `fx` 块（中国货币网中间价 2026-09-04，6.7787），汇率与折算分离。
  **build 档那三个数是反解来的，不是官方公示**：xAI 没有单独公示 CLI 档，是用 list × 0.17 三档同系数复现 CLI 自报
  `costUSD=0.00757112`（19,326 in / 970 out / 128 cache_read；`total_cost_usd_ticks=75711200` 同值，8 位有效数字吻合）。
  复核办法：重跑判官探针比 `costUSD`；CLI 换版或 xAI 调折扣时这行会静默过期，`test_cli_selfreported_cost_reproduces_from_the_build_row`
  只钉住「这三个数与 0.00757112 自洽」，钉不住「今天的 CLI 还按这个折扣计费」。
- **>200k 上下文档未建模**：官方对 grok-4.6 超 200k 上下文翻倍计价（$4 / $12），价目表没有这一档；判官提示词约 2 万 token，
  够不着这道坎，真出现长上下文判官会少算一半。
- 判官模型名不在产物里，报表按 `--judge-model`（默认 grok-4.6）取价；备胎 API 判官接管的 run 会被按 grok 价算——
  `judge_usage.usage_source=mixed` 能看出混源，但分不出各自 token。要精确需在 `judge_usage` 里落 model（另单，需读者）。
- 缓存命中 token 未单列：grok `input_tokens` 不含 `cache_read`（样本 0.7%），GLM `prompt_tokens` 含 cached——报表统一按输入价算，
  偏差方向是少算缓存那部分。
- 估算分支只在 CLI payload 无 usage 时触发，当前 grok 1.0.5 / 1.0.13 都带 usage，生产里预期 `estimated_share=0`；若出现 >0 就是
  CLI 版本变了，先看 `raw.json` 形状。
- `_post_chat_synthesis` / `_post_chat_message*` 未改（工单只点名 `_post_chat`）；写手 token 仍以 `outcome.usage` 为准，
  台账里写手记录的 token 为空、`purpose` 为空（`tokens_by_purpose.unlabelled`）。
- ~~全量门禁跑在 `8361b7ac`（合 main 前）……批次门禁应由验收方在合并时点重跑。~~ **已重跑**：见上「合并点全量门禁」，
  `80f6a01e` 7760 P / 0 F，基座漂移 0（`git log gitea/feat/judge-token-usage..gitea/main` 为空，merge-base == `gitea/main`）。
- 快路径（`deterministic_fast_path`）的 metrics 不带 `judge_usage`——读者靠写手 usage 为 0 把它们归入 `writer_unrecorded_runs`。

## 下一步
1. **合 main 这一下由用户点**（2026-09-05 收尾轮确认的分工）。合并点门禁读数与收据见上，PR `mergeable=true`、基座漂移 0。
   合并后切流按 cutover 流程（本单改 runtime 记账，需上生产才有新 run）。
2. 上线积累 ≥ 20 个新 run 后跑
   `python -m intelligence.eval.research_cost --runs-root /Users/a77/.local/share/finance-workbench/users/linxiaoqi5111/runs --since <上线日>`，
   把写手 / 判官 / 合计三列与元/次回填 BP §7.3 与本文；`estimated_share > 0` 时 BP 里注明「判官侧为估算」。
   **回填时连口径一起写**：判官侧按 CLI 实付档（¥2.3048 / ¥6.9143 每 M），不是 API list。
3. ~~填 grok-4.6 价目~~ 已完成（见上）。首个新 run 落地后做一次对账：把 `metrics.judge_usage` 的 token 代进价目表算出的元/次，
   与同一次调用 CLI 自报的 `total_cost_usd × 汇率` 比——对不上就是 build 档折扣变了，改 `llm-prices.json` 而不是改报表。
4. 可选另单：`judge_usage` 落判官模型名 / 捞 CLI 自报 `total_cost_usd`（都要先有读者，否则 unread-fields 门禁拦）。
   捞 `total_cost_usd` 能把上一条对账变成自动的，优先级比模型名高。
5. INDEX #23 行在合入后改「✅ 已合（PR #593）」。

## 踩过的坑
- **grok CLI 的 `input_tokens` 比提示词字符估算大 15 倍**（19,326 vs ≈1,240）：`--system-prompt-override` 之外 CLI 仍塞自己的
  上下文。若当初走估算分支，判官成本会被低估一个数量级——「先探明再设计分支」这条省下的不是代码量，是错一个量级的结论。
- 既有测试把 `complete_grok_cli` monkeypatch 成 `(provider, messages, timeout)` 三参函数，任何加 kwarg / 换返回类型的方案
  都会在 `conformance_transport` 上炸——`str` 子类是唯一不动测试替身的带数方式。
- `ps -eo command | rg -c 'python -m pytest'` 会把 **自己的命令行**也数进去（zsh -c 包装 + rg 进程），空闲时也报 3–4；
  要用 `ps -eo pid,etime,command | rg 'python -m pytest|Python -m pytest' | rg -v ' rg '` 看进程列表才准。
- Cursor shell 壳一次楔死在 bootstrap `cat <&3`（12 分钟假等待，pytest 根本没起），与 `docs/prediction-ledger.md` 08-27 记的形状相同；
  `ps -o ppid` 看到子进程只有 `cat` 即可判死，kill 后重发命令。
- 全量 pytest 同一时段有另一棵树的 `run_main_gate.sh` 并跑，`latest.json` 被覆盖——按指令只读自己的 `<stamp>-<rev8>.json`。
- `report.json.llm.model` 才是写手真实模型（`runtime_backend=continuous_glm` 不等于 GLM）：8 月 243/356 个 run 跑在 `gpt-5.6-terra`。
- `ruff.toml` target py39：`with (a, b):` 括号多上下文写法虽在 3.12 可跑，改成嵌套 `with` 才与声明一致。
