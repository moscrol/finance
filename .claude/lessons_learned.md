# 错误与教训

> 格式：`[日期] 错误 → 根因 → 正确做法`

## 日期语义与验证身份

- **[2026-09-21] 日期不齐被当成事实失效，正文事件日又被当成来源日。** 根因：准入、取数上界与证据时点混为一谈。做法：保留真实诊断，按各源截至cutoff的实际日期交付；预取转文本同样保留来源元数据。明确未知不补参照日，NULL不补0，比较另核期间/单位。正式测试和11项撤保护反证见 `docs/handoffs/2026-09-21-market-date-advisory.md`。
- **[2026-09-21] 把已提交的修复误认为测试中改码，误停06de全量。** 根因：把记忆里的编辑顺序代替进程开始时间、SHA与树对象。做法：停止自有测试前重新对账身份和时序；本次首尾其实同树，保留错误原件并追加勘误，不编造源码漂移。随后完整失败与修后完整通过各自留证。
- **[2026-09-21] 窄正则未命中就提前概括为归档扫描通过。** 后续实际SecretScanner命中测试夹具及代码模块名。做法：执行错误不算未命中，模式命中也不等于泄密；逐项核上下文和夹具来源，记录扫描范围与排除依据，不改原始测试报告。

## 夜跑安装与收据读取

- **[2026-09-21] 开跑时20GiB空闲，不代表共享宿主全程有空间。**
  2ea6最终全量后段ENOSPC，12454P/2F/8error；全部失败元素有磁盘错误。只归档验哈希后回收本轮3.1GiB scratch，两失败模块诊断25P，不能拼成完整绿。同期Quality exit1无报告、原因未证，不能说模型已审过或自动重试。后续需协调并发与空间余量；失败收据原样保留，见 `docs/handoffs/2026-09-21-nightly-deploy-execute-blocked.md`。
- **[2026-09-21] JUnit不是“一case一种状态”的表。**
  setup/call/teardown可产生多条error或单独testcase元素；外部汇总互斥计数会漏teardown。原进程rc1、终端与收据是红则维持红，逐个failure/error元素归因，不靠重分类转绿。

- **[2026-09-21] `plutil -lint` 绿，却不是可安装的任务配置。**
  根因：OpenStep 格式允许裸字符串，语法有效不等于 LaunchAgent 字典合法。安装前再验 Label 与目标任务一致、RunAtLoad=false；真实安装器在临时 HOME/记录型 launchctl 上验证拒绝发生在写入前。五个撤保护变异均被捕获。见 `docs/handoffs/2026-09-21-nightly-deploy-closeout.md`。
- **[2026-09-21] 全量 pytest exit0，外层汇总误报没有收据。**
  根因：行首正则假定收据独占一行，实际接在 `[100%]` 后。保留原汇总exit1；仅从同一保存stdout提取唯一精确路径，与进程退出码、SHA/树/时刻、JUnit逐项及终端计数交叉核对。没有重跑测试，也没借共享latest或零项嵌套收据洗绿。

## 生成段代码与持久化分根

- **[2026-09-15] 父根与绝对路径都通过，仍可写入代码树或执行数据树脚本。**
  根因：未解引用用户/日期/状态目录和已有输出文件；绝对脚本路径仍可软链外逃；启动器与 daily 两套参数解析器对 `--summary-j` 含义不同。
  做法：项目 import 前验代码软链归属；原 CLI 只解析一次、同一结果校验和执行；副作用前验实际写入后代，合法外置软链保留。三处删闸均在独立副本复现副作用，恢复后拒绝，不能把旧代码自己报错当根门生效。冻结 `387028b8` 作者复验不替独立验收，也不是 OS 沙箱。证据：`docs/handoffs/2026-09-15-generation-root-boundary-guards.md`。

## [kb] 进程归属与维护边界

- **[2026-09-18] 把索引发布进程误归为 Cursor，让没开 Cursor 的用户去协调。**
  根因：只看 shell 的 `__CURSOR_SANDBOX_ENV_RESTORE` 模板标记，没查实际父进程；继承的环境不是身份。
  做法：用户授权后核 PID/启动时间/父链，实际父进程是 Grok Bot 的 local-exec-daemon，任务已正常退出，无须杀应用。
  三个 Git post-* 暂停也不是全写者锁；本窗口改用可回滚的 macOS 文件防写标记保护两份索引，先在临时副本测覆盖/替换/删除，再核生产字节不变与查询可读。该保护不包含远端 Release，也不能对抗同用户主动清除标记。详见 `docs/handoffs/2026-09-18-kb-index-writer-coordination.md`。

## [kb] 解析、覆盖与消费者探针

- **[2026-09-19] 全文迁移 exit 0，四篇非空原文却没有任何入库块。**
  根因：页首水平线被当成 YAML 页头，非 mapping/非法 YAML 也丢掉两线间正文；只验解析后的计数会共享同一个错误。
  做法：从源文件白名单闭合覆盖分母；修解析器、升切块版本v4，原文不改。四篇原文逐字节未动且恢复24/21/20/23块；14页历史冲突继续隔离，不从分母消失。
- **[2026-09-19] 用“液冷+L3必有命中/无完整词必为空”做探针，先后误设正负例。**
  根因：没先核待复核否决与实际分词；L3标签不等于合格证据，汉字单字posting可以只匹配“液”。
  做法：固定资料先用现有资格规则和token交集验样本；过滤回执正确不等于相关性/答案质量通过。三轮错误断言留证，后续不改排序/过滤凑绿。详见 `docs/handoffs/2026-09-19-kb-v4-delivery-acceptance.md`。

## [kb] 受管目标与异常收尾

- **[2026-09-20] 已有批准启动器，但受管未批准/退役索引省略 manifest 环境仍能查询，库级 save(None) 仍默认写回旧树。**
  根因：是否受管由可缺省环境判断，共同 writer 仍猜目标。做法：沿实际选中的索引路径核受管 marker；受管目标必须完整绑定，保存必须显式目标。根/源/输入重叠在 mkdir 和取锁前拒绝。原真实 CLI、库接口及旧目录新增65条的反例均保留；固定1bd5e1dc复验拒绝且旧目录新增0。
- **[2026-09-20] 主流程有锁，换根或失锁后的 except 却继续写失败记录；控制清单软链和上传中标签变化也未在终验发现。**
  做法：控制文件走稳定读取；异常落盘同样先核写者身份，失权时保留原错并非零退出；整包回读之外，成功收据前再核标签绑定的代码SHA。独立五例原输入复验5/5；只签临时小索引/替身传输，不宣称生产重启或真实发布完成。后续Quality又在activate成功路径发现同类身份丢失；7e07addb补全部已识别的控制写入点，正式回归80P、全量911P；末轮独立复核是静态，原动态没有在新SHA重跑。见 `docs/handoffs/2026-09-20-open-work-execution.md`。

## 夜跑恢复与完成凭证

- **[2026-09-20] 显式要求刷新仍会借旧audit报完成：底价12、成员10、180日内无基线，零写入却rc0。**
  做法：完成位同时核本轮候选/实际写入、skip/fail/provider待补及审计；dry-run仅预览。恢复消费者必须因rc2停止且不写成功状态。main整合只豁免计划明确的Hithink skip，保留“未更新”收据；不能所有skip都放行。两类撤保护均实际断言红、恢复同输入绿，正式回归已落。跨午夜日期门未删，见 `docs/handoffs/2026-09-20-nightly-refresh-resume.md`。

- **[2026-09-17] 股票事实补全，但已完成板块仍缺新增成员，质量门照样绿。**
  根因：stitch 按身份快照的 success 跳过，未反映行情输入变化；覆盖率/非空率不能证明依赖一致。
  做法：恢复入口在 staging 显式 `--include-completed`，复用原 writer 重建，再按日重算下游；抽查新增身份和板块合计/边际量。删刷新分支的变异 1F，恢复后 114P。不能外推为全链自动失效机制；详见 `docs/handoffs/2026-09-17-local-review-recovery.md`。

- **[2026-09-17] 旧数据树没有 local 被误读成机器不支持 local，装机计划被改 auto。**
  根因：代码能力、模板配置和 launchd 实际装载环境不是同一个事实源。
  做法：三态逐项核对，修配置只改目标键并保留 L2 根；local 的子模块也必须拒绝隐藏复盘会回退，不能只跳登录预检。

## 判官探针记录

- **[2026-09-16] 新诊断脚本把四个真实判官返回记成 provider error，calls=0。**
  根因：记录器用 `dataclasses.asdict(ModelTurn)` 深拷贝工具参数中的只读 mappingproxy，异常发生在记录追加前；原测试只覆盖字典回调，没有原生工具返回。
  做法：复用 `ModelTurn.to_dict()`，调用前先记尝试，失败保留异常类型；原生工具返回和异常路径各补回归。记录0不等于零外呼，旧四例不能算语义拒绝。见 `docs/handoffs/2026-09-16-e2-claim-rendering-and-judge-receipts.md`。

## 异步消息可见性

- **[2026-09-19] run已completed，报告按钮缺失，上一轮迟到加载还覆盖同会话追问。**
  根因：终态仲裁早于报告落盘；只保护会话切换，没保护同会话代际。做法：先观察writer活性再读产物，交付中保留刷新；排空SSE尾部，新提交使旧快照失效。未挪取消仲裁、不加超时；只适用当前单进程执行器。
- **[2026-09-19] 源码测试绿但构建令候选变脏；补构建物后全量又暴露测试线程泄漏。**
  做法：静态构建物纳入提交，新干净候选再验；复用672abcc5的三夹具wait-join修复，不改受害收据测试/生产关闭行为。旧e9脏构建、058全量1F照留；新收据只签自己的提交。

