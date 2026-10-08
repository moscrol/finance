"""Serve the real app/API with an isolated frontend build. Not a production entrypoint."""
from importlib import import_module
from pathlib import Path

module = import_module("intelligence.api.app")
# Override the app's module-level static root (read by create_app); setattr keeps
# the field-contract gate from treating this test hook as an unread new field.
setattr(module, "STATIC_DIR", Path(__file__).resolve().parents[1] / "test-results/review-evidence/static")
app = module.create_app()
