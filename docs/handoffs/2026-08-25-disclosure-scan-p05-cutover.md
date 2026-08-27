# 2026-08-25 · 披露扫描 P0.5 投递卫生：合入 #392 并切 8792

一句话：生产探针 `run_20260825_155459_372046` 暴露的三处投递毛病（附录截断误标整包 partial、excluded 逐条淹稿、「注册受理」误入 L_reg）已修复合入（PR #392，`c4a4ea17`），8792 已切 `54a6f0966ecb`，切后冻结题探针五判据全过。

- 切流正文：`~/.finance-runtime/cutover-20260825l-8792.md`（含回滚锚、账本、readiness、快照验证 6493P/0F）
- 切后探针收据：`~/.finance-runtime/disclosure-scan-p05-probe-20260825/`（`run_20260825_184015_292309`，与切前对照臂逐条比对）
- 设计稿：`docs/superpowers/specs/2026-08-25-sector-disclosure-scan-design.md`（v1.2）

## 这条线剩下什么（接手者从这里开始）

| 片 | 状态 |
|---|---|
| P0 / P0.5 | 已合已切，冻结题两发全过 |
| P1 | 未做：残差写手（只解释、不增删代码行）；巨潮详情/PDF 抽品种与金额；问句自定义窗口 |
| P1-b | 未做：残差 UX——0 工具降级 vs 研究缺口分列 |
| P2 | 刻意不做（模型从注册菜单点扫描，等开关板原子） |

已知残留（P1 词表活）：康弘「圭亚那《药品注册证书》」仍进 L_reg——境外注册与境内获批混层；西点「受理」类已被 P0.5 排掉。

## 坑（本单特有）

- 封顶只能落渲染层：`to_dict` 收据必须保留全量 excluded，否则裁判/回读丢证据。
- `L_reg` 排「受理」是标题级子串排除，联合标题（同含「受理」「获批」）会落 unclassified——fail-closed 方向，可接受。
- worktree 跑 e2e：`WORKBENCH_E2E_PORT` 换端口（8791 常被占，勿杀勿 reuse）+ `WORKBENCH_PYTHON=主树 .venv-workbench`（树内无 venv，回退宿主 python 缺 uvicorn）。
- `audit_deploy_ledger.py`：`record` 有 `--port`，`check` 只有 `--url`；真本账在 `$FINANCE_WS/state/deploy-ledger.jsonl`，`~/.finance-runtime/deploy-ledger.jsonl` 是无数据仓时的回退位。
