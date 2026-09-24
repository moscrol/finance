# #83：3c5 作者工程验收原件镜像

唯一候选 `3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59`，基线 `4cc15e703f81bce8abadee00f68caacdb0c72b4d`。本目录原始内容来自 `~/.finance-runtime/reviews/backfill-302132-0923/continue-08/`，不是另一轮测试，不改写原收据的版本或绝对路径；文档HEAD不是被验代码。

- `verified-closeout.json`：14份小原件的哈希、merge-tree、版本/范围核验结论。
- `python-receipts/gate-47iUwvcM/pytest.json`：15457P/0F/0E/85S/2X、完整收集15544；同目录 `pytest.log.txt` 为门禁保留的完整原始输出。
- `scope.command.json / scope.log.txt`：明确收据路径、expected-revision、require-full-scope，exit0，基座漂移0。
- `focused-receipt.json`：118P。
- `frontend/frontend.json` 与6份逐步日志：install/lint/typecheck/120P/build/E2E34P+2S全部通过，日志哈希与收据一致。步骤1/2/3的原始输出末尾空行触发diff-check，故存为同名`.b64`（Base64无损编码）；解码后再与收据里的log_sha256核对，未修剪原字节。
- `registry-complete/receipt.json` 与5份日志：CI五项exit0，finance-only范围与CI一致。
- `rehearsal/summary.json / acceptance.json / amount-control.json`：37项全绿、异常金额只命中预期项、拒收不发布、恢复及生产身份不变。
- `production-authorization-draft.md`：未获授权的后续模板，只认forward-02/3c5，不是已经执行的生产命令。

例如在本目录执行 `base64 -D -i frontend/frontend-1.log.txt.b64 | shasum -a 256`，结果应等于frontend收据该步骤的log_sha256。

完整E2E产物、JUnit、冻结输入及演练运行附件仍在树外原目录；大库副本核验后已清理，不提交数据库。所有工程原件只证明3c5，不能移签其它候选。

**#75独立审查待完成；WIP保留，未合main、未执行生产。** 完整交接：`../../handoffs/2026-09-24-backfill-302132-current-main-ready.md`。此前ca4归档仍保留，但不是本轮收据。
