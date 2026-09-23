# feat/adaptive-research-loop 在途

## 这个分支做什么
#72 传输层绝对截止 / PR #868，及 #76 L6 候选验收；不合入、不部署。

## 决策与被否方案
- live 固定 `31f1b40dd`；全量工程收据固定 `7ad61a0d3`，不移签后来的预检工装 head。
- 三题各至多一次；Q2失败即停，否了补Q3/重发。判官 llm/flash、检索判官 auto，不做 off 对照。
- 原 protocol 保留，新 `protocol-closure.json` 接替终态；否了倒写原始运行证据。
- 工装问题与产品缺陷分开；否了把全部超时归咎候选。详见 `../2026-09-23-adaptive-l6-closure.md`。

## 当前状态
本批 **NOT_PASSED**，已完成审计、停批与收尾。Q1 partial/判官 unavailable；Q2 writer 两轮超时、零工具；Q3未提交。实际首发1/1/0，重发/续问0。#75仅核对并更新候选，独立双轴终审未启动。
归档在 `docs/verification/2026-09-23-adaptive-l6-closure/`；原件 `~/.finance-runtime/reviews/pr868-l6-natural-20260923-1455/live-r2/`。本次提交只归档报告/探针与更新交接，运行代码不变。PR已认证核对仍WIP/open/unmerged。

## 已验证
Q1逐句审计重放与原JSON一致，拒签PASS；冻结751/751无漂移，候选/生产稳定身份未变，密钥未落盘，拥有的进程/锁已释放。原候选严格模拟13场景零越窗。宿主离线复现shim流式缓冲，0模型请求。五处timeout直接来源已核对，并非全经Deadline.slice。

## 未验证 / 已知边界
Q1无实际repair新稿/自然迟到判官样本；parse_error不证明寒武纪本地无数据，Q2也不能评价查询能力。shim两次BrokenPipe、退出计数失真，read(65536)延后首块；没有证明它是历史超时全部根因。旧取消转发变异15P仍属测试缺口，未在新候选重做。KB/外部输入未冻结。#75、最新head完整门禁及联合main未验。

## 下一步
1. 独立修/验工装小块透传、断连与退出计数；新自然验收另获授权，不向本批补题。
2. #75按K3工单独占树/分段会话，作者测试与审查探针分账；补停顿期取消撤保护/还原。
3. 合入仍等用户明确确认；main已漂移，届时重冻head/base再验。

## 踩过的坑
模型修订稿未观测不等于候选revision未识别；run completed不等于质量PASS；shim落盘0不等于0请求。工程历史绿不覆盖新工装，冲突clean不等于联合树通过。
