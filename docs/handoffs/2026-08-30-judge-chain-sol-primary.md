# 2026-08-30 · 语义判官链收口：sol 长期主判官 + grok 备胎（09-02 激活）

## 背景（不读这段会误判后面每个决定）

判官供给史：grok-cli 曾是主判官（独立于合成链的双审查设计）→ 2026-08-28 grok
402 断供，运维手工改 env 把判官切到 sol（`gpt-5.6-sol` 经 x.ailzd.com 中转），
env 注释当时写「额度恢复当天切回」并留了回切备份。2026-08-29 rejudge 积压清账
（97 行）把断供的真实代价第一次量化：**44 条可重放里 95.5% overturn**——判官
宕机窗口交付的答案九成五本该进修复轮，其中至少一条实打实的数据矛盾句（R4
「逐日递减」与自引证据冲突）。且积压横跨 08-19..28 每一天：这是慢性病，不是
单次事故。由此升格出判官备链工单（`R-20260829-03`，PR #515）。

2026-08-30 用户拍板：**sol 长期当主判官；grok 下周三（09-02）额度恢复后以
备胎身份回归**——推翻 env 注释里的「切回 grok」计划。拍板时基于的信息：
sol 服役表现（29a/29b 两次切流探针 judge_unavailable=0；44 条离线重放裁决
抽查质量可用，还抓到生产判官漏掉的真实内容瑕疵）+ grok 断供到 09-02。

## 按发现顺序

1. 清账归因 → 备链工单 `R-20260829-03`（PR #515）：`judge_provider_chain()`
   = 主（解析逻辑不动）+ 显式备胎（新词表 `LLM_JUDGE_FALLBACK_*`）；verifier
   槽位轮转（attempt 0 主、1+ 备，主放弃且窗口未烧穿才换人）。
2. 用户问「不是用 sol 做判官了吗」→ 发现我按 env 旧注释把激活手册写成
   「grok 主 + sol 备」，与用户意图相反。
3. 用户拍板 sol 长期主 → 发现表达力缺口：备胎词表只会构造 HTTP 形态，而
   grok 在本机是 CLI 传输，「sol 主 + grok 备」**配不出来**。
4. 补 CLI 形态备胎 `R-20260830-01`（本 PR）：`LLM_JUDGE_FALLBACK_BACKEND=
   grok-cli` → 构造 transport=cli 的 `grok-cli-judge-fallback`；激活手册
   随之改写为 sol 主形态。

## 决策与被否方案

| 选了什么 | 否了什么 | 为什么 |
|---|---|---|
| 判官备链（主+显式备胎，槽位轮转） | 只靠 rejudge 事后补账 | 事后重放救不回已交付的未质检答案；95.5% overturn 是内容代价不是观测噪声 |
| 备胎用独立词表 `LLM_JUDGE_FALLBACK_*` | 复用 `LLM_JUDGE_MODEL`；从主链自动派生备胎 | 前者：CLI 主历史部署用它命名 grok 模型，共用互踩；后者：合成 provider 进判官链=相关自审，`judge_provider` 在案红线明禁「不静默退回相关自审」 |
| **sol 长期主、grok 备**（用户拍板 2026-08-30） | env 注释的「额度恢复切回 grok 主」 | 拍板依据=sol 服役读数（两次切流探针 judge_unavailable=0、44 条重放裁决质量抽查可用）；grok 断供史（402 慢性）反而更适合当备。**该依据若变（sol 中转劣化/成本变化），此决定应重议** |
| 备胎 CLI 形态走 `FALLBACK_BACKEND=grok-cli` | 给 grok 找 HTTP API 端点当备 | 本机 grok 只有 CLI 订阅通道；CLI 形态复用 `complete()` 既有 cli 分派与 #513 钉住的传输契约，零新传输 |
| 槽位轮转不加尝试槽（MAX=3 不动） | 给备胎独立时间窗 | 窗口记账与释放安全账是精调过的（多测试钉住）；加槽=改预算语义，收益不明 |
| 09-02 激活与切流合并为一次中断 | 现在就切流 #514-#516 | 备链代码在 sol 单主下休眠（链退化单主，行为逐字节一致），单独切收益为零 |

## 验证与收据

- #515（链本体）：TDD 3 救场钉（含生产真实 402 形状）+5 链构造钉；变异
  「枯死换人判定」精确杀；判官面 174P 零回退；全量 7286P/0F @`fb5a502a`。
- 本 PR（CLI 备胎）：sol 主+grok 备链构造 2 钉；判官面 188P；全量 **7291P/0F/15S/1xf**
  干净树 @`2d4b4215`（收据 `~/.finance-runtime/test-receipts/20260829T170007Z-2d4b4215.json`，
  `check_test_receipt.py --expect-revision 2d4b4215` exit 0）。
- rejudge 清账：44 收据 + 汇总 `intelligence/eval/runs/20260829T140500Z-rejudge-drain-sol.json`；
  49 条旧式行永不可重放的根因已由 `R-20260829-04`（PR #516，行即夹具）根治。
- **不成立的结论别引用**：95.5% overturn 是「sol 按生产提示词字面从严 + 未修复
  轮答案」的读数，不能直接当「生产答案质量分」用；其中休市披露句判罚属可辩护
  从严，非全部真瑕疵。

## 09-02 激活（接手者照做）

激活手册全文在 `docs/superpowers/specs/2026-08-29-judge-fallback-chain-workorder.md`
（已按 sol 主形态更新）。要点：sol 三行**不动**；新增 `LLM_JUDGE_FALLBACK_BACKEND=
"grok-cli"` + `LLM_JUDGE_FALLBACK_MODEL="grok-4.6"` + `LLM_JUDGE_GROK_BIN`；
顺带切流当日 main（含 #514-#516 与本 PR）；kickstart；验证=readiness 13/13 +
health 三读 + 长电探针，另加一条判官验证：人为断中转不可行，就看激活后首个
研究 run 的调用台账 judge provider 记录正常即可。

## 不要做的

- **不要取消注释 `LLM_JUDGE_BACKEND` 三行**——那会把 grok 抬成主判官，与拍板
  形态相反（工单手册里有同样的反向提醒）。
- **不要把备胎配成同中转的另一个模型**——中转挂时主备一起死，链形同虚设；
  grok CLI 的价值恰在传输独立。
- **不要在 sol 服役正常期间为本链单独重切 8792**——休眠代码，切流零收益。
- 台账四行 `R-20260829-01..04` + `R-20260830-01` 的 live 腿都是自然观察窗，
  不需要人工触发。

## 工具沉淀盘点

- sol 子代理批量裁决的 **prepare 步已固化**：`scripts/rejudge_pending.py
  --export-fixtures DIR`（R-20260829-04）。
- verdicts/apply 两步仍是手法（裁决方是 Cursor 子代理，进不了仓内脚本）：
  流程=夹具 × 生产判官原版提示词（`_judge_system_prompt` + `dumps_judge_request`
  渲染）→ 子代理逐批裁决出 `{passed, rejected_sentence_indexes, issues}` →
  `run_offline_rejudge` 落收据。全程收据链见清账汇总 JSON。
- 可迁移模式（已在台账留痕，未另立 10_knowledge 条目——单例待第二次复用再
  提炼）：「主备链的备胎必须用独立词表 + 显式 backend 优先规则」，防主备
  共用变量互踩；这在任何多 provider 降级链上都成立。
