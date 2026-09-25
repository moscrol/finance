# RAG 双向管道截止时间补修

## 身份与范围

用户要求继续修复。独立工作树 `~/fwp-wt-rag-recovery-state-0923`，分支
`fix/rag-recovery-state-0923`；未修改主脏树、冻结 runtime、生产数据或索引。
将 `gitea/main@2edbe4c46595cbea3eb3abe04fe84a7bd5afd55e` 无冲突合入本分支，
组合提交 `7ac3840cbc93548e6b4454ddf60180c39edbe913`。补修代码为
`d29d554f176336b1ae97fb6a0a2aeb72bfcd3d49`，本篇是后续文档，不移签测试收据。
收尾 fetch 后基线仍为 2edbe4c46；未推送、开 PR、合 main、重启或部署。

结论为 HOLD：最新固定候选相关回归有一条红、管道变异基线三条红，独审没有最终报告，
全量 Python 与前端/E2E 未跑。不能拿早期 431P 或旧版收据当放行依据。

## 按发现顺序

1. 查询装机调度：`com.a77.finance-akshare-snapshot` 工作日 16:15 更新行情快照；
   `com.financeworkspace.daily-full-review-sync` 每日 18:30 启动主库 staging 同步；
   finalize 为 20:40。16:15 后快照 09-23、主库 09-22 与调度时间差吻合，尚不能
   断言当天入库失败。没有提前启动全量复盘、回写日期、降级 readiness 或改装机配置。
2. 新组合 7ac3840c 定向 422P、Ruff 通过，跨三仓 registry 四项通过，解析 61 个 skill。
3. 第一只读独审针对 7ac3840c，因模型容量不足退出，无最终报告，不计独审通过。
4. 作者发现 stdin 仍阻塞写入：长请求写满 stdin，子进程同时写满 stderr 时互等，
   而超时计时在写完后才开始。新增真实子进程测试，先复现三条失败，分别为长请求与
   大量 stderr、冷进程不读请求、热进程不读请求；均有看门狗兜底，不让 pytest 永久挂起。
5. 将 stdin 纳入现有非阻塞 selector，与 stdout/stderr 共用截止时间。处理短写入、
   暂时不可写和 BrokenPipe；请求完整发送才允许热进程首次超时保留。部分 JSON 发送
   后超时必须杀进程，不能把下一条请求接到残帧上。未增加线程、预算或模型加载。
6. 补五条确定性传输用例：UTF-8 短写三种分片、暂时不可写、收发共享截止时间；
   管道注册失败用例扩到 stdin。总共增加九条，迭代相关 431P，提交钩子通过后提交 d29。
7. d29 启动恢复 14 组撤保护全过；管道组原始基线 80P/3F，未进入变异。三条失败为
   代码变化换进程两种文件参数及查询中代码变化，均在 3 秒查询阶段 TimeoutError。
   随后同代码、同超时定点复查 3P。不是首次红集被推翻，也未证明资源压力是唯一原因。
8. 固定干净 d29 的十文件组合再验为 430P/1F，失败
   `test_keepalive_not_due_right_after_real_traffic` 在 2 秒预热阶段 TimeoutError；
   不是 due 判据断言失败。没有修改超时、放宽断言或继续循环重跑。
9. d29 的新只读独审因服务额度用尽退出，同样无最终报告；不再请求新的审查。

## 决策与被否方案

| 选择 | 被否方案与理由 |
|---|---|
| stdin/stdout/stderr 共用非阻塞 selector | 新开日志线程增加另一套关闭/清理责任；只读 stderr 仍不能覆盖阻塞发送 |
| 收发共享绝对截止时间 | 写完再开计时或每次进展续期，会把最容易卡住的一段排除在预算之外 |
| 半帧超时终止进程 | 一律保热会让下一条请求接到半份 JSON；完整帧首次超时仍保留原策略 |
| 保留红集与单次复查各自含义 | 后来通过不证明先前超时无害，不延长测试/生产超时求绿 |
| 暂不启动完整重型门禁 | 宿主同时有其他全仓任务、swap 使用约 11.4 GiB，且生产探测再超时；未停止无关任务 |
| 数据时差与 RAG 故障分别记录 | RAG 修复不能补行情事实，health 200 也不能替代 readiness |

