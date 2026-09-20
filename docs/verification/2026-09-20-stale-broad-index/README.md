# 宽基指数收尾作者证据

PR #806，代码SHA d4d944cb67f9a91380949e18c33d28e22c3a0c00，基底728f327160bbd2485cb635e7ef09d040d718d7b5。

- `pytest-red.txt`：未修实现3F4P，选择器 `broad_indices or dimension_refresh or historical_provider_error`。
- `pytest-invalid-path.txt`：测试文件名错误，exit4/零执行，非通过。
- `pytest-fixed.txt` / `receipt-fixed.json`：固定代码SHA 139P，五个文件见收据target。
- `head-*.txt`与`status-*.txt`：测试前后SHA同且树干净；`receipt-check-fixed.txt`严格匹配通过；`ruff-fixed.txt`全仓静态检查通过。
- `source-backup.patch`：旧树三个未提交文件原始差异。仅保全，不能原样应用；里面吞Unknown thscode的方案已否决。
- `run-focused.sh.txt`与`receipt_redirect.py.txt`是一次性验证的原样留档，不是生产脚本。后者只重定向收据目录，早先red未使用重定向。
- `SHA256SUMS`覆盖以上14个证据文件；用 `shasum -a 256 -c SHA256SUMS` 检查。原件不为去掉whitespace提示而改写。

仅窄回归，不代表全量CI、独立审查、真实采集或生产数据验收。文档提交的tip不是这里代码SHA；最终tip复跑在PR评论单独记录。
