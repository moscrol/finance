# #841 前向重验收尾回执

本目录保存主干前向重验归档提交后的后验检查，不重签测试、不覆盖旧包。

- `committed-archive-check.json`：新主包提交`c03b4c148dd374603db2b97e36f4b7878e43935e`，68/68文件集合与Git blob字节一致。
- `pr-main-revalidation.json`：归档提交`c03b4c148`推送后回读#841，head与归档一致，PR仍open/WIP、未merged，base为`fix/react-trace-qc-0921`，Gitea仍声称`mergeable=false`。
- `memory-graph-complete.log.txt`：隔离agent-memory树接上远端更新后的完整路径审计；94行、273条断言无漂移，0行因缺仓跳过，222条在途/未校验。该检查只验证路径/符号，不证明运行时行为。
- `main-at-closeout.json`：收尾主干前进到`e82717d9a`（#831），现有基座漂移函数返回1<=5；只检查漂移，未验新组合，不覆盖原f73的漂移0收据。
- `memory-graph.log.txt`：首次未传`--repos-root`的失败覆盖原件，保留以说明为何补跑；首次默认根造成90行跳过，不能当完整审计。

固定候选`f73d2133968d51d3c782d3e12ee9aa4d0618ef45`包含`gitea/main@028a251a1b2c`，全量12681P/87S/2X/17W、前端110P/E2E34P2S、定向370P、七组撤保护和225行历史回放均已在主包中封存。基座漂移为0，但这是候选组合工程结论，不是已经合入main后的批次结论。

共享记忆最终提交`08e93969359b5a0173b0cb507183bae63a76f5b6`已推送；rebase时保留远端#845、日期验收和引用修复记录。独立Spec/Quality、自然金融质量、#793/#794完整行为及#833/#845联合树仍未验；未合main、未部署8792、未生产写入、自然模型调用0。

本目录使用`sha256-manifest.txt`和`scripts/check_evidence_archive.py --revision <归档提交>`校验Git文件集合与blob字节。
