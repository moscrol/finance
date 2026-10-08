"""Serve the real app/API with an isolated frontend build. Not a production entrypoint."""
from importlib import import_module
from pathlib import Path

module = import_module("intelligence.api.app")
module.STATIC_DIR = Path(__file__).resolve().parents[1] / "test-results/review-evidence/static"
app = module.create_app()
