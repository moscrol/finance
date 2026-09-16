# fix/e2-delivery-closeout

## 这个分支做什么
E2 P4（D5）：material_only 逐题交付（legal_gap / memo 槽 / 判官拒绝重开 / 投影后复验 / outage 分离）+ 两条前置修复（题包解析吞题、验收采集 followup 错会话）。只动 `fwp-wt-e2-delivery-closeout`，主树不动。

## 决策与被否方案
- 全树 AST 门 `test_public_answer_assignments_all_go_through_view` 在 P4 提交上红：三处 `public_answer=裸变量` 改经 `view(TerminalFacts(CAUSE_VERIFIED))` 并登记 `_VIEW_CALLERS`；否加宽 `_ALLOWED_PUBLIC_ANSWER_CALLEES`（等于把拼串路径合法化）、否只改测试。
- `recheck_material_public_delivery` 形参 `public_answer`→`projected`：它是调用方送入的投影文本，不是 outcome 字段；否让适配器再包一层 view（多登记一个非出口）。
- 变异后 4 个仍绿的门各补一条直接反例（含调私有函数、monkeypatch 最后一步公开变换）；否只写进文档。
- 展开：`docs/handoffs/2026-09-16-e2-delivery-p4.md`（设计）、`…-p4-verification.md`（精确提交验证）。

## 当前状态
提交链：`5ebd6e61` 解析 → `2e81b2ae` 采集 → `2462cfde` P4 → `9a98f4fc` view 门修复 → `1f24a6ef` 四条反例 → 文档提交。树干净。未推送 / 未合并 / 未部署，不跑正式 T2→T3 / Knevo。

## 已验证
python：`1f24a6ef` 10018P/0F，收据见验证记录，`check_test_receipt --expect-revision` ✅。frontend：`2462cfde` 四步 0，webapp tree hash 三提交相同。e2e：`9a98f4fc` 15P。registry：五条 0。变异：28 落盘，`9a98f4fc` 24 红，补反例后 28/28 红，基线与还原后全绿。

## 未验证 / 已知边界
作者自验非独立 QC；判官全是离线替身；不证明材料锚点真实（D6）。M22 的 issue/mandatory 分支在 material_only 下可达性未论证。前端/e2e 未在 `1f24a6ef` 重跑（靠结构性等价）。引擎 B 仍无合同意识；local_only 原题号槽、跨轮继承五格（P5）、纯度/锚点（P6）、隔离验收（P7）未做。

## 下一步
1. 合并窗口：四叶绿 + 变异闭合，是否合回 main 等用户确认。gitea/main（`727b2611`）领先 45 提交，`merge-tree` 唯一冲突 `skills.registry.json`（生成件，双方各一次 resync）：合并时 `build_registry.py` 重生成并跑五条 registry 检查，不手改；合并头再 `check_test_receipt.py --expect-revision`。
2. P5 起点：`intelligence/runtime/conversation_orchestrator.py` 约 2030/2048 行 `conversation_materials=material_history` 进 `decide_turn`；真实 run_turn→controller→Episode 的五格继承与角色身份是下一片，另开分支。

## 踩过的坑
定向集绕不过全树结构门：`rg -l 'ast\.walk|rglob\(' intelligence/tests tests` 把这类文件加进迭代集。zsh 不分词，`cmd $var` 整串成文件名→假 exit 2。跑收据期间别动树（docs 也算脏）。变异驱动 JSON 会被重跑覆盖，先复制。
