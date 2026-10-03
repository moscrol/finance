## 这个分支做什么
从GitHub主线06198093e集成Harness四片并验收；不扩剩余P1b。

## 当前状态
独占树`~/fwp-wt-harness-integration-1003`。产品验收 pin 为`d09e3b08d3b7b8ee49c27b6fb6c00c8cec464fc8`，其最后生产补丁为`46d9875c6`；本次后续只补验收文档，不改产品代码。Draft [PR #30](https://github.com/moscrol/finance/pull/30) 未合并/部署，未启用自动合并。

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
核对树外`closeout.json`、最终 PR checks 和 docs-only follow-up SHA。补丁独审需先确认模型身份与费用，不自行追加调用。真实对照最多12格需另批型号、配置、物理调用帽、费用和判卷；草案未预注册。合main/部署均等用户明确批准。

## 踩过的坑
共享主目录和旧候选不动。Python只用`/private/tmp/harness-opt/tmp/arena-harness-release-1002/.venv-workbench/bin/python`，env -i、umask 022、Keychain=0、独立收据。源码变更重新pin；变异红不是产品失败。

## 已验证
`d09e3b08`：Python `20558P/76S/2X/0F`，collected `20636`，收据审计 exit 0；前端 209P、E2E 52P/2S；registry 五项 exit 0；变异 `9/12/13/14`，历史 8、边界 16，审计 exit 0。GitHub run `37133397297`/`37133397266` 全绿，PR仍 Draft。ledger 反向 warning 102 条保留；工程绿不等于回答质量提升。
