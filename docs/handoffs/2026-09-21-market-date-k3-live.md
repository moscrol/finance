# 日期差异策略：K3 真实 Workbench 验收未通过

## 背景与授权

用户要求继续真实 Workbench 验收，并指定真实模型写手使用 K3。本轮没有合并、推送、开 PR、部署、补采或生产库写入授权。旧作者工程收据绑定 c57ec654，不能替代模型公开答案验收。

受测代码根 `/Users/a77/fwp-wt-market-date-advisory-0921`，完整 HEAD `786a3b627da9ae37e042881f2c0e8ef12ccac539`、tree `da8fbef79b8b1aaa8e280d532d169bfe7d7c0827`。首尾身份相同且干净，运行目录与 c57ec654 无差异。后续证据/交接提交不获得旧源码测试收据移签。

本轮角色是作者真实入口自验，不是独立 Spec/Quality，不是浏览器视觉验收。最终结论：**AUTHOR_REAL_ENTRYPOINT_OBSERVED_NOT_ACCEPTED**。

## 发现顺序

1. 同步当时 gitea/main 并核差分，固定候选不混入其他在途分支。复用现有 sidecar 启动接口，只加载生产 launcher 的 export，不执行其生产启动命令。
2. `readiness` 显示 09-21 快照 PASS/ready、provider=akshare_exact、fresh/complete；结构化库最新09-18，差异只做 advisory，整体 ready。与用户要求一致。
3. 在19276启动隔离服务，独立 users、Episode store和启动台账；8792仅首尾GET health。K3通过会话级配置作为写手，remember=false；配置回读 credential_persisted=false。语义判官继续配置GLM，未改生产模型。
4. 两道题分别创建真实 conversation并POST messages，按run_id等终态，按返回assistant_message_id取正文，避免读取旧答卷。两题各一次，没有通过重试筛选好答案。
5. 当前题实际取到48条本地证据并输出分析，没有因为结构化数据旧就拒答。但正文两次声称09-21行情本地未收录，与启动时已存在的09-21快照矛盾。
6. 历史题正文给出09-11成交额19710.64亿元、阶段与题材，实际119条证据观察/118唯一hash均未超09-11；公开引用13条也没有超窗。但context中的information_cutoff仍为09-21/runtime_default，history_intent=null，市场问题还被分类为company/stock_deep_dive。
7. 据原始TaskFrame重建同一日期语义与local_only注册表，不调用模型，分别省略查询时间与显式请求09-18。两次finance_query都成功返回09-18事实。自然答卷守窗只是这一次模型选对时间，不能认证硬约束。详见cutoff-diagnostic.json。
8. 两题最终语义判官均unavailable，report business_status=partial，pending_rejudge=true；自然运行虽completed，不能签质量通过。历史报告还留有numeric_unsupported问题，aggregate content_degraded_count=0不能掩盖它。
9. 初始引用核对以原始source标签精确比较，当前题五条不匹配；复用实际展示sanitizer后，current 15/15、historical 13/13在title/source/date上都匹配证据。保留初始观察及追加勘正，不把展示差异写成虚构引用。
10. 两个Episode runtime_handle均closed，服务进程退出、19276端口关闭；8792首尾source_revision仍adcda94b5e401158f1c3aa51f210e1e8d0f0b713且runtime身份相同。六表行数/max日期及三表两个截止日行值审计前后相同，不等于整库字节验证。

## 具体阻断

### 明示截止没有进入强制合同

`intelligence/services/honesty_gates.py::requested_information_cutoff`未识别“把信息截止严格限定为2026年9月11日……不使用9月11日之后的数据”，返回None。`episode_factory.py::build_episode_context`因此取runtime_default；本题也未产生strict HistoryIntent。`episode_tools.py::finance_query_runner`仍允许09-18查询。缺口是在自然题意转为合同的入口，不是把09-18数据标成09-11。

不把此诊断叫第三份真实模型答卷：它是无模型、本地只读的对抗复现，原始两次run没有改动。也不凭它断言全仓所有历史句式失效。

### “本轮取得”被说成“本地存在”

