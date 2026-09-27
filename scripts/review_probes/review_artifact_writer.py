"""Write only reviewer-owned stage artifacts, never host receipts or frozen probes.

The host supplies work_root/group/stage, not the model. This is a file-tool
boundary, not a sandbox for arbitrary probe Python; probe processes need their
own OS write policy before this can be used for an independent review.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys

GROUPS = frozenset({'e2', 'timer', 'consent'})
ARTIFACTS = {
    'explore': frozenset({'EXPLORE.md', 'EXPLORE.json'}),
    'execute': frozenset({'EXECUTE.md', 'EXECUTE.json'}),
    'report': frozenset({'FINAL.md', 'FINAL.json'}),
}


def _allowed_artifact(relative: Path, stage: str, group: str) -> bool:
    if relative.as_posix() in ARTIFACTS[stage]:
        return True
    if stage == 'explore' and group == 'consent' and relative.as_posix() in {
        'transaction-review.md', 'transaction-review.json',
    }:
        return True
    if len(relative.parts) != 2 or relative.parts[0] != 'probes':
        return False
    name = relative.name
    if stage == 'explore' and name in {'test_reviewer.py', 'test_positive_control.py'}:
        return True
    if stage == 'explore' and group == 'timer' and name == 'activity-reviewer.test.tsx':
        return True
    if stage not in {'explore', 'execute'}:
        return False
    return bool(
        re.fullmatch(r'test_reviewer_[a-zA-Z0-9_]+\.py', name)
        or (group == 'timer' and re.fullmatch(r'activity-reviewer-[a-zA-Z0-9_-]+\.test\.tsx', name))
    )


def write_artifact(work_root: Path, group: str, stage: str, target: Path, content: str) -> None:
    if group not in GROUPS or stage not in ARTIFACTS:
        raise PermissionError('unknown review identity')
    if not isinstance(content, str):
        raise TypeError('artifact content must be text')
    if not target.is_absolute() or '..' in target.parts:
        raise PermissionError('absolute non-traversing artifact path required')
    root = work_root.resolve(strict=True)
    try:
        relative = target.relative_to(root / group)
    except ValueError as error:
        raise PermissionError('artifact outside assigned group') from error
    if not _allowed_artifact(relative, stage, group):
        raise PermissionError('host evidence or artifact owned by another stage')
    # Directory descriptors plus O_NOFOLLOW keep parent symlink swaps from
    # redirecting this write. Probes are create-only to preserve first failures.
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open(root, directory_flags)
    try:
        for part in (group, *relative.parts[:-1]):
            if part == 'probes':
                try:
                    os.mkdir(part, mode=0o700, dir_fd=directory)
                except FileExistsError:
                    pass
            child = os.open(part, directory_flags, dir_fd=directory)
            os.close(directory)
            directory = child
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
        if relative.parts[0] == 'probes':
            flags |= os.O_EXCL
        fd = os.open(relative.name, flags, 0o600, dir_fd=directory)
        with os.fdopen(fd, 'wb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise PermissionError('artifact must be a single-link regular file')
            stream.truncate(0)
            stream.write(content.encode('utf-8'))
    finally:
        os.close(directory)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', required=True, type=Path)
    parser.add_argument('--group', required=True, choices=sorted(GROUPS))
    parser.add_argument('--stage', required=True, choices=sorted(ARTIFACTS))
    args = parser.parse_args()
    request = json.load(sys.stdin)
    write_artifact(args.work_root, args.group, args.stage, Path(request['path']), request['content'])
    print(json.dumps({'written': request['path']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