- **[2026-09-16] 全量绿后文档收尾再现三轮会话消息pending，定向复验也红。**
  根因：`_send` 只等run终态，却立即断言或让下一轮读取message；claim与revise是两次写（c50714f7已有契约），不是跨对象事务。
  做法：复用消息自身终态等待，保留断言/超时；用事件屏障固定窗口，禁用等待的变异1F、修复7P，不以反复重跑代替修复。新适配器桩首次漏必填字段被门禁抓住，补齐后才计绿。详见 `docs/handoffs/2026-09-16-release-merge-message-wait.md`。

## 视角画像

- **[2026-08-28] `review_patch` 整表回写把风远收口 HOW / 四表 / patch_history 盖成薄副本。**
  根因：`_save_profile` 把调用方手里的整份 dict 写盘。官方 `review_patch` 每次会重读，但批量脚本或更早 load 的对象一旦更薄，一次保存就丢人工字段。磁盘已经薄了救不回；挡的是「内存薄、磁盘厚」。
  做法：写前比磁盘做长度/`article_count` 棘轮，下降就 `ProfileRegressionError`；ingest/评审在副作用前再 `load_profile`。换措辞同长度放行。详见 `docs/handoffs/2026-08-28-fengyuan-spt-closeout.md`。

## CDP / Web 抓取

- **[2026-05-08] CDP eval 用 `--data-urlencode` 导致 "Uncaught" 错误。**
  根因：CDP 代理的 `/eval` 端点不对 body 做 URL decode，`--data-urlencode` 把表达式编码后代理无法解析。
  做法：用 `-X POST -d "expr=<原始JS>"`，不要用 `--data-urlencode`。Python 中直接拼 `f"expr={expr}".encode()`，不调 `urllib.parse.quote`。

- **[2026-05-08] fupanhui market data 页面 JS 环境损坏，eval 持续报 Uncaught。**
  根因：页面加载后某脚本抛未捕获异常，破坏全局执行上下文。即使是 `'hello'` 也报错。
  做法：新开标签页（`/new`）比 `navigate` 可靠；所有 eval 用 IIFE `(function(){...})()` 包裹 + try/catch。

- **[2026-05-08] Python f-string 中写 JS 代码，大括号 `{}` 冲突。**
  根因：JS 代码块和 JSON 对象花括号与 Python f-string 语法冲突。
  做法：复杂 JS 用字符串拼接或 `.format()`，不用 f-string。

## 飞书写入

- **[2026-05-08] 写入后不检查空字段，导致 45/140 条记录缺行业占比数据。**
  根因：早期抓取只解析了页面部分数据，行业3/占比3 被遗漏但未发现。
  做法：写入后立即运行 `verify_and_patch.py` 检查关键字段，白名单字段为空则定向重抓。

- **[2026-05-08] `均线上方家数占比` 字段不在飞书表中，但被加入了检查白名单。**
  根因：表结构和代码中的字段列表不同步。
  做法：检查白名单中的字段必须在飞书表中实际存在，写入前验证字段名。

## [kb] 结构化文件的行级三方合并

- **[2026-08-14] entity YAML 修复 PR 与历史重号 PR 对同一页 CONFLICTING，不能按旧号全局替换。**
  根因：Git 三方合并按「行」比，不管 YAML 语义。一边把重复 `log:` 收成一块，一边在悬挂的第二块里改号，两边都改同一段。旧号本身在撞号（`#1647` 对应多个新号），全局替换会改错。
  做法：结构听语义修复（单键 YAML），号按 **log 文案** 对齐重号映射，不能按旧号→新号字典替换。详见 kb #338 接替 #328。

- **[2026-08-14] 解冲突时「哪边 YAML 合法就听哪边」，把上游 writer 的丢数据固化。**
  根因：#317 的 writer 重演了同一个整行覆写 bug，长光华芯 log 9→3、长电科技 25→2——main 侧 YAML **合法但不完整**。合法性是语法判据，完整性要比条目。
  做法：解冲突前对每页比一次条目数/条目集，main 是超集才可直接听 main，否则取并集（本线时序为基序，文案匹配的号听 main，新条目追加末尾）。

- **[2026-08-14] 自写的「零丢失」校验脚本三次给出假通过。**
  根因：①用 `git diff -- "$f"` 传 git 转义引号路径，两边都匹配不到文件、双双为空被判「相同」；②只用 `re.findall(r'"([^"]*)"')` 抓条目，漏掉不带引号的块序列项（`- raw/xxx.json`），误报丢失；③`re.match(r'^---\n(.*?)\n---\n')` 匹配不上就 `continue`，于是 4 个闭合分隔符畸形的页从两轮「0 失败」里溜掉。
  做法：路径一律 `git -c core.quotePath=false`；损坏侧用文本兜底解析、干净侧用真 YAML 解析；**「解析不了」必须单列为一类失败，不能 `continue`**——这三次假通过里有两次是「跳过被当成通过」。

- **[2026-08-14] 闸门报 0 错，可能是因为它跳过了坏数据。**
  kb 4 个 entity 页的 frontmatter 闭合 `---` 紧贴在末行行尾（`...]---`），仓内所有 `split_frontmatter` 都按「独占一行的 `---`」定位，定位不到就返回「无 frontmatter」，于是 sources/log/tickers 对入库与图谱全部隐形，而 `ingest check` 一路 0 错。
  做法：闸门的「通过」要能区分「检查过且合格」和「没检查」。凡是 parser 有 early-return/skip 分支的，都要单独统计 skip 数并纳入判定。

- **[2026-08-14] rebase 到已瘦身的 #317 时，`kb-relations-union` 把旧 `evidence_index` 近 5800 条复活。**
  根因：merge driver 按 append-only 假设，以 theirs 列表为骨架不删 base 已有条目。#317 合 main 后 items 25165→19437，#335 还带着旧胖索引；并集得到 25312，而本线真实增量只有 137。
  做法：对方分支有过删除时，不要用 union 骨架。以**当前目标分支为底**，只加「源分支相对共同祖先的增量」。详见 kb #339 接替 #335。

## [kb] log 撞号与图谱口径（对抗性审查）

- **[2026-08-13] 取号只看 log 标题，看不见页面预留号，IMA #3770–#3787 与 miracle 补档撞号。**
  根因：`max(log 标题)` 扫不到只写在 frontmatter/index 的预占号；多写者共用序列时，预占未落表是经典撞号源。
  做法：取号必须计入「页面预留号」；定号前 `git fetch` 扫全部远端。详见 kb #329 / `docs/handoffs/2026-08-13-log-collision-fix.md`。

- **[2026-08-13] CI 放行 token 扫 `HEAD` 全历史，被 main 祖先的 token 污染，之后每个 PR 都误跳过守卫。**
  根因：放行口扫的是整段历史，不是本 PR 独有提交。
  做法：CI 放行 token 只扫 `base..head`（PR 独有提交）。#330 无放行 token、走守卫正常路径才算守卫工作实证。

- **[2026-08-13] 把丢数据洗成口径：页面声称写了图谱，实际丢失，却补 `cascade: none`。**
  根因：`cascade: none` 只该用于设计上不写的批次；声称写了的必须真在。
  做法：设计上不写 → 才标 `cascade: none`；页面声称 graph_only 等已写的必须补数据，不能用声明掩盖丢失。

- **[2026-08-13] 往 curated 节点补弱来源时直接调 `update_entity_exposures`，会整体覆写既有节点。**
  根因：writer 对已有节点是整节点覆写，不是追加。
  做法：补弱来源走最小增量（只追加 `sources[]`），别直接调会整体覆写的 writer。#330 按 0616 同形状补 5 条即此法。

## [kb] 卖方研报 / entity-delta 入库

- **[2026-06-28] 验证 entity-delta/concept-delta 路由时用 `writer < payload.json | grep ...` 管道，导致 writer 被重复执行、内容重复追加。**
  根因：shell 管道会**完整执行**左侧的 writer（含写盘副作用），再把 stdout 喂给 grep；以为"只是看一眼"实际又跑了一遍。叠加先前已正常跑过一次，结果 entity 页「## 高信度研究线索」多段重复、source 索引「## 已更新实体」追加两次、新建卡（甬矽电子.md）被创建多次。
  做法：delta writer **只跑一次**，stdout 重定向到文件（`writer < payload.json > /tmp/out.json 2>&1`）；验证阶段**只读已写好的 entity/concept/source 文件与 relations**，绝不再调用 writer。误跑后用 `git checkout -- wiki/concepts wiki/entities wiki/relations` 回滚 + 手动截断 source 索引追加段，再干净重跑。

- **[2026-06-28] 同日两批卖研入库，第二批险些覆盖第一批产物。**
  根因：sources/synthesis/raw 文件名按日期命名，同日第二批会与第一批同名。
  做法：batch 隔离——第二批文件名加 `晚卖研汇2_`（raw/sources）/`-batch2`（synthesis）后缀；log 用独立 `#NNN` 条目；index.md 各处并列登记不覆盖。

- **[2026-06-28] 内置 git_create_pr 对 linxiaoqi5111-del 仓返回 404 Not Found。**
  根因：内置 git 工具走会话默认账号（noah-smith439374），无该私有仓权限。
  做法：PR 用 `GITHUB_PAT_LINXIAOQI5111` 走 GitHub REST API（`POST /repos/.../pulls`）创建。

## [kb] 年报 baseline 入库

