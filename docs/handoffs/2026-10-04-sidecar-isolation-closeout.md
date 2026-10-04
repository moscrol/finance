# PR35 评测状态隔离交付检查点

FINANCEWORKS-8；PR35原头67d08ac73独审发现相对目录错落及报告排序精度两项问题，最终头c97996380883320dd367cd2eec51635dee6ab303均闭合。旧头全量主动中断exit2保留，未当通过证据。修复方案沿现有启动器绑定输出根，未改生产输入来源或造新监督器；调用者相对目录在shell切换前固定，避免运行状态落到另一位置。先断言隔离再调用真实写入器是本次测试必须满足的安全条件。

## 交付与验证

- GitHub PR35在2026-10-04T03:17:56Z合入180dbf1e76370a3fe8cc60a97b0882cc0a4df758，合并树与受验头内容一致。
- 干净最终头本机完整20,377P/78S/2X，collected20,457、0F/0E；full-scope与完整SHA校验通过。收据 `~/.finance-runtime/test-receipts/gate-92mD8a07/pytest.json`。
- 前端六步含E2E exit0、clean/stable：私有根 `sidecar-frontend-c97996380/frontend.json`。独立Spec/Standards零发现：同根 `sidecar-{spec,standards}-c97996380.md`。独立8/8路径探针通过、旧4/4相对路径反例写前拒绝。
- GitHub python/frontend/e2e/registry/workbench-check五项成功。合前证据 `sidecar-premerge-c97996380.json`。
- Gitea备份2026-10-04T03:19:45.697548Z success，341源引用，updated1；bundle `~/backups/github-finance/2026-10-04/repository-7abeb4f58fafbdd1442e9cd16e3a737ef9fdd6c2d4411fac51c777a90a18ce24.bundle`。正式status.json已回读成功，不宣称未来备份均成功。

私有根为 `~/.finance-runtime/harness-quality-closeout-1003/`。原件索引及首次测试误写精确恢复见 `docs/verification/2026-10-04-memory-raw-query-and-isolation.md`，不删失败历史。

## 接续与限制

生产8792仍ffe1c60d84da，未由本补丁切换。BGE原句22/24伴随60次无关返回，默认keyword保持；新题和真实内容采用未通过。接续 `docs/superpowers/specs/2026-10-04-personal-recall-failure-exit.md`，当前树recall-failure-exit-1004；先修故障下未经确认的任务漂移，再回到独立题集/必要限定/实际采用。主干工程绿与任务板初衷分开记账。

未另建通用脚本：现有sidecar入口和其真实shell回归已承载路径归属规则；内容判读/排序限定仍需语义评审，不能把一次性人工裁决硬编码成检索规则。当前在途树和此前受验树的回收状态以任务板最新评论、worktree_board及应用归档记录为准，不按本快照推断已删除。
