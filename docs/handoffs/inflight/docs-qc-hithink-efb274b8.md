# hithink 十三轮修复 QC：P1 关闭，最新主干组合门禁待补

## 这个分支做什么
独立审 efb274b8（修复 b98441c5），只留审查文档/证据，不改候选业务。

## 决策与被否方案
- 两处 P1 关闭；否了因主干前移推翻旧数据与全量收据。
- 合并暂不放行：fetch 后 main=d7e53805，候选基座=e40f22b8，组合未验；否了用文本无冲突代替组合测试。
- 详情 `docs/handoffs/2026-09-14-hithink-efb274b8-qc.md`。

## 当前状态
审查资料随本提交落账；候选/施工树未改，未合 main、未切运行时、未打开生产库。主干独有6提交（含1次合并），新增L2写库代码/测试与三份文档；合并预演 exit 0，但不构成合并门禁。

## 已验证
- 独立干净 efb274b8 全仓 Ruff 通过；五组相关测试81p/10.21s/exit0，收据 `20260913T165041Z-efb274b8.json`。
- 63f377da 真实探针原样重跑：输出路径冲突→exit1+独立临时目录FAIL；坏索引+真实脏文件→git128/gate1+git_invocation FAIL，无tree_clean=true。
- 存档 before/parquet 正常重放22/22 PASS/exit0，绑定efb274b8。
- 提交gate/child等于原run；脚本/parquet/before哈希链相符。
- 核到b98441c5全量原收据9612p/0f/77skip/exit0、dirty=false；非本轮全量重跑。
- 小证据：`docs/handoffs/evidence/20260914-hithink-efb274b8-qc/`；仓外根 `~/.finance-runtime/reviews/hithink-efb274b8-qc/`。

## 未验证 / 已知边界
未跑最新main+候选组合四叶；本轮未重跑全量/前端/E2E/registry。历史快照重放不代表当前生产新鲜度；未穷尽所有异常。检查器校验旧全量在当前HEAD不全等会拒绝，不宣称validator通过。

## 下一步
隔离候选纳入最新gitea/main→组合干净revision跑齐四叶→全绿后用户授权main合并。生产换库另行授权并按当前源库重验；302132历史回填和并跑表另案。

## 踩过的坑
测试目标先读原收据target；本轮一次猜错路径exit4/no tests，已保留失败收据后纠正跑81p。复用已有探针/收据工具，未新增通用工具；没有把测试调用错误算业务回归。