- **[2026-06-23] 批量年报入库共用 batch source note 导致追溯断裂。**
  根因：`entity_baseline_writer.py` 的 `write_updates()` 对整批使用同一个 `source_name`（如 "年报 baseline batch 2026-06-23"），所有公司的 evidence 都指向这个 batch note，但 batch note 的 `company` 字段只记录了最后一家。
  做法：新增 `per_company_source_name()` 函数，年报类型时自动拆为 `<公司> <报告名> baseline <日期>` 独立 source note。batch note 只作批次清单，不作 evidence source。

- **[2026-06-23] entity 页 key_data 和一句话定位留空，baseline 对后续分析帮助弱。**
  根因：writer 不自动从 raw JSON 提取营收/净利润等财务数据，也不从 industry+main_business 生成定位。
  做法：新增 `extract_key_data_from_raw()` 自动抽取营收+归属净利润；新增 `generate_one_liner()` 从 main_business+industry 生成朴素定位。

- **[2026-06-23] 完成闸门缺少 source 追溯审计步骤。**
  根因：`check_relations_integrity.py` 只检查 JSON 格式完整性，不验证 source note 的公司归属和 raw_traces 指向。
  做法：新增 `scripts/audit_missing_evidence_sources.py` 作为第 7 步闸门，检查每个 entity 的 source note 存在性、company 字段一致性、raw_traces 可达性。

- **[2026-06-23] 年报 batch 4-5：Rule 6 双层保护 + 语义 QA + manifest 格式。**
  错误：①Rule 6 只保护 entity 正文，relations 里 `ima_stock_logic` 等高价值记录被 baseline 覆盖降级（盘江股份→煤炭）；②子串验证通过但语义错误（环保政策当主营、目录碎片当产品、保荐机构文本挂黄金概念）；③manifest 顶层 list 导致 writer `--preflight` 报 AttributeError；④重建时旧 entity 文件的脏 baseline section 被 Rule 6 "保护"。
  根因：Rule 6 只做了 entity markdown 单层保护；缺少 relations 层的 update_type 检查；语义验证完全依赖子串匹配无人工 QA；manifest 格式未标准化。
  做法：`knowledge_graph.py` 扩展保护为"任何非 baseline update_type 都不覆盖"；SKILL.md 从 8 条扩展到 11+S4+O2（新增 Rule 6 双层保护/Rule 8 manifest 格式/Rule 9 语义 QA/Rule 10 回归检查/S1-S4 应该规则/O1-O2 可选规则）；重建前必须删除新 entity 文件再重跑 writer。

- **[2026-06-23] 年报 batch 2 质量修复：5 类问题沉淀初始 8 条防护规则。**
  错误：①已有 F10 baseline 被低质量年报 OCR 覆盖（宁德时代主营变成表格噪声）；②正则扫全文误抽财务数据（宁波银行营收 7.20万元）；③`source_date` 从 PDF 误抽出未来日期；④修页面忘了同步修 relations JSON 导致 agent 结构化召回脏数据；⑤文件名冒号/下划线不一致导致 source 断链。
  根因：`extract_key_data_from_raw` 用正则扫全文无验证；`entity_baseline_writer` 无条件覆盖已有高质量 baseline；修复流程只看页面不看 relations。
  做法：`extract_key_data_from_raw` 默认关闭（`AUTO_KEY_DATA=1` 才启用）；SKILL.md 新增"年报 baseline 质量防护规则"8 条（relations 同步修 / 安全文件名 / source_date 分离 / OCR 噪声词过滤 / 已有 baseline 不覆盖 / 验收看内容不只看退出码 / 批量抽样）。

## 批量操作

- **[2026-05-08] 日历选择器月份导航最大迭代次数不够。**
  根因：历史日期可能跨多年，nav_to_month 的 max retries 不够。
  做法：至少 20 次迭代（覆盖 2 年范围），从当前月份计算差值，选择正确方向。

- **[2026-05-08] 批量脚本中第一次日期切换失败后，所有后续均失败。**
  根因：失败后的恢复逻辑不足，页面可能卡在中间状态。
  做法：每次切换失败后关闭并新开标签页，重置状态。

## 复盘流程

- **[2026-05-08] 周均线和偏离度临时获取失败，但之后某步补全了。**
  根因：market data 页面间歇性 JS 错误，部分时候能成功但也可能静默失败。
  做法：Step 3.5 必须验证返回值非空，空则重试或新开标签页重试，不能无声跳过。

- **[2026-05-11] verify_and_patch.py 只检查周均线/偏离度，行业聚散字段空缺被漏检。**
  根因：`PATCHABLE_FIELDS` 硬编码只有 `周均线` 和 `偏离度`，缺少 `前三占比`、`集中度`、`行业1-3`、`占比1-3`。
  做法：verify 脚本的 PATCHABLE_FIELDS 应覆盖所有关键业务字段；写入后人工抽查飞书表全字段，不能只信脚本报绿。

- **[2026-05-12] 飞书日期年份前缀写错（25-05-12 应为 26-05-12）。**
  根因：从页面看到 `05-12` 后直接拼了 `25-` 前缀，没有确认实际年份。
  做法：从页面日历/日期面板/URL 确认完整年份，用 `str(year)[-2:]` 截取前缀。不能假设年份等于当前年份——用户可能抓历史数据。

## 概念入库

- **[2026-08-25] IMA DeepDive 必须 Copilot 15章 → md → 入库桥 → 人工 plan。** 搜标题、有 md 直接 writer、把 queue 里几十个零部件名建成概念页，都是错路。规范只在知识库仓 `skills/concept-ingest/SKILL.md`，提示词 `references/ima-deepdive-prompt.md`。
- **[2026-05-24] YAML frontmatter 中 wikilink 和中文不加引号导致 Obsidian 渲染异常。**
  根因：`sources: [[研报名]]` 中的 `[[` 被 YAML 解析为数组嵌套语法，`tags: [中文tag]` 中的中文无引号也可能解析失败。frontmatter 解析失败后 Obsidian 回退渲染整个文件。
  做法：所有 YAML 字符串值统一用双引号包裹——`title: "中文标题"`、`tags: ["中文tag"]`、`sources: ["[[wikilink]]"]`。concept_writer.py 输出已自动处理，手动编辑时需注意。

## Skill 结构

- **[2026-05-11] up-line skill 只有 README.md 没有 SKILL.md，不会被自动发现。**
  根因：Claude Code skill 系统只识别 `SKILL.md`，`README.md` 不算。
  做法：每个 skill 目录必须有 `SKILL.md`（含 YAML frontmatter），README 可作为补充文档保留。

## fupanhui API

- **[2026-05-13] fupanhui.com 有内部 REST API，可替代页面 DOM 抓取。**
  发现：通过 `performance.getEntriesByType('resource')` 发现前端调用的 API 端点。用浏览器内 XHR 调用自动携带 session cookie，无需 API key。
  适用：limit-advance（已改造）、market-overview（待改造）、研报入库。
  关键端点：`/api/v1/client/reviews/market`、`/api/v1/client/limit/ladder`、`/api/v1/client/calendar/month`、`/api/v1/client/reports/list`。

- **[2026-05-13] fupanhui API 字段名不等于直觉猜测。**
  根因：latest-date API 返回 `latest_date` 非 `trade_date`；calendar API 返回 `trade_date` 非 `date`。
  做法：先用小数据量打印 API 响应的 keys，确认字段名后再写逻辑。

- **[2026-05-13] 均线上方家数占比不需要抓取。**
  根因：用户确认复盘流程中不需要此字段。
  做法：verify_and_patch.py 和复盘流程均跳过此字段。

## UP 线计算

- **[2026-05-20] IFIND_DIR 路径因 symlink 错误解析。**
  根因：`shared/` 在 5月12日变为指向 `~/.claude/shared` 的符号链接。`Path(__file__).resolve()` 跟随 symlink 后，`IFIND_DIR` 变成 `/Users/lbq/.claude/skills/ifind`（不存在），iFinD 调用静默失败。
  做法：去掉 `.resolve()`，用 `Path(__file__).parent` 即可。其他引用 `shared/` 的脚本也要检查是否有同样问题。

- **[2026-05-20] iFinD `get_stock_info` 不再返回 MA/STD 数据。**
  根因：iFinD MCP 服务端工具分配变更，MA/STD 等技术指标现在走 `get_stock_performance`。
  做法：`feishu_utils.py` 的 `ifind_query()` 已改为 `get_stock_performance`。其他 skill 如需技术指标数据，确认工具名是否匹配。

- **[2026-05-20] UP 线偏离度算错（26.91% vs 预期 32.5%）。**
  根因：MA 和 STD 分开查询，iFinD 返回不同日期的数据（MA 取 5/19、STD 取 5/20），`parse_md_table` 保留每个查询的最后出现值导致日期不一致。另外用户公式用 `H`（最高价），最终确认用户决定用收盘价。
  做法：MA+STD 合并为单次查询（`"XX的MA简单移动平均和STD标准差，周期26日"`），用 `_parse_combined()` 解析双列表格，确保同日期。用当天数据（非上一交易日）计算 UP。

- **[2026-05-20] 飞书日期前缀再次写错（05-19 应为 26-05-19）。**
  根因：与 5/12 同一 bug，复盘子 agent 写入时直接用了 API 返回的 `2026-05-19` 格式转 `05-19`，丢失了 `26-` 前缀。
  做法：复盘流程写入前必须统一转换 `YYYY-MM-DD` → `YY-MM-DD`，用 `str(year)[-2:]` 截取。写入前打印日期值确认。

