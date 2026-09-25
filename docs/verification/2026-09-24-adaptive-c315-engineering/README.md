# c315 联合工程红轮与零消费阻断

## 结论与身份

**本轮不能合入。** 正式工程候选 `c315cfdaa96a5b18cedb060b09ddc92ec2a14559`，已联合主线 `3bb81b9638f97b4773ce0f338df3a505b7c0162f`。工程根为 `~/.finance-runtime/reviews/pr868-merge-ready-20260924-0205/`。本文只封存已结束的结果，不给后续 revision 移签。

| 证据 | 结果 | 边界 |
|---|---|---|
| 完整 Python 工程 | 15383P / 7F / 85S / 2X；collected 15477；exit 1 | 干净 c315，scope 无 ignore / deselect / keyword / markexpr，maxfail 0；7F 全在 `intelligence/tests/test_rag_worker_keepalive.py` |
| Ruff | PASS | 同一正式入口，先于 pytest |
| 正式前端 | install / lint / typecheck / test / build / test:e2e 均 exit 0 | 仅此候选，不补 Python 红叶 |
| 注册表与台账 | parseability / registry / tables / views / ledger 均 exit 0 | 七叶总态仍 RED |
| 单文件诊断 | keepalive 9P | 不改原 7F |
| 邻接诊断 | worker + keepalive 60P；五个 RAG 模块 114P | 两次独立范围，不能加总 |
| 全收集后筛选 | 9P / 15468 deselected | 收集完整不等于执行完整，不能称全量 |
| 原序前缀诊断 | 7165P / 1F / 20S / 2X；6360 deselected，exit 1 | 收集15477、选前9117；首次失败即停，只执行7188，余1929未执行，尚未抵达 keepalive |
| 日志保全修复反例 | 旧入口4F，加收据/临时区重叠控制2F | 作者工作树新测试验证旧入口；不是正式工程失败数 |
| 日志保全修复后 | 两文件72P，Ruff / bash语法 / diff及提交钩子通过 | 仅作者相关回归；提交为e7a6cb412，不宣称修复RAG或阶段覆盖 |

正式收据见 `engineering/pytest-receipt.json`。原入口只保留控制台末尾，原7F没有完整堆栈；不能从后来局部绿倒推它们的失败原因。新增日志保全不会补造丢失的历史输出。

前缀唯一红项：
`intelligence/tests/test_llm_timeout_diagnostic.py::test_shared_window_zero_rejection_is_not_a_third_request`。
它记录了两次尝试/调用账，但服务端只收到一次请求，断言 `1 == 2` 失败；这属于新增阶段覆盖失败，不解释原7个RAG失败。完整日志见 `engineering/rag-prefix.log.txt`，选中列表与XML以无损压缩封套保存。

## 独审与 L6

- QC0208：`BLOCKED_NO_RETRY`，工程红阻止准入，阶段0、新请求0。旧0015+0024的74/152消费不重置；本批不可续跑，宿主不代签。
- L60210：`BLOCKED_PREFLIGHT`，严格探针、金额回放、proxy检查、冻结数据/检索、旁车和自然题均未执行。模型与自然提交0，不宣称比较过生产身份。
- 两批均有 `closure-unadmitted.json`。封存时19899由其他任务占用，只确认本批无遗留监听，未停止其他任务进程；19897/19898及前端端口当时空闲。
- 旧 Spec 证据不足、Quality CHANGES_REQUIRED、旧自然 NOT_PASSED，以及更早的严格覆盖/检索失败均不改判。历史见 `../2026-09-24-adaptive-merge-history/README.md`。

## 作者量具证据

c315取消量具的 baseline / 撤转发 / restored 三组均完成：正反例有效，三路径绑定实际进入响应上下文后的计时。正式L6入口另做判据与调用接线两层撤保护，分别5F / 1F，恢复25P。它们不计独审行为覆盖，也不计自然验收。

e7a6cb412仅补工程证据留存：每轮 `gate-*/pytest.log` 保存完整输出；tee / tail失败或日志缺失返回设施失败4；收据目录不得落进会被清空/删除的显式basetemp。原测试预期、0.8秒/0.2容差及检索120秒均未放宽。新e7候选在 `pr868-merge-ready-20260924-0326/` 单独验证，不属于本封存结果，未自动排付费任务。

## 存储与格式

`archive-manifest.json` 记录51份工件的原路径、原字节数/哈希、存储字节数/哈希与编码。无格式问题的原件逐字保存；原有空白或大文件采用 `base64-json` / `gzip-base64-json` 可逆封套。两份大文件为原序选中列表与XML；解码结果均与运行目录原件逐字相同。原脚本存为 `.py.txt`，避免被仓库测试收集或当作当前可执行入口。

解码算法：读取JSON的data，严格base64解码；仅在encoding为gzip-base64-json时再gzip解压；与source_bytes和source_sha256对账。不得把压缩封套的存储哈希冒充原始证据哈希。

整条PR另有8份旧封存文本的行尾空白/末尾空行，`git diff --check gitea/main...HEAD` exit2，详见 `engineering/whole-pr-format.json` 及对应日志封套。未裁剪原件、未豁免该检查；本新归档的格式检查与整PR检查不是同一范围。