## 证据与范围

证据根 `~/.finance-runtime/reviews/rag-recovery-state-0923/`：

- `closeout-01/related/gate-IufdjsQ3/pytest.json`：干净 7ac，422P；不是 d29 收据。
- `closeout-01/request-write-red.log`：补修前 3F。
- `closeout-01/request-write-related.xml`：提交前迭代 431P，只属脏树迭代。
- `closeout-01/independent-review.log`：容量不足，无最终报告。
- `d29d554f1/related/gate-unhMl4IH/pytest.json`：干净 d29，430P/1F，180.12 秒。
  `related.log` 与 `related.xml` 保留失败详情，失败的 `related-tmp` 未清除。
- `d29d554f1/startup-mutations/results.json`：14 组红 -> 绿，基线/最终整套 29P，
  complete=true、final_status 为空，各恢复字节哈希一致；成功临时树已移除。
- `d29d554f1/transport-mutations/results.json`：complete=false，基线 80P/3F，
  mutations 为空；保留干净还原树，确切路径在 results.json，不认作 12 组通过。
- `d29d554f1/timeout-recheck-exact/gate-vuD25fJb/pytest.json`：干净 d29 定点 3P。
  首次 `timeout-recheck/gate-mZCkreyy` 因给空格分词 runner 传带转义的 `-k` 表达式，
  exit4、零执行；改为两个精确 node ID 后才执行，零执行不计通过。
- `d29d554f1/registry-*.log`：check、check-parseability、backfill-tables --check、
  generate-views --check 四项通过，三仓在场，无缺仓跳过。Ruff、分层/路径/字段等钩子通过。
- `d29d554f1/independent-review.log`：额度用尽，无最终报告，不等于无发现或批准。

所有测试使用主树 `.venv-workbench/bin/python`，Python 3.12.13，未用宿主缺依赖解释器。
本轮所有自有测试及独审进程已结束。未验完整合入门禁、真实 BGE、自然金融会话、部署效果。

## 生产观察

生产仍为干净 `3b7e473575b0ff2dea3c1088ba7b5e330e95c8e4`，不是新候选。
16:43:46 health 200/0.342 秒，source_dirty=false、code_matches_repo=true；同次 readiness
20 秒未返回，curl exit28，不能写成 ready。16:45:26 单次复查返回 503/15.543 秒，
missing_critical 为 `rag_query_protocol` 与 `market_data_consistency`：

- CLI 能力探测超时；常驻 worker 仍 ready、model_load_count=1、recoveries=0。
- 快照 2026-09-23、主库 2026-09-22。
- 应用任务 active=0、queued=0。

原件 `d29d554f1/production-*`，两次告警经 notify_ops 写 canonical alerts.log。
未定位探测超时根因，不归因到 swap 或本补丁；本补丁未部署，不能宣称它解决了线上探测。
没有写部署账本、生产 run 或生产库，不重复旧 cutover、不运行 rag update。

## 下一步与沉淀

1. 资源条件允许后，先定位/控制 2 秒与 3 秒子进程测试超时，再对届时固定候选完整复验；
   保留本轮红集，管道变异须从基线开始，不能从中间接续伪装完整。
2. 独审服务可用后取得绑定新候选的正式报告；不要使用中断会话日志作批准。
3. 补完整 Python、前端/E2E 及合流身份门禁，用户确认后再讨论合 main。
4. 正式夜跑后复核快照/主库一致性，独立排查 CLI 探测超时；生产就绪及真实模型/会话
   验收齐全才准备可回滚部署。

新用例及变异定义直接扩展既有 runner，没有遗留一次性 /tmp 工具。
可迁移边界已补入共享记忆 `kill-on-timeout-is-an-amplifier.md`：保留热进程有完整请求帧前提。