- **[2026-05-20] 每日指标表格式不一致（"亿"后缀、缺失%和+号）。**
  根因：不同 session 写入时格式不统一——有的写了"亿"后缀，有的百分数字段漏了 `%`，正数缺 `+` 号。148 条记录中有 6 条格式异常。
  做法：写入每日指标时，所有百分比字段统一带 `%`，正数带 `+`，成交额和 20 日均不带"亿"。格式规范见 `market-overview/references/feishu_write.md`。

## 板块边际量

- **[2026-05-21] 电子表格插入列导致数据混乱，用户反馈不要移位。**
  根因：sector-data 写电子表格时，试图把新日期插入 B 列并把现有列右移，打乱了用户的列序。
  做法：始终写到最后一列（最右侧空列），列排序由用户手动完成，不要自动插入移位。

- **[2026-05-22] sector-data 条件格式公式引用用 `$A1` 不是 `$A2`。**
  根因：飞书电子表格条件格式中，即使应用范围从第 2 行开始，公式引用也从 `$A1` 开始。
  做法：条件格式公式统一用 `$A1` 引用板块名。

- **[2026-05-21] fupanhui sector-cycle kline API 偶尔返回 502 Bad Gateway。**
  根因：后端临时过载，同一请求稍后重试即可正常返回。
  做法：遇到 502 时 sleep 2s 重试（最多 3 次），通常第二次即可恢复。不要因此放弃改用 sectors/search 的 strength 字段（不是成交额）。

## 飞书 bot 召回（dream-loop 提炼）

> 以下条目由 dream-loop 推理半从 transcript digest 自动提炼，标注「待人工复核」者为候选。

- **[2026-06-17] 同一题材「液冷」当晚连续 6 次查询返回 `召回=FAIL`（图谱命中 0 概念 / 0 公司暴露），约一小时后同一查询无任何改动地变为 `召回=PASS`（图谱命中 5 概念 / 12 公司暴露）。** _(候选，待人工复核)_
  根因（从 transcript 推断，待人工确认）：FAIL 时不只是「当日盘面候选未命中」，连声称「仅基于知识图谱」的回退也返回 0 概念——说明此刻盘面/图谱索引尚未就绪（盘面=—）；待 2026-06-16 盘面候选就绪后（盘面=2026-06-16）召回立即恢复。即「数据/索引未加载」被对外呈现成了「题材无命中」。
  做法：① 对液冷这类已知有图谱覆盖的题材，若出现 `召回=FAIL 且 图谱命中 0`，应优先判为「盘面/索引未就绪」而非「题材无价值」，待当日盘面候选 ingest 完成后再重查；② bot 侧把「盘面候选未就绪 / 图谱索引为空」与「题材确无命中」区分为不同状态（如 `召回=NOT_READY` vs `FAIL`），避免把数据时效问题误报成无命中，误导判断。
  依据：`raw/transcripts/digest-2026-06-17.md` 22:18–22:58（液冷 FAIL×6）→ 23:08（液冷 PASS）；对照 23:28「光模块」为 `召回=WARN`（盘面在、题材未触发但图谱命中 6 概念 / 12 公司 / 证据 8 条），与液冷 FAIL 的 0 命中形成反差，进一步指向「索引未就绪」而非题材本身无内容。

## Agent 执行纪律 / 确定性脚本执行

> 适用：拿到含完整真值表/字段口径/writer 行为的 handoff 或 spec 后的 ingest、回填、批量入库类任务。与 `AGENTS.md`「Agent Token Discipline」红线一致。

- **[2026-06-19] 拿到确定性 handoff（已含完整路由真值表 + writer/校验逻辑 + log_id 处置）后，仍把 `entity_delta_writer.py`/`check_relations_integrity.py`/`knowledge_graph.py` 整文件重新通读一遍。**
  根因：把「确定性脚本执行」误判成「探索/理解项目」。handoff 已把所有路由规则、字段枚举、writer 行为、log_id 优先级写死，无需再读源码建立理解；但默认行为习惯性「先把基础设施读懂再动手」。
  做法：handoff/spec 已是确定性真值表时，直接按步执行；只有当某行字段判断或某条分支即将被用到时，才用一行 `rg`/`grep -n -A` 点查那一处，绝不预读整文件。能用 frontmatter/manifest/精确命中解决就不读正文。

- **[2026-06-19] 为「验证早已知道的状态」写了一堆临时探查脚本（`recon.py`…`recon9.py`、`probe_*.py`）。**
  根因：用「写脚本求证」代替「按 handoff 既定结论执行」，把 handoff 已给定的事实（next log_id、已建的 7 个实体、待补字段缺口）又用脚本重新跑一遍。
  做法：不写探查脚本验证 handoff 已给的结论。需确认单点事实时用一条 shell（`ls`/精确 `rg`/`python3 -c`），用完即弃，绝不在仓库/家目录留 `recon*/probe*` 垃圾文件。

- **[2026-06-19] 「先把所有东西读完再动手」，迟迟未入库，被用户两次点名「为什么处理那么慢 / 没按脚本执行」。**
  根因：把「理解」和「执行」串行化——先求 100% 读懂再开始第一步，而非边执行边按需点查。确定性任务下这是纯浪费、且拖慢首步交付。
  做法：确定性流程一律「立即执行 + 按需点查」。不依赖任何源码理解就能起步的步骤（如先建 source 页）先做掉；后续每步只在真正用到某机制时点查该机制那几行。首步交付优先于全局理解。
- [kb] 2026-08-13 用脚本往 markdown 固定小节追加一行时，三元表达式拼接漏了尾段（text[:nl]+line 忘接 text[nl:]），把「交接记录」23 条历史全删 → 根因：就地字符串手术无断言保护，diff 也没看就 commit → 正确做法：①逐行遍历插入而非切片拼接；②写后断言旧内容探针仍在（>=3 个随机旧条目）；③commit 前必看 diff --stat，插入型改动出现 deletions 即中止。push 被拒反而救了一命——远端保护是最后防线，不是第一道。
- [kb] [2026-07-02] 年报披露日锚点抽取 4/20 落空 → 部分年报无内控披露/审计报告日锚点段落 → 兜底顺位加「财务报表业经公司董事会于X年X月X日批准报出/董事会批准报送日期」；另注意「资产负债表日后事项」中的日期会造成误抽（三峡能源 2026-01-19 误判），抽取后需 sanity check 日期是否落在 3-6 月披露季。

## Agent Runtime / 预算诊断（2026-08-08）

- **[2026-08-08] 按 handoff 的诊断（"档位表按更快的 provider 标定，重标定它"）准备动手，差一步就改错了地方。**
  根因：诊断只看了 `ResearchPolicy` 档位表（quick 30 / standard 90 / deep 240），没算实际生效值。真实链路是
  `effective_timeout = min(tier_total, turn − verification_reserve) = min(tier_total, 80)`——`80` 恒为较小者，
  **档位表根本不参与首轮**。探针实测：standard 从 90 调到 180、300，首轮预算恒为 26.67s，一秒不变。
  真正的绞索在 `episode_factory.py:360` 的 `reserve = min(60, 80 × 2/3) = 53.33`，于是首轮 `min(75, 80−53.33) = 26.67s`，
  而该 provider P50=28s——**首轮预算连中位数都不到**。
  做法：改预算前先用真实常量算一遍生效值，并与观测值对账。**数字对不上任何一条预算边界（28s ≠ 25 ≠ 70 ≠ 75）就是归因错层的信号**，
  此时应停下读盘上真实 run（`continuous-episode.json` 的 `events[].payload`），而不是继续调那个看起来最像的旋钮。
  前两次修（换模型、加回合预算 120→300）都失败，因为都假定了"档位太小"。

- **[2026-08-08] 在 `ResearchDeadline` 上加新方法 `opening_stage_timeout()`，三条护栏测试立刻 `AttributeError`。**
  根因：`context.deadline` 是**鸭子类型注入点**，测试替身（`_ScriptedDeadline` / `_LateRecoveryDeadline`）只实现
  `stage_timeout` / `synthesis_timeout` / `remaining` / `expired` 四个方法。给真实类加方法，替身全炸。
  做法：改这类注入点的行为时，只用替身已有的接口；需要读可选字段走 `getattr(obj, name, default)`。
  本次最终实现放在调用方（`agent_episode._opening_planning_timeout`），一个新方法都没往 `ResearchDeadline` 上加。
  另一半教训：那条 `test_planning_turn_cannot_spend_the_reserved_finalization_budget` 断言 `calls[0]["timeout"] <= 11.0`，
  正是被改掉的语义——**没有改测试去迁就实现**，而是把"整段不扣 reserve"收窄成"只借超出合成地板（20s）的余量"，
  于是生产 26.67→60s（≥P95 50s），而该测试（reserve=4，借不到）与四种其他配置一秒未变。

- **[2026-08-08] 提交代码后读 `/api/health`，`code_matches_repo` 仍报 `True`，据此以为快照已含改动。**
  根因：`runtime_provenance.py:113-115` docstring 明写指纹 *"called once per process (`create_app`) and the result is
  reused by every health response"*——**启动时算一次，之后所有 health 复用**。仓库前进了，读数不会变。
  讽刺的是同文件 :100-111 正是在讲"版本号会在最可能出错的时刻前进"这个 bug 类，缓存让它换了个形式重现。
  做法：判断快照新旧只能靠 `scripts/deploy_workbench_runtime.sh` 里那次**现算**（它 `cd` 到快照再算，并先断言
  "加载树必须在快照内"），或直接比对两棵树的文件 hash。**长驻进程的自述字段一律视为启动时快照，不是当前状态。**

