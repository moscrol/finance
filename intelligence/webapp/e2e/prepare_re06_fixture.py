"""research-evolution 绑定 e2e 的隔离服务夹具：真实市场库 + 预置会话与判断。

为什么需要它（QC 第二轮放行条件 #1）：绑定表单必须打真浏览器 → 真 bindings API →
真刷新投影，而真服务上的证据目录来自 river 读市场库。本脚本把这条链的输入造真：
schema.sql 建全套表（多为空表，river 对空轨如实报缺口）、一个 published 板块快照、
两天板块行情；再往用户态写一条会话与一条属于该会话的判断（trackable 对象按
session_id 过滤，预置判断必须落在预置会话上）。

产物：
- ``--db`` 指向的 duckdb（每次重建，保证可重复）；
- ``<users-root>/default/`` 下的会话元数据与 judgments.jsonl；
- ``<users-root>/re06-conversation-id.txt``：预置会话 id，spec 启动后读它。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--users-root", required=True)
    parser.add_argument("--db", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    users_root = Path(args.users_root).resolve()
    db_path = Path(args.db).resolve()
    sys.path.insert(0, str(repo_root))
    os.environ["FORESIGHT_USERS_DIR"] = str(users_root)
    os.environ.setdefault("FORESIGHT_USER", "default")

    # ---- 市场库：schema 全量 + published 快照 + 两天板块行情 ---------------- #
    import duckdb

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    con.execute((repo_root / "market_feature_store" / "schema.sql").read_text(encoding="utf-8"))
    for day, pct, amount in (("2026-09-11", 1.5, 200.0), ("2026-09-12", 2.0, 240.0)):
        con.execute(
            "INSERT INTO ops_sector_universe_snapshot_daily VALUES (?, 'snap-e2e', 'fixture', 1, 0, 'published', ?::TIMESTAMP AT TIME ZONE 'Asia/Shanghai')",
            [day, f"{day} 18:05:00"],
        )
        con.execute(
            "INSERT INTO fact_sector_daily_generation VALUES (?, 'snap-e2e', 'BK0001', '制冷剂', '基础化工', ?, ?, NULL, NULL, NULL, NULL, NULL, 'fixture', ?::TIMESTAMP)",
            [day, pct, amount, f"{day} 18:00:00"],
        )
    con.close()

    # ---- 用户态：预置会话 + 属于它的判断（走真实服务的写入路径，不手搓格式） ----- #
    users_root.mkdir(parents=True, exist_ok=True)
    from intelligence.services import judgments as judgments_svc
    from intelligence.services.conversation_store import ConversationStore

    conversation = ConversationStore(user_id="default").create_conversation("研究进化绑定 e2e")
    user_root = users_root / "default"
    judgments_svc.record_judgment(
        user_root / "judgments.jsonl",
        memo="配额收紧下三代制冷剂价格中枢上移（e2e）",
        themes=["制冷剂"],
        stocks=[],
        session_id=conversation.conversation_id,
        ts="2026-09-02T20:00:00+08:00",
    )
    (users_root / "re06-conversation-id.txt").write_text(conversation.conversation_id, encoding="utf-8")
    print(f"fixture ready: db={db_path} conversation={conversation.conversation_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