当前local_only合同仅允许已审计为local_read的工具；`market_data`综合runner可能联网，不能直接加入白名单。当前真实菜单与证据没有交付09-21快照。写手基于09-18结构化事实分析本身合理，但把其范围扩展为“所有本地行情最新09-18”不合理。修复需同时解决本地快照的只读可见性与来源范围表达，不能为了得到新日期放宽网络授权。

### 质量结论缺席

两题的judge_unavailable单独记录，不算日期差异导致拒答。公开答案保留复核超时提示；本轮没有完整逐句语义裁决。证据哈希可回溯、引用日期匹配都不等于每句推论正确。

## 方案比较

| 决策 | 采用 | 被否方案与原因 |
|---|---|---|
| 入口 | conversations/messages真实Episode | CLI或直接工具返回不覆盖公开稿/判官/消息合同 |
| 模型与隔离 | K3写手、现有判官、19276独立用户 | 切8792越过生产授权；关判官会改变验收对象 |
| 数据 | 已有本地事实，读生产DuckDB | 回填/补采越权；强行统一来源日会失真 |
| 截止验收 | 自然样本+无模型越界探针 | 单凭答卷没超窗会把模型自律误当底座约束 |
| 失败处置 | 固定候选留证、明确未通过 | 边改边跑会混淆版本；反复刷同题不能代替统计 |
| 证据 | 新包归档+Git对象核验 | 覆写旧工程包或移签c57收据破坏身份边界 |

## 收据与复现

仓内包：`docs/verification/2026-09-21-market-date-k3-live/`；原件：`/Users/a77/.finance-runtime/reviews/market-date-advisory-k3-20260921/`。

| 题目 | run_id | 模型轮/工具调用 | 耗时 | 结果 |
|---|---|---|---|---|
| 当前市场 | run_20260921_223455_384576 | 2/5 | 253.0秒 | 分析已交付；错误否认09-21本地快照；judge unavailable |
| 历史截止 | run_20260921_223908_394353 | 5/10 | 297.17秒 | 自然证据守窗；强制cutoff未守；judge unavailable |

关键文件：raw/REVIEW.md、raw/observations.json、raw/cutoff-diagnostic.json、raw/citation-display-audit.json、raw/closure.json；每个run的continuous-episode.json/trace.jsonl/report.json/answer.md及消息均保留。

65份文本原件共3,806,068字节，复制前后逐字节一致；另README、manifest.json、scan-review.json，共68内容文件，另有SHA清单自身。SQLite/锁/缓存未入包。冻结脚本后缀.py.txt、日志.log.txt，原字节不变。

包内扫描实际覆盖67文件（在扫描报告与哈希清单生成前）；2个文件/模式组、6次匹配、5个唯一值，均为模块/属性路径，未发现实际凭据。初始外置扫描60文件是另一范围，不混计。执行成功不等于零命中，不声称全面安全认证。提交后用现有check_evidence_archive.py逐Git blob核验完整文件集合与SHA，结论另记最终提交收据。

尽管启动WORKBENCH_PERSIST_LLM_CONTEXT=1，本次没有首轮完整prompt文件，只保留hash/字符数与模型/工具事件；不得声称完整输入可重放。N=1/题，不比较改进率或稳定性。脚本Ruff通过不等于自然质量通过。

## 下一步与不做事项

- 修明示截止解析及不可变合同，添加这两种越界请求的反例；其后新候选重跑完整工程门禁与真实K3答卷。
- 在不破local_only授权下让本地快照与结构化来源可见，并限制“未取得”到“未存在”的无依据推断。
- 市场对象被识别为公司另列路由问题；不接管其他并行分支，不关闭或更换他人PR。
- 独立Spec/Quality和逐句答案仍待验；浏览器展示、后来main组合、生产效果未验。
- 不push/合main/部署，不补采或生产写入，不覆盖旧工程归档或凭此次记录改其通过边界。

工具沉淀：复用现有sidecar、conversations API、展示sanitizer、SecretScanner、Git blob校验；新增脚本仅封存固定样本。没有将两个样本的临时编排升格为通用框架，也未新建共享工具清单。真正运行保护的改动留待新源码候选，不以交接文字冒充已修复。
