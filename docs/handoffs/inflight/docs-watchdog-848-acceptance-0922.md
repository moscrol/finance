# #848 验收收尾

## 这个分支做什么
记录 watchdog 测试修复独立审查与固定版本全叶门禁；文档分支不推进受审 #848 head。

## 决策与被否方案
- #848 固定 `2007edfa5de9c0db704095a51fa54a318362d59b`；否了补文档后移签收据，改用独立 docs 分支。
- 沿用0.2s预算与真实线程，否了扩生产预算；0.8s已收窄为到期至watchdog返回，旧整轮时延保证不宣称保留。
- E2E缺浏览器先补缓存再单次复验；否了无解释重跑全仓，保留原红收据。
- 背景/限制/证据：`docs/handoffs/2026-09-22-watchdog-848-acceptance.md`，原独立报告在 `docs/verification/2026-09-22-watchdog-848-independent-review.md`。

## 当前状态
- #848 open/WIP，head2007edfa5；base main `e82717d9a7c3dfa811a4538bd44985b61258355a`。用户只授权验收，未授权本次合并。
- 当前分支只交付文档，不纳入代码收据；旧fix分支交接“无PR”已过期，以本文件及#848评论为准。
- 生产仍adcda94b5e40 recovery；未合/部署/重启/改行情，#846仍WIP。

## 已验证
- 独立Claude session `7bf22b99-ba7a-4dbf-aa0e-08e8848a8fb6`：两轴PASS_WITH_LIMITS，只有一位审核者，非双签；自行2P+2P与反例1F，首尾干净。
- 固定2007edfa5完整Python12511P/85S/2X，Ruff、registry五项0；原生收据 `20260921T183408Z-2007edfa.json`，来源/完整SHA/base drift0校验通过。
- 前端前五步0、单测110P；E2E首轮缺浏览器27F/9P，补v1179后34P/2S、exit0；首尾身份稳定。
- 门禁根 `~/.finance-runtime/reviews/watchdog-full-gate-20260922/`，`audit/evidence-audit.json`核对日志哈希/JUnit/收据；merge-tree clean且等于受测树。

## 未验证 / 已知边界
- 候选绿不覆盖正式main原12509P/1F；实际merge commit尚不存在、未验。
- 独立限制：模块时钟影响同进程所有deadline；整轮真实时钟合同缺口；异常诊断和线程窄窗。当前永久挂起未复现，报告假设场景另列。
- 首次E2E日志/收据保留，但默认test-results被重跑清理，首轮trace包未归档；安装exit码未采集，ps的1不能充当它。
- Codex限额与首轮Claude认证失败无结论；旧作者107P文件名independent不代表独立。

## 下一步
1. 用户确认#848精确head/base及限制后，才解除该PR WIP并合并；#846不动。
2. 合并后实际main再跑完整门禁，生产禁令不因测试绿解除。
3. docs分支单独处理，不移签代码收据；不整体部署含未验K3的main。

## 踩过的坑
- `ps`退出码、收据来源码、测试退出码不可混用。
- 临时重跑会清默认Playwright输出，先归档再执行；不碰他人树或事故现场。
