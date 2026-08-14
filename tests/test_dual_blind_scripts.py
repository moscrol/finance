from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    ROOT / "scripts" / "dual_blind_auto.sh",
    ROOT / "scripts" / "dual_blind_flows.sh",
]


@pytest.mark.parametrize("script", SCRIPTS)
def test_dual_blind_scripts_use_current_codex_runtime(script: Path) -> None:
    text = script.read_text(encoding="utf-8")

    assert "/Applications/ChatGPT.app/Contents/Resources/codex" in text
    assert "/Applications/Codex.app/Contents/Resources/codex" not in text
    assert 'CODEX_DUAL_BLIND_MODEL="${CODEX_DUAL_BLIND_MODEL:-gpt-5.5}"' in text
    assert 'exec -m "$CODEX_DUAL_BLIND_MODEL"' in text
    assert 'if [ "$dow" -ge 6 ]; then' in text
    assert 'if [ ! -x "$CODEX_BIN" ]; then' in text


@pytest.mark.parametrize("script", SCRIPTS)
def test_dual_blind_scripts_preserve_schema_v11_prompt(script: Path) -> None:
    text = script.read_text(encoding="utf-8")

    assert 'schema_version "1.1"' in text
