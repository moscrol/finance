# 09-21 行情恢复：纯候选构造已实现，仍不能写库或发布

## 目标与权限

承接“继续推进”，完成只读取证、日期专用纯构造及反例测试。代码提交 `7311a7738`，在途交接提交 `4c0162a9b`，分支 `fix/market-recovery-0921`。前置证据与背景见 `2026-09-22-market-recovery-input-contract.md`；那份历史快照保留，不用本轮新结论覆盖它。

本轮没有生产或 staging 写入、全目录同步、L2 解算、原子换库、合并、部署，也没有修改 RAG #844、K3 写手、模型判官或共享 KB。日线候选的成功不是整个复盘恢复成功；same-day、cross-day、L2 最近失败结论仍在，本轮没有重跑这些发布门。

## 发现顺序

1. 东财未复权历史接口对 6 个指定代码各请求一次，全部 `RemoteDisconnected`。保留 `history-receipt.json`，不重试、不借最新快照填历史日。
2. 下载两只复牌股的新浪历史原件。第一次严格解析遗漏供应商尾部块注释，返回 `ValueError`；保留失败收据，在本地用 AKShare 既有解码器解析已下载字节，不重复联网。不调用 AKShare 高层日线的前向填充流程。
3. 新华传媒 `600825.SH` 的 09-04 原件收盘 5.31，华锡有色 `600301.SH` 的 09-11 原件收盘 45.43，均与封存同花顺行、腾讯 09-21 前收一致。两条旧 bar 的 OHLC、成交股数逐字段一致；新浪整数元成交额比同花顺分别少 0.19 元、0.32 元。原件填上了此前缺失的 09-04 见证，但仍不证明整个复牌间隔没有遗漏公司行动。
4. 比较已封存的新浪当前名单与腾讯日期报价。在共有 5564 只中，名称不同 381 条，换手率差异超过 0.011 个百分点的 21 条。名称包含空格、简称、公司全称及 XD 前缀差异；两源上游也未证明相互独立。新浪只有时分秒、不提供目标交易日期，不能因值接近而升级成历史日证据。
5. 实现 `market_feature_store/hithink_recovery_candidate.py`。沿用 `hithink_stock_preview._calculate` 的金额、成交量、现金除息与半入规则，不改通用预演和 `SPEC_20260911`。固定 `CANDIDATE_20260921` 的日期、范围指纹、12 只无 bar 名单、两条复牌参考、21 个目标日事件代码、两条精确半分舍入差。
6. 纯函数只接收显式数据集合，输出候选与缺失处置，不读取文件、网络或数据库。名称暂保留腾讯观测及时间，不宣称已接受为正式字段；`turnover=None`，另存 `observed_turnover_pct`。调用方仍必须验证原始字节，函数内指纹不是签名或源真实性证明。
7. 本地回放先核对原 manifest 的 278 文件、封存失败库、历史见证文件；再对原始 Parquet 与封存表逐字段核验。DuckDB 仅以 `read_only=True` 打开封存失败副本，未打开生产连接、未创建新库。
8. 最终结果：声明范围 5565，候选日线 5553，缺失处置 12。复牌两行通过完整见证比较；舍入差仍保留为 600184.SH 的 -3.13 对腾讯 -3.12、603259.SH 的 4.98 对腾讯 4.97。所有正式回放的结果指纹一致，但不据此声称长期稳定或数据源完备。
9. 变异首轮发现范围指纹保护删除后测试仍绿：其他范围保护提前挡住了原反例。补入“只改指纹，输入其余部分完全合法”的反例，最终六类撤保护全部报测试失败。旧首轮收据保留。

## 决策与被否方案

| 方案 | 评价 | 结果 |
|---|---|---|
| 新增日期限定候选规格，复用现有精确计算 | 不改变旧修复器假设；候选范围与例外可复核 | 采用 |
| 给 09-11 RepairSpec 换日期 | 旧白名单与分母前提不同，可能绕过历史合同 | 否决 |
| 两只复牌具名参考 + 连续停牌区间 + 原始历史见证 + 无记录事件检查 | 比通用向前找收盘更窄；仍需公司行动完备性审查 | 仅候选采用 |
| 缺前日统一向前查最近收盘 | 可能跨除权、身份变化或未解释交易日 | 否决 |
| 12 只无 bar 保留缺失清单与原声明范围 | 不造 K 线，不暗中减少覆盖分母 | 采用；下游政策未定 |
| 复制停牌股旧价凑齐 5565 行 | 会制造并不存在的历史 bar | 否决 |
| 选定腾讯捕获名称并保留观测时间；换手率不进入拟正式值 | 让差异可见，避免拼接两个未经确认的口径 | 仅候选采用 |
| 用新浪当前名单替换所有名称、换手率 | 时间与名称语义不一致；21 条换手差异尚未解释 | 否决 |
| 保留通用 ROUND_HALF_UP，仅接受具名、精确半分差 | 两条差异不会变成任意 0.01 容差 | 采用 |
| 指纹、输入校验、候选计算均不授予发布权 | 局部成功与完整质量门、授权是不同条件 | 采用 |

## 固定证据

根目录为本树 `tmp/recovery-20260921/`，本轮新增内容在 `resume-candidate/`。所有原件、数据库、原始报价、日志与候选 JSON 保持本地，不提交 Git。

