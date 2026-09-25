# #83 / PR #813：Quality continuation batches 04-06

## 背景
固定候选 `3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59`，工程基线 `4cc15e703f81bce8abadee00f68caacdb0c72b4d`，发布观测 main `d21707ca6c71e4e39194b01ef9549bc893595d3f`。目标仍是只做 C3 的独立 Quality，不能移签旧作者工程绿、旧 Spec 局部绿或宿主诊断。PR 保持 WIP/open/unmerged，未读写生产。

## 决策与被否方案
1. 将“首 bash、阳性对照字段、失败不得报 PASS”写成 `review.mjs` 工具入口和 `deliver_stage` 硬门，而不是继续依赖提示词；离线反例6项、沙箱预检通过。
2. 04 不补投：pytest 的 rootdir 自动选择导致沙箱根目录拒绝，模型已耗尽执行配额；宿主同沙箱加 `--rootdir=quality/work` 得10P，只能作命令诊断。
3. 05 不补投：探索阶段8请求用尽而无结构化交付；不把半成品当探索收据。
4. 06 把探索限制为验收脚本/索引，探针留到执行；执行命令固定 `--rootdir=quality/work`，避免重复的环境错误。
5. 06 报告拒收保留原件，不手工补 `verdict` 或改写模型 JSON；拒收说明硬门确实拦住了缺字段终稿。

## 结果
- 04：网关4、探索7、执行10，共21；首控制件未在第一条 bash，后续 pytest 环境错误，无正式交付。
- 05：网关4、探索8，共12；无探索交付。
- 06：网关4、探索5、执行9、报告1，共19。首 bash原始收据 exit1 且含 `intentional probe_bug`；给定来源的两组供应探针10例真实执行10P；报告真实调用 `deliver_stage`，但缺 `verdict`、C1-C7 `id/status/evidence`、标准计数对象及 `positive_control.status/classification/evidence`，被宿主终稿门拒收。
- 三批共52次请求，无自动重试。C3生产形64/39/161、C1/C4-C7、当前 main 组合均未验证。

## 证据位置
原始批次在 `~/.finance-runtime/reviews/pr813-glm-qc-20260925-04/` 至 `-06/`；Git归档 `docs/verification/2026-09-25-backfill-302132-quality-continuation/`，manifest逐项做原字节SHA/长度/解码核验，480份、2,389,778字节。排除候选树、凭据/auth、临时DB、用户目录、缓存、软链。旧398份归档不变。

## 后续
先不要合入或生产回填。若继续，必须新建批次并先确认动态 CURRENT、PR head、main 和归档；优先补一个能按标准 schema 交付的真实报告，仍需保持 C3 数值限制明确。完成独立 QC 后才可对当前 main 做工程门禁；所有生产操作仍需逐字授权、重新冻结输入并取得父备份。
