# fix/pr868-delivery-validation-0924

## 这个分支做什么
在deliver_stage接受前核探针路径，让审查者在原阶段剩余预算内修正；不改产品循环或封存批。

## 决策与被否方案
从#906的4e0ca6373延伸，否重复complete修补。即时拒收加原退出检查，否宿主代补路径/额外请求/重开封存批。临时测试独占随机端口，不停别人审查。背景见`../2026-09-24-pr868-delivery-validation.md`。

## 当前状态
独立树`~/fwp-wt-pr868-delivery-validation-0924`已推gitea并开#910/WIP；实现4bda6613e、隔离测试3e8ea5b64。#906已由owner合入#868，本PR已改base=feat/adaptive-research-loop；相对f261预演无冲突。未合main/部署，未改原owner树。
#868作者已前向f2610293f并开始工程验证。2105封存批仍spec有保留通过/C3C7未验、quality路径阻塞、213/244；20260925-next只观察到准备脚本，无STATE/授权，本会话未执行。
研究链交付另见#911与`~/fwp-wt-pi-research/docs/handoffs/2026-09-25-pi-research-forward-delivery.md`。评论#906/6854、#868/6857已通知owner。

## 未验证 / 已知边界
只验协议，不证明自然模型纠错/研究质量。未跑本枝全仓/前端门禁、独审、L6或8792 HTTP。
prepare保留历史候选配置，不能直接执行；4e0拒reviewer全部控制器字段，而2105临时版曾容许complete=true，协议和提示词必须一起更新。
09-25观察共享venv的httpx0.25.2不符当前锁0.28.1，已通知owner，未改环境；旧57P不作新环境门禁。

## 下一步
1. 原owner审阅#910相对4e0的两个补丁，再固定最终候选/基座、重建输入、做工程及身份准入，另取明确额度。不续1405/2105、不继承旧收据。
2. 独审闭合后接#76/L6逐行授权；合main、部署分别确认。
3. 复用已有生成器和测试；可迁移原则已回写共享知识，无新框架。

## 踩过的坑
删/private仍是有效/var别名。测试先绑定私有随机端口，生产仍固定19899；4P/53S不能作通过。最终保留请求失败直接停，不追加轮次。

## 已验证
干净3e8ea5b6488f：57P/0F/0E/0S，collected57，真Pi CLI+本地假响应，真实模型0。双轴路径反馈、撤验证变异、预算硬停、交付后文件消失及原回归；Ruff/node/提交钩子通过。
原收据`~/.finance-runtime/test-receipts/20260924T142406Z-3e8ea5b6-bb7eca42a070.json`仅属当时tests/test_pi_review_repair.py及3e8，不移签PR文档HEAD、f261或新环境。
