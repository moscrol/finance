# 097a99745：完整四叶验收

## 结论

实际受测干净版本：`097a9974543a5a17e312d149fcbfe5d1b6a65f72`，树`/Users/a77/fwp-wt-architecture-audit-0924`。该版本包含整合提交`bb556febd`及后继证据文档，已整合的主干为`72402839075e3eefdee7b185db015a0545096b22`。本轮没有修改产品代码、测试断言或筛选范围。

| 叶子 | 状态 | 实际结果 |
|---|---|---|
| Python | PASS | 全仓Ruff通过；16444P/0F/0error/74S/2X，完整收集16520，17 warnings；外层gate与完整范围校验均exit0 |
| frontend | PASS | 安装、lint、typecheck、123项组件测试、build全部exit0 |
| E2E | PASS | 桌面/平板/移动端，34P/2S，exit0 |
| registry | PASS | 五条命令全部exit0；98条反向引用warning保留 |

Python最终收据为`python-fixed/gate-RlQaTIwF/pytest.json`，范围和身份校验为`python-fixed-scope-check.log.txt`。完整收集16520与16444+74+2对平；没有`-k`、deselect、ignore、last-failed或maxfail收窄。解释器为主树`.venv-workbench/bin/python`，Python3.12.13，依赖指纹`e1c50cb821a30f00`，dirty=false。

前端收据`frontend/frontend.json`包含六步日志、首尾完整SHA、dirty=false、identity_stable=true、complete=true、exit_code=0；六份日志哈希已逐个核对。注册表收据`registry/registry.json`记录五条命令及首尾身份，日志哈希均已核对。E2E服务、Python进程、临时防休眠进程均已退出，19981/19984无监听；成功轮basetemp已由门禁清理，首轮失败basetemp保留。

## 首轮红与归因

首轮同一SHA全仓结果为16443P/1F/74S/2X，完整收集同为16520。唯一失败：`tests/test_code_map.py::test_structure_probe_daily_full`，结构命中列表为空。原件在`python/gate-gtGrfLew/`及`python-gate.log.txt`；`python-scope-check.log.txt`确认红收据身份和范围可采信，不代表测试通过。

原因是执行者构造白名单PATH时遗漏`~/.local/bin`，不是源码回归。`uvx`实际在`/Users/a77/.local/bin/uvx`。同一张地图、同一代码只改PATH的对照：

- `code-map-clean-env.json`：structure.state=unavailable，reason=uvx_missing，hits=0。
- `code-map-fixed-env.json`：structure.state=stale，reason=null，hits=20，含`market_feature_store/cli.py::cmd_daily_full`。

这组对照发生在地图刷新之前，避免把刷新与环境修正混为因果。随后只刷新本工作树忽略目录中的代码地图，节点数仍34404，版本标记更新至受测SHA，见`code-map-build.log.txt`。不涉及生产知识库索引。

修正环境后整份`tests/test_code_map.py`为44P/3S，收据与校验在`probe-receipts/`及`map-probe-receipt-check.log.txt`。之后另起目录重新执行完整Python门禁，才得到最终全绿；44P是定位用的子集，不能与全仓相加。没有删图、增加skip、改断言或移签旧结果。仓内既有同类教训见`.claude/lessons_learned.md`的2026-09-20记录，本轮未重复新增通用工具。

## 环境与时间

每组先独立采样资源准入，再启动；原件为`admission-*.json`。采样不是全机锁；运行中仅排除本任务拥有的进程组49193做观察，见`resource-*.json`，没有干预其他任务。

最终Python白名单环境、命令和umask022在`python-fixed-exit.json`。PATH同时包含主树venv、`$HOME/.local/bin`、Homebrew及系统工具目录。用户、Episode、部署台账及收据写入本轮树外临时根；E2E按既有配置使用`intelligence/webapp/test-results/`下隔离夹具用户和数据库，部署台账由frontend runner重定向。未读写真实用户、未新增真实模型调用或生产HTTP请求。

第二轮UTC 15:49:12启动，16:51:54写出pytest收据，16:52:10外层门禁结束；pytest报告3761.73秒。期间有较长执行间隔，未独立证实其原因，不作性能比较。恢复后为已运行的自有pytest加临时`caffeinate -i -w 49216`防空闲休眠，随pytest结束退出；未修改持久电源配置。`caffeinate.json`保留动作记录。

## 主干与未验边界

测试完成后fetch所得主干为`1341f5c2262935c59add397faa0735c05832bcda`，比已整合主干多10个提交、10条路径，其中两运行时文件为`asof_prefetch.py`和`episode_semantic_verifier.py`，涉及双红时间轴单位/窗口计数及型号/月份数值预检。另有三测试文件、五文档路径。

`main-preflight.json`与`main-merge-preflight.log.txt`记录固定候选和该主干的文本合并预检exit0，树为`4aca4bfaaa6bd344747edf2ac7184e52e8354b91`。本轮未实际再merge；无文本冲突不等于语义兼容，当前四叶不能覆盖该新组合。最新#76第三批NOT_PASSED仍归原owner，不借其预算。

生产装配、真实模型采用、金融质量、生产readiness仍UNKNOWN，合入/发布BLOCKED。未push、开PR、合回main、部署、补数、换库或恢复采集。data-quality-check相对已整合主干无触发路径，不另算专项已运行。

## 归档与下一步

`manifest.json`核对42份原始产物字节与SHA-256；不含临时用户原文、完整提示词、完整评分原因或测试数据库。原始根为`/tmp/architecture-full-097a99745.DYk89M/`。哈希证明归档完整，测试结论来自对应收据和日志。

下一轮先冻结待合入的实际组合，对新主干两处运行时变化做交叉复核及整合验收，再取得用户合入确认。不要将本收据移签到后继文档HEAD或新merge。生产、真实Workbench/CLI及质量仍按各自前置和预算独立验收。
