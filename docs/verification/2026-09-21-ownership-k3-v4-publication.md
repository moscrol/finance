# K3 v4 中断轮次：归档发布设施纠正

本记录不改变候选、模型输出或独立审查状态（仍BLOCKED_INFRASTRUCTURE）。

本地封档819成员（不含manifest），原件/归档字节校验通过；首次提交`66f848e46afecced40a5a0d1c3a29127dd72c516`只有600个归档文件（含manifest）。原因是仓库通用`.gitignore`的`tmp/`规则静默忽略220份已精选文本证据，不是文件丢失或哈希改变。提交后逐文件`git show`复核发现exit128，原始错误保留在同目录`2026-09-21-ownership-k3-v4-publication-initial-error.txt`。

保留首次提交，不amend，不改旧归档/manifest或ignore规则。已按原manifest逐个核对220份文本/收据的成员、大小、哈希、无symlink、非DB/缓存，使用明确文件pathspec补暂存；本提交将其补齐。没有整目录force-add，没有提交真实临时缓存或二进制。归档仍819文件/33,027,503字节。只有包含补齐提交且再次通过Git字节/成员验证的tip才作为发布锚点；66f848e46单独不算完整归档。

最终提交字节校验记录在`~/.finance-runtime/reviews/ownership-k3-v4-closeout-20260921/archive-committed-verification.json`。此处记录的是设施错误，不是候选产品缺陷，也不允许将中断审查改报通过。
