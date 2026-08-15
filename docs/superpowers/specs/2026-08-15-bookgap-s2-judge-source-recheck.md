# S2 · 语义 judge 模态切换：数据源回查（引入新信息）

- 索引：`2026-08-15-bookgap-index.md` · 靶：第 10 章 🔴 · 仓：finance · 优先级 P2
- **串行依赖：R-24（E-007 修复）落地后再动 verifier 文件；见索引 §2**

## 1. 背景（证据）

- 08-10 审计核心发现 [实测]：semantic judge 用**同一模型**读**同一份
  草稿+同一批证据**，无外部反馈——按书第 10 章准则「协作是否引入生成时
  不存在的新信息」，正好落在无效协作那一类，却每次付 15+7.5+7.5s。
- 书给的正确方向（第 4 章模态切换）：不是第二个模型重读，而是换模态
  检验——对我们即：**拿 claim 回查 DuckDB 复算**、或用另一 provider 的
  检索结果交叉核对。
- 书的成本警告：多 Agent token 可达 15 倍，token 用量解释 ~80% 性能差；
  所以本 spec 是**实验臂先行**，不直接上生产。

## 2. 目标 / 非目标

- 目标：给 judge 增加一条**可选**的「数值 claim 回查」路径：从草稿抽取
  可复算断言（如「A 股 X 板块今日涨幅 Y%」），用 `finance_query` 只读
  通道复算，回查结果作为 judge 的额外输入。
- 目标：先出**价值测量**：同题对照（回查臂 vs 现状臂），量化
  「新信息让 semantic 判定翻转了几次」和额外耗时/token。
- 非目标：不换 judge 模型（书说了换模型解决不了信息问题）；不动
  judge 窗口数值（S3 的缝）；默认关（`ASK_JUDGE_RECHECK=off`），
  本 spec 不改生产行为。

## 3. 改动面

| 文件 | 改什么 |
|---|---|
| `intelligence/services/judge_source_recheck.py`（新） | claim 抽取（规则先行：带数字+日期的句子）、finance_query 只读复算、比对报告 `{claim, source_value, verdict}` |
| `intelligence/services/episode_semantic_verifier.py` | **只加一处**开关钩子：recheck 报告注入 judge 上下文；不碰 `_marker_loss_partial_public`（R-24 保留地）、不碰窗口函数（S3） |
| 测试 | 新模块单测（抽取、复算、比对、超时 fail-open）+ verifier 钩子开关测试 |
| 实验 | 10 题带数值断言的对照收据，进 `docs/verification/` |

## 4. 验收判据（预注册）

1. 开关 off 时字节级不影响现有路径（现有测试全绿，无新分支进入）。
2. 开关 on 夹具：植入一条与 DuckDB 不符的数值 claim，recheck 报告标
   `mismatch`，judge 上下文里能看到该报告。
3. 复算通道只读（duckdb `read_only=True`），且单条 claim 复算 ≤3s，
   总额有硬顶（不吃 synthesis reserve）。
4. 对照实验报告：给出「判定翻转次数 / 额外秒数 / 额外 token」三个数，
   并按书的准则给出**值不值**的建议（可以是否定结论——否定也算交付）。

## 5. 风险

- claim 抽取规则化会漏（召回不全）：接受，v1 只要 precision——抽到的
  必须可复算，抽不到的不硬抽。
- 与数据层同步窗口撞车：复算失败按 fail-open 记 `recheck_unavailable`，
  不影响 judge 主判。
