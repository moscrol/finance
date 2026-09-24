# P3e 独立代码审查报告

## 裁定：通过（仅限 P3e 词典早读闸门）

实际执行者：本次 pi 会话的独立代码审查助手；不是作者，未委托其他模型。
固定应用树：`/tmp/e2-p3e-qc-0b83e14f`（macOS 实际解析为 `/private/tmp/...`）。
HEAD：`0b83e14f5c6e664772d617f075a24911f16f7547`。
父提交：`39af312f51fa73f7a3db3b7f8c1fa8f8420213c9`。
起始与完成工作树均 clean，未改应用、作者测试、原题或评分，未提交/推送/合并/部署。

本片范围内未发现应退修的 P1/P2/P3 缺陷。此裁定不是完整 P3、E2 全链、合并或部署许可。

## 静态审查

已读 AGENTS.md、指定 README/commands/manifest、产品门 E2 段及设计 D1/D2/D4/D7、A13–A17；检查固定父到 HEAD 的三个指定文件差异。

- `query_resolution.py:175–198` 在历史主题解析、实体解析、主题词典、冲突候选与比较实体解析之前执行材料范围判断；缓存命中路径也在闸门后。
- 直接复用 `split_user_message` 与 `compile_material_contract`。`task_frame.py:298,416` 使用同一拆分器和编译器；没有第二份关键词规则，也没有先调用语义理解再覆盖其结果。合同编译在 TaskFrame 构造时会重复计算，但不是第二套语义权威。默认 source_turn=0 不影响此处仅消费的 data_scope。
- 受限路径调用原有 `understand_query(cleaned)`，保留原题和材料载体；anchor=None，candidates 与 comparison_entities 为空。`_unanchored_tristate` 是原三态尾逻辑的等价抽取，不新增 clarify；reference_kind 与 context_dependent 仍由既有文本规则决定。
- full/local_only/普通路径除前置纯文本编译外保持旧逻辑，包括历史特例与比较实体。保护区禁令不会由 resolver 自行升级，显式放宽遵循同一编译器。
- 静态路由配置、简称/日历先验仍可能参与文本理解，不能作为材料内事实。未知边界、state_unavailable 和可信续轮尚未在这里被封闭；设计要求的预取前澄清尚不能据本片宣布实现。这是明确的后续全链缺口，不构成对本片“编译器明确 material_only 时不读词典”承诺的反例。

## 独立执行结果

证据根：`/tmp/e2-p3e-qc-0b83e14f-evidence/`。
数据根：`/tmp/e2-p3e-qc-0b83e14f-data/`。

| 执行 | 实际结果 | 禁止尝试/终态 | 证据 |
|---|---|---|---|
| manifest 字节 SHA-256 校验 | 41/41 匹配，含应用源码与新增测试 | 成功 | manifest-check.json |
| 首次 focused（审查启动器路径错误） | 36 errors / 5 failed | 41 次临时 DuckDB 连接被误拒，shell 1 | focused.log、focused-io.json、launcher-v1.py |
| focused-v2：原样重跑作者测试 + 独立补针 | 作者36P；独立5P；合计41P | 禁止尝试0，pytest/shell均0 | focused-v2.log、focused-v2-io.json、focused-v2-shell.exit |
| 8文件相关回归 | 347P | 禁止尝试0，pytest/shell均0 | regression.log、regression-io.json、regression-shell.exit |
| 两个改动 Python 文件 Ruff | All checks passed | exit0 | ruff.log、ruff.exit |

首次失败是审查者启动器比较已 resolve 的 `/private/tmp/...` 与未 resolve 的 `/tmp/...`，所有事件均为合成库连接，在 native connect 前被拒。保留失败源、日志与调用栈；修正仅对 DATA 根执行 resolve，没有扩大生产路径白名单，没有改测试求绿。整轮审查记录中的拒绝累计为41，不能把整个过程写成零拒绝；修正后的两个有效验证运行均累计零禁止尝试。

