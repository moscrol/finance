"""检索运行时代码身份（不是数据新鲜度，也不是供应链认证）。

只哈希 query CLI、RAG 包和它的轻量脚本依赖；不读 wiki / 索引 / 模型。
供负能力缓存和常驻 worker 共用，避免路径相同但已加载代码不同。
发布仍应使用不可变检出并重启服务，不支持部署中原地逐文件改写。
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def code_identity(kb_root: Path) -> str:
    root = kb_root.resolve()
    paths = {root / "scripts/rag_index.py"}
    paths.update((root / "scripts").glob("rag_*.py"))
    paths.update((root / "skills/lib/rag").glob("*.py"))
    access_log = root / "skills/lib/access_log.py"
    if access_log.is_file():
        paths.add(access_log)
    digest = hashlib.sha256()
    for path in sorted(paths):
        name = str(path.relative_to(root)).encode()
        data = path.read_bytes()  # 读不到就失败；不可给多个未知版本发同一身份。
        digest.update(len(name).to_bytes(8, "big") + name)
        digest.update(len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()
