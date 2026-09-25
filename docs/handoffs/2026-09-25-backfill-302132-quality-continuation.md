# #83 / PR #813：Quality continuation batches 04-10

## 背景
固定候选 `3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59`，工程基线 `4cc15e703f81bce8abadee00f68caacdb0c72b4d`。04-06关闭时 main 观测为 `d21707ca6`；07-08观测为 `fe9fdbfd70a637efc5bcf0cfecf74080a8d6a90c`，09-10观测为 `4db9a42b69b0d30bcf55b2eafb64151a6c1bb317`。这些 main 组合均未验收。PR 保持 WIP/open/unmerged，未读写生产。

## 决策与被否方案
1. 首 bash、阳性对照字段、失败不得报 PASS 均由 `review.mjs` 工具层硬门执行；离线反例6项和每个真实批次的沙箱预检保留原始收据。
2. 04-06的失败批次不补投、不改写；其原始 evidence 单独保留。
3. 07因 explore cap 用尽无交付，08因准备漏复制 fixture 依赖导致 collection error，09因探针旧绝对路径未重绑定导致 collection error；三批均保留原始收据，不移签为产品失败或独立通过。
4. 10在宿主复制层把旧 `/06` 路径重绑定到新 candidate，并以 host assertion 检查没有旧路径后才启动模型；execute只允许直接 pytest，不允许 wrapper或新断言。
5. report只真实调用一次 `deliver_stage`；10的结构化终稿通过硬门，未人工补字段。供应探针属于既有审查断言与宿主夹具修复，不算本轮新写。

## 结果
- 04-06：52次请求；06的10个供应探针通过，但终稿schema缺失，被硬门拒收。详情见旧归档 `2026-09-25-backfill-302132-quality-continuation/`。
- 07：gateway4、explore8，共12次；explore未形成结构化交付。
- 08：gateway4、explore7、execute10，共21次；execute首控件合同满足，但入口缺少同目录fixture依赖，2个collection errors。
- 09：gateway4、explore5、execute12，共21次；首控件合同满足，但探针引用旧 `/06/candidate`，沙箱拒绝，2个collection errors。
- 10：gateway4、explore3、execute7、report1，共15次。首控件 exit1 且含 `intentional probe_bug`；两组供应探针10/10 passed、0 failed、0 errors，作者测试0；host evidence audit 为 `EVIDENCE_COUNTS_VALID`；唯一 report 的 `PASS_WITH_LIMITS` 通过最终schema硬门。

07-10合计69次请求；04-10合计121次请求；均无自动重试。10的C3结论仅覆盖合成数据上的10个外部验收入口断言，生产形 `64/39/161` 未直接观察，所以C3 claim仍为 `not_verified`。C1/C2/C4-C7不在本批次范围，不能升级为完整QC或整体批准。

## 证据位置
- 07-10原始归档：`docs/verification/2026-09-25-backfill-302132-quality-0710/`，797份、3,803,807字节，manifest SHA `e9bfd26ad6d7c8731e9b7861930c595679843be399abf4bfe533334d8de82943`。
- 04-06原始归档：`docs/verification/2026-09-25-backfill-302132-quality-continuation/`，保持不改。
- 最新批次原始目录：`~/.finance-runtime/reviews/pr813-glm-qc-20260925-10/`。
- 动态状态：`~/.finance-runtime/reviews/backfill-302132-0923/CURRENT.json`。

归档排除候选工作树、凭据/auth、临时DB、用户目录、缓存和软链；所有原始请求、响应、命令、XML、报告包、失败现场和host audit均保留并按manifest原字节校验。

## 后续
不要合入或执行生产回填。若继续，必须重新核对CURRENT、PR head和main；下一步应先补验C3生产形数量及未覆盖数据契约，并对届时最新main重新做工程门禁。所有生产操作仍需逐字授权、重新冻结输入并取得本轮父备份。
