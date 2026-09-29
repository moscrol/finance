# 8792 Controller 协议修复上线回执

2026-09-28，用户在会话 `01a0e5e3-ec08-71d3-853b-7ad710f02bfb` 明确授权“合并部署”。PR [#952](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/952) 已合入 `8e45e299a13bb3e3d21deae5f9de9b4f8384b2e0`，该版本已通过合后全量门禁并实际部署至 8792。最终收据与后续纯文档归档身份统一见 [release/result.json](/Users/a77/.finance-runtime/reviews/8792-harness-20260928/release/result.json)。本文记录这个上线时点，不把后续文档提交号冒充运行版本。

## 交付范围

Controller 的提示、纠错和解析共用六字段协议，同时精确兼容旧五、七字段；合法性与路由校验通过后才接收任务补充，成功重试使用有效回复，必需输出仍由任务合同拥有。设计、固定回复消融、独立规格与质量审查见 [实施快照](2026-09-28-8792-harness-protocol.md)。本轮没有修改模型、预算、工具菜单或判官。

## 合入与工程验收

`E=/Users/a77/.finance-runtime/reviews/8792-harness-20260928/release`。

- 合入前 head `7ef3e08d7c0263014888ee072c1239e85626f2f6`，base `bdd19f4165ab5ad4121e797933eb3ec281cb67ce`；合入后父提交、主干指向与预演树均核实，原始授权与回读保存在 `E/merge-952.json`。
- 合后固定 `8e45e299a13b` 独占检出：Ruff 通过；pytest **18375P / 0F / 0E / 72S / 2X**，收集 **18449**，无收窄选项；完整范围与精确 revision 检查 exit 0。原件 `E/python/gate-wBjXa4q1/pytest.json`，日志同目录；scope 回执 `E/deployment-retry/scope-check.txt`。
- 同版本独立前端检出：安装、lint、typecheck、125 项单测、build、E2E 34P / 2S 全绿，收据起止身份一致且干净。注册表五项全绿。汇总 `E/gates.json`，详细收据 `E/frontend/frontend.json`、`E/registry.json`。
- 解释器仍为主仓共享 `.venv-workbench`；实际 httpx 0.25.2 与 lock 0.28.1 的既有漂移保留为边界，没有更新共享依赖。

## 切换与真实入口

运行软链指向 `~/.finance-runtime/finance-workspace-8e45e299a13b`；前端资源来自同 SHA 门禁构建，逐文件哈希相同。launcher 内容哈希前后不变。health 三读均为完整目标 SHA、`source_dirty=false`、`code_matches_repo=true`；readiness **13/13 true**，连续引擎版本也一致。canonical 部署账本 homes 通过、无旧家。回执 `E/deployment-retry/`。

第一次切换辅助脚本误把成功记账命令的空 stdout 当 JSON，导致前切和回滚后的解析均异常。保留 `E/deployment/` 与 `E/apply_release.failed-v1.py`；人工恢复旧版服务后实际验证 health/readiness 通过，再修正输出处理并重新切换成功。账本保留所有真实 switch，不删失败历史。旧版回滚锚 `~/.finance-runtime/finance-workspace-5a5e4cbb671a`。

固定日期上线题沿真实 conversations/messages → Episode 路径执行：`run_20260928_123331_914428`。独立只读核对 `fact_stock_daily` 与最终答案：2026-09-24 为库内最新日，长电科技收盘 68.78、涨跌幅 -4.17%、成交额 37.5914 亿元；真实字段与来源日期齐全，degrade、secret/public scan 均为 0。`E/production-grounded.json` 保存原件路径与哈希，不以 CLI ask 或模拟工具替代上线探针。

## 必须保留的失败与边界

首次“库内最新交易日”问法 `run_20260928_122950_851921` 降级。Controller 确已进入 research，首轮 16 个工具可见、工具窗 539.581 秒；模型三次回复均未发起工具调用，生成无来源数值和不存在的 E2，终局校验拦下。此处 `judge_unavailable_count=1` 不能概括根因；第一次偏离在工具可用时直接作答。`E/first-probe-triage.json` 保存定位。

新旧版本分别在独立进程、不准调用模型的条件下执行同题 `decide_turn`，结果逐字段相同，均走确定性 stock_deep_dive owner；此题没有进入本次修改的模型回复解析分支。沿用同版本、同问法另开独立测试用户复跑 `run_20260928_123331_915369` 完成，三项请求数值核对通过、degrade 0（`E/production-repeat-grounded.json`）。**同问法仅两次，一败一成；固定日期题通过不抹掉首次失败，不是可靠性或 ReAct 追平证明。** 重复题额外生成的分析正文不在独立数值核验范围内。

后续若继续压研究稳定性，应单独覆盖这类“行情题被归为深挖、工具可用却跳过取数”的路径；不放松证据校验来换完成率。暂未开展同模型、同题、同数据版本的 ReAct 对照。

## 备份与归档

Gitea 切后归档 `~/backups/gitea-20260928-post952.tar.gz`，4,624,513,098 字节；tar 与 gzip 完整性检查 exit 0，SHA256 `3288328685ab9555f1ffee8d326c474441eae33a94b606aba2cd7f81d5dd2395`。`E/gitea-backup.json` 记录范围：在线文件系统备份，未演练恢复、不额外宣称数据库一致性认证。

已完成的实现分支 inflight 在本归档中移除，历史实施快照保留；后续文档 PR 的独立门禁和实际合入身份只写 `E/result.json`，避免反复修改收据所绑定的源提交。共享 `inflight/main.md` 已有 21,557 字节，预算门禁拒绝继续增加；本单改以这份日期回执和共享项目索引登记，不扩写或删改他人的主干交接。没有新增生产工具，本轮操作脚本留在 E 作审计证据；通用协议合同与验证前不接收状态的原则已沉淀到共享知识。