- **[2026-09-12] 821 字材料题被判成 disclosure_scan 并返回 183 字节存根——`answer_status=complete`、`warnings=[]`、`llm.used=false`，静默成功；修了两道闸才算修完。**
  根因（两层）：①细粒度词面路由的判据是「几个提示词同时出现」的去空白全文无锚点子串匹配，自带 examples
  全部 8–21 字，却套在任意长度输入上——「行业」@64（小节标题）+「公告」@72（材料正文）+「哪些」@437
  （第 1 题题干）在互不相干的段落 AND 成立，0.98 置信度命中。②同一个匹配器 `is_disclosure_scan_query`
  有两个调用点（`turn_controller._fine_grained_route_row` 与 `query_understanding.understand_query`），
  第一版修复只闸了前者，`decide_turn` 端到端仍经 envelope 兼底分支判成 disclosure_scan——**验证钉在
  被改的那一层，没钉端到端**。更深的形态教训：`answer_synthesis` 的 `status="validated"` 与
  `diagnostic.state="not_requested"` 同时为真——「校验通过」被用来描述一件根本没发生的事，只看 status
  的仪表永远绿。评测语料 24 道冻结题全是短问句、一题没命中，靠语料扫不出这类缺陷。
  做法：词面路由一律加长度闸（阈值 SSOT `route_table.FINE_GRAINED_ROUTE_MAX_CHARS=160`，去空白后），
  闸下在**每个**调用点；失败方向设计成安全的（超长退回正常 lane 由模型判）。**改完匹配器先 grep 它的全部
  调用点，验证钉 `decide_turn` 端到端**；事故题逐字节钉进
  `intelligence/tests/test_fine_grained_route_length_gate.py`（SHA 断言防「回归测试悄悄测了别的题」）。
  事故全记录 `docs/learning/knevo-distill/recheck/2026-09-12-t23-nogrok/README.md`。

- **[2026-08-11] `check_inflight_stale.sh` 报「交接过期」，证据是 3 个 moneyflow 脏文件——而本分支 8 个提交一次都没碰过它们。**
  根因：判据是「代码路径前缀 + mtime 比文档新」，即**拿文件系统事实推断版本控制事实**。未提交改动在 git 里
  **没有分支归属**，它只属于这棵树；本仓主检出树常年多 agent 共用，这类误报是必然而非偶然。
  更隐蔽的是它这次**结论恰好是对的**（交接确实过期，因为分支在文档之后又提交了 2 次），只是理由完全不相干——
  巧合是那批脏文件的 mtime 比真正的最后一次提交只晚 2 秒。**"报警响了且事实成立" 不等于 "判据成立"，
  验证门禁必须查它引用的证据，不能只看结论对不对。**
  做法：改成两级判据——一级用 `<base>..HEAD` 的提交时间（提交自带分支归属，共树污染不进来）；
  二级把脏文件与 `git diff --name-only <base>...HEAD` 求交集后再比 mtime。基线解析不了时退回宽判据但
  **在告警里声明「本次未做归属过滤」**。误报的代价不是烦人而是失效：喊过狼来了的门禁，下次没人看。

- **[2026-08-11] 用 `grep '^## ' file | sort | uniq -c` 数交接文档的小节，6 个不同的中文小节被合并成 1 个、计数报 5。**
  根因：macOS 的 BSD `sort`/`uniq` 在 **UTF-8 locale 下按 collation 比较**，CJK 表意文字主权重相同 →
  **不同的中文行被判为相等**。`LC_ALL=C`（按字节比）才正确；`LC_ALL=en_US.UTF-8` 与不设一样错。
  做法：**任何对中文文本的 `sort`/`uniq`/去重统计一律加 `LC_ALL=C`**。这条可迁移到所有 macOS 上的中文日志/清单统计。
  元教训：当聚合结果与直接 `grep -n` 的原始行对不上时，先怀疑量具而不是数据——本轮正是靠"两个读数打架"才发现的。

- **[2026-08-11] 给注入脚本加了按小节重排的 awk，一份「没有任何 `## ` 小节」的文档注入结果为空，退出码 0、无报错。**
  根因：awk 用**未初始化变量**做数组下标时，下标是空串 `""` 而不是数字 `0`。首个 `## ` 之前的正文写进 `body[""]`，
  END 里 `for (i=0; ...)` 读的是 `body["0"]`——两个不同的格子。真实文档因此也悄悄丢了标题行和「更新：日期」行。
  做法：`BEGIN { sec = 0 }` 显式初始化。凡是「累加到 arr[var] 再按数字下标遍历」的 awk，都要先给 var 赋数字初值。
  这个坑的形状与本文件已记的另外三条一致：**失败方式是静默出空而非报错**，只有构造边界样本才能抓到。

- **[2026-08-11] 给 stale 门禁加了「本分支提交晚于交接文档就报警」的一级判据，写完交接、提交，门禁当场又报警——死循环。**
  根因：**提交交接文档这个动作本身产生了一个比文档 mtime 更新的提交**（`git commit` 不改文件 mtime）。
  于是「写交接」永远无法让门禁满意，写了也没用。这是本文件已记的「活文档先写未提交再提交 → 提交动作让文档
  当场失效」在门禁侧的重现——同一个形状，换了个位置。
  做法：一级判据用 `git log ... -- ':(exclude)<交接文档路径>'` **排除只动交接文档的提交**（那是交接行为本身，
  不是新干的活）；文档时间取 `max(工作区 mtime, 最后一次改动它的提交时间)`，让「文档与代码写在同一提交里」
  也成立。**可迁移原则：任何「产物必须跟上源」的门禁，都要把「更新产物」这个动作本身排除在「源变动」之外，
  否则门禁自噬。** 同类：lint 自动修复触发 lint、changelog 门禁、格式化 hook。
  抓到它靠的是**闭环验证**——修完不是跑一遍通过就完事，而是把门禁放回它本该静默的真实状态里再跑一次。

- **[2026-08-11] 对比分支与 main 的测试失败集合，`diff` 报「完全一致，零回归」——两个文件其实都是空的。**
  根因：把文件列表放进变量再 `$FILES` 传给 pytest，词分割没发生，整串被当成一个路径，pytest 报
  `no tests ran`（退出码 4）。`grep '^FAILED'` 于是两侧都抓到 0 行，`diff` 自然「一致」。
  **空对空的差分永远通过，且和真正的「一致」长得一模一样。**
  做法：任何 A/B 差分**先断言两侧非空**再比内容（`[ $(wc -l < a) -gt 0 ]`），并把「两侧各 N 条」
  打进结论里。同类形状：grep 管道对账、集合比对、快照 diff——**只报「无差异」而不报「比了多少条」的
  对账结果不可采信**。这条与本文件已记的「量具被自己污染的输出骗了」同族。

- **[2026-08-11] 验证「改了代码门禁会不会重新报警」时用 `touch file`，门禁静默，差点判成「门禁被修哑了」的回归。**
  根因：`touch` 只改 mtime，**不产生 git 改动**，而门禁的二级判据读的是 `git status --porcelain`。
  测试动作和被测判据读的不是同一个量——测试本身无效，不是被测物有问题。
  做法：构造反例时先确认「这个动作真的会被判据看见」（这里应当真改文件内容，改完 `git checkout --` 还原）。
  推广：**用 mtime 造脏、用 touch 模拟改动、用 sleep 模拟并发**，都属于「造的假象不在判据的观测面上」。

- **[2026-08-11] 15 条「常年失败」的测试里，11 条的根因是测试直连了真人数据——而且在**写**。**
  根因：本机为跨机同步真实设了 `FORESIGHT_USERS_DIR`（指向云同步 vault）、`FORESIGHT_USER`（真人 id）、
  `SUBCONSCIOUS_VAULT=...`，而 `userspace.users_dir()` / `resolve_user_id()` 是**运行时**读 env 的（这是对的，
  跨机同步就靠它）。不显式指定用户的测试于是落到真人目录：断言 `len(buf)==1` 实际读到 **913** 条真实会话缓冲；
  断言 judgments 文件不存在实际为 True。**更糟的是写**：实测 测试用的 `tester/`、`alice/` 两个用户目录 被测试创建，
  真人目录 mtime 被改动，而那是个云同步 vault——测试垃圾会同步到另一台机器。
  做法：conftest 加 autouse 夹具默认 `delenv` 这三个变量，让「密封」成为默认；需要的测试自己 `monkeypatch.setenv`
  设回来（`test_workbench_api.py` 20 多处早就是这个正确写法）。实测 15→0 失败，且全量跑完真实目录**指纹零变化**。
  **元教训：长期红着的测试套件不是「知道有几个坏的」，是掩体。** 这 11 条数据污染之所以活了很久，
  正因为它们混在「反正一直有 15 个红的」里没人分辨。红的数量必须归零或全部转成带理由的 skip，
  否则新出现的真回归会被同一片红淹掉。

- **[2026-08-11] `pytest.approx(30.0)` 断言一个从活时钟算出来的值，单独跑 5/5 失败、全量跑反而过。**
  根因：`pytest.approx` 默认是**相对**容差 `rel=1e-6`——对 30.0 就是 ±3e-5。而该值来自
  `ResearchDeadline.from_timeout(60)` 的实时预算，真实流逝的几十微秒会被减掉（实测 29.99995141645195，差 4.9e-5）。
  于是**机器忙闲决定红绿**：全量跑时时序恰好落进容差，单独跑就必红。测试注释明写「断言规则不是数字」，
  但默认相对容差把它悄悄变回了断言精确值。
  做法：对时钟/IO 派生的量用**绝对容差** `pytest.approx(x, abs=0.05)`，宽度按「真回归会挪多少」定
  （这里真回归是 15 vs 30 秒级，50ms 足够紧）。改后 10/10 通过，人为压满 CPU 也通过。

