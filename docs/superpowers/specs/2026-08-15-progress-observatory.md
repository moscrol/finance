# 进度观测台(Progress Observatory)——让生命周期推进可观测,不用问 agent

- 日期:2026-08-15 · 作者:检阅方 · 仓:finance(跨仓只读引用 kb / harness-reference / fde-os)
- 优先级 **P1** · 形态:文档 + 只读生成器,零 runtime 改动
- 关联:`harness-reference/DESIGN.md`(七层生命周期,参照系的骨架)、
  `2026-08-15-bookgap-index.md`(战役层数据源)、`docs/prediction-ledger.md`(闭环数据源)

## 0. 要解决的问题(证据)

1. **推进只存在于 agent 的上下文里**:用户要知道项目进度,只能问会话中的
   agent;换个会话、换个 harness,同样的问题要重新拼一遍。[实测:2026-08-15
   晚间会话即为此形态]
2. **手写状态文档必然腐烂**:`docs/handoffs/inflight/main.md` 在 8792 已切到
   `fdb23114` 之后仍写着 `32f73f53`,漏记两次切换——靠自觉更新、无 staleness
   闸门的状态文档,掉队是常态不是事故。[实测]
3. **已有看板只覆盖任务层**:dao flow 的任务看板观测「当下任务分层」,是
   战术视角;缺的是宏观视角——现在处于生命周期哪一层、离"好的设计"多远、
   每次合并让哪条曲线动了。
4. **观测的原料其实都在,只是没人聚合**:账本状态流转、spec 状态、验收批
   JSON、PR 合并史、8792 health——全部机器可读,零新埋点。缺的是一个
   **只读的聚合面**。

## 1. 定位与反腐烂原则

三个平面,一屏看完:

| 平面 | 回答什么 | 数据从哪来 |
|---|---|---|
| **参照系**(北极星) | 什么是好的设计;未闭合的最低层是哪一层;每层离"好"多远 | 七层×资产映射表(§3,手写、月级);章审计总评;bookgap S 状态 |
| **推进**(战役) | 本周合了什么;哪些战役 in_flight/blocked;下一个用户决策是什么 | roadmap L0/L1(手写薄账、周级)+ L2 全部生成(本机 worktree / 仓 PR 史分栏) |
| **运行**(读数) | 生产健康吗;交付率曲线在动吗;量具命中率如何 | `/api/health`、`intelligence/eval/runs/*.json`、账本 outcome 统计 |

反腐烂三原则(本 spec 的立法层,执行不得违反):

1. **手写的只许薄**:手写层只有 L0 阶段线 + L1 战役表 + 决策队列,总预算
   ≤120 行(同 handoff 3K 预算的精神)。任务层(L2)**禁止手写**,一律生成。
2. **生成的必须只读、幂等**:生成器不写仓、不调模型、不联网(gitea 本地
   API 除外);跑两次结果一致;缺数据源响亮失败,不出假页。
3. **状态流转必须过闸**:L1 状态枚举流转(如 S9 `in_flight→done`)若未同步
   roadmap,`--check` 非零退出,挂进合并前本地 CI 替身。列名与枚举值冻结在
   本 spec,各 agent 不得自拟(同账本「列名不自拟」纪律)。

立法三句(与三原则同级,见 `docs/adr/0001-observatory-legislative-core.md`):

1. **未闭合的最低层**:五问①不问「哪层质量最差」。沿 P0→P6 找第一根未达
   该层完成判据的 rung,只标这一个指针。禁止跨层打分或无出处红黄绿。
   下层未闭合时,上层资产可以在场,但闭合列记 `未评`,不得宣称该层已闭合。
2. **进步 ≠ 合并**:任意合并都出现在「本周合了什么」。只有声称的进步必须
   留下 L1 翻转或曲线位移;无位移合并只做可见,`--check` 不因此失败。
3. **L2 分栏**:worktree / ahead 是本机投影;PR 史是仓全局。推进平面 L2
   必须分「本机 / 仓」两栏,禁止混成一张表假装全局。

