# 2026-09-22 E2 边界与 RE06 收尾：计时同意范围决策与 PR 工单

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
姊妹：#75（独立 QC）、#76（P7 隔离验收：新会话 + 原始 T3 + 真实模型）。本单含一处用户决策：计时按钮的同意范围三选一。

## 背景与动机

- 分支 `fix/e2-re06-resume-0922`（HEAD `100dcb32a`，基座 `a2c8d1f90`，6 提交，**未推**；树 `~/fwp-wt-e2-re06-resume-0922` clean）。四件事：
  1. `8fd6882ea` **E2：local_only 按原题号逐题交付**——按原号冻结 `answer_qN` 必需槽；结清口径不共用：`material_only` 零读权限，交代缺项即诚实交付，`legal_gap` 可结清；`local_only` 有本地读工具，认 `legal_gap` 等于用「缺少 X」买断取数义务，故回普通 `required_output_gap`。坑：跨轮恢复判据用「契约已有 `answer_q*`」而非「有编号题」，否则旧会话一恢复就报错。
  2. `8975ce0f2` **RE06：写读同意折叠抽共用** `consent.py::scopes_at` + `covers_measurement`；有意差异不进共用件（读侧只认带 `participant_id` 的记录、无记录返 None；写侧认 owner、无记录按自用默认放行；坏时间戳读侧抛、写侧跳过）。
  3. `8cb1b4929` **RE06：同意门锁内复核（TOCTOU）**——门在锁外读台账，到抢锁之间 API 侧可追加撤回，老实现不复核就写，**修复前实测真写出了 run_started**。改为 `try_transaction` 内复核同一谓词；锁外那道门保留。同族已筛：全仓 17 处事务点只此一例（`fold_run_terminal` 正例、`create_binding` 锁外预检只是快路径）。
  4. **计时按钮与测量门耦合（现状刻画，待用户定口径）**：前端 `ResearchActivityControl` 在停止 / 切会话 / `pagehide` 发的 withdraw 记在 owner 名下，用的又是测量门那组 scope（`["research","logging"]`、`consent_version="workbench-activity-v1"`），故**停一次计时 = 自用测量永久关停**，界面却只说「研究功能不受影响」。已补门页与刻画测试 `100dcb32a`。
- 读数：新测试四份（E2 20、折叠 18、TOCTOU 6、计时门 5）；变异 7/7、8/8、5/5 全杀；RE06 十一套 186P；全量 10630P/23S/2X（含 `test_rag_worker` 负载假红，同一提交两次全量一红一绿）。作者自验，非独立 QC；P7 隔离验收未做。
- 09-22 另一发现（已纠正的继承断言）：「F2 前端同意入口仍缺」是从 0916 QC 文档继承的过期断言，实际 `ResearchActivityControl.tsx` 早已存在——**从文档继承的断言会腐坏**，写进交接前当场验一次。
- **已定的形态决策**：切题是 `user_task.py` 的确定性正则、无模型参与，扩到无编号等于改信任模型，属产品判断不在本单；TOCTOU 修法是锁内复核同一谓词，不是「锁外再读一遍缩小窗口」（变异 T2 专守此伪修法）；时间语义按事件自身时刻判定不按写入时刻。

## 决策（09-23 已选择 B）

用户原话 `b`。已在独立候选 `fix/re06-timer-scope-0923@4bb3bf0cb` 实施 B：`activity-timer`/v2，读写共用测量域分类；旧 v1 仅对原控件完整自用形状作对称读取兼容，不改台账或哈希。原任务树保留，固定基线 `ffd1b7f15720`。干净候选授权/API 89P、前端9P，完整四叶和独立QC仍待，不是合入/部署/迁移授权。详情 `~/fwp-wt-wave2-re06-0923/docs/handoffs/2026-09-23-re06-timer-scope-b.md`。

09-23 本轮验收输入固定为 `f9ce5c6b296492b423400ad66d333784a4be13bc`，代码候选未改。17处业务事务逐项作者静态核对已落 `docs/verification/2026-09-23-re06-toctou-family.md`：分母是 RE06 服务/API 直接事务调用，另列底层 `_locked` 1处，不再表述成全仓仅17处。完整C1–C10主张已入#75；K3基础网关请求90.034秒超时，`BLOCKED_PROVIDER_TRANSPORT`，尚无独审终稿/探针。完整四叶仍受资源门阻塞；详情 `docs/verification/2026-09-23-re06-timer-scope/README.md`。

