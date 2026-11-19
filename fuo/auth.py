import json
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright

from fuo.config import AUTH_FILE, BASE_URL, HEADLESS, PROFILE_DIR, browser_path

SITE_HOST = urlparse(BASE_URL).hostname


def is_logged_in(page: Page) -> bool:
    return page.locator('html[data-logged-in="true"]').count() > 0


def site_only(state: dict) -> dict:
    """Keep only the site's cookies/localStorage; drop Google/YouTube session cookies."""
    return {
        "cookies": [c for c in state["cookies"] if c["domain"].lstrip(".") == SITE_HOST],
        "origins": [o for o in state["origins"] if urlparse(o["origin"]).hostname == SITE_HOST],
    }


def login() -> None:
    """Manual login: the user signs in with Google in a plain Brave window (no automation
    attached), closes it, then the site session is read from that profile into AUTH_FILE."""
    print("Log in with Google in the Brave window, then close the window.")
    # Restored tabs would hit the site concurrently with the same session cookie,
    # and the site logs out a session used from two places at once.
    shutil.rmtree(PROFILE_DIR / "Default" / "Sessions", ignore_errors=True)
    subprocess.run(
        [browser_path(), f"--user-data-dir={PROFILE_DIR.resolve()}", "--no-first-run", f"{BASE_URL}/login/"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    shutil.rmtree(PROFILE_DIR / "Default" / "Sessions", ignore_errors=True)
    with sync_playwright() as p:
        # Only read the cookie store; loading a page here would rotate the session.
        context = p.chromium.launch_persistent_context(
            PROFILE_DIR, executable_path=browser_path(), headless=True
        )
        state = site_only(context.storage_state())
        context.close()
    if not any(c["name"] == "xf_user" for c in state["cookies"]):
        sys.exit("No site login cookie found. Run again: uv run main.py login")
    AUTH_FILE.write_text(json.dumps(state))
    print(f"Session saved to {AUTH_FILE}. Verify with: uv run main.py check")


@contextmanager
def open_session() -> Iterator[Page]:
    """Yield a logged-in page on BASE_URL; exit if the saved session is missing or expired.

    The site rotates its session cookie, so the updated cookies are written back to
    AUTH_FILE on exit; otherwise the next run would present a revoked session.
    """
    if not AUTH_FILE.exists():
        sys.exit(f"{AUTH_FILE} missing. Run: uv run main.py login")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=browser_path(), headless=HEADLESS)
        try:
            context = browser.new_context(storage_state=AUTH_FILE)
            page = context.new_page()
            page.goto(BASE_URL)
            if not is_logged_in(page):
                sys.exit(f"Session expired ({page.url}). Run: uv run main.py login")
            try:
                yield page
            finally:
                AUTH_FILE.write_text(json.dumps(site_only(context.storage_state())))
        finally:
            browser.close()