## 2. 数据契约(全部已存在,写死解析口径)

| 源 | 路径 | 取什么 | 口径 |
|---|---|---|---|
| 预测账本 | `docs/prediction-ledger.md` | Open/Closed 各表行数、fix_type 分布、confirmed/refuted 命中率 | 解析 markdown 表,`outcome` 列只认三值 |
| 书距索引 | `docs/superpowers/specs/2026-08-15-bookgap-index.md` | S1–S10 状态 | §4 执行记录有该 S 小结 = done;冲突矩阵在飞 = in_flight |
| 验收批 | `intelligence/eval/runs/*.json` | 每批交付率(evidence_bound>0 计数)、efh≠eb 数、slips 数、sha256 | 只读整批 JSON;批次按 `generated_at` 排序成曲线 |
| 生产身份 | `http://127.0.0.1:8792/api/health` | source_revision / dirty / pid | 与 main tip 比对得「生产落后 N 个合并」 |
| PR 史 | gitea API `/repos/a77/finance-workspace-private/pulls?state=closed` | 最近合并列表(编号/标题/时间) | 凭证走 osxkeychain,token 不落盘 |
| worktree 态 | `git worktree list` + 各分支 `ahead` 计数 | L2 **本机**在途视图 | 本机投影,不是仓全局;与 PR 史分栏,禁止混表 |
| 轮次记录 | `docs/handoffs/2026-08-15-runtime-trace-triage-loop.md` 附录 | 最近轮次与判定 | 只取「### Round」标题行与判定行 |

新增台账只有一份:`docs/roadmap.md`(L0/L1 手写薄账)。**建档时必须在
`docs/learning/ledger-map.md` 登记**(canonical 路径 + 唯一写入者 = 检阅方,
更新时机 = 每次 PR 合并/轮次收口)。

## 3. 参照系平面:七层×资产映射(冻结,月级评审)

列名冻结:`层 | 完成判据 | 当前刻度取数口径 | 本仓资产`。
七层定义以 `harness-reference/DESIGN.md` 为唯一事实源,本表只做映射:

| 层 | 当前刻度取数口径 | 本仓资产(2026-08-15 快照) |
|---|---|---|
| P0 领域契约 | uq15 密封题集存在 + 判分协议版本 | `UBIQUITOUS_LANGUAGE.md`、S5 uq15 |
| P1 底座 | dsh P0 五步完成数 / 5 | episode protocol、`fwp-wt-dsh-seams` |
| P2 观测 | trace_depth 档位 + 盲区清单未清项 | trace D3、`normalize_harness_trace.py` |
| P3 量具+诚实性 | 假绿事故数(月)+ 探针在场率 | 五态 tally、preflight 探针、身份三角 |
| P4 基线+循环 | 账本 confirmed/refuted 命中率 + 最新干净基线批龄 | 分诊循环、`prediction-ledger.md` |
| P5 质量战线 | recall@5 / 交付率 N=3 / uq15 分(三条曲线各自最新值) | S4 标注集、批 JSON、S2(未开) |
| P6 记忆/资产 | memory_gate 裁决量 + corrections 累计 | S6 候选链、corrections 台账 |

「离好多远」不打主观分:**每层只显示取数口径算出的客观刻度 + 该层
in_flight/blocked 的战役数**。禁止出现无出处的红黄绿。

## 4. 交付分期

### Phase 0 · roadmap 薄账 + 闸(半个执行方轮次)

- 新建 `docs/roadmap.md`:L0 阶段线(七层各一行,引 §3 口径)、L1 战役表
  (列名冻结:`ID | 战役 | 状态 | 完成判据 | handoff/spec 指针 | 谁在做`,
  状态枚举:`planned / in_flight / blocked_on_user / done / dropped`)、
  决策队列(等用户裁决事项,含提出日期)。
