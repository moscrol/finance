# Ruff 技术债分批清理与增量门禁设计

日期：2026-08-02  
分支：`fix/ruff-debt-burn-down`  
基线：`origin/main@78187ec7`

## 1. 背景与实测基线

此前验收分支报告的 `164` 条 Ruff 告警不是当前正典 main 的固定数字。重新从最新
`origin/main@78187ec7` 建分支后，确定性运行：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check . --statistics
```

结果为 171 条：

| 规则 | 数量 | 含义 |
|---|---:|---|
| F401 | 59 | 未使用 import |
| F541 | 31 | 无占位符的 f-string |
| E402 | 25 | 模块 import 不在文件顶部 |
| E702 | 19 | 分号连接多条语句 |
| F841 | 18 | 局部变量赋值后未使用 |
| E741 | 9 | `l` 等歧义变量名 |
| F821 | 5 | 名称未定义 |
| E701 | 3 | 冒号后同行多语句 |
| E401 | 2 | 一行导入多个模块 |

其中四个已在 `CLAUDE.md` 明确标为 broken、等待迁移的 legacy 文件占 27 条：

- `scripts/backtest_sector.py`
- `scripts/detect_turning_points.py`
- `scripts/sync_to_local.py`
- `scripts/render_daily_review_template.py`

排除这四个文件后的活跃债务为 144 条。当前 `.pre-commit-config.yaml` 与三条 GitHub
Actions workflow 都没有 Ruff 门禁，这是债务持续累积的工程根因。

## 2. 已确认的 correctness 问题

本轮不是纯格式化。诊断已用最小命令确认两类真实缺陷：

1. `skills/report-search/scripts/api_client.py` 在脚本入口调用 `os.getenv()`，但没有
   导入 `os`；无 key 启动稳定触发 `NameError`。
2. `intelligence/chat/feishu_bot.py` 的四个公开函数引用 `AskResult`，但模块全局没有
   该名称。普通调用因 postponed annotations 暂时可用，`typing.get_type_hints()`
   稳定触发 `NameError`，会破坏依赖运行时类型反射的消费者。

另有两处必须通过测试裁决、不能当死变量直接删除：

- `skills/lib/pdf_ingest_lint.py` 读取 `source_quality`，但“只检查 broker source”的
  注释没有对应过滤条件，可能扩大 annotation gate 的适用范围。
- `skills/limit-advance/scripts/write.py` 忽略 `batch_update()` 返回的实际成功数，却打印
  请求数；部分更新失败时可能制造成功数量假象。

## 3. 目标与非目标

### 目标

1. 先修真实 correctness 问题，并为每个问题保留可失败的回归测试。
2. 将活跃 Python 范围的 Ruff 告警从 144 降到 0。
3. 明确隔离四个已停用 legacy 文件，不用格式清零伪装成“脚本可用”。
4. 建立 Ruff 增量棘轮，阻止新债务进入；活跃范围清零后升级为全量门禁。
5. 每个批次保持行为等价或有明确测试证明的行为修正。

### 非目标

- 本任务不迁移四个 legacy 脚本到星型 DuckDB。
- 不修复全量 pytest 已记录的宿主环境基线失败。
- 不借 Ruff 清债重构 Theme Radar、问答编排或复盘业务模型。
- 不部署、不切换 8792/8799、不合并 main、不强推。

## 4. 方案比较

### 方案 A：一次执行 `ruff --fix .`

优点是快。缺点是 Ruff 所谓 safe fix 只保证语法层面；实测五个活跃 service 中有 15 个
局部 `import duckdb` 是可选依赖探针，自动修复会把它们替换成 `pass`，改变缺依赖时的
降级归因。第 16 条 DuckDB F401 位于已停用的 `scripts/fast_daily_sync.py`，是单独处理的
模块级死 import。70 个文件同时变化也无法建立可信回归边界。拒绝采用。

### 方案 B：把当前 171 条全部加入 ignore

优点是立即绿。缺点是同一文件后续新增的真实 F821/F841 也会被隐藏，相当于把告警
数字消失误当成质量提升。拒绝采用。

### 方案 C：correctness-first + 分批清债 + 增量棘轮（采用）

先修可复现缺陷，再按模块清理；E402 用最小行级例外，legacy 用精确文件级隔离；
每批独立测试与提交。该方案速度较慢，但每个变化都有可审计原因，用户已于
2026-08-02 明确要求“开始逐步修”。

## 5. 分批设计

### Batch A：F821 与两条可疑 F841

- `api_client.py` 增加真实 `os` import，并新增无 key CLI smoke test。
- `feishu_bot.py` 从轻量 `intelligence.services.ask_types` 导入 `AskResult`，新增
  `typing.get_type_hints()` 回归，避免为了类型导入整个重型 ask facade。
- 为 PDF ingest annotation gate 增加 broker/non-broker 对照测试，测试先决定
  `source_quality` 应参与过滤还是删除无效变量与错误注释。
- 飞书批量更新使用实际 `updated` 数量；若实际数小于请求数，必须 fail closed 或至少
  明确返回失败，不继续打印全量成功。

Batch A 单独提交，不能夹带格式化。

### Batch B：收敛可选 DuckDB 依赖 seam

15 个活跃调用点的局部 `import duckdb` 不逐个删除。把“依赖是否可用、连接是否成功、失败原因”收敛
进 `intelligence.services.retrieval_cache` 的小接口，调用方消费结构化结果：

- dependency unavailable；
- database missing/open failed；
- connection available。

这样既消除重复 F401，又保留现有降级语义。为缺模块、坏路径与正常连接写确定性测试，
随后迁移 `ask_blocks.py`、`market_analogs.py`、`market_moneyflow.py`、
`market_midterm.py`、`market_timeseries.py`。

### Batch C：活跃代码机械清理

只对人工审核后的文件清单运行 Ruff safe fix：

- F541 去掉无意义 `f` 前缀；
- E401 拆分 import；
- 普通 F401 删除无副作用的死 import；
- E701/E702 拆成多行；
- E741 将 `l` 改为 `line`、`label` 或领域名；
- F841 按上下文选择删除、使用实际返回值或补齐遗漏判断。

不对整个仓库运行 `ruff --fix .`。每个子目录单独提交，并运行对应测试或脚本 selftest。

### Batch D：有意 E402 与 legacy 隔离

25 条 E402 逐条确认启动顺序。对确需直接执行、必须先设置 `sys.path` 或环境变量的 import，
在该行添加带原因的 `# noqa: E402`；不使用目录级 E402 通配忽略。

