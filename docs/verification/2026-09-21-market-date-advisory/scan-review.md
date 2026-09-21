# 敏感信息扫描复核

## 范围

首次扫描对象是本目录当时的200个文本文件，使用仓库现有 `scripts/smoke_workbench_self_use.py::SecretScanner` 的模式集合。首次调用的包装命令返回非零，报告为6个文件、12组“文件-模式”命中；这不是零命中安全认证。

加入本说明后重新扫描：201个文件（含哈希清单）、7个文件/15组命中、22个去重匹配值。新增的3组来自本说明引用的Bearer夹具、Python类名及赋值样例，不是原件新增秘密。扫描器方法本身记录命中、不返回进程退出码；最终包装命令正常结束仅说明扫描执行完成。

## 复核结果

逐项读取命中上下文后，命中属于以下已知非秘密类别：

- `raw/final-c57ec654/python/junit.xml` 与同类 JUnit：参数化测试名中的云凭据前缀样例、Bearer/JWT形状样例、`PRIVATE_SECRET` 和不暴露真实值的测试参数。
- `raw/final-c57ec654/mutation_probe.py.txt`、`raw/fixed-06de3dfc/mutation_probe.py.txt`：变异探针中的Python模块及属性路径命中三段点分隔模式，不是认证令牌。
- `raw/related.log.txt` 与 `raw/related.xml`：`starlette.testclient.TestClient` 是失败输出中的Python类名，三段点分隔被JWT形状模式命中；不是对象的十六进制地址，也不是认证令牌。

原件的21个去重匹配值均已回看上下文；本说明新增的匹配来自样例后附Markdown标点。云前缀和JWT夹具对照 `tests/test_smoke_workbench_self_use.py::test_model_label_rejects_other_credential_families`；Bearer与secret_assignment对照 `intelligence/tests/test_acceptance_trace_capture.py` 的 `Authorization: Bearer PRIVATE_SECRET`；query参数对照 `intelligence/tests/test_llm_settings.py` 的不安全URL拒绝测试。其余为模块名、属性访问、JUnit类名。未发现实际凭据；`api_key=[REDACTED]` 是扫描器明确忽略的另一个测试，不属于本次命中项。

## 限制

- 本复核只证明归档内容中命中项的上下文分类，不证明仓库或运行环境的全面密钥审计。
- 两个此前猜测的独立 `secret_scan.py` 路径不存在；没有把路径不存在写成“扫描通过”。一次较宽的 shell 正则尝试因引号错误失败，也没有计入成功证据。
- 原始报告不做内容清洗，以保留失败与测试身份；若未来发现真实凭据，应先在新归档包中停止发布并按仓库密钥处置流程处理。
