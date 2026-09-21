# 晨汇消费质检修复

## 这个分支做什么
修 IMA 缺输入假成功，验证 KB 补档经教学旁路进入时间长河；不发布生产。

## 决策与被否方案
- 缺队列 exit 2；否决泛改 runner，缺陷局限在具体 CLI。
- 真实行情只读 + 独立教学库；否决更新脏主树/覆盖共享库。
- 缺行情保留 BLOCKED、二维空值保留 NULL；否决造行或提前可知时间刷绿。
- 细节与复跑：`docs/handoffs/2026-09-22-briefing-qc-closeout.md`。

## 当前状态
代码已提交 `a7288f503`，未合 main、未部署。KB 内容已提交 `fix/briefing-evidence-qc-0921@0ad67b928`。基线028a251a1；最后fetch时main=e82717d9a，尚未合流。

## 已验证
- 干净代码提交80 passed/7 skipped；Ruff/提交钩子通过。收据 `docs/verification/2026-09-22-briefing-consumption/targeted-tests.json`。
- 正式build-labels读取真实库、独立输出；09-15落09-16，0/6/6、二维、market_confirmed=NULL、lag5。真实slice_river读到，关闭开关不变，strict过滤3个事后教学对象。
- 09-18有13行，但行情截至09-18，下一交易日消费BLOCKED/exit2，见同目录river-acceptance.json。

## 未验证 / 已知边界
未跑两仓全量合并门禁、前端/E2E、生产部署/自然问答、索引发布或官方金融事实核验。7项旧测试因隔离树无默认真实库跳过；脚本真实验收不代签它们。
普通切片trade_date_only，没用冻结行情快照；只认证晚写教学对象过滤。长河是市场级统计，不含晨汇全文。

## 下一步
独立审核、候选合流全叶门禁，用户确认后合入。部署另核KB版本、运行代码与教学库绑定；行情补齐后按真实时间重建并复跑 `scripts/verify_briefing_consumption.py`。不直接更新他人的主检出。

## 踩过的坑
概念页不存在会被IMA报告跳过，测试有效队列必须有页面。验收用final库，不用手填computed-at的首次试跑。产物在 `$HOME/.finance-runtime/reviews/briefing-consumption-qc-0921/`，库不入Git。缺行情不是PASS，配置部署不是实际执行。
