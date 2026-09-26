## 范围

从 #798/#800 抽出两项无需未合领域父枝的修复，前向移入 `gitea/main@f783f19c8a01fbe8d0ed70d851df7ed14598c051`：

- 测试夹具登记并等待自己触发、已从任务表移除的 Timer；不扫描全局线程，不改生产 shutdown。
- code-map 保留原查询，至多追加一次连字符→下划线查询；去重/限额，区分不可用与正常零命中。

固定代码候选：`ea5c3a94618a15e37f914c8b1a13e271875e4337`。

## 作者验收（不冒充独立审核）

- Timer 原版反例 3F/3P；code-map 原版 7F/35P/3S。修复后相关 103P/3S（迭代树）。
- 冻结干净 SHA 全量 Python：**12444 passed / 87 skipped / 2 xfailed / 0 failed**。
- Ruff、四项 registry、crosswalk 均 exit 0；crosswalk 留98条既有反向警告，不称零债务。
- 同 SHA 独立 detached 前端树：安装/lint/typecheck/test/build/E2E 六步 exit 0；110 单测、34 E2E passed/2 skipped；identity_stable=true、dirty=false。
- Python 收据校验 exit 0、基座漂移0。

证据根：`~/.finance-runtime/reviews/research-tail-integration-20260921/`；`small-python-receipt.json`、`small-frontend-gates/frontend.json`、`small-*.rc`、首尾身份文件。

## 仍未完成

- 独立复核与用户合并确认尚缺，所以保留 WIP。未合 main、未部署、不接生产。
- 此 PR 不含 #798 的证据恢复或 #800 的历史研究。领域线分别在 `fix/runtime-forward-0921` / `fix/history-forward-0921` 前向整合；旧父枝和原失败质量裁决不变。
- #797 财务/保稿/发布/RAG 领域组合单独在 `fix/financial-forward-0921`，不能借本片门禁移签。
- 历史证据孤儿片保全为 #829，未并回 #809，也未验成 #793/#794 完成。
