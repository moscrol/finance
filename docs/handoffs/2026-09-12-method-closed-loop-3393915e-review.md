# method-closed-loop · 3393915e 三笔续修独立审查

## 结论

**核心修复可以认可；迁移执行文档和权限/归属边界仍未闭合，不能整体结案。** 本轮不是重复判定前轮已修项失败：history 封存闸、坏结构 active、目录/悬空链指针、坏协议判定一致、help 失败停止消费，均已有独立通过证据。

固定审查 `3393915ef7a41c7f8e50190b2ea14c1abd9d1119`（含 1e5ad6f6 / 310e9f4e / 3393915e），树 `/tmp/method-qc-3393915e-review`，独立文档枝 `docs/qc-method-3393915e`。不修改作者树、生产配置或共享库，不跑全量，不停止/指挥别人的进程。

## 现场状态与归属

- `git show --name-only 3393915e` 只有迁移方案文档，确认该提交未裹入 receipts.py。
- 用户消息发出后状态已前进：开审时作者树 HEAD=`2f5c7a03`、干净；对方 receipts 修复已经提交，而不是仍悬在工作区。
- 当时另有冻结在 2f5c7a03 的整树 pytest 在跑。本轮未干扰；其结束后才启动本轮定向检查。
- 本轮**不审 2f5c7a03 的 receipts 改动质量**，也不把它计作 3393915e 的实现。前轮 receipts 缺陷在 3393915e 本身仍存在，不重复开单或忽略后续提交。
- 未取得用户提及 pre-commit 报错的原始日志，不能独立认定是哪个 hook/外部编辑造成；提交路径范围已经核实。

## 已验证的修复

### history 封存闸：通过，含正向对照和存量保护

用本分支测试 fixture 建**可读的临时 DuckDB 旁路库**，真实 CLI、真实协议目录：

1. register 后 history 未封存运行：rc=0，生成 history 与 standing。
2. 封存后对同一研究运行 history：rc=2，明确报「协议已封存」。
3. 比较封存之后、调用之前和之后的研究目录逐文件 SHA256：**完全不变**，包括已有 history/standing。
4. 封存后的 capture：rc=2，报封存而非缺参数。

不是“旁路库不存在”的假拒绝，也不只证明空目录没有新文件。

### active / Shell 消费：前轮反例已闭合

真实 active CLI 双模式：unset=4；数组 JSON、目录指针、悬空软链、坏 protocol 均=3；错误时 --print-dir 为空。两种展示模式在这些用例中判定一致。

执行冻结夜跑绑定段及实际 `run_method_flywheel`，仅把 daily 写入与通知发送换成 spy：

| 场景 | daily 调用 | 告警 |
|---|---|---|
| unset / 有效指针 / 真旧CLI | 是 | 否 |
| 已封存 / 非法JSON / 数组 / null / 目录 / 悬空链 / 坏协议 | 否 | 是 |
| help进程失败 | 否 | 是，保留失败原文 |

consumer 使用前轮隔离 fixture，只读旧 fixture、不写生产。HOME/ZDOTDIR 隔离；被测函数本身仍用 zsh，解释器 spy 用 Bash 避免宿主 zshenv 污染。

### 定向测试

固定源码：

```text
pytest -q intelligence/tests/test_method_validation.py
          intelligence/tests/test_method_validation_cli.py
          intelligence/tests/test_method_flywheel.py
86 passed / 10.52s
```

收据 `~/.finance-runtime/test-receipts/20260912T103505Z-3393915e.json`，dirty=false。相关 Ruff、夜跑 zsh -n、diff --check 通过。不是本轮全量。

## 仍需处理

### P2：lexists 仍把访问失败当成“不存在”

`intelligence/services/method_validation/store.py:269`：

```text
if not os.path.lexists(pointer): return unset
```

`lexists` 能看见悬空软链，但仍是布尔便利接口，会把 lstat 的访问错误折叠成 False；并不保证“只有确实不存在才 false”。

独立实测（本机非 root 用户）：先 register + set_active 建有效指针，再将临时协议根权限改为 0600（去掉目录遍历权限）；目录路径本身还可定位，但无法查其中 active.json。两种 active 输出均 **rc=4 / state=unset，无告警**。探针 finally 恢复权限，未改生产权限。

