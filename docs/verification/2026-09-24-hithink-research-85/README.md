# #85 / PR #894 验证原件索引

冻结候选 `62777a76d7812bf5eebe070892e5977b2aa93003`，基线 `c9dd71dfd678855b61662100ec74625b92ad1f1b`。这是该候选的证据，不为后续文档tip或main移签；没有合并/部署授权。

完整解释、叶子收据与边界见 [续推快照](../../handoffs/2026-09-24-hithink-research-85-qc.md)。当前结论：Python14932P/0F/0E/85S/2X（collected15019）、frontend120P、E2E34P/2S、registry五项通过（98条反向warning）；Spec23P、Quality17P，双轴PASS_WITH_LIMITS。

## 原样封存

- [spec-report.md](spec-report.md)：continue-03 Spec终稿。
- [quality-report.md](quality-report.md)：continue-03 Quality终稿，正式撤销M1。
- [previous-quality-report.md](previous-quality-report.md)：continue-02旧候选09b437c2f上的CHANGES_REQUIRED，保留原判，不覆盖。
- [original-claims.md](original-claims.md)：审查前C1-C6合同；本轮只有候选身份改变，合同文字未改。
- [author-response.md](author-response.md)：交给Quality的作者回应，不是判决。
- [spec-probes.py.txt](spec-probes.py.txt)、[quality-probes.py.txt](quality-probes.py.txt)：独立审查者探针原件；以文本封存，不进入作者pytest收集，也不作为新公共工具安装。

完整执行证据根为 `~/.finance-runtime/reviews/hithink-research-85-20260923/continue-03/`。原报告里的ROOT是该根下的`qc/`；previous报告的ROOT则为`continue-02/qc/`。探针重放需对应独占TREE和WORK，不直接在当前开发树运行。

`runtime-artifacts.sha256`列的是外部证据根的相对路径；在该根执行`shasum -a 256 -c <本文件同目录>/runtime-artifacts.sha256`核对。`archived-reports.sha256`则在本目录核对归仓副本。阶段`execution.json`再以哈希引用命令、退出码和完整输出。

## 不可省略的限制

两组作者测试在审查沙箱收集期blocked，不是通过；宿主正常入口94P与完整门禁另账。两组explore提前试跑是规程偏差，原件保留，最终只计独立execute一次。故意assert1==2的两条阳性各1F单列，不是产品红；两组探针文件执行前后未变。模型只走K3订阅通道，无自动重试或模型回退。

Quality保留F2既存异常分类观察、F3未知上游空响应形态、F4未知身份拒写的可用性变化；没有已证实的新增合同违反。两份报告仍有静态覆盖与未核范围。没有真实供应商调用、生产写入或部署；离线结果不证明真实限流窗口或夜跑恢复。
