# 东财熔断 · #60 合并候选与部署预演（在途）

分支 `fix/eastmoney-circuit-breaker-0922` = PR #856，树 `~/fwp-wt-eastmoney-circuit-breaker-0922`。
**未合、未装机。** 时限：09-23 18:30 前熔断须进夜跑 sync 代码根；用户 17:00 前给部署授权。

## 已做（09-22 23:30 起，S3）

- 推了 `fix/eastmoney-snapshot-direct-ip-0922`，并入其根因修正交接；前向到 `gitea/main@f24a61a8a`，零冲突，两个代码文件未被前向改动。
- `01e25264f` 只改文案：`UpstreamRefusing` 的 message/注释从「按出口 IP 封禁」改为「端点拒绝服务、连发拖垮同主机端点」；判据与逻辑未动，测试断言收紧。
- `9876f0e60` 钉根，照 #827：两份 plist 的 sync 根键、s7 launcher 缺省、wiring 测试常量四处 → `finance-sync-01e25264f218`。
- 已建代码根 `~/.finance-runtime/finance-sync-01e25264f218`（detached @`01e25264f`，干净）。干净 shell 导入探针 + 63 例定向测试在根内通过。**尚无 plist 指向它，非生产。**
- 阳性对照：阈值 3→999 恰红熔断组 3 例，还原后 11 绿。
- 证据 `~/.finance-runtime/reviews/eastmoney-cb-deploy-20260922/`：四叶收据 `gates/`、装机 dry-run、plist diff、B 方案补丁与 before/after sha256、明日 runbook `deploy-steps.md`。四叶结论以 PR #856 描述为准。

## 明日（每步一句授权）

- A 正门：用户确认 → `gitea_pr.py merge 856 --yes --expect-head <head> --record …` → 合后 main 干净检出跑 `install_eval_launchd.sh --nightly-only --dry-run` 贴出 → 授权 → 去 `--dry-run` → `plutil -p` 与 `launchctl print` 回读 `FINANCE_SYNC_CODE_ROOT`。
- B 临时：17:00 仍未合 → 按 `plan-B-hotpatch/` 只热补 snapshot.py 进旧根（fund_flow 指纹未变），落 `deployment-circuit-breaker.json`。
- 19:00 后回读 sync 日志：clist 请求数 ≤ 3×host；`UpstreamRefusing` 一条之后该 host 零请求。

## 边界

未碰生产库、未装 plist、未动 8792 与旧根 `finance-sync-adcda94b5e40`（保留作回滚）。python 叶带 `--ignore=scripts/archive`（#58 未合，仓根收集仍 Interrupted）。#61 若要进同一根，需重钉到合后 main tip（四处同改）。
