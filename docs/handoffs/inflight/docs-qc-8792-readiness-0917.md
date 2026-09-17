# 8792 独立质检

## 这个分支做什么
核验 #781/#779/#782 与测试准入，另按授权清盘；业务逻辑不改。裁决 `docs/handoffs/2026-09-17-8792-readiness-qc.md`；最新清盘 `docs/handoffs/2026-09-17-system-disk-cleanup.md`。

## 当前状态
质检完成、三类缺陷待修；main=0a1cb8c4，8792=bf662e9310ff，仅四文档差异。两轮清盘完成：5.4→28.3→36.7GiB；第二轮清缓存/安装包/闲置Docker构建产物及29棵已合无脏临时树，留恢复映射。8792与原容器状态不变；未重启/写生产/删聊天。
不能签「全部落地」；可准备隔离小规模测试，不宜直接批量效果比较。

## 决策与被否方案
- 选独立干净树；否主检出混合改动测试，无法归属 revision。
- 选反例+同树部署源码离线重放；否全绿测试代替行为验收。
- 选固定范围分项验收；否等真人周期全部结束才做工程测试。

## 未验证 / 已知边界
- F1/P1：`不需要登记这只股票为长期跟踪` 仍写 checkpoint；正则禁「只」误伤量词，8字间隔也漏常见长句。真实编排层同样复现。
- F2/P2：新日期门把未来复查计划当证据日期错配删掉，llm/off 均触发。仅移除新检测器则保留。
- F3/P2：冻结财务题加【输出要求】或编号列表→question空/materials=1，路由变 kol_review/subject=null。
- #770 仍 WIP，D6/P7 等未签；RE06 I14 任务级链未闭，I13/I15/#53真人或前向协议待授权。不能照旧交接把已合功能当缺失。
- 生产仍 llm、证据判官 auto；改 off 需确认。judge_mode 看私有 semantic_verifier，不在公开 gate_receipt。
- readiness 请求09-17却服务09-15；最新行情题先补数或明确冻结历史日。清盘未改变行情覆盖。
- 本轮无新模型请求、无前端/E2E复跑；仅复核原同树107P/34P+2S证据。

## 下一步
1. 修F1→F2/F3并纳入正式回归；`scripts/review_probes/qc_8792_readiness.py --repo <干净树>` 应从exit1变0。
2. 固定候选完整门禁→用户确认合并/部署；判官模式另确认。最新数据与真人协议分线推进。
3. #55步骤10的旧收据路径、门页off生产取值文字需订正。

## 已验证
main干净源码 Ruff0、pytest11435P/0F/81S/2xfail；收据20260917T105500Z-0a1cb8c4.json校验通过；registry五项/路径检查0。新探针main与部署各15项、9失败/6对照过/0error/0skip，三类缺陷非九个bug；源码指纹一致。
结果：`docs/verification/2026-09-17-8792-readiness/results.json`。原始证据：`~/.finance-runtime/reviews/qc-8792-readiness-0917-0a1cb8c4/`。

## 踩过的坑
同SHA的10:50收据是零用例；空地图不作证据。探针exit2=加载错、exit1=拒收，须收编回归。APFS大小≠回收量；恢复映射：`~/.finance-runtime/reviews/disk-cleanup{,-system}-20260917/`。第二轮工作树看receipt-v2；首版是0删除跳过。不得盲跑一次性清理器。