- **[2026-08-11] 测试 `monkeypatch.setattr(acceptance, "latest_run", ...)` 完全没生效，因为 cmd_board 早就不调它了。**
  根因：生产码重构成 `select_latest_case_runs(RUNS_DIR, ...)`（直接扫目录），**mock 点随之失效成了空操作**，
  测试于是读真实的 runs 目录——目录里运行记录从 1 份长到 20 份，断言随之漂移。
  失败信息看起来像「看板渲染坏了」，实际是测试没钉住输入。
  做法：mock 点要跟着实现走；更稳的是**走公开接口传参**（这里 `Namespace(run=...)`）而不是打补丁内部函数。
  同批还改了一条过度具体的断言：钉死整行表头 `| 题 | 组 | 运行 | 真值 | 体验 |`，板子加了七列就红，
  而它真正要守的不变量（三轴各自独立成列）完好无损。**过度具体的断言会在无关变更上报警，把真回归淹掉。**

- **[2026-08-12] 按 `git status --porcelain` 判「工作区干净」筛出 12 棵可删的 worktree，逐项复核时 7 棵被拦下。**
  根因：`git status` 的「干净」是**相对 gitignore 而言的干净**，不带 `--ignored` 时看不见被忽略的文件。
  那 7 棵各有 1~7 个忽略项（`__pycache__`、`.pytest_cache`、`.DS_Store`，以及最要紧的
  `.ingest-transactions/` ——ingest 的回滚备份，160 个里 113 个的内容在 git 对象库里根本不存在，
  是唯一副本）。若信了第一次快照直接 `git worktree remove`，这些会随目录一起消失且不可恢复。
  做法：**凡是要删目录的判据（worktree / 临时检出 / 容器卷），必须用 `git status --porcelain --ignored`**；
  判「要不要提交」才用默认。两个问题问的不是同一件事。
  **可迁移原则：判据的作用域必须匹配动作的作用域。** 删除动作影响整个目录，判据却只覆盖 git 跟踪面
  ——差一档就漏。这与 `10_knowledge/gate-assertion-granularity.md` 是同一个形状。
  另一半：**不要信几分钟前的快照**。本次是在执行循环里对每一棵重新跑三条件（已并入 / 脏 0 / 忽略 0）
  才抓到的；如果沿用先前算好的清单，复核这一步根本不会发生。

- **[2026-08-12] 「留还是删」常常是伪二选一——先把可恢复部分和唯一部分拆开量。**
  场景：3 棵已合并 worktree 共 3.3 GB，里面既有能从 git 完整恢复的检出（1.84 GB），
  也有不在 git 里的事务备份（1.49 GB）。直接删会丢唯一数据，全留则浪费。
  做法：**归档唯一部分 + 删可恢复部分**。那批备份是同几个 relation JSON 的连续快照，
  相似度极高，`tar.gz` 压到 216 MB（7 倍），于是 3.3 GB → 216 MB，一份唯一数据都没丢。
  两条配套纪律：归档后**逐文件比对内容哈希**再删源（只对文件数会漏内容损坏）；
  归档目录里放一份 README 写清「这是什么 / 为什么留 / 什么时候可以删」，
  否则三个月后它自己就变成新的谜团。

## 能力盘点 / 负面断言的举证（2026-08-25）

> 适用：任何「我们没有 X」「这张表没人用」「这个能力够不着」类结论——契约体检、死代码清理、
> 能力盘点、dataset 注册审查。与用户级 SessionStart 注入的「负面断言规矩」是同一条纪律的落地版。

- **[2026-08-25] 审自家 DuckDB 覆盖面，一次断言里错了四处：把有意豁免说成「失败形状复发」、
  推荐注册一张 0 行空表、引用计数少算、收益夸大成「翻倍」。**
  根因：对外部世界（竞品逆向、第三方 API、ClickHouse）核得很勤，因为默认自己不知道；
  回头看自家库时松了弦，因为默认自己知道。**熟悉度不减免举证责任。**
  具体机械原因是 `grep -rl "$t" intelligence/services intelligence/runtime` 只扫了两个子目录，
  结论却写成「`intelligence/` 全层 0 引用」——**口径限制写在命令里、没写进结论**，
  于是数字不可复现，而条目还标着 [实测]，等于用格式给错误背书。
  做法：负面断言落笔前三件事，缺一不可——
  ① **查数据存在性**：`SELECT COUNT(*)`。「入库 ≠ agent 能查到」的姊妹病是**「建表 ≠ 入库」**；
     本仓 `fact_top_gainers` / `fact_high_volume_gainers` 都是只有 schema、无写入链的空表，
     注册进语义层只会得到一个永远空的 dataset。
  ② **查历史处置记录**：往下多读几十行常有「暂不注册，保持工具面收敛」这类**有意豁免**。
     豁免只活在文档正文里、不是机器可读，正确叙事是「豁免未固化」，不是「上一轮漏了」。
  ③ **把计数口径写进结论**：扫了哪些目录、排不排 tests/、算不算数据产物，随数字一起出现，
     否则复核者无法复现，数字等于没有。

- **[2026-08-25] 基线量错了棵树。** 报「dataset 从 13 →」，但 13 是在**已弃用的脏分支**上量的；
  `gitea/main` 的真实基线是 16。做增量类结论前先确认「我量的是哪个 checkout 的哪个分支」，
  这与能力图谱 `graph_audit.py` 打印 checkout/sha 是同一条理由：**exit 0 只对某个 revision 成立**。

- **[2026-08-25] 列名碰上证据层 `source_date`，不能靠「换一列当时间轴」躲同名。**
  `fact_historical_mapping.source_date` 是被对照日，证据层 `source_date` 是信息日。
  躲开同名去选 `similar_date` 当 `time_field`，过滤会太松：问 2024 会看到 2026 才算出的映射。
  选 `end_date` 则相反——约 89% 在未来，`filter_future_dated` 整批丢掉。
  做法：发生日和信息日先量清；同名用语义别名（`as_of` → 物理列 `source_date`），**不要换列**。
  **不要把「两义碰巧对齐」写进结论**：本表 `updated_at` 671/687 行是 2026-08-12 回填墙，
  那是入库时间不是算法信息日。回填墙不能当 `cutoff_column`，否则历史问句全空。
  别名拆开后，T1b / `dataset_max_date` 必须按语义名解析时间维，不能只拿物理列反查。

- **[2026-08-26] 对照日 ≠ 会话日。** 外盘表 `trade_date` 是 A 股日历（隔夜包的对照日），
  `source_trade_date` 是外盘实际会话。问「今天隔夜」打对照日；把会话日当 `time_field`，
  休市窗口会对不上 A 股 as-of。市值原样美元，不能标「亿」。这与 mapping 的
  `as_of` vs `similar_date` 是同一条：两根日期列先量清，再决定哪根是时间轴。
## [kb] 晨汇批量回填（2026-08-18，PR #25）

- **[2026-08-18] 长文批量生成时，U+FFFD（替换字符）是「自产」缺陷——写完必须立即扫，不能靠小心。**
  场景：回填 15 天晨汇，source/briefing 共 30 页，其中 8 页被我自己的生成过程引入
  转码残留（"不可修改"写成"不可<U+FFFD><U+FFFD>"、"协议"写成"<U+FFFD><U+FFFD>议"，单页最多 7 个）。
  根因：不是原料损坏，是**生成端**在长输出里偶发产出坏字符；写作者「更小心」无法根除，
  且肉眼 review 中文长文极易漏过。
  做法：**写完即扫，扫完即修，修完复审**——`grep -c $'\ufffd' <file>`（或 Python
  `t.count('\ufffd')`）作为每次 write 的固定后验步；批量场景下用一段脚本对整批
  `briefings/ + sources/` 汇总输出，任何一页非零就停。这次 15 天全绿靠的就是
  「每写一天验一天 + 收尾全批再扫一遍」双层闸门。
  **可迁移原则：凡是「上游可能自产垃圾字符」的生成管线（LLM 转写 / PDF 抽取 /
  编码转换），U+FFFD 扫描是必配的廉价后验，成本一行 grep，漏过的代价是污染知识库。**

- **[2026-08-18] matcher 命中 ≠ 库内有页——wikilink 的判据是「文件存在」，不是「概念被索引」。**
  场景：晨汇 matcher 的 concept_hits 里有 `AIDC`、`黄金珠宝`，据此写 `[[AIDC]]`
  生成坏链；实际 `wiki/` 下并没有同名 `.md`（概念在 relations JSON 里、但从未建页）。
  根因：matcher 对照的是关系底层数据（concept_graph 等），wikilink 解析对照的是
  页面文件系统——**两个真本源不同**，中间没有保证一致的约束。
  做法：链接候选先跑存在性校验（`Path(wiki).rglob(name + '.md')`）再写入；
  已写的批次用脚本全量重扫 missing 链接，发现即改为纯文本或换成已验证存在的页面。
  同批另一坑：matcher 的 `concept_hits` 是 **list 不是 dict**，解析脚本按 `.keys()`
  取值会直接崩——读外部 JSON 先看结构再取数。
  **可迁移原则：任何「A 系统的输出」要喂给「B 系统消费」时，以 B 的解析规则为准做校验；
  A 的命中只说明 A 认识它，不代表 B 能解析它。**

