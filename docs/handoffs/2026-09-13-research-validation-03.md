# 2026-09-13 · 03 方法验证与真实前向概率实验 v1 —— 决策留痕

分支 `feat/research-validation-03`，代码提交 `e38d6a63`，基线 `gitea/main@5fb13a8c`。写完不改。

## 背景

总合同 `docs/superpowers/specs/2026-09-13-research-evolution/README.md` 把「时间长河后续优化」拆成六轨并行；03 负责**同一冻结案例的删轨消融 + 事前概率的到期评分**，独立开发，06 接入 Workbench。规格的关键约束：

- 首版人工概率 / 确定性规则，LLM 概率只作历史演练；不训练、不晋升、不荐股、不改情景树。
- 一天一个胜出 bool 做主检验；平均 Brier 差只描述；p0=0.5 是对称胜负不是市场上涨率。
- eligible 由冻结身份与曝光记录派生；任何输入自填 `eligible=true` 拒收。
- v1 不改既有文件；`api/app.py`、`userspace`、ledger-map、UI 归 06。

任务 0 实测：`stats.block_bootstrap_readout` 与 `readout` 都用 `bool(x)` 强转输入，+0.1 与 −0.1 同为「命中」——这是规格点名要堵的洞；本轨在自己这一侧堵，不动既有统计平台。

## 按发现顺序做了什么

1. 建干净工作树 → 跑四组回归（117 passed）→ 读 `stats / rules / compiler / runner / method_validation.{protocol,store,study} / userspace / replay_engine 字段 / dual_blind._calibration_metrics`，登记签名映射。
2. 写 `contracts.py`：先定「语义身份」——哪些字段进 SHA-256、哪些是记录时间。写到 receipt 时发现 `as_of_now`（now 的市场日）也是记录时间伪装，从身份里剔除。
3. 写 `repository.py`：沿用 `method_validation.store._publish` 的 tmp+`os.link`，但把「已存在」从抛错改为返回原件——同意图重试与异意图冲突必须能区分。
4. 写 `service.py` 六函数；写 `scoring.py` 时发现日期等权 vs 配对等权的差别必须在测试里钉死（`test_daily_deltas_equal_weight…`）。
5. eval 侧：编译器只产「条件成立集」，答不了 False vs Unknown → 用 Python 在标签行上做三值合取；两桶 recipe 进代码白名单。
6. 首轮 89 测试 3 红：夹具生成公式让「dual_red 真 + top10 未知」的日子不存在（改公式）；换名 study 全暴露时状态是 `insufficient` 而非 `descriptive`（改设计，见决策 3）；区间相交把 3 个 case 都标暴露而测试只写了 1（改测试、保留保守口径，见决策 4）。
7. 变异探针 6 处各至少 1 红；四组回归 117；全量 8432 passed；pre-commit 11 道过；提交 `e38d6a63` 后在最终 SHA 重跑验收拿收据。

## 决策与方案对比

### 1. 外来曝光的判定口径

| 方案 | 评价 | 结果 |
|---|---|---|
| 同谱系 + 同 framework_hash 的其他 study 不算外来 | 打开「只留赢家」：看完 A 的逐日结果，开同方法的 B 只覆盖赢的日子，B 仍 eligible | **否** |
| 任何非本 study 写的曝光都算外来；同方法重试 = 重评同 study_id（同意图返回原件） | 关掉事后挑窗；子 study 只要覆盖**新**事实就不受影响 | **选** |
| 只看 lineage_id | 换 lineage 即洗白，与规格「换 study_id / lineage_id 均不能洗白」直接冲突 | 否 |

### 2. 曝光身份用什么匹配

| 方案 | 评价 | 结果 |
|---|---|---|
| case_id | 改事件描述 / 宇宙 ref / 阈值都会换 case_id → 洗白 | 否 |
| (entity_type, entity_id, as_of, horizon) 精确键 | 看过 S1@D0 的 D+1..D+5，S1@D1 的 D+1..D+5 共享 4 天，精确键判「未见」 | 否 |
| 同实体 + 结果区间 [as_of, outcome_due] 相交 | 保守：D0 曝光会连带 D1..D4 的 case；发现窗 / 验证窗按日历 purge 后天然不相交，正常实验不受影响 | **选** |

### 3. 已暴露的 case 在评估里怎么处理

