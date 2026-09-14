# 302132 第六轮审查

## 这个分支做什么
独立审查代码 5b0cd87e / 文档 4606ef96，不施工、不执行生产。

## 决策与被否方案
- 退修 1 P1 + 2 P2；不因正常产物 33/33 通过关闭坏产物反例。
- 关闭前轮三个具体 P1 反例及基线角色矛盾；完整 schema 的 P2 未关闭。
- 完整报告：`docs/handoffs/2026-09-14-302132-round6-5b0cd87e-review.md`。

## 当前状态
- 审查报告、探针、小证据已提交 `595a9acd`；未改施工代码，未合并、未 push、未写生产。
- 原树他人改动未触碰。审查大库副本均已精确删除，原演练 JSON 产物前后 SHA256 一致。

## 已验证
- 原 run9/run10 产物真实验收脚本 33/33 PASS。
- 交付单测 26 passed；相关 preflight/write-path 14 passed；ruff 全仓通过。
- 核到施工方全量收据 9,643/0/77 @5b0cd87e，dirty=false；不是本轮重跑全量。
- 6 个收据变异：5 个错误 PASS，缺 ma26 裸 KeyError rc=1/无 JSON。
- P1：自有副本 07-02 open 主表+并跑源表共同 58→59，验收仍 25/25 PASS。

## 未验证 / 已知边界
- 未重新执行 apply/verify 父发布链；只复验留存产物与隔离反例。
- 未跑全量 pytest、前端/e2e/registry，不作合入门禁声明。
- 12 位历史哈希前缀+mtime 不能严格证明完整文件历史从未修改。

## 下一步
1. P1：oracle 从不可变基线取源，比较源表不变并核两轮源指纹。
2. P2：递归 schema（含子 ok/数值/格式/非空）及结构化异常处理。
3. P2：verify parquet 也绑定实际文件；两轮授权 spec 对齐。
4. 用 `scripts/qc_302132_round6_probes.py --expect-fixed` 复跑；源共同变异另加 `--source-mutation-only`。均须新输出目录。轻量回归由施工方移植。
5. 新干净修订后重演练，审查通过后分别申请合并/生产授权。

## 踩过的坑
- 父=子只能证明内部一致，不能证明与外部冻结输入一致。
- 方法追加既有 `evidence-hygiene-three-failure-shapes`；脚本是专用事故探针，不是通用生产门禁，未改脏的 harness-reference。
