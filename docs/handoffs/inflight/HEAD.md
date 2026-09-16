# HEAD · 2026-09-06 晚 · 逐日发布管线：SIGPIPE 误判修复 + 制冷剂草稿补落

## 这个分支做什么
主仓本枝无代码改动；本轮动的是 finance-research-site 与 ~/公众号/pipeline 两仓（见下）。本文件按工作区事实要求覆写 HEAD 交接。

## 决策与被否方案
- 05 步误判修法：选命令替换捕获（`OUT=$(cmd) || die` 再 grep 字符串）/ 否了 `|| true`（掩错）与局部关 pipefail（掩同管道其他错）/ 因保留 wrangler 真失败检出且无竞态。
- 跨午夜补跑：选逐 step 补 06/07/08 / 否了重跑 run_daily / 因 $TODAY 已翻 09-07 会把明天的 gpu 提前发。
- 制冷剂适配稿重排石英砂支（b2ac40b）：h3=23/表1/金句框6，数字全量保留；镜像同步 ~/公众号、~/内容矩阵。

## 当前状态
- 已提交推送：site b2ac40b+41b84d4（=gitea/main）；pipeline d66e4d0。
- 已完成：05 实弹重跑全绿、06 CONFORMANCE PASS、07 草稿箱 DRAFT_SAVED（登录态经用户扫码恢复）、08 等价动作 done=2026-09-06、看板/vault 已回写。
- 未动：本仓他人未提交 scripts/build_bp_public.py；pipeline state/ 下 stablecoin、refrigerant 两份 html（运行产物，沿 09-04 前例不入库）。

## 已验证
05 修复后实弹（wrangler Deployed→llms→线上200→indexnow→state 回写）；06 九项门禁 md=html=104；07 标题/正文/封面/保存截图齐全。

## 未验证 / 已知边界
草稿箱保存仅到「保存成功 toast 未出现」的兜底分支（脚本自认需人工核验）；建议用户开公众号后台核一眼。明晚 21:00 管线走的是修复后 05，首次自动验证待发生。

## 下一步
- 遗留决策（要用户拍）：09-05 固态变压器草稿缺口——当天 05 死后无人补 06/07，适配稿 796bcf0 已就绪，说一声即可补落。
- 明晚 21:00 观察 gpu 是否走通全链（新 05 的首场自动实弹）。

## 踩过的坑
- `grep -q` 在 `set -o pipefail` 长输出管道 = 竞态炸弹（SIGPIPE 141）；任何「成功判据靠 grep 输出」的管道都该用命令替换。
- 非交互 shell 推 gitea：osxkeychain 可能够不着，`-c credential.helper=store` 兜底。
- 过午夜补跑禁用 $TODAY。
