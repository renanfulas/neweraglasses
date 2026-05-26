from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the local New Era MVP runtime.")
    parser.add_argument(
        "--with-e2e",
        action="store_true",
        help="Also run browser E2E tests. Requires the playwright extra and browsers.",
    )
    parser.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip the full unit suite and only run local smoke probes.",
    )
    parser.add_argument(
        "--with-scanner-comparison",
        action="store_true",
        help="Also compare direct text, image OCR, and simulated mobile scanner text paths.",
    )
    return parser.parse_args()


def build_base_env(repo_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(repo_root / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}{os.pathsep}{existing_pythonpath}"
    return env


def build_smoke_env(repo_root: Path) -> dict[str, str]:
    env = build_base_env(repo_root)
    env.setdefault("NEW_ERA_LOCAL_AUTH_USER_ID", "local-demo-user")
    env.setdefault("NEW_ERA_LOCAL_AUTH_PASSWORD", "local-demo-password")
    env.setdefault("NEW_ERA_SQLITE_PATH", str(repo_root / ".new_era" / "validate_local.sqlite3"))
    return env


def run_command(command: list[str], *, cwd: Path, env: dict[str, str]) -> int:
    result = subprocess.run(command, cwd=cwd, env=env)
    return result.returncode


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    base_env = build_base_env(repo_root)
    smoke_env = build_smoke_env(repo_root)

    if not args.skip_pytest:
        print("[validate] Running pytest...", flush=True)
        tests_status = run_command([sys.executable, "-m", "pytest"], cwd=repo_root, env=base_env)
        if tests_status != 0:
            return tests_status

    print("[validate] Running authenticated local smoke probes...", flush=True)
    smoke_code = """
import os

from fastapi.testclient import TestClient
from new_era.infrastructure.http import create_app

local_user_id = os.environ["NEW_ERA_LOCAL_AUTH_USER_ID"]
local_password = os.environ["NEW_ERA_LOCAL_AUTH_PASSWORD"]

with TestClient(
    create_app(
        enable_dev_auth=False,
        local_auth_user_id=local_user_id,
        local_auth_password=local_password,
    )
) as client:
    unauthenticated = client.get("/api/auth/session")
    login = client.post(
        "/api/auth/login",
        json={"user_id": local_user_id, "password": local_password},
        headers={"Origin": "http://testserver"},
    )
    session = client.get("/api/auth/session")
    grocery = client.post(
        "/api/simulations/grocery/missing-item",
        json={
            "session_id": "session_validate_grocery",
            "item_name": "eggs",
            "confidence": 0.88,
            "trace_id": "trace_validate_grocery",
        },
        headers={"Origin": "http://testserver"},
    )
    contract = client.post(
        "/api/simulations/documents/contract-review",
        json={
            "session_id": "session_validate_documents",
            "document_text": "Contrato com renovacao automatica, fidelidade de 12 meses e multa de cancelamento.",
            "trace_id": "trace_validate_contract",
        },
        headers={"Origin": "http://testserver"},
    )
    job = client.post(
        "/api/jobs/documents/contract-analysis",
        json={
            "session_id": "session_validate_documents",
            "artifact_label": "validate-contract.txt",
            "idempotency_key": "validate-contract-job",
            "document_text": "Contrato com renovacao automatica, fidelidade de 12 meses e multa de cancelamento.",
            "trace_id": "trace_validate_job",
        },
        headers={"Origin": "http://testserver"},
    )
    client.app.state.runtime.document_job_worker.wait_until_idle(timeout_seconds=10)
    job_payload = job.json()
    result = client.get(f"/api/jobs/{job_payload['job_id']}/result")
    feedback = client.post(
        f"/api/document-analyses/{result.json()['analysis_id']}/feedback",
        json={
            "session_id": "session_validate_documents",
            "feedback": "useful",
            "trace_id": "trace_validate_job",
        },
        headers={"Origin": "http://testserver"},
    )
    history = client.get(
        "/api/current-user/sessions/session_validate_documents/trace?module=documents&limit=10"
    )
    logout = client.post("/api/auth/logout", headers={"Origin": "http://testserver"})
    after_logout = client.get("/api/auth/session")
    checks = {
        "unauthenticated": unauthenticated.status_code,
        "login": login.status_code,
        "auth_session": session.status_code,
        "health": client.get("/health").status_code,
        "root": client.get("/").status_code,
        "device_capabilities": client.get("/api/device/capabilities").status_code,
        "grocery": grocery.status_code,
        "contract": contract.status_code,
        "job": job.status_code,
        "job_result": result.status_code,
        "analysis_feedback": feedback.status_code,
        "history": history.status_code,
        "logout": logout.status_code,
        "after_logout": after_logout.status_code,
    }
    for name, status in checks.items():
        print(f"[smoke] {name}: {status}")
    expected = {
        "unauthenticated": 401,
        "after_logout": 401,
        "logout": 204,
    }
    for name, status in checks.items():
        if status != expected.get(name, 200):
            raise SystemExit(1)
    if grocery.json()["outcome"] != "delivered":
        raise SystemExit(1)
    if contract.json()["analysis_id"] is None:
        raise SystemExit(1)
"""
    smoke_status = run_command([sys.executable, "-c", smoke_code], cwd=repo_root, env=smoke_env)
    if smoke_status != 0:
        return smoke_status

    print("[validate] Running device bridge harness...", flush=True)
    bridge_status = run_command(
        [sys.executable, str(repo_root / "tools" / "device_bridge_harness.py")],
        cwd=repo_root,
        env=base_env,
    )
    if bridge_status != 0:
        return bridge_status

    if args.with_scanner_comparison:
        print("[validate] Running mobile text scanner comparison harness...", flush=True)
        scanner_status = run_command(
            [sys.executable, str(repo_root / "tools" / "scanner_comparison_harness.py")],
            cwd=repo_root,
            env=base_env,
        )
        if scanner_status != 0:
            return scanner_status

    if args.with_e2e:
        print("[validate] Running browser E2E smoke...", flush=True)
        e2e_env = base_env.copy()
        e2e_env["NEW_ERA_RUN_E2E"] = "1"
        return run_command(
            [sys.executable, "-m", "pytest", "tests/e2e", "-m", "e2e"],
            cwd=repo_root,
            env=e2e_env,
        )

    print(
        "[validate] Browser E2E skipped. Use --with-e2e after installing Playwright browsers.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