| 方案 | 评价 | 结果 |
|---|---|---|
| 从配对里剔除 | 全暴露时 n_pairs=0 → 状态 `insufficient`，读者分不清「样本不足」和「你已经看过答案」 | 否 |
| 仍算描述性读数，study 级 eligible=false，verdict 置空、`verdict_if_eligible` 留参考 | 数字就是数字；不能升级为声明；`holdout_exposed_pairs` 单列 | **选** |

### 4. 期末未到时的收据

| 方案 | 评价 | 结果 |
|---|---|---|
| 照常给累计平均差与 verdict，标 pending | 「pending 但已经 supported」会被读成结论；规格要求累计评分封存 | 否 |
| 只报 pending 数与单项 Brier，平均差 / verdict / 胜负计数置 None | 与规格 §7 一致；到期后同一函数自动切到确认检验 | **选** |

### 5. forward 协议冻结时限

| 方案 | 评价 | 结果 |
|---|---|---|
| 必须严格早于 forward_start 一天 | 06 规格允许「以有效 D0 输入冻结首例」——当天早上建协议、盘后登记是合法流程 | 否 |
| 冻结日 ≤ forward_start（当日可）；登记仍卡 D0 盘后 | 冻结在登记之前由时序保证 | **选** |

### 6. 人工概率的模式边界

| 方案 | 评价 | 结果 |
|---|---|---|
| 允许人工给历史 case 填概率 | 填的人知道结局，不是实验 | 否 |
| `human_manual` 只进 forward；`historical_rule` 只收确定性；`historical_llm` 只收 replay 原件 | 三种模式不混；两臂都是人工 → 只描述 | **选** |

### 7. 残留信息的拦截时机

冻结时静态拒绝（规则标签 ⊄ allowed_fields、或与删轨字段 / 派生量相交）**加** 运行时对实际 projection 复核（`isolation_verified=False` → eligible=false）。只做运行时会让坏协议先落盘再发现；只做冻结时无法覆盖 06 将来接入的非规则臂。

## 验证与收据

见 `docs/superpowers/plans/2026-09-13-research-evolution/03/PROGRESS.md`「验收命令与收据」。三条不成立的读法：

- 夹具全 synthetic：`test_full_forward_flow…` 得到 `supported` 只证明代码路径，**不是**任何方法有效的证据。
- 全量套件排除了 `test_codex_sandbox.py`（本机已知随机红）——它没跑，不是「已知红带过」。
- 变异探针在对话内执行，没有沉淀为脚本（`scripts/` 不在 03 白名单）；下一任若要复现，PROGRESS 里列了六处改法。

## 后续要做 / 不要做

要做（06）：注入 `userspace` 根与可信时钟；实现 `PitVerifier`；在 ledger-map 登记对象布局；Workbench 收据入口复用 `read_receipt`（它先记曝光）；首例真实 D0 按规格 §9 冻结，非交易日预建下个合格日协议。

不要做：不要为了让 fixture 出 `supported` 而调 `analysis_policy`（冻结校验会拒绝，且那是规格明令）；不要给 `Repository` 加 `os.replace` 路径（覆盖会毁证据，7 个测试盯着）；不要把 `holdout_exposed` 的 case 从描述性读数里删掉（决策 3）；不要在 `foreign_exposures` 里恢复「同框架不算外来」（决策 1）。

## 工具沉淀盘点

| 问 | 答 |
|---|---|
| 同一手工排查做了两次以上？ | 变异探针跑了 6 次同一形状（改一处 → 跑 → 复原）。候选脚本：`scripts/mutation_probe.py`（输入：文件 / 旧串 / 新串 / -k 表达式；带 `PYTHONDONTWRITEBYTECODE` 与 `__pycache__` 清理）。**未写**：`scripts/` 不在 03 白名单；交 06 / 集成人决定归位 |
| 只在 /tmp 或对话里跑过的脚本？ | 同上一条 |
| 现有门禁的洞？ | `stats.readout / block_bootstrap_readout` 的 `bool()` 强转不是门禁洞，是接口契约；本轨用 `strict_bools` 在调用侧兜住，并保留反例测试 |
| 可迁移模式？ | 「任何非本对象写的访问都算外来，同意图重试走同 id」——通用的 holdout 防复用形状；`~/harness-reference` 树脏（session facts 报脏 1），未写入，留给整理者 |
