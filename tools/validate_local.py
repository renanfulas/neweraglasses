from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    src_path = str(repo_root / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}{os.pathsep}{existing_pythonpath}"

    print("[validate] Running unittest discovery...")
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover"],
        cwd=repo_root,
        env=env,
    )
    if tests.returncode != 0:
        return tests.returncode

    print("[validate] Running localhost smoke probes...")
    smoke_code = """
from fastapi.testclient import TestClient
from new_era.infrastructure.http import create_app

with TestClient(create_app()) as client:
    checks = {
        "health": client.get("/health").status_code,
        "root": client.get("/").status_code,
        "device_capabilities": client.get("/api/device/capabilities").status_code,
    }
    for name, status in checks.items():
        print(f"[smoke] {name}: {status}")
    if any(status != 200 for status in checks.values()):
        raise SystemExit(1)
"""
    smoke = subprocess.run(
        [sys.executable, "-c", smoke_code],
        cwd=repo_root,
        env=env,
    )
    return smoke.returncode


if __name__ == "__main__":
    raise SystemExit(main())
