# E2 P3b：本地工具读取上限与阶段收据

2026-09-14。应用提交 `8ea6c5c11995d8af9f3f24a3f39b3addea8406f8`，分支 `fix/e2-boundary-closeout`，树 `/Users/a77/fwp-wt-e2-boundary-closeout`。已提交，未推、未合、未部署；独立 QC 503 受阻，不标阶段通过。

## 背景与发现顺序

接手时 HEAD=e0051804，五个修改文件、material_permissions.py 与 test_e2_local_freeze.py 两个新文件均来自前序 P3b session；主树的无关未跟踪文件完全未动。旧日志197 passed未包含新测试，新测试首次运行10 passed。

1. 前序补丁已做最终能力收窄、ToolSpec.io_effect、注册表read_scope、EpisodeScope与dispatch共用授权。认证点在具体runner装配处，不从cost/local或freshness/stable推断效果。
2. 审到临时数据库测试仍可能在实体解析时读全局证券词典。保留本地runner不用subject_anchor，因此local_only直接不解析、不装默认联网工具；没有为此更改普通full行为。
3. 发现受限注册表直接构造可以带opening_prefetch/calc_loader，只有with_read_scope派生会清除。把禁止夹带约束移到构造器，所有副本自然继承；新增反例先失败后通过。
4. 静态产业链预检是非工具读取，knowledge可由调用方替换。local_only与material_only均不调用；不拿未经授权的查询结果提前决定缺口。
5. 将四条本地runner都跑到真实临时结果：finance_query/主线→临时DuckDB，evidence_lookup→临时JSON，memory_lookup→临时用户判断台账。记忆仍是user_memory先验，不能当市场事实。
6. 增加数据正常/缺库/空表/过期四种路径。socket connect/connect_ex/getaddrinfo与subprocess.Popen替身既报错也累计尝试，避免异常被fallback吞掉后假绿。19条新针通过。

开发反例原日志 `/tmp/e2-p3b-red-tests.txt` 的6红含4个预期应用边界红、1个测试共用task_id在失败栈留住预算后的串扰、1个不命中历史意图的问句。后两者修测试：唯一task_id，使用已支持的历史意图表达；不是6个产品bug。另一次mainline参数错误按其无参快照协议改成{}。缺库针确认既有FinanceQuery直接抛duckdb.IOException；测试钉“不创建库/不联网替补”，没有借此改金融查询错误契约。

## 方案取舍

| 采用 | 否决 | 原因/代价 |
|---|---|---|
| 能力白名单+实际runner认证两层 | 同能力工具一概本地，或看cost/freshness | 同名替换/新增runner可能外呼；未知默认拒绝 |
| with_specs/without/with_read_scope保留较严上限 | full参数能洗白局部registry | 派生不能放宽既有约束，dispatch还看context |
| 受限构造器清预取/加载器 | 仅派生方法清理 | 直接构造是另一个入口；复制路径自然封住 |
| 暂停未分类自动静态预检/播种 | 工具菜单为空就算无IO | 自动读取早于工具调用且不在能力审计面 |
| 保留已证明的本地路径 | local_only直接变material_only | 禁联网不是禁本地数据库/文件；正向针必须真返回数据 |
| 历史附加工具暂不挂，finance_query窗口仍保留 | finance_query能力授权顺带挂全部history runner | 保存/原件路径未单独认证；不把历史工具名补回输出证据类型 |
| 缺库保留原异常 | 本次顺手统一FinanceQuery错误行为 | 阶段要证不外呼，不扩大到通用查询错误契约 |

## 已验证

提交前Ruff、unread-fields、diff及提交钩子通过。提交后代码地图按正式build刷新，固定干净8ea6c5c1上：
- 定向10个测试文件：286 passed，3.13s；收据 `~/.finance-runtime/test-receipts/20260914T130652Z-8ea6c5c1.json`。
- 全仓pytest：9762 passed、83 skipped、2 xfailed、17 warnings，869.72s，exit0；收据 `~/.finance-runtime/test-receipts/20260914T132230Z-8ea6c5c1.json`。
- 原始输出已归档 `docs/verification/e2-boundary-closeout/frozen-8ea6c5c1-tests.txt` / `full-8ea6c5c1-tests.txt`。warnings为market_stage数值运算与utcnow弃用提示，未屏蔽。
- 独立检出开始/结束clean；Codex在任何审查工具执行前503，无结论。详见 `qc-8ea6c5c1-blocked.md`。
- 未跑前端链、E2E或正式金融产品对话。本次全仓Python绿不等于合并全部叶子绿。

## 边界与后续

P3b只覆盖明确local_only的Episode工厂/注册表可信装配。不承诺所有本地工具均可用：kb_search的子进程/模型加载、graph_lookup研究地图、evidence_search判官等仍未知；金融与估值混合外呼路径拒绝。

`io_effect`是可信Python装配声明，不防恶意Python伪造local_read，不是OS沙箱。受限registry上限不能替代所有runtime入口的同源过滤；原始未绑定registry的预取/恢复消费者、controller旧摘要、视角/stance/project prior、压缩、子研究、确定性旁路仍须逐条接线。local_only普通context尚未来源分型，不宣称模型输入已纯净。

local_only原题号槽/最终三态尚未做；material_only已有原题号装配但最终材料锚点与跨轮恢复仍不完整。P4–P7、全新原始T2→T3、模型策略冻结与Knevo正式配对均不执行。下一步先补P3b独立复核，再按v10继续剩余P3–P7。

工具沉淀：反例已归仓内 `test_e2_local_freeze.py`（不是只存/tmp的脚本）。“计数失败尝试以防异常被吞”作为通用测试手法沉淀知识层；本轮没有新增可迁移harness工具，harness-reference树脏，未动它。主树、生产数据库与服务均未改动。
