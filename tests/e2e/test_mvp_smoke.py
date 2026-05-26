from __future__ import annotations

import io
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

if os.environ.get("NEW_ERA_RUN_E2E") != "1":
    pytest.skip("Set NEW_ERA_RUN_E2E=1 to run browser E2E tests.", allow_module_level=True)

playwright_sync_api = pytest.importorskip("playwright.sync_api")
pil_image = pytest.importorskip("PIL.Image")
pil_image_draw = pytest.importorskip("PIL.ImageDraw")
pil_image_font = pytest.importorskip("PIL.ImageFont")


LOCAL_USER_ID = "local-demo-user"
LOCAL_PASSWORD = "local-demo-password"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def mvp_server(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, Path]:
    repo_root = Path(__file__).resolve().parents[2]
    port = _free_port()
    runtime_dir = tmp_path_factory.mktemp("new-era-e2e")
    env = os.environ.copy()
    src_path = str(repo_root / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}{os.pathsep}{existing_pythonpath}"
    env["NEW_ERA_SQLITE_PATH"] = str(runtime_dir / "runtime.sqlite3")
    env["NEW_ERA_LOCAL_AUTH_USER_ID"] = LOCAL_USER_ID
    env["NEW_ERA_LOCAL_AUTH_PASSWORD"] = LOCAL_PASSWORD
    env["NEW_ERA_ENABLE_DEV_AUTH"] = "0"

    log_path = runtime_dir / "uvicorn.log"
    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "new_era.infrastructure.http.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=repo_root,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("E2E server exited before becoming healthy")
            try:
                with urlopen(f"{base_url}/health", timeout=0.5) as response:
                    if response.status == 200:
                        break
            except URLError:
                time.sleep(0.2)
        else:
            raise RuntimeError("E2E server did not become healthy")
        yield base_url, log_path
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        log_file.close()


def _launch_browser():
    try:
        controller = playwright_sync_api.sync_playwright().start()
        browser = controller.chromium.launch()
    except Exception as exc:  # pragma: no cover - depends on local browser install
        pytest.skip(f"Playwright Chromium is unavailable: {exc}")
    return controller, browser


def _sign_in(page) -> None:
    page.locator("#auth-user-id").fill(LOCAL_USER_ID)
    page.locator("#auth-password").fill(LOCAL_PASSWORD)
    page.locator("#auth-login-button").click()
    playwright_sync_api.expect(page.locator("#auth-title")).to_contain_text(
        "Companion session active",
        timeout=10_000,
    )


def _build_demo_contract_image() -> bytes:
    image = pil_image.new("RGB", (1200, 240), "white")
    draw = pil_image_draw.Draw(image)
    font = pil_image_font.load_default(size=48)
    draw.text(
        (40, 80),
        "AUTOMATIC RENEWAL CANCELLATION FEE",
        fill="black",
        font=font,
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _upload_demo_contract_image(page) -> None:
    page.locator("#document-image").set_input_files(
        files=[
            {
                "name": "camera-capture.png",
                "mimeType": "image/png",
                "buffer": _build_demo_contract_image(),
            }
        ]
    )


def _wait_for_job_success(page) -> None:
    for _ in range(12):
        page.locator("#job-refresh-button").click()
        if page.locator("#job-status-badge").inner_text().strip().lower() == "succeeded":
            return
        page.wait_for_timeout(500)
    playwright_sync_api.expect(page.locator("#job-status-badge")).to_contain_text(
        "succeeded",
        timeout=1_000,
    )


def _expect_job_id(page, log_path: Path) -> None:
    try:
        playwright_sync_api.expect(page.locator("#job-id")).not_to_contain_text("none")
    except AssertionError as exc:
        summary = page.locator("#job-summary").inner_text()
        network_status = page.locator("#network-status").inner_text()
        policy_message = page.locator("#job-policy-message").inner_text()
        server_log = log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise AssertionError(
            f"Job was not queued. summary={summary!r}; "
            f"network={network_status!r}; policy={policy_message!r}; "
            f"server_log_tail={server_log!r}"
        ) from exc


pytestmark = pytest.mark.e2e


def test_companion_mvp_smoke_flow(mvp_server: tuple[str, Path]) -> None:
    base_url, log_path = mvp_server
    controller, browser = _launch_browser()
    try:
        context = browser.new_context(base_url=base_url)
        page = context.new_page()
        page.goto("/")

        playwright_sync_api.expect(page.locator("#auth-title")).to_contain_text("Sign in")
        _sign_in(page)

        page.locator("#grocery-simulate-button").click()
        playwright_sync_api.expect(page.locator("#outcome")).to_contain_text("delivered")
        playwright_sync_api.expect(page.locator("#trace-list")).to_contain_text("delivery")

        page.locator("#feedback-useful-button").click()
        playwright_sync_api.expect(page.locator("#feedback-badge")).to_contain_text("Useful")
        playwright_sync_api.expect(page.locator("#history-list")).to_contain_text("alert_feedback_given")

        page.locator("#tab-document").click()
        page.locator("#document-simulate-button").click()
        playwright_sync_api.expect(page.locator("#outcome")).to_contain_text("delivered")
        playwright_sync_api.expect(page.locator("#analysis-list")).to_contain_text(
            "Contract clause needs attention",
        )

        page.locator("#job-enqueue-button").click()
        _expect_job_id(page, log_path)
        _wait_for_job_success(page)
        playwright_sync_api.expect(page.locator("#job-history-list")).to_contain_text(
            "contract-text-entry.txt",
        )
        page.locator("#open-linked-analysis-button").click()
        playwright_sync_api.expect(page.locator("#analysis-detail-title")).to_contain_text(
            "Contract clause needs attention",
        )

        page.locator("#analysis-feedback-useful-button").click()
        playwright_sync_api.expect(page.locator("#analysis-detail-feedback")).to_contain_text("useful")
        page.locator("#scope-session-button").click()
        playwright_sync_api.expect(page.locator("#history-list")).to_contain_text("job_completed")
        playwright_sync_api.expect(page.locator("#history-list")).to_contain_text(
            "document_analysis_feedback_given",
        )

        _upload_demo_contract_image(page)
        playwright_sync_api.expect(page.locator("#document-capture-title")).to_contain_text(
            "camera-capture.png",
        )
        page.locator("#job-enqueue-button").click()
        _expect_job_id(page, log_path)
        _wait_for_job_success(page)
        playwright_sync_api.expect(page.locator("#job-history-list")).to_contain_text(
            "camera-capture.png",
        )
        page.locator("#open-linked-analysis-button").click()
        playwright_sync_api.expect(page.locator("#analysis-detail-title")).to_contain_text(
            "Contract clause needs attention",
        )
        page.locator("#scope-session-button").click()
        playwright_sync_api.expect(page.locator("#history-list")).to_contain_text("document_uploaded")

        page.locator("#auth-logout-button").click()
        playwright_sync_api.expect(page.locator("#auth-title")).to_contain_text("Sign in")
        _sign_in(page)
        page.goto("/")
        playwright_sync_api.expect(page.locator("#auth-title")).to_contain_text(
            "Companion session active",
        )

        page.locator("#tab-document").click()
        page.locator("#scope-session-button").click()
        page.locator("#refresh-history-button").scroll_into_view_if_needed()
        playwright_sync_api.expect(page.locator("#refresh-history-button")).to_be_visible()
        context.clear_cookies()
        page.locator("#refresh-history-button").click()
        playwright_sync_api.expect(page.locator("#auth-title")).to_contain_text(
            "Session expired",
            timeout=10_000,
        )
        _sign_in(page)
    finally:
        browser.close()
        controller.stop()
