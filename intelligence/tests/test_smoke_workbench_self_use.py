from __future__ import annotations

from scripts.smoke_workbench_self_use import PublicLeakScanner


def test_public_scanner_does_not_treat_http_url_as_windows_path() -> None:
    scanner = PublicLeakScanner()

    scanner.scan("来源：https://example.com/a/1 后续判断", "answer")

    assert scanner.hits == []


def test_public_scanner_still_rejects_local_paths() -> None:
    scanner = PublicLeakScanner()

    scanner.scan("C:/Users/name/file.txt ", "answer")
    scanner.scan("/Users/name/file.txt ", "answer")

    assert [item["marker"] for item in scanner.hits] == [
        "local_path",
        "local_path",
    ]
