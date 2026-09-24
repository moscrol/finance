# 同题重复句绑定修补

## 这个分支做什么
Pi尾项队列的离线局部修补：同题重复句按出现位置绑定本次来源，不按文字展开所有组合。基座main03352758c，代码3198df4964f3fc52fff7488b17763955ba15e4f2。

## 当前状态
代码已本地提交，未push/PR/合main/部署，付费请求0。未接管#877原作者树7a89e2510。两组变异定义已入库但尚未运行，末次load1=9.31>8，不启动新测试。无本轮后台。

## 决策与被否方案
沿用题号与未消费句索引，否了文本去重和新增持久化ID；题内原有有序合同足够。只改question输出，边界声明旧映射不扩修。删前句后继续匹配其他文本，否了耗尽共享迭代器。详情见2026-09-25-material-claim-occurrence.md。

## 未验证 / 已知边界
原八问续稿同题重复组=0，本缺陷不是其方向/基期/库存定性/盈利预设错误的根因修复；真实八问仍失败。未做独审、新自然问答、全量Python、前端/E2E或registry整套准入。doctor报httpx0.25.2不符锁0.28.1，未改共享环境；收据可采信仅指当前环境与受验环境一致，不证明符合锁文件。边界声明及同文删句后的完整来源追踪未验。

## 下一步
load1<=8且预计pytest<=2时，以固定3198运行现有runner：--definitions scripts/review_probes/material_claim_occurrence_mutations.json --tests intelligence/tests/test_e2_material_claim_review.py --output <新目录>。再交独审；与#877合流及真实复验另行固定组合/授权，不移签收据。

## 踩过的坑
Knevo分支独有test_material_prompt_contract.py不在main，首次误列导致exit4/no-tests，原件保留。主检出他人脏改不动。公开投影已删某句时不能因匹配失败吞掉后句。

## 已验证
旧实现新例7F/1P，修后8P；固定3198相关21文件736P/4S、collected740，0F/0E；四跳过是旧同类引号排除。Ruff全仓、diff-check、提交hook、定向收据校验均过。收据20260924T161513Z-3198df49-efe4dcd1eb34.json；证据根~/.finance-runtime/reviews/pi-closeout-execution-20260924/material-occurrence-0925/。