独立补针 `test_independent.py` 不导入作者测试：新合成实体“星舟设备”，新材料数值与利润率问题，使用“不读取材料外数据”“仅根据以下材料回答”两种受限表达，对照普通、不要联网、可以查真实数据。每项冷/热两次 resolve。受限读取计数均为空；允许路径冷调用断言真实 KB open 与 DuckDB connect 均大于0，热调用记录 stat=4，实体锚点确为合成库实体。作者测试另外覆盖主题别名、代码、历史比较、PermissionError 吞错仍计数、scope切换、保护区/放宽以及默认/注入 QueryResolver 的真实 decide_turn。本次未重新运行父版本或变异，作者相应读数仅经归档哈希校验，不冒称独立复现。

## 隔离与命令

解释器统一为 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（记作 P）。每条 shell 均先 `cd /tmp/e2-p3e-qc-0b83e14f`。

pytest 执行前使用 `env -i PATH=/usr/bin:/bin:/opt/homebrew/bin` 清空宿主凭据与真人环境，再设置：
`E2_TEST_ROOT=$PWD E2_TEST_EVIDENCE=/tmp/e2-p3e-qc-0b83e14f-evidence E2_TEST_NAME=<运行名>`。
运行：
```
P /tmp/e2-p3e-qc-0b83e14f-evidence/launcher.py <测试清单> \
  --basetemp=/tmp/e2-p3e-qc-0b83e14f-data/<运行名>/pytest -q
```
focused/focused-v2 额外 `-s`，清单为：
- intelligence/tests/test_e2_query_resolver_reads.py
- /tmp/e2-p3e-qc-0b83e14f-evidence/test_independent.py

regression 清单均位于 intelligence/tests/：
`test_query_resolution.py test_query_understanding.py test_turn_controller.py test_task_frame.py test_user_task.py test_e2_material_contract.py test_e2_top_level_regions.py test_e2_question_group_edges.py`。

Ruff：`P -m ruff check --no-cache intelligence/services/query_resolution.py intelligence/tests/test_e2_query_resolver_reads.py`。
终态：`git status --short` 与 `git rev-parse HEAD`，收据为 final-status.txt（空）和 final-head.txt。

启动器由归档 v3 改造，HOME/KB_VAULT/KNOWLEDGE_WIKI/FINANCE_WS/FORESIGHT_USERS_DIR/MARKET_FEATURE_STORE_DB 均置于本次临时数据根，ENTITY_ANCHOR_SECURITIES_DB=0 禁用默认回退；测试仅临时覆盖为合成库。禁用插件自动加载、字节码及 pytest cache，使用独立 basetemp。Python audit 对网络、子进程、生产用户/KB/仓库主库、共享记忆及密钥配置路径先记事件与栈再拒绝，finally 持久化计数并最终 assert 无违规。native DuckDB 另包裹 connect，仅允许本轮 DATA 内路径或内存库；不是仅靠 Python open 事件。允许源码、依赖及静态配置读取。

这不是 OS 沙箱，也不证明任意 native SQL 外部文件读取已被系统级阻断；本次受测代码及合成 SQL 未使用此类路径。未调用金融模型/API、生产 Episode、Grok/Knevo、真人台账或生产数据库。

## 未覆盖与后续约束

- 未执行作者453项完整组合或452项服务子集；本次347项不是它们的替代收据。API导入隔离红针仍未覆盖，未给生产路径开白名单。
- q3 被上游划作材料的缺口未修，本次 q1 测试不证明完整题组已好。
- controller更早历史/context、禁令提前被剥掉、恶意注入 resolver、可信继承/未知边界澄清及完整 P3/P4–P7 均不在通过声明内。
- 无本版全仓 pytest、前端或端到端结论，旧9797P不可迁用。P3d四先验生产者结论不被本报告扩大。
