## 这个分支做什么
FINANCEWORKS-8：评分准入、Mac摘要和日期首次点击修复。本分支已合入，当前工作接续codex/memory-consumption-closeout-1004。

## 决策与被否方案
| 选了什么 | 否了什么 | 为什么 |
|---|---|---|
| 局部修复按范围验收 | 工程绿代表答案质量 | 原始自然提问仍有召回/控制器缺口 |
| 默认keyword保持 | 按带主题召回高分切默认 | 用途污染和真实输入未验 |

## 当前状态
GitHub PR32固定65999171bec7通过门禁后合入，PR32/33最终主干abdb31ec38dd。Gitea本轮备份success。8792仍ffe1c60d84da，未部署本增量。完整状态及原件见docs/verification/2026-10-04-memory-consumption-closeout.md和同名receipt。

## 已验证
干净完整Python 20366P/78S/2X、收集面无收窄；前端lint/typecheck/test/build/E2E、GitHub五项和独立Spec/Standards均过。旧环境红、日期竞态红、构建改脏树和中断收据均保留且未采信。

## 未验证 / 已知边界
真实flash首对未通过准入：旧版目标漏召回；候选控制器超时转一般金融研究后未交付，另有诊断知识库隔离遗漏。两次保留，余六次停止。不能宣称弱强模型获益或记忆整体验收完成。

## 下一步
从接续分支inflight和同日memory-consumption-followup-spec继续；任务板FINANCEWORKS-8仍in_progress。发布另需固定合并SHA门禁与真实入口内容证据。Pi活动树及主检出只读。

## 踩过的坑
完整门禁PATH需含uvx；build跟踪产物要先提交。WORKBENCH_KNOWLEDGE_WIKI优先于KB_VAULT；EpisodeState用to_dict序列化。已见题不能转成独立留出题。
