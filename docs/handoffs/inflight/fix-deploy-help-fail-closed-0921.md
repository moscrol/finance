## 这个分支做什么
修复旧部署脚本 `--help` 真部署事故。背景 `docs/handoffs/2026-09-21-deploy-help-incident.md`；最新门禁和审查边界见同目录 `2026-09-21-deploy-help-gates.md`。

## 决策与被否方案
- 帮助先退出；写入需apply/显式源/完整SHA/干净树，不保留隐式部署。
- Git快照及目标intelligence软链拒绝覆盖，版本快照新建切链。
- 恢复同revision新快照，不部署含已回滚K3的最新main。

## 当前状态
源码4f9a2af56+8a82ec780、被测完整提交d3d27bce已推送。#846仍WIP，作者工程全叶通过，独立审查无结论，未合并/部署。PR评论5464、#831评论5465已写；之后只追加交接文档，不将旧收据移签新SHA。
8792仍为 `~/.finance-runtime/finance-workspace-adcda94b5e40-recovery-20260921`；同父目录旧adcda94b5e40树是受损现场，不作回滚。证据 `~/.finance-runtime/reviews/release-831-20260921/incident-8792/`。

## 未验证 / 已知边界
- 独立Claude首轮bare未登录；次轮safe-mode只读240秒超时无输出，原因未明，不是PASS；本轮进程均结束，QC临时树已核查后移除。
- standalone真实部署成功链、运行期并发换链/写锁未验；旧主检出脚本仍危险，禁帮助探测。
- #831仅165038af候选通过，028a251a与ea5c3a94合流c4ebdbd4未测，仍WIP、不部署。
- 8792healthy且问答完成，readiness503：数据库09-18/快照09-21，不改数据凑绿。

## 下一步
有界恢复独立审查并固定最新base/head，临时目标复跑防护反例；无签字不解除WIP，合并另需真实授权。行情日期差另查数据链路；磁盘约5.7GiB，先协调空间，勿重跑第二套全量或删他人树。

## 已验证
d3d27bce全量12528P/85S/2xfail、Ruff0；收据 `~/.finance-runtime/test-receipts/20260921T142641Z-d3d27bce.json` 校验0，依赖/解释器/干净身份匹配。证据根 `~/.finance-runtime/reviews/deploy-help-846-20260921/`：前端六步0、110单测、E2E34P/2S，registry五项0，JUnit/rc/首尾身份齐。固定base028a251a的预览树77f9bc59与被测树相同；仅文档后继不冒充同SHA。定向59P，三轮撤保护3/6/2例红。

## 踩过的坑
帮助不是天然只读。收据插件忽略FWP_TEST_RECEIPT_DIR，实际路径取完整stdout，不凭预期目录判缺失。健康/就绪/问答分账。harness-reference有他人改动，通用目录回填暂缓；正式保护已进部署入口与测试。