- **[2026-08-21] 对「未提交交付」做变异测试，还原用了 `git checkout --`，把执行方的实现连变异一起抹掉。**
  场景：验收 W1（实现全部是工作区未提交改动）。亲手变异 verifier 后跑红确认击杀，
  然后 `git checkout -- <file>` 还原——checkout 回到的是 HEAD，不是「变异前」；
  执行方的全部 verifier 实现被抹掉，且未提交内容 git 无处可找（无快照、pyc 已重编译）。
  W1 执行方在交接里明明写了「变异前先提交：git checkout 会丢掉未提交实现」，验收方重蹈。
  自救：从执行 agent 的 Cursor transcript（`agent-transcripts/<uuid>.jsonl`）提取它对该文件的
  **全部 StrReplace tool_use 参数**按序重放（14/14 applied），起点相同（HEAD 干净版）+
  确定性替换 ⇒ 结果逐字节可信；再用行为面三对账验证等价：9 钉全绿、两个变异击杀数
  （5F/4F）与执行方声称一致、全仓全量 5897P/13S 与收据逐数一致。
  做法：**验收含未提交改动的树，动手变异前必须先存底**——`cp` 目标文件到 /tmp 或
  `git diff > /tmp/xx.patch`（stash 也行但会动工作区）；还原一律从备份 `cp` 回来，
  **禁止对未提交树用 `git checkout --` 还原变异**。
  **可迁移原则①：`git checkout/restore` 的还原目标是 HEAD，对未提交工作它是删除器不是撤销器。
  可迁移原则②：agent transcript 里的 tool_use 参数是「编辑操作的完整重放日志」——
  未提交工作丢失时，从 transcript 按序重放同起点的确定性编辑可以保真重建，
  重建后用「测试读数逐数对齐 + 变异击杀数对齐」当等价证明。**


- **[2026-09-09] 对着闪断网关做端到端验收：把驱动节奏对齐可用窗口，别拿固定重试撞。**
  场景：写手网关（本机 Mirasim 127.0.0.1:8080）整晚闪断——真请求 1–3s 后 502，随后熔断器
  打开、数十秒内一切请求瞬时 503；可用窗口 1–4.5 分钟、down 段 2–4 分钟。一个 tier=max
  episode 要 4–6 个模型轮（1–3 分钟），两题连跑必然跨窗。
  做法：① 探针盯 **down→up 翻转**，翻成 200 立即进场（起跑线最长），不在 down 段定时盲试；
  ② **一窗一题**，第二题用 `--conversation <id>` 续同一会话，不在一个窗口里塞两题；
  ③ key 会随上游重启轮换——**每次探针前从生产进程环境现抄**（`ps eww <pid>`），不落盘不打印；
  ④ 判定一律**事后读磁盘 episode 原件**（episode/report.json 晚于 run 状态翻 completed 落盘，
  驱动脚本即时打点恒 False，会把真通过读成失败）；
  ⑤ 「复核服务不可用」批量降级先查 `semantic_verifier.exc_class`——这次是判官二进制钉在
  带版本号下载件上被自动更新清掉，修一个符号链接（`~/.grok/bin/grok`）即回。
  **可迁移原则：依赖方是「窗口化可用」而不是「稳定可用/稳定不可用」时，驱动器的第一公民是
  窗口探测器（翻转触发 + 进场即跑），重试预算按窗口数而不是按次数计。**

## 历史发现研究复验 / 运行底座（2026-09-09）

- **[2026-09-09] 空池回退替模型补的一枪以 role=tool 进入下一次请求，前面没有 assistant.tool_calls 声明，OpenAI 兼容接口回 400（M3 第 3/4 轮、M6 第 5/6 轮）。**
  根因：应用发起的工具调用只落了 tool_request + tool_result，没有承载「声明」的事件；`derive_messages` 忠实派生出同样的孤儿，INV-R1 两边一样错所以对账过。
  做法：新 durable kind `application_tool_call` → `assistant(content="", tool_calls=[…])`，在 tool_request **之前**落账（声明 → 意图 → 效果）；不伪造 model_turn（会把底座的决定记成模型说过的话），不只在发送边缘补消息（durable / live 分叉）；恢复路径对「声明落了、意图没落」合成 tool_error{interrupted} 配平。
  **可迁移原则：「派生 == 实际」这类奇偶校验抓不到两侧共享的形状错误；模型可见不变量之外还要有一条 provider 无关的线格式规则（每条 tool 消息的 id 必须被前面某条 assistant 声明），检查器 `undeclared_tool_call_ids`。**

- **[2026-09-09] finish 校验白名单只收四种 query 算子，把模型合法引用的、本轮刚保存的 case 原件判成 integrity，整篇有依据的回答退成缺口模板（UI / M2 / M4 三题全因此失败）。**
  根因：checker 与 producer 的合同没对齐——producer（save / read）落的元数据 operation 不在 checker 的集合里，read 的 case 分支更是提前 return 什么都不落。
  做法：引用分两类（evidence 四算子 / product 本轮 save 或 scope 校验 read 的 case），合法性 ⊆ 并集，资格（missing_result / missing_comparison）只看 evidence；未知引用照旧 integrity。
  **可迁移原则：拒收码是 integrity 还是 substance 决定上游动作；先问「引用是不是真的」再问「引用算不算证据」，两问合在一个白名单里就会把合法产物当伪造。**

- **[2026-09-09] 判官二进制写死 `~/.grok/downloads/grok-1.0.5-…`，grok CLI 当天 11:18 自动升到 1.0.24 把旧版删了；run 照常 completed、finish 也过，公开回答却全部降级成 160 字「复核服务不可用」。修好路径后 1.0.24 的 `--sandbox read-only` 又因 `/var/run/docker.sock` 是符号链接拒绝启动。**
  做法：`LLM_JUDGE_GROK_BIN` 指稳定符号链接 `~/.grok/bin/grok`；`LLM_JUDGE_GROK_SANDBOX=off`；发一批真实验收前先单独探一次判官（`complete_grok_cli` 一条 2+2，9 秒回合法 JSON）。生产 8792 进程环境里仍是失效路径，下一次生产 run 的判官就会失败——要用户改启动脚本并重启。
  **可迁移原则：只看 run_status 和 finish 门看不到判官死了，`semantic_verifier.exc_class` 才是病因字段；带版本号的自动更新下载件不能当固定路径。**

- **[2026-09-09] 六题串行连发，M5 结束 1 秒后发 M6，约第 100 个事件起连续三次 429，重试间隔 0.6 秒；直接探网关：`model_cooldown`，两个模型所有凭据同时冷却，reset 4939 秒。**
  做法：批量真实验收按供应商配额排期，题与题之间留间隔；runtime 对 429 没有退避（0.6 秒连打三次即放弃进 finalization_recovery），这是底座待修项，本轮未动。
  **可迁移原则：限流失败是能力结论的噪声不是能力结论；网关 429 body 里有 reset_seconds，先读它再决定等还是换时段。**

- **[2026-09-09] 分支交接时的 1101P 收据只跑了 30 个目标文件；全仓一跑 7 红（T-7 capability/metadata 一致性、切换板漂移、`unknown runtime capability`）加 runtime 目录不新鲜、进度标签缺失，全是新增三工具后没跑全套留下的。**
  做法：交接前必跑全仓等价 CI 并留干净树收据；目标收据只证明「改动没弄坏我测的」，证明不了「没弄坏门禁」。全仓收据要标机器负载：负载 40 时 `test_rag_worker` 与会话集成用例是时序抖动（单跑可过），别把它们写成回归。

- **[2026-09-13] 多 worktree 仓 + harness 每条 bash 重置回默认 cwd：合并后核对 diff 读到「789 文件 −116k 行」的灭失假象，全量 pytest 又在主检出树（别人的脏树）白跑两次才把 4 个「失败」辨成别树产物。**
  做法：跨树操作逐条 `cd <树> &&` 或 `git -C <树>`，跑测试收据前先打印 `pwd && git rev-parse --short HEAD` 自证在哪棵树；合并完整性核对（`git diff <base>..HEAD --stat`）与跑测必须在同一条命令里完成定位。
  **可迁移原则：任何「按 cwd 解析」的工具在 agent harness 里都没有隐含上下文——每个调用都是新 shell；读数先证树，再读数。**
  同日升级（下午 QC 收口 session，踩中 12+ 次）：**git add/commit 同样中招且后果更重**——在主检出树跑 `git add -- <相对路径>` 把别人 untracked 的运营文件暂存进了主树索引（靠 `git reset -q -- <文件>` 退回，commit 被 pre-commit 拦下才没带走）；`git log`/`git status` 无 cd 读到的是别树历史。教训：cd 前缀不是「跑测试才需要」，是**每条命令**都需要，包括 git 与 read 相对路径。另：共享收据目录会被同时在跑的其他 agent 污染（同名时间戳收据指向别树 rev），认领收据先核 `tree`/`branch` 字段。

## 换库与并发窗口（2026-09-13，daily-swap 六~七轮）

- **[2026-09-13] `clone_to_staging` 末尾为了填收据里一个字节数，克隆完成后又回头 `source.stat()` 一次；那一行在「克隆完来源被删」时抛裸 `FileNotFoundError` 逃出编排（调用点只捕 `DatabaseLockedError` 家族）。**
  做法：把那次 stat 整个删掉，字节数改从副本量（克隆体与来源逐字节相同，取值等价）。
  **可迁移原则：能删掉的窗口不要改成能处理的窗口。** 给它加 try 只是让失败有出口，删掉它是让失败不存在；先问「这次 IO 是不是必需的」，只为凑一个展示字段的 syscall 通常不是。

