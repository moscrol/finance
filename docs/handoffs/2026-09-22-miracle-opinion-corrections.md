# 2026-09-22 · miracle 卖方观点订正与消费截止

## 背景
用户手贴 `调研纪要miracle` 共17期、475条事件，全部在09-21迟到入库。原文恢复和抽取结构通过，不等于语义核验，也不等于线上时间长河能消费。原台账共11867行，必须保留原字节和旧事件ID。

## 发现顺序与决策
1. 真实消费者探针确认 river 读 `fact_research_report_catalog`，不是 `opinion-events.jsonl`；因此分支可读、健康接口或目录外命中都不能叫长河已接通。
2. 只按报告日回放会把迟到内容当已知；缺/坏 `ingested_at`、推断日期和修订版本也必须有独立门控。新增共享只读 `load_events`，按报告日、首次入库、订正发布时间分别过滤；无效入库时间不回退报告日，时间戳必须带时区，未来 cutoff 需显式 hindsight。
3. 直接修改原JSONL会破坏错误版本和审计链。采用不可覆盖订正批次，绑定原记录 canonical SHA、完整修订链、原文 SHA 和 Python 字符区间；损坏订正隔离整源，不回退旧事件。
4. 475条只做可定位修复：九州一轨主题改为金刚石散热、L3；国机精工改为金刚石散热、L4；两者均软推演、未核验、空硬证据。中信建投与国泰海通署名误主体撤回。其余471条 quarantine，不猜摘要、不升L2。
5. 催化归因、Workbench、教学叙事和事件定价接投影。Workbench 用市场库交易日，卖方缺口进入既有 `data_status`；收益必须匹配 revision 且 `computed_at` 不晚于 cutoff。教学/定价仍是事后研究，不是严格历史回测。

## 验证与收据
金融提交 `6de192c61`，定向107项通过，ruff/compileall/提交门通过。KB 527 passed/1 quality baseline failure；missing_wikilinks 3407 > 3326、台账体积7.8MB > 7.7MB，未抬基线。projection 收据 `wiki/raw/sellside/reviews/2026-09-22-opinion-projection-6de192c61.json`；独立全仓 `12547 passed, 85 skipped, 2 xfailed, 17 warnings`，最终收据已写入 `docs/verification/2026-09-22-sellside-consumption.json` 和 KB raw sidecar。

测试启动时 HEAD 仍为 `e82717d9a`，收据保留这一事实；另将15个被测改动Python文件的SHA逐项对账，均等于随后提交的 `6de192c61`，没有改写启动revision。前两次失败日志与第三次JUnit保存在 `/Users/a77/.finance-runtime/reviews/sellside-consumption-6de192c61-20260922/`。第二次只确认临时根消失，未确认删除者；pytest `keep=0` 不建运行锁提供机制解释，不能据此指认其他会话。

09-11历史截止本批0条；09-21仍保留当时475条旧版，不表示旧版语义获认可；09-22默认0条，显式允许推断日期的研究预览才见2条订正。其他来源的催化命中不能冒充本批命中。尚未运行前端lint/typecheck/test/build/E2E或独立验收，Python通过不授合并、发布权。

## 工具沉淀
反复的消费核验已固化为 `scripts/audit_opinion_projection.py`；发布与批次准备分别为 `scripts/review_opinion_events.py`、`scripts/prepare_miracle_review.py`，包含拒绝/幂等回归。`/tmp/close-sellside-receipts.py` 仅打包本次固定路径的现成日志与哈希，不是新验收入口；产物已进版本库，未把一次性打包器扩成通用框架。

## 不做什么
不合并、不部署、不改生产DB/长河、不释放471条；不把两条订正当作已确认日期（09-11仍 `inferred_unconfirmed`）。不把晨汇、收益写入器和 river 目录同步的边界藏在“统一读取层”后面。

## 后续
最终全量收据已封存；合并前仍需独立验收和其余叶子检查。用户确认09-11后用新批次释放两条；471条逐条复核。若要接 river，另开桥接任务，定义目录/事件投影、版本和严格 PIT 合同，并用真实线上 revision 验收。
