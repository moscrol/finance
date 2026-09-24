# 2026-09-22 自然金融质量验收批（有界真实模型）工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
本单是**服务单**，六条线各一行，每行独立可派、独立授权、独立证据根。**每行开跑前都要用户一句授权**（模型预算 + 数据冻结副作用），本单只把条件写死，不替用户授权。姊妹：#75（工程 / 正确性审查，本单不重复）。

## 背景与动机

- 09-22 全天的模式：工程门禁绿、变异全杀、独立 QC PASS_WITH_LIMITS 的候选，一到真实模型答真实金融题就暴露缺陷（研究答案保留的空指针交付、A 股数据链的 0.7474→0.7473 抄错、K3 的四类口径越界、R6 四题 0/4）。三态分账不得互相代签：**工程门禁 / 独立审查 / 自然金融质量**。
- 真实验收的共用协议已在 09-22 跑通一次（`~/.finance-runtime/reviews/research-preservation-natural-live-20260922/`）：候选代码根用冻结检出，health 自证 `source_revision / source_dirty=false`；数据按固定口径冻结（主库 clone + 快照合约 PASS + 只读 manifest）；预算首发 1 / 重发 0 / 续问 0；旁路实例端口避开 8780–8830，用户根独占；`audit.json` 是结论件，`launch-config-amendment.json` / `protocol-amendment.json` 记偏差；收尾核实实例已停、锁释放、生产身份七字段不变、冻结数据 manifest 不变。
- 通道事实：K3 写手可达（小请求 200、5.4 秒），拒收 `temperature` 需剥参 shim；判官若继承 K3 慢思考必超 75s 窗，判官用 flash；网关批前探冷却，并发 ≤ 2。
- **已定的形态决策**：未触发不等于通过（机制没进场就没有结论）；重发 0；不重发旧样本；新样本要新授权与新证据根；判定项按各行写死，不用总分；「判官不可用」类 degrade 单列不计入内容质量。

## 六条线（每行独立派单）

| 行 | 线 | 候选 SHA 来源 | 题面 | 判定项（全部为真才 PASS） | 前置 |
|---|---|---|---|---|---|
| L1 | 研究答案保留 + 空指针交付门 | #70 合入后的 main SHA（或 `fix/research-empty-delivery-0922` head） | 需要**能稳定触发拒收**的题型或注入点（正常路径不进修复机制）；#70 给出注入点前不派 | 首次 finish 被拒收 ≥1 次；`repair_attempts ≥ 1`；终稿正文非指针、必需三输出齐；四类 09-22 金融问题不再现 | #70 注入点卡 |
| L2 | A 股研究数据链两题 | #71 合入后 main SHA | `historical-iso`、`financial-calc` 两原题（`research-data-acceptance-20260922-01` 内） | financial-calc 六格全对且零误报；公告句全留；historical-iso 保持通过形态；判官 `passed/repaired` 非 `unavailable` | #71 合入；判官用 flash |
| L3 | 历史四题 | #68 / #67 定下的历史 head | 四道真题（分支 `docs/handoffs/2026-09-1x-history-*.md` 系列） | 四题各：启动判据由规则触发、控制组存在且有证据、引错算子被剔除而非整题作废、`max_status` 与已执行历史结果一致 | #68 结论 |
| L4 | R6 四题（财务链） | #66 或 #67 合入后 main SHA | R6 四题原件（`8792-ttl-baseline-20260922` 干跑用的封存答卷同源） | 四题各：截止日进上下文、「最近两期」选中中报 + 一季报、计算产物行数对、无跨期别混比句、TTL 无自相矛盾、比较基线存在或走补数 | #66/#67 合入 |
| L5 | K3 无判官再验 | #65 合入后 main SHA | 09-21 两道首跑原题 | `check_answer_claims` CLI 退出 0；四类越界零命中；`marker_coverage` 非 incomplete | #65 条件卡；K3 shim |
| L6 | 自适应回路真实改稿复核 | #72 合入后 main SHA | 三题冒烟原题（`adaptive-absence-live`） | 严格探针 exit 0 前提下：改稿轮 ≥1 且改后数值条件句（有证据的）零误删；`judge_late_report` 类零采纳 | #72 探针 0 越窗 |

## #82 移交的待授权补充（不改变原六行）

09-23 决策阶段收到 [FinArena 三条旧样本](../../handoffs/2026-09-23-finarena-quality-transfer.md)，原运行 `bf662e93`，三轮均未完整通过；本轮只重验 18/18 原件哈希，不重跑、不翻旧结论。

