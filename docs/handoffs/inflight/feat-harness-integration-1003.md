## 这个分支做什么
从GitHub主线06198093e集成Harness四片并验收；不扩剩余P1b。

## 当前状态
独占树`~/fwp-wt-harness-integration-1003`。生产末改46d9875c6；Draft [PR #30](https://github.com/moscrol/finance/pull/30)，未合并/部署。最终pin与门禁读树外`~/.finance-runtime/reviews/harness-integration-20261003/closeout.json`；文件缺失或complete非true即未收口，不用旧绿推断。

## 决策与被否方案
- 保主线材料预检/拒绝顺序；否全选候选：会削弱冻结来源检查。
- 路由同步输出ID与来源；否删来源：用户义务见证不能丢。
- causal_chain必需、cause_attribution提示可选；否退回双硬槽，补缺因果答案拒收反例。
- 阶段诊断并入独立交付说明；否裸索引并集：旧索引不属于当前稿。
展开见[日期快照](../2026-10-03-harness-main-integration.md)。

## 未验证 / 已知边界
独立规格/代码只读审查覆盖5266b5f8；46d9875c6修补未另独审。CLI实际模型glm-5.2，不是Claude；费用字段约$8.34、计价依据unknown。原Codex额度失败保留。
题型/主体/时间窗在线修订、完整HTTP新计划交付、SDK跨进程恢复未由本轮验收。金融Workbench真实对照0；脚本模型/E2E不是回答质量证据。R17/R19和240格封存。

## 下一步
核closeout及其完整SHA/收据，再核PR当前checks。补丁独审需要先确认模型身份与费用，不自行追加调用。真实对照最多12格需另批型号、配置、物理调用帽、费用和判卷；草案在证据根。合main/部署均等用户明确批准。

## 踩过的坑
共享主目录和旧候选不动。Python只用`/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python`，env -i、umask 022、Keychain=0、独立收据。源码变更重新pin；变异红不是产品失败。

## 已验证
5266b5f8：全量20556P/76S/2X，收集20634、完整范围审计绿；前端209P、E2E52P/2S、registry五项、四组47及历史8/边界16变异、GitHub必需检查绿。之后混合诊断丢失反例先红、修复定向411P；这些不转签给最终pin。
