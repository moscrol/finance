# fix/research-empty-delivery-0922 — 最终交付门（收口批 #70）

**状态**：PR #862 已开（base main）。等四叶读数、用户拍决策 A/B、#75 独立 QC；合并等用户确认。worktree `~/fwp-wt-research-empty-delivery-0922`；`.venv-workbench` 只在主树，用绝对路径。

## 已做

- `d68b8f512` 门本体 + 接线：`services/public_delivery_gate.py` 纯函数，接在 `_complete_continuous_turn` 的 `complete_report` 之前（那之后的正文才是用户读到的）。双钥匙：指针形态 × 必需输出缺覆盖；单钥匙放行；长度不是钥匙；落点 `answer_status`，缺口模板豁免，只删开头指引 + 追加披露。
- `bc058ed44` 前向合入 `gitea/main@f24a61a8a`（#851），tree == merge-tree 预览，零冲突。
- `425ae78ac` 现场夹具 `intelligence/tests/fixtures/live_products/run_20260922_191550_067475/`（answer/report 逐字，episode 去三处重复拷贝，MANIFEST sha256 钉措辞）+ `test_public_delivery_gate_live_products.py` 6 条（钥匙 1 / 钥匙 2 各清空的阳性对照）。目标集 16P。
- 占位单 #78/#79/#80 + INDEX #70 行：分支 `docs/closeout-placeholders-78-80`（叠 `docs/closeout-workorders-0922` / #858）。

## 读数

- 全量 12521P/0F/85S @ `d68b8f512` 干净树（`test-receipts/20260922T141228Z-d68b8f51.json`）。
- 本 head 四叶日志 `~/.finance-runtime/reviews/research-empty-delivery-gate-0922/`（frontend-leaf / python-leaf / e2e-leaf / registry），读数贴 PR #862 评论。负载 25–41 时不跑全量；1F 按 #59「单跑 ×3 + 低负载整文件 ×1」。

## 决策待拍

`marker_coverage=incomplete` 仍 observation_only：A 保持（推荐，本 PR 形态）/ B 单独升阻断（先量误伤面，另开单）。

## 下一步

1. 四叶绿 → #75 QC → 用户确认 → `gitea_pr.py merge 862 --yes --expect-head … --record`。
2. Engine B `/api/runs` 同洞：`app.py` `_ask_answer_coverage` 只观测，`complete_report` 缺 `answer_status` 回落 complete；复用同一纯函数，另开单。
3. 门只降状态 + 披露、不回修订轮；验自然纠错要把 missing 接回修订轮（运行时改动，另授权）。

## 别再踩

- 长度不能当钥匙（拍红 4+1 条既有测试）；绝对下限 8。
- 不用 `-c core.hooksPath` 提交；push 命令串里别带 main 字样（hook 全串匹配）；Gitea 超时后先 `open` 重试（幂等），别开第二张。
