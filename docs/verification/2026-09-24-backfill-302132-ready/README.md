# #83 ca4 作者工程验收证据

本目录是原件的小型镜像，不是另一轮测试。被验版本 `ca4b33316c47862ecd3ec71a535a51d540ada986`，基线 `a54fed0d065ffdf025734a69420c1fe530615eb1`；原始目录 `~/.finance-runtime/reviews/backfill-302132-0923/continue-07/`。本文所在文档分支的 HEAD 不是被验版本。

`verified-closeout.json` 对应本目录同名路径的 SHA256；脚本退出码/pytest counts/身份/全量范围均来自原始收据，未移签、未补写历史字段。前端和 registry 收据中的逐步日志哈希指向树外原件，镜像未复制这些日志或 E2E 大产物。`production-authorization-draft.md` 是未获授权的后续模板，不是已执行命令。

| 项目 | 结果 | 本目录入口 |
|---|---|---|
| Python | 15400P/0F/0E/85S/2X，collected15487 | python-receipts/gate-QOq3gEkV/pytest.json |
| 收据身份/范围 | exit0、完整范围、基座漂移0 | scope.command.json、scope.log.txt |
| 定向 | 118P | focused-receipt.json |
| 前端/E2E | install/lint/typecheck/120P/build/34P+2S 全通过 | frontend/frontend.json |
| registry | 五项全0，finance-only 范围与CI一致 | registry-complete/receipt.json |
| 副本 | 37 PASS，异常金额仅 oracle 失败，恢复及生产身份不变 | rehearsal/summary.json、acceptance.json、amount-control.json |
| 汇总 | 原始 runner ok=true；收尾身份/哈希核验通过 | summary.json、verified-closeout.json |

作者工程与副本验收已完成，**#75 独立审查仍待完成**。保留 WIP，未合 main、未执行生产。完整背景与边界见 `../../handoffs/2026-09-24-backfill-302132-engineering-ready.md`。