| 对象 | SHA256 |
|---|---|
| 原 `input-manifest.json`，278 文件 | `3943ed43d2c68cbc53fb421a8694def27eabd41c871f67643544cc6431203525` |
| `resume-candidate/extension-manifest.json`，新增 136 文件 | `e572d214d42e3e10cd8fec63a14e95a8bdb614bc82fadf550b2043dda9f29a9c` |
| `sh600825.raw` | `1d5cbd6d42c80e43effb6e2d0da0c86c72e6b2ac97022f483d324e642b1055e8` |
| `sh600301.raw` | `3170dd6bdf31ef1364289bf9688e2a19049dc3ffc7ad7910cc273db4d2419e42` |
| `decoded-history.json` | `eee9592ef43a6cf3b99569f2c8aadcc92b28fabc7e621ec0be181e655a9d9894` |
| `candidate-final.json` | `d23960250d3fca5eb900a38e082b350c8cd7cc8f427ed55a2b7bee8da5d70266` |
| `candidate-receipt-final.json` | `1c9927bd7902ae51bda3accc29f3df6a768288b04222fc1e0d44004489d84dd7` |
| 最终构造器源码 | `23bd4b59efe67a9741dffbf75e441e1e64755f8e0f5b95b6bc8121021ca195f3` |

扩展 manifest 单独引用原 manifest 哈希，封存后逐文件回读 136/136 一致；原清单不覆盖。原失败抓取、第一次解码失败、首轮存活变异、各版回放及保护收据均保留。

候选输入指纹 `52410f4ded44667b9249719e6ed300b84772c91bdf7160103131a6eea1501206`，结果指纹 `446cf3af8c3401f7e05ee20a007a187cfcb96b2e18802e7cd6ac8aead8b31d4a`。所有版本均为 `production_ready=false`、`database_writes=false`、`publication_attempted=false`。

## 验证与边界

- 新构造器测试 88 项。干净提交 `4c0162a9b` 上五个测试文件合计 247 passed；收据 `~/.finance-runtime/test-receipts/20260921T192049Z-4c0162a9.json`。
- 测试文件为 `test_hithink_recovery_candidate.py`、`test_hithink_stock_preview.py`、`test_audit_dated_quote_capture.py`、`test_repair_hithink_stock_day.py`、`test_recover_local_review.py`。
- 最终变异收据 `resume-candidate/mutations-final/receipt.json`：范围指纹、全天区间、间隔事件、历史 bar、股手单位、半分边界六类分别触发 1/3/1/1/1/1 个失败。中间首轮与 v2 只归属于各自源码和测试哈希，不替代最终版本。
- Ruff、diff check、提交钩子通过。未跑全仓 Python、前端、E2E、整合 tip 门禁或独立审查，不作可合入判断。
- `preservation-receipt-final.json` 于 03:19:48 核对生产库 SHA、inode、大小、mtime 与原封存一致；两个快照哈希也一致。封存失败库在真实回放前后 SHA 一致。
- 此前命令曾使用不存在的恢复测试文件名，退出 4、没有测试执行；后来已按真实文件名运行，不将那次算通过。保护收据的重复文件名曾触发 `FileExistsError`，未覆盖旧证据，随后用新输出名复核成功。

复现测试：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  tests/test_hithink_recovery_candidate.py tests/test_hithink_stock_preview.py \
  tests/test_audit_dated_quote_capture.py tests/test_repair_hithink_stock_day.py \
  tests/test_recover_local_review.py
```

本地 `replay_candidate.py` 是固定此次证据的取证适配器，默认输出已存在，会拒绝覆盖；复验须另选新输出名，保留固定输入哈希，不重新生成哈希去迎合变动。

## 剩余工作与禁止项

1. 核实官方历史上市范围和公司行动完备性，接受或修订名称来源合同；换手率的流通股本分母尚未核实。不要把 5565 并集当官方历史全集，也不要把 21 条差异解读为已证实供应商错误。
2. 决定 12 只缺 bar 对涨跌平统计、板块成员及质量门的分母政策。`sync_local_sector_members` 当前会略过没有当日值的成员；不能把本候选的 exclusions 自动当作准许缺员的声明。
3. 申万历史、板块全目录、冻结宇宙与成员 generation、市场统计、派生表和 L2 完整恢复仍未做。接口抽样成功和 7z 存在不构成恢复完成。
4. 用户显式调用写入技能并授权相应阶段后，才建立新隔离 staging，检查活动写者，逐表回读真实值，日历最后写。禁止最新 snapshot 补历史、写 VIEW、复制旧价凑数或删除失败现场。
5. 所有生产质量门通过且另获发布授权后，才走既有原子换库；合并、部署、RAG #844 与 K3/judge-off 各自单独授权。

## 沉淀边界

可复用的纯计算、日期范围和例外验证已入仓代码与 88 测试；没有新增 agent 可调工具、数据库写者或能力图节点。取证适配器依赖这次封存布局和特定见证，不提升成通用历史修复 CLI；它不是经过任意输入验证的加载器。跨源名称、换手率、停牌分母仍需领域判断，不能以脚本条数替代合同审查。`~/harness-reference/BUILD.md` 仍有他人脏改动，本轮不修改该仓或新增平行方法论清单。
