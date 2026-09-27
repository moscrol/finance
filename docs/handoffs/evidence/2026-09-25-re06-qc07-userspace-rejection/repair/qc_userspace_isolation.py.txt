"""Pytest plugin template: copy to <review>/inputs before freezing a new batch.

The host sets REVIEW_SCRATCH and both user-directory variables. This plugin
also relocates the fallback used when conftest clears FORESIGHT_USERS_DIR.
Import it only in the sandboxed test child; it mutates process-local state.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(os.environ['REVIEW_SCRATCH'])
TARGET = Path(os.environ['QC_ISOLATED_USERS_DIR'])
for path in (SCRATCH, TARGET):
    if not path.is_absolute() or '..' in path.parts or path.resolve() != path:
        raise PermissionError('review userspace requires canonical absolute paths')
try:
    relative = SCRATCH.relative_to(ROOT / 'scratch')
except ValueError as error:
    raise PermissionError('scratch outside review scratch root') from error
if len(relative.parts) != 2 or relative.parts[0] not in {'controller-v3', 'e2', 'timer', 'consent'}:
    raise PermissionError('scratch must identify one group and one invocation')
if not SCRATCH.is_dir() or TARGET != SCRATCH / 'users':
    raise PermissionError('userspace must belong to this invocation')
if os.environ.get('FORESIGHT_USERS_DIR') != str(TARGET):
    raise PermissionError('explicit userspace and fallback must agree')

# Validate the destination before importing or changing application state.
from intelligence import userspace  # noqa: E402

TARGET.mkdir(exist_ok=True)
userspace.USERS_DIR = TARGET