建议直接 `lstat()`，仅明确 FileNotFoundError 归 unset，其他 OSError 归 corrupt/查询失败；根路径类型不正确也不能随意当从未配置。

**范围限制**：这个权限例中默认研究也在不可遍历的根内，本轮没有证明随后能成功写错协议；不能把它升级成已发生错误观察写入的P1。但它确实违反“查不出来不得冒充没配过”的状态合同。

### P2：supersede 的 --user 没有限定封存对象，文档把查询根写成写入归属边界

`docs/superpowers/specs/2026-09-12-label-version-migration-plan.md:163–164` 将 register/activate/supersede/active 归为“--user选协议根，决定读写哪个用户协议与指针”。

实际 `scripts/method_validation.py:556–565`：先 `_root_of(args)`，然后 **直接 `supersede(args.study_dir)`**，root 只用于后续 active 查询；没有像 set_active 那样验证 study 属于 root。

隔离用户树实跑：

```text
supersede --user u1 --study-dir <users/other/method_validation/合法协议> --reason ...
→ rc=0，other 协议真实写入 superseded.json
```

这是现有行为与本轮新文档的冲突，非多用户服务授权漏洞的证明。处理需选明合同：

- 若 --user/--root 应约束变更范围，封存前做与 activate 等价的归属检查；跨根失败应在写标记之前。
- 若显式 study_dir 本来就有最终决定权，文档不得把 --user 说成封存目标保护；明确它此处只决定回读哪个用户的 active，并清楚提示不一致。

capture/daily/recheck 的 --user 是 checkpoint 台账归属、不选研究目录，这一纠正本身正确。register 的 --user 是协议根，不是台账；3393915e 提交说明把 register 列进“那里是台账”那段亦应避免作为事实源。

### P2：迁移表仍未达到“直接执行且完成验收”的承诺

位置：迁移文档 §3.3、§4.1、§4.3。

1. **组合命令放字符串对 zsh 无效**（154–155）：`MV="$PY $CODE_ROOT/scripts/method_validation.py"` 后执行 `$MV ...`，zsh 默认不对变量做空白分词，实测 rc=127，把“解释器+空格+脚本”当成一个不存在的文件。文档代码块标 Bash；在明确 Bash 下该无空格路径可工作，但本仓入口/用户默认均为 zsh，未显式切 Bash 不能称直接粘贴。建议每行用 `"$PY" "$CODE_ROOT/scripts/method_validation.py" ...` 或定义函数，不要用标量模拟参数数组，也不要 eval。
2. **刚登记后的 status 不能做表中验收**（175）：真实 register 后 `status --study-dir` rc=2，报“没有立场摘要”。命令形式合法，却没有完成“出协议卡片、核对 forward_start”。应保留并校验 register JSON 输出，或明确调用可检查协议的入口/派生步骤。
3. **history 后普通 status 不打印 label_version**（176）：本轮正向 history 后 status rc=0，有历史与前向起点，但输出中无 label_version，无法按表证明“口径为v5”。需要指向可见该字段的原件或明确 JSON 字段核验。
4. **report 参数仍写错**（167）：文档说 status/history/report 都“只认 --study-dir”，实际 report 必填 **--record**。真实 `report --study-dir ...` 是 argparse rc2；help 明确 --record。
5. **枚举行不是命令**（178）：`active ... --print-dir 之外用 list_studies(root)` 仍是叙述，不是直接可执行核验；active 指针也不能代替默认枚举结果。
6. **文档探针再次合并 help失败与无能力**（194–195、223–224）：`help | grep && echo 已完成 || echo 未做`，help失败仍输出“未做/夜跑会用默认”，而此次已修夜跑会停止并告警。应与运行时代码共享三态语义。两个分支 echo 都成功还会使该检查不具备失败退出信号。
7. §3.3 仍有不经解释器直跑脚本，以及“指向封存后 active非零会回退默认”的旧表述；§4前仍说“所有命令都带--user或--root”，与无该参数的命令相矛盾。

这些有些是前轮未修，有些是本轮替代命令引入；不能用“CLI没报参数错误”作为整条核验通过。

