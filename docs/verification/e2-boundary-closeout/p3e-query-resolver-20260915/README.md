# P3e 作者收据：QueryResolver 材料范围早读

基线 `39af312f51fa73f7a3db3b7f8c1fa8f8420213c9`；本目录与应用改动同提交冻结。
**独立 QC 已完成并通过；不是完整 P3、产品验收、合并或部署许可。**

独立报告与原始失败/修正版证据已归档：[P3e 独立 QC](../p3e-query-resolver-20260915-independent-qc-20260915/README.md)。裁定仅限本片词典早读闸门：focused 41P、相关347P，修正版禁止 IO 尝试0；首次启动器误拒41次的失败证据保留。

## 修复与边界

`QueryResolver.resolve` 在实体/主题/证券词典入口之前调用既有 `split_user_message` +
`compile_material_contract`。只有确定 `material_only` 走 `understand_query` 的文本理解；
anchor/candidates/comparison_entities 不再取自材料外词典。三态尾逻辑抽成一个纯函数复用，
没有复制禁令短语，也没有先跑一次语义理解再覆写结果。其他 scope 的既有分支不变。

本片不覆盖 `understand_query` 内的静态路由配置/简称/日历先验、controller前历史、
legacy/injected resolver、预取前歧义、可信续轮、九类来源、恢复/压缩、P4–P7。
q3 吞题缺口不在此修，题号测试固定 q1，不以动态题号断言冒充原题完整。
历史题在受限路径不再生成词典验证的 comparison_entities；材料正文仍完整保留供后续处理，
不是“历史比较能力已验收”。调用方更早剥掉禁令的路径也不由本片保证。

## 收据（作者执行，不是独立裁定）

| 运行 | pytest 终态 | 启动器终态 / 禁止尝试 |
|---|---|---|
| before：应用未改 | 23F/13P | 1 / 0 |
| after：新闸门 | 36P | 0 / 0 |
| mutation：唯一改动令新 if 恒假 | 23F/13P | 1 / 0 |
| parent：固定父应用+同一新增测试 | 23F/13P | 1 / 0 |
| related：11文件 | 453P | **3 / 8，隔离失败** |
| related-traced：加调用栈再跑 | 453P | **3 / 8，隔离失败** |
| service-regression：同组排除1项API导入测试 | 452P/1 deselected | 0 / 0 |
| normal-pytest：仓内conftest的新文件 | 36P | pytest exit 0，无启动器IO总计 |
| Ruff全仓 | All checks passed | exit 0 |

以上集合重叠，不加总为覆盖数。没有本版全仓pytest/前端/E2E结论。
新测试覆盖冷/热缓存、拒绝/允许读取、公司名/数字/主题别名/历史比较题、full/local_only/
普通正例、引号/围栏中的禁令不升级、显式放宽、scope连续切换，以及真实controller的默认/
注入QueryResolver。临时KB两份JSON与真实临时DuckDB，Path stat/open及duckdb.connect计数；
模拟PermissionError被业务吞掉也仍断言累计尝试为零。不读生产金融数据、不调金融模型。

## 失败归因与隔离限制

1. 最早 `/tmp/e2-p3e-precontroller-probe.py` 是不完整临时探针：先因PYTHONPATH缺失失败，
   再因frozen dataclass不能赋方法失败；修后仅记录aliases调用，未封默认证券DB，
   未捕获controller提示词。不能把它当全隔离或历史注入证明；保留源文件但不用作通过依据。
2. `related-traced-io.json` 指向：普通问候测试的默认KB读取2次；
   `test_real_app_factory_injects_same_run_writer_only_for_history` 导入 `api.app` 后版本指纹
   扫描触发Git子进程2次、代码树内 `intelligence/users` 遍历4次。均先计数再拒绝，
   不能写“453P所以隔离过关”。
3. 启动器v1/v2用了实现不识别的 `KNOWLEDGE_BASE_ROOT`；v3改为实现实际读取的
   `KB_VAULT/KNOWLEDGE_WIKI` 指向临时目录。没有放宽路径拒绝；API导入测试明确排除，
   故452P只能称服务层子集，不替代453项完整隔离结论。v2仅新增调用栈，v3仅修临时路径。
4. 首轮未设独立basetemp，pytest清理宿主旧临时目录时输出OSError警告；原log未修剪。
   后续每轮使用独立basetemp，避免触碰其他测试目录；未删他人文件。
5. 启动器是Python audit hook，不是OS沙箱，不能捕获所有native IO；新测试另拦
   duckdb.connect且库只在tmp，不能外推到未覆盖模块。允许读取源码与静态配置。

## 复现

独立审查的完整报告、失败/修正版收据、启动器、补针与哈希见上方独立 QC 归档；以下是作者收据复现路径。

取 `launcher-v3.py.txt` 复制至临时 `.py`，显式设置三个变量后用主树venv：
```
cd <固定工作树>
E2_TEST_ROOT="$PWD" E2_TEST_EVIDENCE=<新临时证据目录> E2_TEST_NAME=qc \
  <主树>/.venv-workbench/bin/python <临时launcher.py> \
  intelligence/tests/test_e2_query_resolver_reads.py --basetemp=<新临时目录>/pytest -q
```
服务层清单见 `commands.txt`，唯一排除项显式 `-k` 标注。launcher-v1用于before/after/related；
v2用于mutation/related-traced；v3用于parent/service-regression。原件按字节归档，
`.py/.log` 加 `.txt` 防pytest收集/日志禁提；SHA-256见manifest.json。临时DB/大型harness日志不入Git。
