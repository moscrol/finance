# 评测 sidecar 状态隔离执行计划

所属：FINANCEWORKS-8；接续 `2026-10-04-memory-consumption-followup-spec.md` 的诊断准入。

**目标：** 现有 `live_probe.sidecar_zsh` 已重定位 users，但 Episode、部署账本、待重判索引和记忆向量缓存仍可继承正式启动器或家目录。将这四种可写状态固定在本次探针的 users 目录旁。

**取舍：** 复用现有启动器，只补输出状态的绑定；不改全局默认路径、不另造监督器。此入口原本读取启动器指定的真实金融/知识库来源，不能把本修复宣称为冻结输入或全工具沙箱。未来记忆配对仍须核实际代码、数据、身份、成本和失败出口。

**文件：** 修改 `intelligence/eval/live_probe.py`、`intelligence/tests/test_live_probe.py`；离线结论写 verification 文档，原件保留私有 runtime。

- [x] 在现有测试文件通过真实 zsh 执行生成脚本，用只运行路径解析器的 Python 替身代替 uvicorn；真实 `pending_index_path()`、`resolve_episode_store_root()`、`resolve_ledger_path()`、`cache_root()` 都必须落入探针输出根，实际待重判写入也只能在那里。
- [x] 分别注入父进程、启动器 export 的相冲突路径以及全缺省路径；用带空格/引号的输出目录检验 shell 引号。所有数据均为临时合成数据，禁止调用模型或启动服务器。
- [x] 在旧实现跑反例并保留失败；然后在 source launcher 之后写入四项 export，例如 `export FINANCE_REJUDGE_PENDING_INDEX=<shell-quoted probe state path>`，不能让 inherited 值反向覆盖。
- [x] 运行 `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_live_probe.py intelligence/tests/test_rejudge_pending_isolation.py` 与 Ruff；报告中清楚区分 HTTP completed、Episode partial 和真实答案质量。
- [x] 独立复审发现相对输出目录在 shell `cd` 后指向错误根。生成脚本时以调用者当前目录解析 users 的绝对路径，四种状态与其共用该根；真实 zsh 回归覆盖绝对/相对目录 × 父环境/启动器/两者/缺省，先断言实际解析根再写入。旧实现四个相对用例均失败，原绝对用例保持通过。
- [ ] 记录原句 BGE、双用户隔离诊断与原始失败，独立 Spec/Standards 复审；最终干净 SHA 跑规定完整本机/GitHub 门禁，绿后合入备份。本修复不触发生产发布或新云模型请求。

不引入 query 词表或改变召回默认。BGE 原句 22/24 属已见调试集；60 次无关返回、跨用途记录和后续限定缺失使其仍不满足启用条件。
