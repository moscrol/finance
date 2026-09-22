# fix/research-empty-delivery-0922 — 最终交付门（收口批 #70）· 已合入

**状态**：PR #862 已合 main `8d3d722c95d4`（09-23 03:2x），分支已删；**8792 未部署**，上线另行决定。决策 A 已定（`marker_coverage` 保持只观测，靠双钥匙拦「指针 + 缺覆盖」），用户原话「继续按照最优方案推进，需要跑真实的话就用k3」。证据目录 `~/.finance-runtime/reviews/research-empty-delivery-gate-0922/`。

## 合入了什么

- `services/public_delivery_gate.py` 纯函数 + `_complete_continuous_turn` 在 `complete_report` 之前接线；双钥匙（指针形态 × 必需输出缺覆盖），单钥匙放行，长度不是钥匙，落点 `answer_status`，缺口模板豁免，只删开头指引 + 追加【交付自检】。
- 现场夹具 `intelligence/tests/fixtures/live_products/run_20260922_191550_067475/`（sha256 钉措辞）+ 16 条门测试（含钥匙 1 / 钥匙 2 各清空的阳性对照）。

## 门禁与验收

- 合前预览 `6fea2de2d` = trunk `72be60059` + head `e14983a51`：ruff 0，14379P/0F/85S/2xfail，收据 `gate-qxDVONt9`（副本 `preview2-receipt-6fea2de2d.json`），基座漂移 0；合并树 == 预览树 `b0ae68407`；记录 `merge/merge-862-record.json`。
- head 四叶：python 12545P/0F、frontend（重装 node_modules 后 @ head）全过、e2e 34P/2S（首跑 1 红 = RE06 端口只设一半）、registry 一致。
- K3 独立 QC（pi，隔离树）Spec/Quality PASS_WITH_NOTES：M1 `answer_status` 覆盖可抬升字段值 → 加固 PR #874（WIP，base 已改 main；今天 failed 投影走早退到不了门，属加固）；其余 note 见 PR 评论。
- K3 live 一轮（预览侧车 18896、冻结 09-18 数据、去 temperature 垫片、RAG off、首发 1/重发 0）：写手 draft 1038 字不以指针开头，门判 ok 零误伤；拦截分支未被自然触发；金融质量不宣称。`live/protocol.json` / `audit.json`。

## 未做 / 下一步

1. 部署到 8792（按 `deploy-8792-switch-procedure`，切前/切后对照探针）。
2. Engine B `/api/runs` 同洞：`app.py` `_ask_answer_coverage` 只观测，`complete_report` 缺 `answer_status` 回落 complete；复用同一纯函数，另开单。
3. 门只降状态 + 披露、不回修订轮；验自然纠错要把 missing 接回修订轮（运行时改动，另授权）。
4. 占位 #78/#79/#80（回调方向对照 / 筛选口径 / 自造实体）在 PR #867（叠 #858）。

## 别再踩

- 长度不能当钥匙（拍红 4+1 条既有测试）；绝对下限 8。
- 磁盘只剩几百 MiB 时整仓会读成几千 errors 且收据不写出（`run_main_gate.sh` 只留 tail）：起跑前看 df / load / pytest 数，`--pytest-args` 加 `--junitxml -rfE`，basetemp 用完 `chmod -R u+w` 再删。
- 同机清理会删所有树的 `.code-review-graph/*` 与 node_modules：门禁前 `git checkout -- .code-review-graph/`，frontend 前 `pnpm install`。
- push 命令串里别带 main 字样（hook 全串匹配）；Gitea 超时后 `open` 幂等重试。