- **[2026-09-13] 把「目标消失」归一成结构化拒绝时，差点用一层宽 `except` 判定——实测损坏库 read_only 打开抛的是**同一个** `duckdb.IOException`（与「库不存在」同类），宽 except 会把损坏、权限、存储故障全报成「目标被第三方替换」。**
  做法：只在**复查确认路径确已消失**时转换，文件还在就原样抛；并补一条「不掩盖其他 IO 故障」的测试钉住收窄面（它在修复前后都绿，是防将来放宽，不是缺陷回归）。
  **可迁移原则：异常归一要收窄到可复查的事实，否则把诊断信息抹平，运维照着错误方向查。**

- **[2026-09-13] 首次建库路径用 `os.replace` 发布，写的理由是「生产库本就不存在、无既有数据可丢」。独立探针否掉了它：最终检查之后、发布之前，一个普通 `duckdb.connect(target)` 写者能建库、插入、提交、关闭，`os.replace` 照样静默覆盖，编排还报 rc=0/swapped=True。**
  做法：改同目录 `os.link`——EEXIST 判定与建名字是同一个 syscall，没有 check-then-act 窗口；实测普通文件/有效软链/悬空软链/目录一律 EEXIST 且不跟随软链。失败不回退 replace（回退等于把刚拒绝掉的覆盖又做一遍）。
  **可迁移原则：「此处无数据可丢」是个待证断言，不是可以顺手写下的理由；并发窗口里别人可以凭空造出数据来。** 另：`link` 能关掉 absent→present，关不掉「必须仍是我锁的那个 inode」——别把前者的结论扩大成后者。

- **[2026-09-13] 修完之后，上一轮审查方的注入探针两条变红，红因是「注入未触达边界」——`source.stat()` 已删、bootstrap 不再走 `os.replace`，注入点本身不存在了。**
  做法：把等价覆盖迁成 `tests/` 常规回归（bootstrap 那条同时挂在 `os.replace` 与 `os.link` 上，对新旧两种实现都触达），并在报告里把「探针失效」与「结论反转」分开记。
  **可迁移原则：探针失效 ≠ 结论反转，更 ≠ 修好了。** 注入式探针的绿必须配一条「注入确实打中了」的断言，否则改完代码后它会安静地什么都不测。

- **[2026-09-13] 开工探针已经成功打开过旧库，随后的 `target.exists()` 却得到 False（探针与取分类之间目标被第三方删除），本轮被静默重新归类为「首次建库」——子进程建出缺历史的新库并发布成功，旧库历史就这么没了还报 rc=0（七轮独立探针实测复现）。**
  做法：existing/absent 的分类钉死在**本轮首次观察**（探针之前那次 `exists()`），之后不再就分类重新观察；已见旧库的轮次后来缺失只能由下游守卫拒绝（探针窗口内消失 → SwapTargetReplacedError；之后消失 → hold_swap_lock 开锁失败），绝不降格为 bootstrap。
  **可迁移原则：已被观察为「既有的对象」，它的随后消失不能被静默重新解释为「从来没有过」。** 分类要么钉死在首次观察，要么由首次观察显式向下传；在中间再观察一次而不比对前后，就是把「消失」洗成「初始化」。

- **[2026-09-13] 交接里写「三个源文件在 main 侧零漂移，所以门禁绿可以外推到合并之后」。七轮审查裁定不成立：main 侧累计改了 48 个路径（依赖、测试集合、执行环境都变了），merge-tree 只验证文本可组合、不执行行为。**
  做法：删掉外推断言，改写为「收据只对被测快照成立；整合候选必须重新组装干净树、重跑适用门禁」。
  **可迁移原则：「我改的文件对面没动」≠「合并后测试还过」。** 门禁收据绑定的是整棵树的快照，不是某几个文件的字节；文本能合起来与合起来后行为正确是两件事，后者只能跑出来，不能推出来。

- **[2026-09-13] 交接里写「全量 9,521 passed / 0 failed（干净树）」，八轮审查核收据 JSON：revision 是上一提交、dirty=true、dirty_paths 恰好是本刀三个文件——先跑全量再提交，收据绑定的是「旧 revision + 未提交修补」，不是干净提交收据。**
  做法：交接收据一律引收据 JSON 的 revision 与 dirty 位说话；要「干净提交收据」就先提交再跑。八轮干净重跑另暴露 codex sandbox 测试全量红/单独绿；归因证据是修补前 7c89ca81 的全量同名失败（九轮复核更正规：「父提交同红」那份收据实为单测复跑，且父提交已含修补，不能当修补前对照）。既有失败只用于归因，不等于预先豁免，不伪装全绿。
  **可迁移原则：收据的可信度 = 它绑定的 revision + dirty 位，不是你跑它时心里想的那个快照。** 引用收据前先核这两个字段；「计数应该真实」不能替代「可复现精确快照」。

- **[2026-09-13] 修了竞态之后，断言旧竞态的 barrier 探针必然死锁——那是修复生效的信号，不是回归；把正确合同钉进仓内测试，别去「修好」探针。**
  做法：QC/审查探针分两类：断言 bug 存在的（修复后必须变红，红了先核对失败原因是新合同再收工）与断言合同不变的（修复前后都必须绿）。并发修复若把验证收进锁内，旧的 barrier(2) 同步探针会让首线程永远等不到对端——仓内替代测试改为线程直调服务层断言「恰好一胜一 409 + 台账只多一行」。
  **可迁移原则：探针的预期结果随修复翻转；验收时逐条确认「它为什么红」，全红≠全修，全绿≠没修。**

## 2026-09-14 研究进化 06 第二轮返修：三处只在真实边界才现形的坑

1. **`from __future__ import annotations` 的模块加 pydantic 字段，类型名必须真导入**：`ContinuationRequest` 加 `dict[str, Any]` 时模块只导了 `Literal`——future 注解懒解析，直到 FastAPI 建 TypeAdapter 才炸 `class-not-fully-defined`，`py_compile` 与 ruff 全看不出来。教训：改 pydantic 模型后跑一个真请求路径的测试，编译通过不等于可用。
2. **跨时区口径比较会定时炸弹**：01 校验 `baseline_cutoff(上海日) > created_at[:10](UTC 日)`，上海 00:00–08:00 UTC 还在昨天 → 真实绑定每天这八小时必被拒。所有「日期 vs 时刻」的比较先对齐时区基准再比。fake clock 的测试时间（下午）永远踩不到这个窗口——合同测试里值得有「边界时刻」用例。
3. **playwright 多 webServer + future 证据链**：放行条件要「真浏览器→真 API→真投影」时，给第二台隔离服务独立端口 + 独立用户态 + bootstrap 现造夹具库（schema.sql + published 快照 + 真实服务写的会话/判断），比往主服务器塞环境变量安全——主 spec 的既有断言零风险。另外 `test.beforeEach` 首参必须是对象解构，`({} )` 撞 eslint no-empty-pattern、`_` 撞 playwright 校验——直接在 test 回调里 `test.skip(project.name !== ...)`。

- **[2026-09-16] 封存别人的未提交改动时只 `git add -u`（tracked），把 cli 新命令 import 的两个新模块、两份测试和 L2 管线 5 个脚本全漏在分支外——单独 checkout 那条 salvage 分支会 ImportError。**
  做法：封存前 `git status -uall` 列全未跟踪件，逐个对主干分类（`git cat-file -e gitea/main:<path>` + `cmp`），源码 / 文档缺的、不同的全封，只跳草稿垃圾与别人当日在途件；封完对每个新 import 目标 `git ls-tree <tip> -- <path>` 证明在。用临时索引（`GIT_INDEX_FILE` + `read-tree / add / write-tree / commit-tree / update-ref`）追加，不碰共用主树的索引与工作区。
  **可迁移原则：备份的完整性要按「依赖闭包」验，不按「git 认识的文件」验。**

- **[2026-09-16] 主检出树里 65 个「无主」脏文件差点被当成垃圾处理——其中 `scripts/moneyflow/` 是每晚 20:40 真在跑的生产代码：装机启动器被手改成从 `$DATA_ROOT`（= 主树）执行 L2，`ops_pipeline_run_daily.source` 从 09-10 起全是 `baidu-share:xianyu-l2-7z`，而主干里根本没有这份代码。**
  做法：动任何共用树的脏文件前三查：`plutil -p` 各 launchd plist 的 ProgramArguments / 代码根变量；`grep DATA_ROOT/scripts` 装机脚本副本；生产表按 `source` 取最新几行——代码只存在于哪棵树，就是谁在生产。处置是把代码搬进主干（PR），不是回退树。
  **可迁移原则：日志里打印的 `code=...` 是自述，执行了哪条路径要看子进程真实路径或数据的来源标签。**

- **[2026-09-17] 修生成根不能整份部署生成分支的旧 nightly wrapper：它含已退役 L2 暂停分支，会回退现役 L2。**
  做法：现役 wrapper 最小接线，用独立 `FINANCE_GENERATION_CODE_ROOT` 仅覆盖生成子进程；正式回归同时验生成收到新根、前后质检及 L2 保留旧根。删子进程赋值变异被抓；模板/装机/launchctl 环境逐键对齐后，真实 kickstart19步PASS。详见 `docs/handoffs/2026-09-17-nightly-generation-deployment.md`。
  **边界：主动触发不证明下次时钟触发；方法日步rc=0仍可包含capture refused，不能合写成「全部成功」。**
