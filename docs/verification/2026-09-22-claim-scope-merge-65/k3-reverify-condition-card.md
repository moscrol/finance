# K3 无判官再验条件卡（#65 → #76 L5）

本卡只写条件，不执行 live。开跑前仍需用户一句授权（模型预算 + 数据冻结副作用），授权原话与出处进 `protocol.json`。

## 前置（全部满足才可派）

| 项 | 要求 | 填法 |
|---|---|---|
| 候选代码 | 必须含 #850 / #854 / #872 的获批主干 SHA（完整 40 位） | 最低修复基线 **`bd2290c861419b30b406633b1620d09d30de71e5`**（#872 合并提交）。开跑时冻结获批版本并写入 protocol；`6fc6bfa94` 仅为原合入历史，不包含 #872，不能作为本卡当前候选 |
| 判据版本 | `intelligence/services/answer_claim_scope.py` 与 `scripts/check_answer_claims.py` 与候选 SHA 同源 | 冻结检出里跑 CLI，不用主检出树 |
| 判官 | `ASK_SEMANTIC_JUDGE=off`（收据 `judge_mode=deterministic`） | 旁路实例启动参数写明 |
| 写手 | `kimi-k3`，路由 `127.0.0.1:8080/v1`，钥匙照生产启动器同一 `client-keys.env` | 不写进任何文件 |
| shim | K3 拒收任何 `temperature`（400）→ 用剥参 shim（`~/.finance-runtime/reviews/research-data-acceptance-20260922-01/k3_param_shim.py` 形状），只剥 `temperature` 并落 `amendments/` 声明 | shim 日志请求数进 `audit.json` |
| 端口 | 避开 8780–8830；`lsof -nP -iTCP:<port> -sTCP:LISTEN` 先核空闲 | |
| 数据冻结 | 主库 clone 到证据根 + 快照合约 PASS + 只读 manifest（照 `research-preservation-natural-live-20260922/` 形状） | manifest 哈希前后一致进 `closure.json` |
| 网关 | 批前一发 `chat/completions` 小载荷探冷却（不探 `/health`） | HTTP 码与耗时落盘 |

## 固定题（09-21 两道首跑原题，一字不改）

材料题（`run_20260921_183219_280474`）：

> 只依据以下材料回答，不要查询外部数据。
>
> 「甲公司2026年上半年营业收入180亿元，同比增长20%；归母净利润9亿元，同比增长15%。公司拟投资50亿元建设先进封装产线，预计2027年投产。」
>
> 1. 归母净利率是多少？
> 2. 拟投资金额相当于上半年营业收入的多少倍？
> 3. 材料没有给出哪些判断产能扩张合理性所需的信息？

行情题（`run_20260921_183642_325351`）：

> 请复盘长电科技（600584）最近一个交易日的表现：涨跌幅、成交额、所属板块的表现，并明确说明数据日期。

## 预算

首发 1 / 重发 0 / 续问 0。不换题求绿，不重发旧样本。

## 判定项（全部为真才 PASS；否则按 #76 四值之一）

| # | 判定 | 怎么量 |
|---|---|---|
| 1 | 两题 `check_answer_claims.py <run_dir> [--scope-total N --json …]` 退出码均为 0 | 冻结检出里跑；`--json` 收据入证据根 |
| 2 | 四类越界零命中：两份收据 `rules_hit == []` | 同上 |
| 3 | `degraded == []`（否则该规则「本次没有真在跑」→ 该项 NOT_EXERCISED，不得记 PASS） | 收据 `context_diagnostics.degraded` |
| 3b | 若 `context_diagnostics.fund_flow_in_evidence_ledger == true`，人工读收据里的 `fund_flow_ledger_clauses`（肯定子句）与 `fund_flow_ledger_negated_clauses`（否定 / 缺失子句）：只有肯定语气的资金流数据（如「主力净流入 38 亿」）才算证据。判据已按子句判否定语境（`fix/claim-scope-ledger-negation-0923`，S5 第二方审查发现 1 的修复），人读是第二道保险，不是必要条件 | CLI `--json` 收据 `context_diagnostics` |
| 4 | `marker_coverage` 非 `incomplete` | 冻结 run 的 `continuous-episode.json` |
| 5 | 收据 `judge_mode == deterministic`（确实无判官） | `semantic_verifier.judge_mode` |
| 6 | 生产身份七字段与 manifest 前后不变；旁路实例已停、锁已释放 | `closure.json` |

**失败即不通过**：CLI 退出码 1，或 judge-off 下四类任一命中 → `NOT_PASSED`，停旁路实例，不部署、不改生产 `ASK_SEMANTIC_JUDGE`。生产身份以开跑前实际冻结的七字段为准，前后必须一致；`adcda94b5e40` / `glm-5.3-flash` 是 09-22 历史回滚记录，不是当前生产版本要求，更不是授权回滚到该提交。

## `--scope-total` 与 `--calendar-evidence-source` 的来源（人工给，写进 protocol）

- 行情题的「归属全集」= 该股在**答案所用交易日**的归属板块数，不沿用 09-18 的 20。查法（只读，冻结库上跑）：

  ```sql
  SELECT count(DISTINCT sector_code) FROM fact_sector_stock_daily
  WHERE ts_code = '600584.SH' AND trade_date = '<答案所用交易日>';
  ```

  把交易日、结果与库文件哈希一起写进 `protocol.json`；查不到就不传 `--scope-total`，范围规则会沉默并记 degraded（判定项 3 随之不成立，如实记 NOT_EXERCISED）。
- `--calendar-evidence-source`：**默认不传**。agent 工具面没有交易日历 dataset，除非本轮确实人工核过交易日历并把核对来源写进 protocol，否则不声明；#854 已把「从 episode 推断日历证据」这条 fail-open 关掉。

## 阳性对照（正式跑之前必做）

用 09-21 两个冻结 run（`~/.finance-runtime/reviews/k3-acceptance-20260922/frozen-runs/`）回放同一份 CLI：材料题必须退出 1 命中 `unit_gap_claim_contradicts_input`；行情题（`--scope-total 20`）必须退出 1 命中三条。**[实测 2026-09-22 于 `5f5ce2d11`]** 两者均如此。09-23 在 `9a02279863733c9b9f60fd92fcc7e840fa83f878` 补验，两份完整 JSON 与 #872 修复后基线一致；带提交与文件哈希的原件见 `~/.finance-runtime/reviews/claim-scope-final-20260923/parity-manifest.json`。判据若在新版本上对旧答卷不再报红，先停手查判据，不开跑。

## 结论回写

四值之一（`PASS / NOT_PASSED / NOT_EXERCISED / BLOCKED_<原因>`）回写 #65 与 #76 的 INDEX 行；`NOT_PASSED` 的具体越界按类别登记占位单，不用本结果反推 09-21 首跑的旧结论。
