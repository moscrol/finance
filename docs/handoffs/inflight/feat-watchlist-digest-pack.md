# 在途交接 · feat/watchlist-digest-pack

更新：2026-08-26 22:05 CST · spec `docs/superpowers/specs/2026-08-26-watchlist-digest-pack-design.md` **P0 完成**（包 + 路由 + CLI），**未合并、未动 8792/8796/8802**。

## 状态

- 分支 `feat/watchlist-digest-pack` @ `4101e214`（基 `gitea/main`=`0735bbe6`，已推 gitea），树 `/Users/a77/fwp-wt-watchlist-digest`；主检出树没动。
- **台账撞号已处理**：spec 预注册 `R-20260826-01…03` 在落表前被当日其他 session 占用（那三行已 confirmed），按 `R-20260824-31` 先例改号 **`R-20260826-05/-06/-07`**（路由 / 快照合同 / 只委托四袋），spec §11 有改号记录。三行 outcome=`pending`，「怎么验」只填了离线收据，**执行方未标 confirmed**。
- 主树上那三份未提交的钉子（spec / 词表 / prediction-ledger 预注册）已随本分支入库（台账为改号版）；合并后主树对应 dirty 可丢弃。

## 测试收据

- `intelligence/tests/test_watchlist_digest_pack.py` 24 钉**先红**（ImportError 收据）**后绿**；定向相邻面 335 绿。
- 全量一读（未提交树）：6623P/1F，唯一红 `test_agent_review_worker.py::test_worker_shutdown_terminates_reviewer_process_group`（进程组关停，单跑 0.69s 绿）。
- 全量二读（提交后 @`4101e214`）：**6624 passed / 0 failed / 12 skipped**，收据 `~/.finance-runtime/test-receipts/20260826T135533Z-4101e214.json`。一读那 1 红未复现 → 负载抖动，与本单无交集，无在案 flake 记录（若再见建议立案）。
- 真库只读 CLI 冒烟：空画像 → 缺口句 exit 0；临时画像「黄金概念/医药」→ fact 行（1.74%/17.11%/990.42 亿）+（推断）多袋行 + 快照落 `~/.finance-runtime/watchlist-digest/smoke/2026-08-26/`。

## 未做（点头再做）

- P1：`focus_themes` 命中挂发酵摘要（tracer 纯函数入口）；Workbench 快照证据页；Claude Code skill 软链。
- P2：夜跑默认用户简报工件。
- **Live 验收**（合 main 后、切 8792 前，见 spec §9）：⚠ 真用户 `linxiaoqi5111` 当前画像**没有** watchlist/focus_themes（真大脑目录 `~/.local/share/finance-workbench/users`，vault 那份已 RETIRED）——live 前用户须先钉清单，否则只会看到缺口句（这是正确的 fail-closed，不是 bug）。

## 已知边界

- 接合是文本包含（与主线∩双红同源、复用 `_names_match`）：`AI` 对不上涨停热度袋的 `人工智能`。spec 禁止第三套模糊匹配；别名映射留给后续决策。
- 库打不开/写锁 → `locked_db`（不冒充「该日无行情」）；显式日无行 → 全文只有无行情句、零邻日数字；清单空 → 缺口句、不回落 `market_watch`。
- 快照：QA 路径自动写、CLI 默认只读（`--write` 才落盘）；目录 `~/.finance-runtime/watchlist-digest/`，`WATCHLIST_DIGEST_DIR` 可重定位。episode 里只有瘦收据（`report["watchlist_digest_pack"]` / `watchlist_digest_snapshot`）。
