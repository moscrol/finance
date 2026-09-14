# feat/research-evolution-06-workbench 在途交接

最近更新：2026-09-14 · HEAD f90e27c5（第六轮返修已提交）· 基于 b481804c

## 当前任务（第七轮 QC 复审等待中）

第六轮 P1×2 + P2 返修完成、全绿待复审。根因：坐标只约束了接受侧与补偿侧，运行中显式登记漏查完整归属；成果侧把「当前唯一 pending」误当因果唯一。

## 本轮改动（相对 c8536482）

- W1/W2：`_link_run_event` 运行中分支写入前查 run 的**完整**既有归属（任何项任何代 → 400）+ 源消息坐标与当前 (项,代际) 一致性核验；R7 裸 run 保留（无来源 ≠ 矛盾来源）。
- W3：auto-pick 唯一性 = 「本会话有史以来只有本轮一次 rejudge 记录」（不再是当前 pending 数）；Q2 单请求自动关闭不变。已取消同伴的迟到成果不再能关唯一剩余项。
- P2：确认表单有效选择派生自候选集合（投影刷新即生效），按 item+request_event_id 作 key 换代重置，提交前再验；面板新增 2 条状态转换测试。
- 仓内新增 W1–W3 镜像回归（test_research_evolution_rework.py）。

## 验证

- 新三针 3/3 原样；组合门禁（5 套件 + 四轮历史探针）**130 passed**。
- **干净候选全量**：HEAD f90e27c5、dirty=false 裸 pytest **10057 passed / 0 failed / 77 skipped**，收据 `~/.finance-runtime/test-receipts/20260914T043357Z-f90e27c5.json`。
- 沙箱两条（codex_headless）本机绿；评审环境的 `live_root_read=unexpected_success` 是嵌套沙箱环境特异、修前即红，未归因本次返修；详情见 REWORK.md。
- 前端 94 tests / lint / typecheck / build 全绿；e2e 31 passed / 2 skipped。

## 细节快照与证据

- `docs/handoffs/2026-09-14-re06-round6-w1-w3.md`（决策与被否方案）。
- `docs/verification/re06-c8536482/`：REVIEW.md（裁决）+ REWORK.md（返修说明）+ test_review_round6.py（探针）。
- 历轮：re06-0c275716（R3）、re06-957e83f4（R4 U1–U4）、re06-ecd90a3c（R5 V1–V4）。

## 信任阶梯（当前全貌，复审参考）

1. 接受侧绑定：只认消息 `maintenance_launch` 坐标（rejudge 台账回查当前代）。
2. 运行中登记：同代复用 → 完整归属矛盾检查 → 源消息坐标矛盾检查 → 登记。
3. 终态折回：当前代登记行；缺失时补偿只认源消息当前代坐标。
4. 成果归属：显式 new_judgment_ref（过 session/ts/存在/未消费闸）或 auto-pick（会话史唯一请求）。
5. 终态重放：会话内 + run 会话核验 + 版本闸。

## 合并顺序（通过后再走，等用户确认）

spec 链 → 主链原序；不合并、不部署、不动其他 worktree。

## 留痕

- judgments 写入侧不扩展（登记依赖）；归属只靠坐标+历史唯一。
- 运行中 link_run 带 new_judgment_ref 被忽略（终态才读）；面板只对已完成 run 开放确认。
- 探针台账：round2 在 ~/.finance-runtime/reviews/research-evolution-06-ba10747d/，round3–6 在 docs/verification/re06-*/。
