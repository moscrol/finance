"""642c3f5d N1 的可逆保留合同；仅写临时目录，不改候选或真实 users。"""

from types import SimpleNamespace

from intelligence.services import personal_export


def test_distinct_torn_bytes_remain_distinguishable_in_export(tmp_path):
    ledger = tmp_path / "observation_scripts.jsonl"
    user = SimpleNamespace(user_id="review-u", observation_scripts_path=ledger)
    prefix = b'{"id":"good-before"}\n'
    suffix = b'\n{"id":"good-after"}\n'
    fragments = [b'{"note":"\xe7\xae', b'{"note":"\xe7\xaf']
    exports = []
    for fragment in fragments:
        ledger.write_bytes(prefix + fragment + suffix)
        exported = personal_export.export_ledger(user, now="2026-09-14T00:00:00Z")
        rows = exported.parts["observation_scripts"]
        assert rows[0]["id"] == "good-before"
        assert rows[-1]["id"] == "good-after"
        exports.append(exported.to_dict())
    print({"input_fragment_hex": [f.hex() for f in fragments], "exported_rows": [e["observation_scripts"] for e in exports]})
    assert exports[0] != exports[1], (
        "两种不同坏字节导出为完全相同的结果，无法从导出恢复或区分原始残片；"
        "原 N1 要求坏行以可逆表示保留。"
    )
