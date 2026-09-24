# Agent 开发基线：固定候选工程验收

受测代码：`03af215e092cf0da25f3c7e8f60256cb60c2836e`，树 `~/fwp-wt-agent-foundation`。
包含本轮抓取的主干 `4cc15e703f81`；2026-09-24 收尾 fetch 后基座漂移仍为 0。
Finance PR #907；共享文档 Harness #16、Memory #4。均未合入/部署。

本目录在独立 `docs/agent-foundation-closeout` 分支归档，不移动已通过门禁的代码候选。
这些收据证明上面的代码提交，不为本归档分支或后来合并提交冒充全量签字。

## 结果

| 检查 | 结果 | 原始证据 |
|---|---|---|
| Python 完整门禁 | 15363P / 88S / 2X，0F / 0E；收集15453，无缩面 | `python/gate-QrXbdo6j/pytest.json` 与 `pytest.log.txt` |
| Ruff | 全仓通过 | `python/controller.log.txt` |
| 前端冻结安装 / lint / typecheck / build | 全部 exit 0 | `frontend/gate/frontend.json` |
| 前端组件测试 | 120P | `frontend/gate/frontend-3.log.txt` |
| Playwright E2E | 34P / 2S，桌面、平板、手机 | `frontend/gate/frontend-5.log.txt` |
| 注册表四项 / ledger / runtime catalog | 全部 exit 0 | `registry/registry.json` 与编号日志 |
| doctor --frontend | ready；地图语义验证仍 not_run | `doctor.json` |

P=通过，S=跳过，X=预期失败，F=失败，E=执行错误。未把跳过或预期失败算成已覆盖。
Python 3.12.13；候选本树 venv，开发锁包含消费锁、测试工具、crypto 与数据变换依赖。
Node 22.23.3 来自 npm 独立缓存；pnpm 10.12.1。未更换全局 Node26 或主树虚拟环境。

Python 门禁使用既有 `run_main_gate.sh`，无 `-k/-m/--ignore`，完整原始输出由主干新合入的日志保留机制保存。
前端门禁使用 `run_frontend_gate.py`，独立测试端口19881/19884，空模型凭证与临时夹具数据。测试服务均已退出。
两部分收据均确认首尾同 SHA、树干净。注册表收据同样采集首尾身份。

原件来自 `~/.finance-runtime/reviews/agent-foundation-0924/round-01/`；`MANIFEST.json` 记录路径映射和字节哈希。
`.log` 仅改归档文件名为 `.log.txt`，内容未改。重复 latest 指针和过程中的 PR 草稿不归档。

## 复核

在**受测代码树**而非本归档树运行：

```bash
.venv-workbench/bin/python scripts/check_test_receipt.py \
  /Users/a77/.finance-runtime/reviews/agent-foundation-0924/round-01/python/gate-QrXbdo6j/pytest.json \
  --require-full-scope --expect-revision 03af215e092cf0da25f3c7e8f60256cb60c2836e --base-drift-max 0
```

本轮已执行并通过；环境或主干后来改变时须重核，不能因为本页写过通过就忽略退出码。

## 边界

ledger 反向回指98条既有 warning 保留。代码图 ready 只对检出版本；未审全图语义。
完整工程门禁不是新机器整栈、真实模型研究质量、生产库准确性或线上效果验收。
用户未授权合主干或部署，三个实现/共享文档 PR 及归档 PR 均保留 WIP。
若共同合入归档文档，须对新的合并预览版本另行验收；不得用本收据签另一个 SHA。
