# 在途交接 · feat/watchlist-digest-pack

更新：2026-08-27 02:25 CST · **画像清单更正（用户纠偏）**：02:00 行写的「watchlist=飞书自选股表 13 只」已作废——用户指出**飞书已退役，连只读也不该依赖**（correction 已落 `record-correction`，原则：退役数据源连读取也不要依赖）。真实自选=用户口述 11 只（银之杰/航天机电/瑞华泰/广钢气体/汉得信息/用友网络/利民股份/新迅达/裕太微/志特新材/江钨装备），已写入 `profile.json`（provenance=用户口述）；派生题材按同规则重算为 4 个（人工智能 5/11、信创 4、工业互联 4、机器人概念 4，`n>=4`）。真名单简报复跑过：人工智能（涨停 6/11.54）、工业互联（5/9.62）命中涨停热度袋，快照 `snapshot-20260826T182251210968Z.json`。**自选清单唯一真本源=本地画像层**，别再去飞书找。

更新：2026-08-27 02:00 CST · **#439 已验收合并 @`547653c4`，本单闭环（QC session）**。验收方独立复验后自建 PR 合并（执行方原话「点头我就发 PR」——实际未建，验收方代建）：定向 111 绿（收据 `20260826T172454Z-001663fe.json`）+ merge-tree 干净 + 真库冒烟复算逐字一致（黄金概念 1.74/17.11/990.42 直查 `fact_sector_daily` 对上）。批次门禁四叶 @`547653c4` 全绿：pytest **6654P/0F/12S**（`20260826T173511Z-547653c4.json`）、ruff、前端四连、e2e 15（8791 被占→8811 + venv PATH）、registry 4/4。live：**真画像已钉**——`~/.local/share/finance-workbench/users/linxiaoqi5111/profile.json` watchlist=飞书自选股表 13 只逐字（provenance 注明），`profile.derived.json` 放板块归属派生 10 题材（`fact_sector_stock_daily@08-26`，n≥4，可 stale 可覆盖），focus_themes 留空待用户手钉；CLI + Workbench（8999 临时实例，生产 env 形状）各一发冻结题全过，台账三行 **confirmed**（收据在台账行内）。**8792 未切**（spec §10 本单默认不切），watchlist_digest 尚未上生产，切流待用户裁决。⚠ 两条新知：① `smoke_workbench_self_use.py` 对确定性 owner 回合必报 `answer_snapshot_draft` 协议错（探针要求 draft_seen，确定性回合无 LLM 草稿阶段）——探针适配缺口非产品缺陷，下次切流/验收前建议给探针加确定性回合模式；② P0 四袋是板块/题材级，纯个股清单项必然全缺口——13 只自选股 live 全走缺口句是设计行为，个股级接合是 P1+ 议题。主树执行方三份脏钉子（词表 0 diff/台账旧号草稿/spec 旧稿）已验明逐字被合并版取代并清理，主树可正常 pull。P1/P2 仍待用户点头。

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
