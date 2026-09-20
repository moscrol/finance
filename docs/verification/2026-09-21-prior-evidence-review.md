# 旧证据恢复、日期误删修复与 V4 复核交接

## 结论边界

本轮完成两处可逆代码修复，并取得当前候选版本的全仓绿和 K3 两轴工程复核：

- `68949b92`：把旧证据恢复的 `old_ref -> new_ref` 私有绑定生成移出 `agent_episode.py`，runtime 不再直接调用公开证据序号投影函数；行为保持 `E2 -> E1`。
- `2cfa9d0d`：只对句首、形状合法且与已绑定证据 `source_date` 月日相同的短日期做局部遮罩，避免 `9-11 是……` 在语义复核前被数值预检误删。

这不等于研究求证行为整体验收，也不等于模型答案质量、材料前提绑定、main 或生产验收。`FINANCE_RESEARCH_REASONING` 继续默认 off；未 push/PR/合 main/部署，8792 未动。

## 版本与自动收据

候选树：`/Users/a77/fwp-wt-research-reasoning-awareness`，分支 `feat/research-reasoning-awareness`；被测代码 revision 为 `2cfa9d0d7e0c5ab2cec4007528d3e7b10c41e103`。本轮仅补外部重放收据和文档，代码文件未改；文档提交不继承代码测试收据。

