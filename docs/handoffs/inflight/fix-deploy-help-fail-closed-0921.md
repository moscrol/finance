## 这个分支做什么
修复旧部署脚本把 `--help` 当真实部署的事故入口，保留恢复证据。背景见 `docs/handoffs/2026-09-21-deploy-help-incident.md`。

## 决策与被否方案
- 帮助先退出，写入需 apply/显式源/完整SHA/干净树；不保留隐式部署。
- Git快照和目标 intelligence 软链拒绝覆盖；版本快照新建切链，不销毁回滚身份。
- 恢复同版本新快照；否了部署最新main，其含已回滚K3变更。

## 当前状态
代码已提交：4f9a2af56 + 8a82ec780。PR #846 保持WIP，未独立验收、未合入或部署；最新代码推送/复验以PR回读为准。
8792运行 `~/.finance-runtime/finance-workspace-adcda94b5e40-recovery-20260921`。旧受损目录是同父目录下 `finance-workspace-adcda94b5e40`，不是回滚目标；事故材料在 `~/.finance-runtime/reviews/release-831-20260921/incident-8792/`。

## 未验证 / 已知边界
- #846未跑完整Python/前端/E2E/registry门禁，不可合入。
- #831仅旧生产基线候选165038af通过；main028a251a与原head的合流树c4ebdbd4未测，仍WIP，不部署。
- 8792健康且真实问答完成，readiness仍503：数据库09-18、快照09-21不一致，不能改数据凑绿。
- 旧主检出脚本仍危险，不得执行其帮助探测。检查不提供运行期换链/并发写锁，也未验证standalone真实部署成功链。

## 下一步
推送最新代码并从干净提交复验59项及Ruff/语法，留PR收据；独立验收者固定实际合流树后补全门禁。行情日期差另查数据链路归属。禁止沿用旧收据解除WIP或直接部署main。

## 已验证
基础4f9a2af5干净收据 `20260921T135024Z-4f9a2af5.json`：57P；软链补丁改动树 `20260921T135920Z-4f9a2af5.json`：59P，不冒充干净提交认证；均在 `~/.finance-runtime/test-receipts/`。语法/定向Ruff绿，基础全仓Ruff绿。三轮撤保护分别3/6/2例断言红，正式代码已恢复。
#831候选前端规范收据六步绿、110单测、E2E34P/2S；同证据根registry五项日志通过。只对165038af成立。

## 踩过的坑
帮助选项不是天然只读；先读源码，测试用临时目标/命令替身。health、readiness、问答分账。harness-reference有他人BUILD.md改动，通用索引回填暂缓；正式保护已落实际脚本和回归，不另造部署器。