| 局部案例 | 待验问题 | 接收状态 |
|---|---|---|
| FA-1 | 用户明确给定的虚构财务数据被外部证据合同挡成无答案 | 待授权补充；不替换 L2/L4 原题；以最终公式、单位、结果和事实/假设分界验收 |
| FA-2 | 同会话改股价并假设利润下降，已继承数据却没有公开交付 | 待独立两轮协议授权；与本批“续问 0”冲突，禁止直接开跑或拆散会话 |
| FA-3 | 行情漏查下跌家数且把复盘会 `.FP` 错标同花顺 | 待授权补充；先冻结并核分母/来源，不将旧 1151 和旧排名硬套新快照，不替换 L3 原四题 |

候选、预算与接收者执行结论均待另定；本节只接住问题，不宣称已修复或已获模型调用许可。

## 目标

1. 每行一个证据根 `~/.finance-runtime/reviews/<line>-natural-live-<日期>/`，含 `protocol.json`（候选 SHA、数据冻结口径、预算、判定项）、`audit.json`（结论件）、`amendments/`（任何偏差）、`closure.json`（实例已停、生产身份不变、manifest 不变）。
2. 每行结论只取 `PASS / NOT_PASSED / NOT_EXERCISED / BLOCKED_<原因>`；`NOT_EXERCISED` 明写哪项机制没进场。
3. 各行结论回写到对应工单 INDEX 行与 PR 评论；`NOT_PASSED` 的具体问题按类别登记占位单。

## 非目标（写死认领）

- ❌ 不重发、不续问、不换题求绿。
- ❌ 不在生产 8792 上跑；不写生产 users 根；不改生产配置。
- ❌ 不用本批任何一行的结果去反推旧结论（09-18 超时、09-21 首跑）。
- ❌ 不做工程 / 正确性审查（#75）。
- ❌ 不把 `judge_unavailable` 类 degrade 计入内容质量。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `~/.finance-runtime/reviews/research-preservation-natural-live-20260922/`（`control.py`、`audit.json`、`frozen-data-manifest.json`、`launch-config-amendment.json`、`closure.json`、`deploy-ledger.jsonl`） | 协议实物：照形状建新证据根 |
| `~/.finance-runtime/reviews/research-data-acceptance-20260922-01/`（含 `k3_param_shim.py`） | L2 原题、shim、判官慢的壳层原因 |
| `~/.finance-runtime/reviews/8792-ttl-baseline-20260922/dry-run-sealed*.log` 与 R3/R6 封存答卷 | L4 题面与两道新门的干跑基线 |
| `~/.finance-runtime/reviews/k3-acceptance-20260922/`、`scripts/check_answer_claims.py` | L5 题面与判据 CLI |
| `~/.finance-runtime/adaptive-closeout-20260922/`、`scripts/review_probes/diagnose_llm_timeout.py` | L6 前置探针 |
| `docs/workflows/acceptance-workflow.md` §1–2 | 翻转率、`judge_unavailable` 单列 |
| `~/.local/bin/start-finance-workbench` | 旁路实例启动参数照抄形状（不改生产件） |

## 步骤（每行相同）

1. 开工三连；确认前置已满足（对应工单 INDEX 行状态）；起草 `protocol.json` 贴用户要授权原话。
2. 冻结数据（clone 主库到证据根、manifest、快照合约检查）；建冻结代码检出；旁路实例起在避开 8780–8830 的端口，K3 需 shim 并写 amendment。
3. 网关探针一发；跑题（首发 1）；`audit.json` 按判定项逐项写 true/false 与证据指针。
4. 收尾：停实例、释放锁、核生产身份七字段与 manifest 不变、写 `closure.json`。
5. 结论回写 INDEX 与 PR 评论；`NOT_PASSED` 登记占位。

## 验收

- [ ] 每行 `protocol.json` 含用户授权原话与出处；`audit.json` 判定项与本表一致。
- [ ] 阳性对照：每行在正式跑前先用一份**已知失败**的旧答卷回放判定脚本，必须判 `NOT_PASSED`；证明判定不是恒真。
- [ ] `closure.json` 的生产身份七字段与 manifest 哈希前后一致。
- [ ] 结论四值之一，无总分、无「基本通过」。

## 红线

- 每行开跑前用户一句授权；预算首发 1 / 重发 0 / 续问 0，不加码。
- 旁路端口避开 8780–8830；不动 8792；不写生产 users 根；不改生产启动器。
- 网关批前探冷却；并发 ≤ 2；429 / 400 立刻停手记账。
- 不写明文密钥；shim 只剥 `temperature` 并落声明。
