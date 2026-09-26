# feat/research-priority · 研究进化 02 下一步研究排序

## 这个分支做什么

按 spec 02 实现 `intelligence/services/research_priority/`：只读适配 01 维护项 / 项目投影 / 旧队列 / 补数请求 → 五组排序 + 同证据合并 + 分钟预算 → `research-priority/v1` 报告。engineering_complete；接线与 product_verified 归 06。

## 决策与被否方案

- 任务 id 由合并键派生（证据版本集合；无证据则问句+范围+对象）；否了沿用来源 id——同证据新增判断时 id 会变。
- 未到期条件进 blocked(not_yet_due)；否了「不生成任务」——P13 要时钟跨越后自动可选。
- 纯重复读取不改写问句，多来源合成才加「同时影响 N 条来源」；队列「降级/观察」桶只 skip 不生成任务（队列本意是减少投入）。
- as_of 的未来判断按市场时区（Asia/Shanghai）日历日，cutoff 仍按真实时刻；裸 datetime 整份拒绝。否了 UTC 日历日——清晨 07:00+08 把当天资料误判未来（QC S5）。
- identity_key 纳入执行窗口（due_at/available_at 折算 UTC）；否了只按证据合并——同证据不同到期互相拖入/拖出（QC P2）。
- hindsight 任务只标记不 blocked，且不与同证据当前任务合并；否了直接 blocked——历史重放要能排序。
展开见 `docs/handoffs/2026-09-13-research-priority-02.md`。

## 当前状态

已提交至 **`a869028e`（QC 第二轮 S5+P2 修复，最新）**，树干净，未 push / 未合 main（等用户确认）。
QC 第二轮：原 13 项固定反例转绿，扩大边界确证 8 项，本轨占 2 项均已修。**06 联测请用 `a869028e`。** identity_key 变了 → golden `expected_combined_synthetic.json` 经语义层闭锁后重生成（仅 id/digest 漂移）。
QC 第三轮：本轨无新增实现发现，S5/P2 复跑保持（≠ 已通过四轨集成验收）。两轮证据在 `~/.finance-runtime/reviews/research-evolution-*qc-20260913/`。

## 已验证

主树 venv：`pytest -k research_priority` 65 passed（含新增 3 条 S5/P2 回归，先红后绿）；ruff 0；QC 探针 `spec_010204_probes.py` S5/P2 组复跑转绿。M1/M2 变异各红 2、恢复后字节一致。01 产物零改动流过（P12）。

## 未验证 / 已知边界

- P12 的 01 产物来自 01 在途版本 + 合成输入；01 定稿后按 BLOCKED §1 重跑替换夹具。
- 未接 API / UI / 用户态；未跑公共完整门禁与 e2e（06 在最终候选上跑）。
- user_pinned 未实现；队列 / 项目投影无 pit_grade，02 标 trade_date_only。

## 下一步

1. 用户确认后 push、开 PR；合并顺序由 06 按 01→02 依赖排。
2. 01 定稿 → 重跑 P12；06 接 `adapt_candidates` + `prioritize` + `render_view`，点击带 `click_payload`。
3. 05 按 task_id + policy_version 关联事件。

## 踩过的坑

- 上轮口径「13 项已修复」实为「原固定反例集转绿」；`docs/superpowers/summaries/2026-09-13-*.md` 从未落盘。
