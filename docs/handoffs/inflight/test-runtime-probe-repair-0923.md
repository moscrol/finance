# Runtime 探针量具修复

## 这个分支做什么
将上一轮 K3 探针修成可执行、能辨别有效撤保护失败的工具；产品源码不改。

## 决策与被否方案
用户已明确可用 K3 写手，已实际委派；两场均请求超时、0工具。宿主随后修副本并验收，否决冒称K3完成/无限重试/用局部绿改写全局独审。详见 `docs/handoffs/2026-09-23-runtime-probe-writer-followup.md`。

## 当前状态
产物在 `scripts/review_probes/runtime_identity_effects/`，runner自测 `tests/test_runtime_identity_effects_probe.py`，9原件封存在 `docs/verification/2026-09-23-runtime-probe-repair/`。本枝继承1ef5bc3ec文档，产品基座ffd1b7f15；未推送/合main/部署。

## 未验证 / 已知边界
被测仅固定760248ecebc7的身份与未知效果预算；旧整体验收仍BLOCKED。未验保存失败/锁争用/重入/inbox/完整交付/入口异常合同/真实计费/完整跨进程驱动。没有本枝全仓及前端绿收据。

## 下一步
按README可复跑工具；K3通道恢复后按单合同委派实现，宿主单独验收。不需再通读全栈后才动手。新prod修改先独立复现；不可重复合#865或将旧门禁移签后来main。

## 踩过的坑
K3首次124.769秒超时；手动补试300秒等待仍126.488秒收到上游504，本地health200不代表模型可用，非额度返回。宿主首轮嵌套mappingproxy红改用事件to_dict；unit首命令漏TMPDIR导致收集前失败，均非产品缺陷。
探针文件命名*_checks.py，显式选择，不能改成默认test_*.py。shadow必须注册sys.modules、用其自己的异常类型。单看退出1会误把收集错误算有效变异。

## 已验证
仓内工具固定760248：16P→身份7指定红/4P→预算2指定红/3P→还原16P，0error；runner13P、目标Ruff绿。两种变异，不是9种；原K3三文件哈希及候选树不变。两写手进程已退出，无K3代码产物。原件路径见日期快照。