- `ledger-map.md` 登记;triage-loop 母本追加「收口时更新 roadmap 对应行」。
  dsh 母本 handoff 现只在未合入分支 `feat/dsh-absorption-p0-seams`,本 Phase
  不把该文件造进 main;该分支下次追加必须含「收口时更新 roadmap L1-DSH」。
- 新 handoff 头部约定:必须带 `roadmap_ref: <L1-ID>` 一行(闸只查在场性)。

### Phase 1 · 生成器 + 检查闸(一个执行方轮次)

- `scripts/progress_observatory.py`(新,stdlib-only):
  - `render`:按 §2 契约聚合,输出单文件 `var/observatory/index.html`
    (gitignored)+ 终端摘要;三平面各一节,L2 分「本机 / 仓」两栏全生成。
  - `--check`:schema 校验(roadmap 列名/枚举)+ staleness 校验(§1 原则 3,
    含 inflight/main.md 声称的 8792 revision vs live health 对账)+
    数据源缺失响亮失败。挂进合并前本地 CI 替身清单(不动
    `.pre-commit-config.yaml`,避开 dsh 在途面)。
- 单测:好/坏 roadmap 夹具各一(仿 skill 仓 validate-report 的
  good/bad testdata 纪律)。

### Phase 2 · 趋势层(一个执行方轮次)

- 扫全部历史批 JSON 出**交付率随批次曲线**;扫账本全部回填表出
  **命中率随轮次曲线**(confirmed / (confirmed+refuted));recall 基线
  随标注集版本。曲线内联 SVG,无 JS 依赖、无外网字体。
- 判据:至少两条曲线来自 ≥3 个真实历史点,零手填数。

### Phase 3 · 挂载面(可选,用户裁决后再开)

- 候选:dao flow 看板加「宏观页」外链本地 HTML;或 8792 workbench 加
  只读路由(动 runtime,须走部署窗);或 gitea 渲染 roadmap.md 作为
  低配入口(Phase 0 起即可用)。本 spec 不预设选型,拿 Phase 1 的
  实际使用体感来定。

## 5. 验收判据(预注册)

1. **五问验收**(核心):用户不问任何 agent,打开观测台 60 秒内能回答——
   ① 现在未闭合的最低层是哪一层;② 本周合并了什么;③ 账本还有几条 open;
   ④ 生产落后 main 几个合并;⑤ 下一个等我裁决的事项是什么。
   验收方式:检阅方按五问逐项截图对答案。
2. 生成器幂等(连跑两次 diff 为空)、只读(仓内零写入,除 gitignored 产物)、
   断源响亮失败(删掉账本文件跑 `render` 必须非零退出且指名缺哪个源)。
3. `--check` 能抓住两类真实腐烂:构造「L1 状态流转未更新 roadmap」与
   「inflight 声称 revision ≠ live health」的坏夹具,均非零退出。
4. roadmap.md ≤120 行硬顶;超了 `--check` 拦截(同 3K 预算的执法方式)。
5. 全程零 runtime 行为改动;不触碰在途保留地(§6)。

## 6. 冲突矩阵

- 纯新增:`docs/roadmap.md`、`scripts/progress_observatory.py`、测试与夹具。
- 只追加:`ledger-map.md` 一行、triage-loop 母本一行。dsh 母本不在 main,
  不在本 PR 造文件;债记在 `docs/roadmap.md` 头注。共享文件只追加,后合并者
  rebase 保留双方行。
- **不碰**:`.pre-commit-config.yaml`(dsh 在途)、`intelligence/` 任何文件、
  `episode_semantic_verifier.py`(R-24)、`agent_episode.py`(dsh/S1)。
- 与 S1–S10 全部可并行。

## 7. 风险

- 手写层仍可能腐烂:接受残余风险,闸门只保证「腐烂会响」,不保证不腐;
  唯一写入者(检阅方)+ 合并时机绑定把窗口压到最小。
- markdown 表解析脆:列名冻结 + `--check` 先行,格式漂移在合并前被拦,
  不会静默出错页。
- gitea API 不可用时:PR 史一节降级为 `git log --merges`,标注降级来源,
  不算断源失败。