原三选一比较保留：
- A **只改文案**：界面明说「停止计时会撤回自用测量同意」。零代码风险，但用户每次停计时都在关测量。
- B **计时同意换独立 scope 名**（如 `activity-timer`），测量门不再受它影响。**推荐**。代价：改 05 读数（测量门的历史同意记录里含旧 scope，需要一次迁移或双认）。
- C **门忽略该 `consent_version`**：写侧测量门跳过 `workbench-activity-v1` 的撤回。最小改动，但把「哪些撤回不算」写死在门里，日后再加一个前端入口就重演。

## 目标

1. 推送分支、开 PR（base main），描述含四件事与决策项；前向 main；低负载四叶；`test_rag_worker` 那条按 #59 口径四读数。
2. 拿到决策后实施（B：新 scope 名 + 迁移/双认策略 + 门页文案；A：文案 + 刻画测试更新；C：门内忽略 + 一条「再加入口会重演」的注释与测试）。变异：把修法拆掉，刻画测试必须红。
3. TOCTOU 同族筛查结论落 `docs/verification/<日期>-re06-toctou-family.md`：17 处事务点各一行判定（真成员 / 正例 / 锁外只是快路径 / 无决策性读）。
4. #75 独立 QC；用户确认后 `merge --record`；P7 条件卡交 #76。

## 非目标（写死认领）

- ❌ 不扩「未编号本地多问题」到模型切题。
- ❌ 不统一读写两侧的有意差异（统一等于把漏掉的 withdraw 当成仍授权）。
- ❌ 不修 `test_rag_worker` 假红。
- ❌ 不做 P7 隔离验收（#76）。
- ❌ 不改 E2 其他阶段（P3–P6 的既有分支 `feat/e2-p5-cross-turn-inheritance`、`feat/e2-p6-conditioned-input` 等）；它们与本单关系写进 PR 描述。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `~/fwp-wt-e2-re06-resume-0922/docs/handoffs/inflight/fix-e2-re06-resume-0922.md` | 四件事、决策、读数、「跑全量前先看 uptime」 |
| `intelligence/services/product_value/consent.py`（`scopes_at`、`covers_measurement`）、同意门写侧（`try_transaction` 内复核处） | 折叠共用件与 TOCTOU 修法 |
| `intelligence/webapp/src/**/ResearchActivityControl.tsx` | withdraw 的 scope 与 `consent_version` |
| `docs/agent-product-door.md` 约 383 行计时控件段 | 门页现状刻画 |
| `intelligence/tests/`（E2 20 / 折叠 18 / TOCTOU 6 / 计时门 5 四份新测试） | 变异对象 |
| `docs/verification/re06-*/REVIEW.md`（历史 QC） | 「从文档继承的断言会腐坏」的实例 |

## 步骤

1. 开工三连；树 clean；推送；开 PR；三选一贴用户。
2. `merge-tree` 探 main 冲突（gitea/main 新提交全在 `market_feature_store` 侧，预期零重叠）；前向；低负载四叶。
3. 决策落地 + 变异；同族筛查文档。
4. 交 #75；确认后合入；P7 条件卡。
5. INDEX #73 行；inflight ≤3K。

## 验收

- [ ] PR head 四叶收据 revision == head。
- [ ] 阳性对照：把锁内复核去掉、只保留锁外读，TOCTOU 用例（含 T2 伪修法守卫）必须红；还原后绿。
- [ ] 决策有用户原话；所选方案的刻画测试更新且拆掉修法即红。
- [x] 同族筛查文档 17 行齐全（固定 f9ce5c6b2，作者静态核对；非独立QC或新行为测试）。
- [ ] 前端 `pnpm test` 含 `ResearchActivityControl` 用例通过（若 B，scope 名断言更新）。

## 红线

- 只用 pathspec 提交；合入 main 等用户确认；不强推。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`；全量前 `uptime`（本机常有十几棵树并跑）。
- 不跑真实模型；不动 8792；不写生产 users 根。
- 不写明文密钥。
