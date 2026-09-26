独立审核 PR #834 固定新组合，不改任何源码，不合并/部署/写生产，不联网查金融数据，不转委派。使用现有 ChatGPT 订阅，同一个session先规格后质量两节，不冒称两位审核者。作者/旧v2审核不可移签。覆盖不全如实 NOT_REVIEWED/BLOCKED，缺陷给可复现反例。

独占检出 /Users/a77/fwp-wt-runtime-forward-review-0921
固定 HEAD cb16cd463db5c19b3187a5137009791082874653
直接基座 ea5c3a94618a15e37f914c8b1a13e271875e4337，主干基座 f783f19c8a01fbe8d0ed70d851df7ed14598c051。
先后核 HEAD/status，源码应clean；只允许忽略的测试缓存。独立探针、日志、最终 report.md 仅放 /Users/a77/.finance-runtime/reviews/research-tail-integration-20260921/runtime-sol-review 。最终答复完整报告。不写仓内handoff/记忆/全局配置，不读凭证，不装包、不删除文件。

这是 runtime-contracts 父实现 + #798 与主干IO来源、delivery_pending/上一轮证据保护的组合。先看diff路径，聚焦运行代码，旧docs和过往绿仅作导览。
合同来源：docs/agent-product-door.md、docs/runtime/events.md；docs/superpowers/plans/2026-09-18-runtime-contracts.md 及 docs/handoffs/2026-09-20-runtime-evidence-closeout.md 导览须核真实实现。
优先验证：
1. episode_evidence schema v3 严格保存 io_effect（local_read / external_or_mixed / unknown）；原件和展示来源一致，同hash不允许展示改来源。v1/v2原线格式/摘要兼容，旧缺来源只恢复unknown；新来源不能无声降级旧版。检查字段白名单、非法值、编码/解码/深冻结与真实ledger消费者，不只构造对象。
2. 可信上一轮原件在首次模型调用前保存；不继承旧 supports/coverage 或当前授权之外有效事实。保存失败不得继续模型调用。io来源用于读取上限，unknown不应被猜成local。
3. 子研究、预算、授权快照：保存确认先于后续副作用，共享fence；恢复授权漂移fail closed，root预算不独立铸新池，升级先保存不抹执行位置。挑真实执行/恢复接缝，不把摘要当用户/代码签名。
4. 主干API delivery_pending、SSE尾部排空仍成立；终态不代表writer完成。main的_seed_prior_evidence不得在父实现迁入时丢失。

入口测试：intelligence/tests/test_runtime_forward_seams.py、test_episode_evidence_snapshot.py、test_episode_evidence_presentations.py、test_prior_evidence.py、test_episode_restore_persistence.py、test_episode_authorization_snapshot.py，按风险选小批。不必跑全量，不请求真实模型/生产库。自行设计几个独立正负例（优先旧版兼容/来源伪造/保存失败），不要只重跑作者测试。
测试固定 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest；umask022，env -i PATH=/Users/a77/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin HOME=/Users/a77 FWP_TEST_RECEIPT=0 PYTHONDONTWRITEBYTECODE=1。每测试命令最多120秒，阻塞保原件报未完成，不无限重试。总审核约15分钟内收口，不转委派/追加模型通道。

输出：准确HEAD/基线、Spec/Quality分节裁决和分合同覆盖、严重度/路径行/触发条件、实际命令和原始输出文件/结果、独立探针与现有测试分列、首红与修探针结果不混。没有跨进程恢复driver、单写者lease、未知效果对账的动态验收，不得外推exactly-once/恢复闭环；不签新main#830、财务/历史联合树或真实金融质量。
