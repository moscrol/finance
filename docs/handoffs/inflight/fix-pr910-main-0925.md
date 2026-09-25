## 这个分支做什么
#910在#868合入后的main上前向，改PR基座并重新验证；不合main、不部署。

## 决策与被否方案
| 选择 / 否掉 | 理由 |
| --- | --- |
| 前向merge / rebase强推 | 保留原父链，原PR可以快进更新 |
| 各PR分账 / 旧fb41移签 | 旧组合范围及基座不同 |
| 四项定向 / 并发叠全量 | 三套他人全量在跑，固定端口沙箱暂不启动 |
展开：`docs/handoffs/2026-09-25-pr910-main-forward.md`。

## 当前状态
新代码候选4ad2cb42b0c58d9b3997a435568eea5e549bccdb，main基座1751e21e0fd30642e0b223604b64b30e38c46f41。merge-tree与实际源码树相同、无冲突。PR#910 base已改main，仍WIP；远端发布分支fix/pr868-delivery-validation-0924，本地工作分支fix/pr910-main-0925。后续文档HEAD不自动继承收据。

## 已验证
固定`/Users/a77/fwp-wt-pi-research/.venv-workbench/bin/python`，依赖66726d345bf37ce5；干净4ad2：doctor/Ruff/PR diff-check/registry五项通过，四目标4P/0F，唯一收据精确SHA/目标/固定main零漂移核验exit0。
证据`docs/verification/2026-09-25-pr910-main-forward/`，原根`~/.finance-runtime/reviews/pr910-911-forward-20260925/910/`。

## 未验证 / 已知边界
完整73例修补套件、沙箱内C3/C7、全仓Python、前端/E2E未重跑；不把4P称整套通过。两轴独审/自然模型/L6/8792未验，本轮付费请求0。旧批STOPPED保持，不能复用授权/余额。

## 下一步
空闲后固定候选跑完整沙箱套件与四叶；main漂移时重评并重绑。工程齐后另申请明确独审额度。保持WIP，不自动合入或部署。

## 踩过的坑
旧收据不继承到新SHA。资源采样非全机锁；不杀他人进程。生成器默认带历史配置，不能把生成等同授权或直接启动。
