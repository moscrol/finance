# 审计分支整合 main724：固定候选四叶通过

## 当前结论

实际受测干净版本`097a9974543a5a17e312d149fcbfe5d1b6a65f72`的四叶已通过。本轮没有改产品代码或测试，证据在`validation-097a99745/README.md`，42份原件由该目录manifest核对。

| 层次 | 状态 | 证据与边界 |
|---|---|---|
| Python | PASS | 16444P/0F/0error/74S/2X，完整收集16520；Ruff、外层gate、同SHA完整范围校验均exit0 |
| frontend | PASS | 安装、lint、typecheck、123项测试、build全部exit0 |
| E2E | PASS | 34P/2S，exit0；隔离夹具服务，不签生产UI或真实模型 |
| registry | PASS | 五条命令全部exit0，98条反向warning保留 |
| 最新主干组合 | UNKNOWN | 新主干1341f5c22仅做文本预检，无冲突；未实际再整合或测试 |
| 生产装配、真实模型采用、金融质量 | UNKNOWN | 无生产请求、真实模型调用或真实用户读写 |
| 合入main、发布 | BLOCKED | 未push、开PR、合回main或部署；尚待实际合入组合验收及用户确认 |

首轮Python同SHA为16443P/1F，失败来自执行者白名单PATH遗漏uvx目录。先在同图同代码下只改PATH对照，再定向44P/3S及完整重跑通过；首轮红收据保留，不用局部结果拼签全仓。完整归因、环境和所有收据见子目录。

## 历史整合与阻塞

固定主干`72402839075e3eefdee7b185db015a0545096b22`与原审计HEAD`8e1d6fc28a2d96bf2015b1be965802c5f7c6385e`实际merge为`bb556febd41fed492bdd9d2c10ac95075f9d6726`，保留双方历史，无手工冲突解决；`097a99745`仅比该merge多证据文档。

整合包括主干按模型推理强度及API时间预算接线，本轮未启用环境配置。此前记忆写入、预取、Episode校验、编排及HTTP异常测试未改动。

本目录根部的`manifest.json`、`integration.json`、`static-checks.json`、两份静态日志、准入记录和controller记录仍是当时8份原件：静态PASS、20分钟41次观测拒绝、当时四叶尚未启动。原始根为`/tmp/architecture-main724-bb556febd.k8BCPV/`。不改写这些历史原件；实际通过结果另存`validation-097a99745/`。

此前`78b25943f`的HTTP22P/24文件824P和`698fd172d`的旧四叶也保留原SHA归属，不移用到新版本。当前成功轮basetemp已清，首轮失败basetemp保留；测试、浏览器服务及临时防休眠进程均已退出。

## 主干边界与下一步

测试后fetch主干为`1341f5c2262935c59add397faa0735c05832bcda`，比已整合主干多10个提交、10条路径，含数值校验和双红时间轴证据修复。文本预检exit0仅证明可自动合并，当前四叶不证明新组合兼容。下一轮应冻结新的实际待合入组合，复核两处运行时交叉影响并取得对应验收与用户确认，不在测试途中移动候选。

本轮没有重采生产health/readiness，既有UNKNOWN不变。#76第三批NOT_PASSED归原owner，不借预算。data-quality-check相对已整合主干无触发路径，不算专项已运行；SPT批准、风远来源、行情/KB/发布前置与真实Workbench/CLI质量继续分别处理。

续跑沿用主树`.venv-workbench/bin/python`和现有门禁入口；先在白名单环境检查uvx等实际工具可达，再资源准入。将`$HOME/.local/bin`纳入PATH，保持独立用户、Episode、部署台账及收据目录。每份收据只签实测SHA，后继文档提交不移签。

整合历史：`docs/handoffs/2026-09-25-architecture-main724-integration.md`。本轮决策：`docs/handoffs/2026-09-26-architecture-fourleaf-097a99745.md`。
