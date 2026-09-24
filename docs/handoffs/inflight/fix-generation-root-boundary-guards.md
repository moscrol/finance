# #50 生成双根返修

## 这个分支做什么
修复原0f6c2810独立复核的三项P2：后代写入软链、摘要解析差异、代码脚本软链外逃。

## 决策与被否方案
- 原CLI只解析一次，校验/执行用同一结果；否两套parser与禁用合法缩写，避免语义漂移。
- import前验代码归属，副作用前验已知最终写入后代；否只验父根/绝对路径字符串。
- 保留数据cwd与合法外置用户态，否搬存量/全局改环境；不扩散给L2。
- 展开：`docs/handoffs/2026-09-15-generation-root-boundary-guards.md`。

## 当前状态
代码已提交并冻结`387028b846a21a1327d964af8c4b428367f88fcf`；作者侧复验通过，待独立复核。工作树`/Users/a77/fwp-wt-generation-root-guards`。未push、合并、部署或生产补跑。原QC提交9b974691及反例判据保留，不改旧退修裁决。

## 未验证 / 已知边界
- 临时DuckDB/质量与SQL夹具，真实launcher/CLI/runner/writer；不是矩阵业务SQL或真实模型episode验收。
- 生产同日/跨日/L2三门、完整runtime快照、模型网关、KB接收未验。
- 静态元数据预检不是OS沙箱；不防运行期换链、未枚举新写入或外部KB代码；直接daily调用不自动受保护。
- 跨仓registry读取KB/研究站当时脏工作树；96条crosswalk warning保留。共享图谱全局仍1条其他分支失效引用，本次三条引用有效。

## 下一步
新人独立复核387028b8；用未改的`scripts/probe_generation_code_root.py --repo <干净冻结树>`复跑并审合法配置。合并/部署另等用户授权，不只cherry-pick返修到未知基线（含前置local-plan）。

## 踩过的坑
pytest/Ruff用主树`.venv-workbench/bin/python`；`umask 022`、清洁env。变异只改独立临时副本，不能污染验收树。收据绑冻结SHA，后续文档提交不冒充新全量。共享BUILD.md有他人WIP，KIT/TOOLKIT未改，探针索引待补。

## 已验证
- 修前17F/25P；最终定向158P，含三处删闸→副作用复现→恢复拒绝。
- 干净`/Users/a77/fwp-wt-generation-root-guards-validation`：9704P/77S/2x/17warnings；Ruff、前端76P、E2E15P、registry四项通过；原独立探针作者复跑7/7。
- 全量收据`~/.finance-runtime/test-receipts/20260915T022354Z-387028b8.json`，校验exit0/基座漂移0。
- 指纹及副本：`docs/verification/generation-root-guards-387028b8/manifest.json`；全日志`~/.finance-runtime/reviews/generation-root-guards/`。
- 能力图谱原条目/项目索引/通用教训已回写，vault自动收录eaeaca71。
