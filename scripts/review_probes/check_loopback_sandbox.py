"""Check IPv4 loopback/remote TCP and security CLI execution before macOS CI.

Use before local CI, not as evidence that arbitrary application IO is safe.
A local-address filter on generic network* can inadvertently allow outbound IO;
inbound and outbound grants must be separate and tested, not merely inspected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

PROFILE = (
    '(version 1) (allow default) (deny network*) '
    '(allow network-inbound (local ip "localhost:*")) '
    '(allow network-outbound (remote ip "localhost:*")) '
    '(deny process-exec (literal "/usr/bin/security"))'
)
KEYS = {"loopback_connect", "external_denied", "keychain_exec_denied"}


def observe() -> dict[str, bool]:
    observations = {key: False for key in KEYS}
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.create_connection(server.getsockname(), timeout=1):
            observations["loopback_connect"] = True
    try:
        # TEST-NET address: an allowed timeout/unreachable result is NOT a pass.
        with socket.create_connection(("192.0.2.1", 9), timeout=1):
            pass
    except PermissionError:
        observations["external_denied"] = True
    except OSError:
        pass
    try:
        subprocess.run(["/usr/bin/security", "help"], capture_output=True, timeout=3)
    except PermissionError:
        observations["keychain_exec_denied"] = True
    except (OSError, subprocess.TimeoutExpired):
        pass
    return observations


def run_probe(profile: str = PROFILE) -> dict:
    receipt = {"profile": profile, "profile_sha256": hashlib.sha256(profile.encode()).hexdigest(),
               "accepted": False}
    command = ["/usr/bin/sandbox-exec", "-p", profile, sys.executable,
               "-B", str(Path(__file__).resolve()), "--child"]
    receipt["command"] = command
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15,
                                env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"})
        receipt.update(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)
        data = json.loads(result.stdout)
        receipt["observations"] = data
        receipt["accepted"] = (
            result.returncode == 0 and isinstance(data, dict) and set(data) == KEYS
            and all(value is True for value in data.values())
        )
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        receipt["error"] = str(error)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--profile-file", type=Path, help="Explicit alternate policy for negative checks")
    args = parser.parse_args()
    if args.child:
        data = observe()
        print(json.dumps(data, sort_keys=True))
        return 0 if all(data.values()) else 1
    profile = args.profile_file.read_text() if args.profile_file else PROFILE
    receipt = run_probe(profile)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
