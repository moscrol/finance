# docs/qc-sync-fcf9cca9 · 快速质检

## 这个分支做什么
独立复核 fix/sync-code-root@fcf9cca9 八笔提交。报告：`docs/handoffs/2026-09-12-sync-code-root-fcf9cca9-review.md`。

## 当前状态
**不放行**，只新增本分支质检文档；原分支/生产未改，未推送合并。

## 决策与被否方案
- 独立冻结树+无副作用探针；否了运行真实补数来证明错误写入目标。
- 肯定配置修复，不将19P或重载成功替代完整链路验收。

## 未验证 / 已知边界
1. **P1** 新SKILL一键命令显式指生产库、直调run_review_sync；无staging包装。shell run_sync也只修根，未修既有直写旁路。实际run_step子进程边界确认继承生产DB（已拦截，没有真写）。
2. **P2** 手动sync|all的干净shell未设专用根/档位时回退runtime/full；plist环境不传给手动shell。
3. **P2遗留** finalize生成仍在cd WORKSPACE后-m intelligence.cli，导入主检出脏树。需明确接替，不能称全链钉根。
4. 已加载两个launchd job是runs=0/never exited，不能称job执行exit0；只证明重载成功。
5. 本分支也重复「旧active --help=0」错误，实际2。关联607f53a6只有正常新旧分流过，整体未放行（前次报告08ca6edf）。
6. 未验真库local/full对照、15日命中率、名单与同花顺水位、全量或真实闭环。数据面不自动算本轮审过。

## 下一步
修补跑安全边界与干净shell合同，加中途/门失败时生产不变回归；生成段旧根明确接替单。最终固定组合后约静默全量、再按授权验真实闭环。原inflight3822字节、日期快照仍写local未做，需作者订正。

## 已验证
干净fcf9cca9：test_eval_launchd_wiring 19P/1.05s，相关ruff/zsh -n过，两源plist经plutil/plistlib过。源/装机/加载态的local与专用根一致，计划18:30/20:40一致。
收据：`~/.finance-runtime/test-receipts/20260912T100011Z-fcf9cca9.json`。
探针与输出：`/tmp/sync-qc-fcf9cca9-evidence/`。

## 踩过的坑
修对代码根只解决“用哪版逻辑”，不解决“写哪份数据/何时发布”；配置注入只属于对应启动进程。临时spy是本次取证，正式行为回归由实现方接到现有测试，不另造通用件。