四个 legacy 文件写入 `ruff.toml` 的精确 `extend-exclude`，注释引用 `CLAUDE.md` 的
broken 说明。隔离只代表“不纳入当前维护门”，不代表脚本已修复；未来迁移时先移除对应
exclude，再以 Ruff + 测试作为迁移验收。

### Batch E：增量门禁

1. 在 pre-commit 中加入固定版本 Ruff hook；pre-commit 天然只检查 staged Python 文件，
   形成“触碰即清理”的本地棘轮。
2. 活跃范围清零后，在 `workbench-check.yml` 安装同版本 Ruff 并执行 `ruff check .`。
3. Ruff 版本与规则选择固定在 `ruff.toml`，避免本地/CI 因版本漂移给出不同结论。

## 6. 测试与验收

每个 batch 都按以下顺序：

1. 新回归测试先红；纯机械规则以对应 Ruff node 作为红灯。
2. 只改本批文件。
3. 运行本批 Ruff 与定向 pytest/selftest。
4. 运行全量 pytest；比较失败**身份**而不是只比数量。
5. `git diff --check`、风险文件扫描与密钥扫描通过后提交。

最终验收：

```bash
python -m ruff check .
python -m pytest -q
pre-commit run --all-files
```

通过标准：Ruff 0；pytest 没有新增失败身份；四个 legacy 文件仍被明确记录为 broken；
无 `.env*`、密钥、PDF/ZIP/DuckDB/数据库、缓存或虚拟环境进入提交。

## 7. 提交、回退与运行边界

- 每批至少一个独立 commit，commit message 写清是 correctness、dependency seam、
  mechanical cleanup、legacy policy 还是 enforcement。
- 任一批出现新失败身份，只回退该批，不用 ignore 或放宽测试换绿。
- feature 分支只做本地 commit；push、PR、合并 main 与运行时切换均需后续明确授权。
- 8792/8799 只做健康检查，不加载本分支代码。

## 8. 设计自审

- 无占位项或未决实现；四个 legacy 文件和五类批次边界均明确。
- Ruff “0”定义为活跃代码零告警 + 精确隔离已停用 legacy，不冒充 legacy 可运行。
- correctness 修复、机械清理和门禁建设分别提交，避免验证范围互相污染。
- 可选 DuckDB 依赖不交给自动修复，保留原有降级可观测性。