### 测试改进（非新增运行时阻塞）：AST 检查只有同函数出现性，不证明先过闸

`intelligence/tests/test_method_validation.py:685–708` 用 ast.walk 收集 Call 名称；只证明函数中同时出现 write_record 与 _refuse_if_superseded。

内存变异（**不编辑冻结源码**）：将 cmd_history 的闸移到 `return 0` 后。

- 当前结构测试同等谓词仍判通过（unguarded=[]）。
- 在隔离已封存研究上运行该变异 CLI：rc=0，history/standing 均写出。

现有 history **行为回归**能发现这种变异，因此这不是当前 history 代码仍漏闸，也不是说测试全无用。结构回归是有价值的“调用缺席报警”，不应声称保证“所有新观察写入前必经闸”。它也只扫脚本内直接 Name 调用，不覆盖委托写入/别名/其他模块。

建议保留此低成本扫描，并配入口行为矩阵（当前 history/capture/daily 的封存态无新副作用），或在可区分记录类型的共同写入边界实现闸。后者必须允许既有观察 recheck 结算，不能把所有 write_record 粗暴一刀切。通用复杂控制流静态分析不是本轮必要工作。

## 其他需收窄的文案

- CLI 顶层 help 仍说 active“无绑定返回1”（scripts/method_validation.py:637），实际为4，应跟随合同修改。
- 原 inflight 已从23023缩到5145字节，但仍超≤3KB，且没跟上history补闸/--user订正/后续receipts提交。停止共享写入时先保持不碰，唯一收口人到位再更新。
- 不把“未指定user必落default”写绝对：userspace是显式user > FORESIGHT_USER > default。明确传user的建议正确，默认行为解释仍需准确。

## 后续全量：已有绿单，不能继续说没有；也不能拿它覆盖独立反例

审查期间读到：`~/.finance-runtime/test-receipts/20260912T103007Z-2f5c7a03.json`。

- revision=2f5c7a03，dirty=false，target为冻结树整树；**9447 passed / 0 failed / 77 skipped，exit0**。
- 当时进程命令是 `pytest -q -p no:randomly`，输出经过 `tail -2`；本轮检查 pytest-randomly 未安装，这个关闭项不是已证实的测试削减。收据本身不记录完整命令，故在此补充。
- 本轮没有执行该全量，不能把它记为3393915e单独全量；也未审后续receipts修复。冻结树稍后已不在原路径，收据仍可读取。
- 这张绿单应认可为对应条件下的Python全量结果，但不是对未覆盖权限/文档反例的证明，也不代表全部合入叶子/生产链路已验收。

## 决策与下一步

| 选择 | 否掉的方案 | 理由 |
|---|---|---|
| 认可已修核心，用新反例收窄余量 | 因新问题就把86P/原失败修复一概否掉 | 必须逐合同记账，不无限移动验收目标 |
| 固定3393915e审三笔，分列2f5c7a03全量 | 用移动HEAD/他人WIP作为本轮对象 | 避免收据与代码归属混淆 |
| 对权限错误失败关闭；明确封存归属 | 静默当unset/让user看起来能保护目标 | 查询不成功不能冒充不存在，参数合同必须对应副作用 |
| AST作补充、行为验证执行顺序 | 仅凭同函数有两个调用就称结构性全覆盖 | 可构造未执行的闸仍过结构检查 |

建议原本负责method_validation与夜跑的作者做唯一收口人，对方交付已提交的receipts SHA后停止同树写入；这只是建议，**不是本会话代用户授权或调度**。由用户确认唯一写者后，先修上述合同与文档、复验新头，再决定重跑哪些门禁。当前问题不只是等一次空闲全量，已有绿单也不能直接结案。

证据 `/tmp/method-qc-3393915e-evidence/`：probe.py/results.json、consumer_probe.py/consumer-results.json、mutation_probe.py/mutation-results.json、targeted-pytest.log。全部研究和DuckDB fixture仅在临时目录；目录权限在finally恢复；变异只在内存加载。只审授权下未把探针或门禁写进实现枝，已给明确失败输入/断言供收口人落地，未改共享知识仓。
