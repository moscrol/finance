# fix/restore-ima-gap-report · 2026-09-21 · 恢复 IMA 缺口清单并回填 7 天

树 `~/fwp-wt-ima-gap-restore`，基线 `gitea/main@f2c3e9e1a`，HEAD `88f8276c4`（1 个提交，**未合 main，待用户确认**）。

## 断因（非脚本失败）

`ima-gap-report` 自 09-03 静默停产，产物断在 09-02。09-03 主检出树前移 main 时，
`intelligence/services/ima_gap_report.py` + 测试连同 `cli.py` / `daily_review.py` 接线被保管进
`wip/mainline-move-footprints-20260903`（该 handoff 明写「不合 main，归属者认领后自己决定」），
无人认领 → 主树切 main 后这一步消失。`ledger-map` 照登记着它：**台账说有、代码里没有**，19 天无人发现。
下游一直吃 09-02 旧清单（知识库仓 09-15 入库提交仍写「ima-gap 0902 积压」）。

## 做了什么

- 取回 `ima_gap_report.py`(253) + `tests/test_ima_gap_report.py`(83)，main 无、直接落地；
  import 依赖 `concept_page_gate` / `research_queue` 在 main 上**实测**齐备。
- 接线**只摘 IMA hunk 移植，不整份 checkout**——主线 `cli.py` 自共同祖先已演进 36 次提交，
  整份取回会抹掉 19 天改动。`cli.py` 两处纯新增（子命令 + `build_parser` 注册）、
  `daily_review.py` 一处 `CommandSpec`。
- 回填 7 天：09-07 / 09-09 / 09-14～09-18（14 个产物，与旧档同为 `ima-gap/v1`，已跟踪口径一致）。
- `ledger-map.md` 新增「IMA 缺口清单断档与回填」节记口径。

## 收据（全绿，可采信）

`ruff check .` 全过；`pytest -q` **12484 passed / 85 skipped / 2 xfailed / 0 failed**（1107s）。
`check_test_receipt.py` exit 0：revision 一致、干净树、依赖门禁未绕过。
另两项定向验证：① 跨日期 diff 7 天 7 个互异指纹（**非克隆回填**）；
② `build_daily_review_plan` 实测 `ima-gap-report` 落在第 16 步、紧随 `kb-ingest-receive`
（读 `research-queue.json`）——**下次 daily-full 自动带上，无需再手补**。

## 口径警告（勿误读）

回填清单拿当日 `research-queue.json` 比**当前** wiki 状态＝「以今天的库看，那天还缺什么」。
对「现在该去 IMA 跑什么」口径正确（已入库的正确判 `skip_have_deepdive`），
**不能当作「当时该跑什么」的历史证据**。
09-03～09-06 / 09-08 / 09-10～09-13 **永久补不了**：无 `research-queue.json`，缺的是上游日报线。

## 待办（执行是下一轮）

去重后 **10 个题材待跑 DeepDive**（数据中心、智能穿戴、汽车芯片各 2 天；风电/智能电网/核电/大飞机/培育钻石/LED/建材）、
**31 只个股待补 12 章逻辑卡**（寒武纪 2 天；余 30 只各 1 天）。走知识库仓 `concept-ingest` / 逻辑卡流程；
本轮未执行（打 IMA 上游 + 写知识库仓，属另一条链）。

## 下一步

1. 用户确认后合 main（合前 `git fetch gitea` 重跑等价 CI，main 会动）。
2. 主树 exports 已有同名产物（生产数据根写的就是那份），合入后一致，无需再拷。
