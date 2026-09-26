# L7 生产行情断档回补（09-21～09-24）· fix/local-backfill-0923-0924

## 当前状态
- 证据目录 `~/.finance-runtime/reviews/unclosed-inventory-20260926/takeover/L7/`（下称 EV）。生产库只读：09-26 16:50 以
  `hold_swap_lock`+`clone_to_staging` 克隆一次（`baseline.json`），此后逐步核对生产 dev/ino/size/mtime 未变（`steps.tsv`）。
- 缺口比简报大：生产 `fact_market_daily` 无 09-21 行、09-22 只有指数空壳行（51 列空），派生层停 09-18。四个交易日按
  local 计划串行补在 EV staging：个股 = 同花顺桥（mootdx 实测停供），名单冻结 + stitch 180 天，本地派生，`features`。
- 09-23/24 在 `compute-limit-stats-local` 被 `InvalidStockName` 拦：桥对新股无历史名。本分支加
  `skills/duckdb-backfill/scripts/attach_capture_names.py`：只给 `hithink:*` 空名行补名，名字来自封存的同场次腾讯捕获
  （既有验证器校验范围/哈希/收盘后时间戳），逐行钉价量，拒绝生产库。补了 5 行：301686.SZ C中塑股份（两日）、
  920229.BJ 世纪数码（两日）、920025.BJ 凯达重工（09-24）。**是否接受该名称来源＝09-22 决策页合同 1，待用户拍板。**
- staging 冻结：`EV/prepared.json` sha256 `4023cd0f…129913`；换库脚本 `EV/publish_prepared_staging.py` 干跑全过。

## 下一步
1. 用户确认名称来源 → 协调者按 `EV/swap-commands.sh` 换库（含备份/回滚/就绪检查）。不接受 → 本 staging 作废，另议。
2. 后续工单：夜跑桥兜底遇新股仍会同样拒跑（结构性），需要合同 1 定案后接入。

## 已验证
- 四日×验收四件在最终文件上全绿：`check_daily_review_data --plan local` COMPLETE、`check-daily --plan local` PASS、
  `qa_backfill_align --plan local` PASS（WARN 仅 turnover 按合同为 NULL、fund_flow 复盘会独有）；双红 13/45/0/0。
- 桥接行与新浪日期化日线抽样 30/30 一致；与腾讯捕获逐只一致。定向测试 + 7 个变异核对（`EV/review.md`、`EV/mutation.log`）。

## 未验证
- 换库本身与换库后 8792 readiness（未执行）；名称来源的合同层认可；四叶全量门禁未在本分支跑（按须知由协调者统一跑）。
