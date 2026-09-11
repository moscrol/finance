# 在途交接 · feat/capability-max-tier（已合 #608 → main `5cc5aa8b`，8792 已切）

## 这个分支做什么
用户 09-06 决策「先找能力 max，再按超限的部分加约束」。加 `max` 档（32 步 / 600s / reserve 60，硬顶 48 次 / 600s 收成 `PRODUCT_MAX_*` 常数）+ 三个 env 开关（`WORKBENCH_RESEARCH_TIER` / `WORKBENCH_TOOL_AUTHORIZATION=all` / `WORKBENCH_TOOL_MENU_HIDE=off`）+ max 档每批帽 4→8。env 不设时逐字节同前。全文 `docs/verification/2026-09-07-cutover-max-cockpit.md`。

## 决策与被否方案
- 8792 直接改 max 形状 / 否 8796 对照臂 / 用户拍。
- sol@57244 主、terra 兜底、同网关双链 / 否单链 / 单链撞 `_retry_single_real_provider` 4×4；08-08 弃 sol 的延迟依据在 57244 上不成立（sol 4.8s）。
- 起步已在 deep 之上时「批 deep」空操作 / 否照旧 replace / 否则 600s 被「升」成 240s。
- 方法论题空授权不随 `all` 放开 / 它是防泄漏规则不是预算规则。
- `ASK_TOOL_BATCH_TIMEOUT=60` 注掉 / 否改 540 / 只能下压的保险丝，留着等于没切档。
- Gitea token 本机 CLI 重生成进 `gitea-local/a77-token` / 否等用户解锁旧钥匙串 / 文档描述的就是这个位置。

## 当前状态
8792=`5cc5aa8bf1e9`，出口 cockpit 57244（sol/terra），max 形状五 env 在启动器。health 三读一致、readiness 13/13、账本 switch ok。回滚锚 `~/.finance-runtime/cutover-20260907-max-rollback-8792.txt`；启动器备份 `.bak-20260906-pre-cockpit`（中转+GLM）、`.bak-20260907-pre-max`（cockpit、standard）。gitea 备份 `post608` **未打**。

## 未验证 / 已知边界
- 同题对照只 n=1：max 16 调用 0 错 `completed` vs standard 8 调用 3 错 `partial`；143s vs 65s。不读成质量提升。
- sol 在 57244 上的 PLAN 率未量（两轮都无 PLAN），子研究可达性未证。
- 判官删句 / 弃权率 / 成本在 max 形状下零读数。
- 登录钥匙串 09-06 被重置：GLM / 中转 key、gitea 网页密码仍在 `login_renamed_1.keychain-db`。

## 下一步
1. 打 gitea 备份 `~/backups/gitea-20260907-post608.tar.gz`。
2. 冻结题集（knevo28 + D 组 10）跑 max 形状，按 verification §4 出六项读数；只对超限项加约束。
3. acceptance-workflow §4 的 `record --action switch` 补 `--port --ledger`（不带会静默不写，09-03 五次切流行全漏）。
4. `sub_research` 工具（spec 09-03）视 PLAN 率而定。

## 踩过的坑
- Keychain 项消失先看 `~/Library/Keychains/` 有没有 `login_renamed_*`。
- `audit_deploy_ledger.py record --health-json` 要 JSON 字串不是路径；`switch` 不带 `--port/--ledger` 静默不写。
- 8796 sidecar 只 source 主启动器 `^export` 行，secret 必须写在 export 行上。
- 启动器备份要在改之前 cp。

## 已验证
门禁 7924P/0F 同基线红集；11 新测试 + 3 变异各击杀 1；两次切流三项验证全过；`served_model` 逐轮 `gpt-5.6-sol`。
