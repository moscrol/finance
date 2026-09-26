# RAG retirement × #789 合并增量复核

结论：**Spec 增量 PASS；Standards 增量 PASS；最终组合门禁 PASS**。仅适用于下列精确候选和主干；新增发现 0 项，无遗留的组合准入阻断。

## 固定范围与完整性

- 主干：`4ace5ec2e9b7735d90eb15bc2351fa193c1120b8`。
- 合并候选：`e51c5157c9ea9aa86491c486663700e7d7696a6f`。
- 两父：RAG `1931b3a32237489bcdf21f51bf8523d697398b92`；#789 `62bbc4ecf1e1d57bad6497fe60911ce6e3b6d717`。
- 两父 merge-base 恰等于指定且当前可见的 `gitea/main`，候选包含主干。
- 只在审查目录另设 Git object 写入区重算 `git merge-tree --write-tree <两父>`，exit 0；树对象 `d06bedfd1dfd0afe96b36c0cfcee13e3fd12e41d` 与候选完全一致。未写冻结检出的文件、索引、ref 或共用对象库。
- RAG 增量 8 路径、#789 增量 147 路径逐项与对应已审父提交 blob 一致，包含 RAG 的 5 个代码/测试文件、前端 runner/测试、验收规程及全部归档证据。合并无额外手工代码，无丢失/覆盖。
- 独立证据：`merge-provenance.json`，SHA256 `54a15e008ad76c4eefd040f1ea568ad1f51d4f46869a74e3903ba364f0091c88`。

## Spec

本轴仅复核双审组件合并增量，新增发现 **0**。RAG 原 Spec PASS 对应 `c4f33c5bcd6835bcc9b15536dc2d0eb1bf6f1279`，最后 Quality 及局部相邻边界对应 `1931b3a3`，不冒称该版重做完整 Spec。最后修补的解释器链 `RuntimeError` 仅在 `python_entry` 路径局部捕获；普通路径仍只捕获 `OSError`，虚拟环境启动 argv、legacy 权限传播及协议回退代码与已审版本全等。keepalive 测试补等待完成查询计数，原最终断言与超时未弱化。#789 与 RAG 无共享改动文件；原双轴审查可按 blob 身份继承。

## Standards

本轴新增硬违规 **0**，需要报告的代码气味判断 **0**。依据仓库 AGENTS.md 与验收规程，重新核验全树首尾身份、日志字节和哈希，不将旧父提交绿测移签候选。Python runner 只继承 HOME/PATH/TMPDIR/LANG，再显式设置测试路径和无字节码开关；前端命令使用同样基础白名单及显式测试端口/解释器。前端身份查询继承进程环境的既知前提仍须由外层 `env -i` 保证；本轮源代码身份另由独立干净环境的 Git 查询交叉确认。

`receipt_redirect.py` 只在 sessionstart 找唯一根 conftest 并替换 `_RECEIPT_DIR`；未改收集、测试函数、断言、结果统计或退出码。原 conftest 仍在 sessionfinish 根据 reporter.stats 生成收据。runner 与 redirect 精确哈希见 `frontend-and-sources.json`。

## 本轮门禁证据

前端 6 个命令全部 exit 0，日志 6/6 哈希与字节数吻合，runner 源码 SHA256 与收据一致；首尾均为候选完整 SHA 且全树 clean。Vitest **110/110 passed**；E2E **34 passed / 2 skipped / 36 total**，两项 skip 对应既有 tablet/mobile 不重复 desktop 绑定链路的条件，并非本轮删测。安装、lint、typecheck、build 均通过。

Python/registry 最终 `complete=true / identity_stable=true / exit_code=0`，7 个命令全部 exit 0，7/7 日志哈希吻合，runner 哈希一致。首尾均为精确候选且全树 clean。Python **11855 passed / 85 skipped / 2 xfailed / 0 failed / 0 error**，共 11942 个已报告结局，17 warnings；未把 xfailed 并入通过数。原生收据只统计 passed/failed/error/skipped，缺的两项预期失败从已验哈希的 pytest 日志尾补列，不伪称原收据有该字段。完整命令没有路径选择、`-k` 或排除参数，target 指向整棵冻结树。

独立重跑只读收据检查器（不重跑测试）：`check_test_receipt.py <20260920T070122Z-e51c5157.json> --expect-revision e51c5157c9ea9aa86491c486663700e7d7696a6f --base-drift-max 0 --main-ref gitea/main`，**exit 0**。精确 SHA、解释器、依赖指纹、干净状态、未绕过依赖门以及基座漂移 0 均成立。独立 `git ls-remote gitea refs/heads/main` 和本地 `gitea/main` 均为 `4ace5ec2…`。复核结束候选 HEAD 未变，status 为空。

日志与命令完整核验记录在 `final-admission.json`；前端及来源哈希见 `frontend-and-sources.json`。关键 SHA256：

| 工件 | SHA256 |
|---|---|
| python-registry.json | `03fe2297a2b9fd97e8f8f8f80e8e9b2205a052aaf7e9fc03bbc55b13d5bc4d40` |
| pytest.log.txt | `5ebeb091eabe10c24c59019197710a13768d6d5eb45a2dcda87a88838506a96b` |
| 原生精确收据 | `ad71141b43b8dc9edfa0cba7dba0b2c15fc1b6dabb1046f1a7cfd8da38c2dc29` |
| 独立 strict check 日志 | `b2f59d7a932575ca390207e7a295897af7a0ea7908fb3e652c68141cbb578b21` |

前端收据 SHA256：`8201cb804a95ca18a64d55b3c71c9fab8e77f5b5cfa9ec3ebdcb08bf5c502d3a`。

## 证据边界

旧 alpha→beta→rollback 双索引/8 child 真实 scratch 仅绑定 `d6812e6220b46ff939dfbcf51ac6c6b93246d361`，本轮没有重跑，不把它标成 e51c 的真实验收。本轮未调用真实模型、生产、BGE、8792、数据库或外呼，未修改候选、合 main 或部署；未另跑组件/整仓测试。此报告不构成部署或自然回答质量通过。