- 全仓 pytest：`12049 passed, 87 skipped, 2 xfailed, 0 failed`，677.26 秒，收据 `~/.finance-runtime/test-receipts/20260920T195644Z-2cfa9d0d.json`；收据确认解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`、revision 一致、dirty=false。
- 全仓 Ruff：`All checks passed!`。
- 相关组合：`477 passed`，收据 `~/.finance-runtime/test-receipts/20260920T185948Z-2cfa9d0d.json`。
- 原 a4f 全仓失败原件保留：`12026 passed, 87 skipped, 2 xfailed, 1 failed`；唯一失败是 `test_agent_episode_no_longer_projects_evidence_ordinals_itself`。修复后相关 `152 passed`，再接日期补丁后 `477 passed`。
- 日期补丁隔离验证：隔离树 `6f935bed`，日期相关/边界组合 `338 passed`；两轮撤保护分别触发 `5 failed` 与 `8 failed`，证明数量门仍在。旧 on2 真实 run 不覆盖、不改写。

## 旧证据恢复合同

恢复只发生在同用户同会话、完整材料链、明确要求复核上一答且“仍只用已取得数据”的窗口。RunStore 校验登记原件、固定路径、软链接、大小、renderer、SHA256、用户/run/会话；恢复器再校验原题、用户消息、TaskFrame/contract/outcome、cutoff 和完整 `AgentEvidence` schema。

仅接纳完成的单跳 `local_only` 原轮、白名单本地工具、有效日期、截止日前观察；排除派生计算、缺日期、越界和重复身份，清空旧 `supports/contradicts`。`material_only` 仍走研究交付但能力为空、`needs_retrieval=false`，通过 `model_input:prior_tool_evidence` 注入原始观察，不伪装工具调用、不重查、不用旧答案造事实。新 episode 重新编 E 号，receipt 保存 old/new/hash/run 映射，旧覆盖、完成状态和权限不继承。

分层修复后，`agent_episode.py` 不再直接导入/调用 `evidence_ordinal_table`、`attach_evidence_ordinals`、`strip_hashes_for_model`；`prior_evidence.remap_evidence_bindings` 复用协议唯一编号表，私有映射行为等价。K3 报告另记：receipt/bindings 在基底已经随模型输入可见，本轮没有扩大；若终态要求严格对模型隐藏，需另立变更，不能把本轮修复说成已完成。

## V4 真实入口对照

四臂从同一 V3 原轮冻结输入复制，revision `a4f51112`、同模型 `glm-5.3-flash`、同问题/材料、同原件 SHA256 `67abf80527add0dc05ff26a9eb37defeeb576983a5e00d7bcdbff00bf7b261c5`，仅切 `FINANCE_RESEARCH_REASONING`：

- `off1`：恢复14条、0工具；撤回出逃/小票/轮动，但未明确纠正占比不等于增量。
- `on1`：明确41.1%只是当日成交分布，不能推增量；仍把放量且上涨家数扩张当作区分资金来源的条件，证据不足。
- `on2`：2模型、1 invalid、日期句被程序 `novel_numeric_condition` 删除，导致“降级为候选解释”整句消失；这是程序误删，不归因于模型。
- `off2`：仍混用跨期解释，并把量价扩张升级为增量假说。

四臂均 `material_only`、能力为空、0工具；同源 judge 的 passed/repaired 只作运行记录，不能当独立语义复核。旧 on2 仍是失败原件，不能被新代码收据覆盖。

日期修复后的真实入口已在代码验证 revision `2cfa9d0d` 的隔离 sidecar 重跑：新用户/新目录、连续会话首答后续问，原题 run `run_20260921_041342_926997`，复核 run `run_20260921_041850_129136`，均 `completed`，复核 `invoked_tools=[]`。复核原件保留了绑定 E27、E28–E36 的 `9-11` 证据句，并明确撤回“存量资金腾挪放大换手”和“不依赖新增资金”，保留“成交额不足以证明新增资金”的边界。注意：新答案使用的是“9月11日”全日期，没有实际命中旧 on2 被误删的句首短日期 `9-11 ...` 路径；因此不能据此证明该特定故障已在真实入口复现并修复。首答仍有“跌停21>涨停40”等错误，复核仍不是独立语义通过。manifest 在外部目录 `v4/date-fix-rerun/MANIFEST.json`。

旧 on2 原件另做只读离线重放：结构重放仍为 `completed` 且与存证无差异；当前 verifier 的确定性预检四类索引均为空，目标句被送入判官请求。该探针使用 stub judge，只证明“未被数量门提前删除并到达判官”，不证明真实模型接受整篇答案。收据 `/Users/a77/.finance-runtime/reasoning-boundaries-20260921/v4/on2/semantic-replay-2cfa.json`，源原件 SHA256 `8e9117…b230cc660`。

虚构供需题的 V4 重跑仍拒答（0工具、结构性终止失败），不能把材料前提整体改成 `user_premise` 以绕过 grounding。E2 owner 的逐句材料绑定仍未合入本候选。

## K3 独立复核

独立目录：`/Users/a77/.finance-runtime/reasoning-boundaries-20260921/k3-independent/`；两个 detached worktree 均固定 `2cfa9d0d`，审核者未改候选、作者树未改。

- Spec：报告 `spec-k3/REPORT.md`，SHA256 `63e2358ddce1065a06f59b3b2cff9a2fa78968d8fba1e9310bc0028924f739a3`，结论 `PASS`。独立跑相关测试 `56 + 180 + 117`，AST/边界探针33项全过；确认准入、零读取、重编号、日期双条件和 fail-closed 边界。
- Quality：报告 `quality-k3/REPORT.md`，SHA256 `f2ae5448498f94d97218196d2c21c3d272ed873cde4df468144b870d712a7155`，结论 `PASS`。独立跑新日期22项及相关331项，Ruff/diff 通过；外部副本两次撤保护分别使标题形状保护 `8` 项失败、绑定限制 `1` 项失败。
- K3 限制：共享 refs 和 `~/agent-memory` 指纹在审核期间发生环境漂移，收据为 `shared_refs_unchanged=false`、`vault_unchanged=false`；候选 HEAD/status 与作者树首尾不变。故 K3 结论仅采信报告中对候选源码的固定 revision 审核，不把全局隔离指纹说成完整通过。
- K3 Spec/Quality 不是模型行为盲审；另有独立语义盲审报告，但结果为负向观察而非验收。Grok 沙箱故障与 Codex host/额度失败原件仍保留，未关闭保护、未购买外审。

## 独立语义盲审

外部 `semantic-k3-independent-3/REPORT.md` 封存了一次无工具、`/tmp` cwd、匿名候选输入的 `mirasim-kimi/kimi-k3` 盲审。执行收据为 exit 0、未超时；候选 `HEAD=33d3505` 与工作树首尾未变，但共享 refs 指纹漂移，不能称完整隔离。模型返回 `passed=false`，拒绝候选 `[1,2,3,5]`，保留 `[4,6]`。核心发现是 E4 的 2026-09-09 上证涨跌幅为 `+0.278%`，候选 1–3 错把它保留为“9-09/9-10 连跌”，候选 5 又把正号写成下跌。该结果是独立负向观察，不替代行为验收，也不抹去真实入口首答的其他错误。

## 非显然决策与否案

1. 选恢复服务封装编号映射，否 runtime 继续直接调用协议投影；理由是既有架构断言已把公开投影职责留在协议/终局层，恢复只需要私有交接映射，行为可差分验证。
2. 选绑定证据日期的句首白名单遮罩，否扩大 `_DATE_TOKEN_RE` 或全局豁免；理由是扩大正则会把 `9-11倍`、`9-11元` 等真实数量条件放空。遮罩只让语义 judge 看见日期，不能替其认可日期或因果。
3. 选保留 V4 旧失败原件并把修复后重跑另记，否用新测试覆盖旧答案；理由是模型行为、程序误删和版本收据必须可分离。
4. 选不搬 E2 材料 owner WIP，否全局改 `user_premise`；理由是材料来源资格与推断正确性是两层合同，绕过前者会制造假成功。

## 下一步与禁做

下一步：与 E2 owner 对齐材料逐句来源；补未见题和新增开发反例的真实答卷；对旧 on2 的短日期路径保留离线重放并另行取得真实入口证据；按归属处理前端/E2E/registry。日期修复重跑原件、离线重放和 manifest 已封存，不覆盖旧 on2。

禁止：不把 K3 PASS 写成业务质量通过；不把同源 judge/零工具/completed 当行为通过；不合 main、部署、重启8792、购买外审额度或删生产原件；不宣称支持跨会话、多层、混合联网、任意日期重筛或崩溃 checkpoint 恢复。

## 原件索引

V4 根：`/Users/a77/.finance-runtime/reasoning-boundaries-20260921/v4/`。K3 根：`/Users/a77/.finance-runtime/reasoning-boundaries-20260921/k3-independent/`。旧 V3、blind request、Grok/Codex 启动失败、日期 probe、测试日志和真实 run 均保留在对应外部目录；不要把外部 JSON/模型输出复制进生产或共享记忆。