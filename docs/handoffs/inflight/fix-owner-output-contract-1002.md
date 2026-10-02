# 输出身份候选阻塞；接续转向 Harness 减法

## 这个分支做什么
保留2aea基座上的输出身份窄修复；用户纠偏后停止单题正文补丁，评审并行通用方案。

## 当前状态
代码4cba44a63、旧文档6ef1d41e9；本轮评审/快照首提交4000f7ab1，后补收尾条件，未改产品。历史相关632P/1F，**仍禁止合入/发布**。正文边界反例保持正常红，非xfail。
并行总spec：`~/fwp-wt-harness-simplification-1002@acc743c84`（产品基线3b78fda25），v0.1 Draft未实施；本轮不改对方树，两个补丁栈收据不能互签。

## 决策与被否方案
| 选 / 否 / 原因 |
|---|
| 拆用户要求与系统建议 / 否词表、单题例外 / 共性是语义管辖权越界 |
| 保来源/权限/预算硬边界 / 否全部删门 / 少规则不证明质量提升 |
| 建议复用PLAN单入口与解释版本 / 否重开规划器或改旧hash / 避免多owner及恢复失配 |
展开：[接续快照](../2026-10-02-knevo-takeover-contract-review.md)。

## 未验证 / 已知边界
21例只测旧AnswerSpec词面门，不能推广到全Episode或算产品误判率。可选项单独缺失仍complete；另有必需项失败时才在补写反馈混成必需。
PLAN已有修订，但自拟answer_elements只能增加；TaskFrame hash/授权v1快照固定。新解释不能只改一处hash或重造预算。
没有替代方案实施、独立评审、自然模型收益、全仓/前端重验。Knevo材料非源码。原632P/1F不可签新版本。

## 下一步
1. 与v0.1 owner对齐消费者身份、PLAN撤回自拟项、版本/恢复、旧词面门退出权力四项，见[评审](../../verification/2026-10-02-knevo-takeover-contract-review.md)。
2. 冻结实施基线后只做P1语义权限；不同时改工具目录、方法、缓冲或修复次数。
3. R19封存/凭据退役、240格未放行；R17不重跑，R18归原owner。原身份红灯不因方向改变而豁免。

## 踩过的坑
源码episode_factory在services。Workbench验收不能用CLI ask冒充。锁解释器在`/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python`；共享httpx漂移。
原身份closeout.json和vault索引已确认存在。新索引被既有auto-sync先提交960b17d9；vault仍46条基线错误，不称全绿。

## 已验证
固定6ef1d离线复跑21例=8匹配/9误放/4误挡，与旧输出/哈希相同；真实verdict→补写/失败投影探针复现可选身份丢失。新增模型0，金融枝未推送/合并/部署。
私有证据：`~/.finance-runtime/reviews/knevo-takeover-20261002T140000Z/`；探针非HTTP/独审，未替代旧正常红测试。
