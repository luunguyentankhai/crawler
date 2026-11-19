import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ["FUO_BASE_URL"].rstrip("/")
BROWSER_PATH = os.getenv("BROWSER_PATH")
# Chromium-based browsers only, Brave first
PATH_NAMES = (
    "brave", "brave-browser", "google-chrome-stable", "google-chrome", "chrome",
    "chromium", "chromium-browser", "microsoft-edge", "vivaldi",
)
MAC_APPS = ("Brave Browser", "Google Chrome", "Chromium", "Microsoft Edge", "Vivaldi")
WIN_EXES = (
    "BraveSoftware/Brave-Browser/Application/brave.exe",
    "Google/Chrome/Application/chrome.exe",
    "Chromium/Application/chrome.exe",
    "Microsoft/Edge/Application/msedge.exe",
    "Vivaldi/Application/vivaldi.exe",
)


def install_locations() -> list[Path]:
    """Where browsers install themselves on this OS (they are often not on PATH on macOS/Windows)."""
    if sys.platform == "darwin":
        apps = (Path("/Applications"), Path.home() / "Applications")
        return [a / f"{n}.app/Contents/MacOS/{n}" for a in apps for n in MAC_APPS]
    if sys.platform == "win32":
        roots = (os.environ.get(v) for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"))
        return [Path(r) / exe for r in roots if r for exe in WIN_EXES]
    return []


def browser_path() -> str:
    """BROWSER_PATH if set, else the first Chromium-based browser found on this machine."""
    if BROWSER_PATH:
        return BROWSER_PATH
    for name in PATH_NAMES:
        if found := shutil.which(name):
            return found
    for path in install_locations():
        if path.exists():
            return str(path)
    sys.exit(
        "No Chromium-based browser found (looked for Brave, Chrome, Chromium, Edge, Vivaldi).\n"
        "Install one, or set BROWSER_PATH in .env to its executable.\n"
        "To find the path: open your browser, go to chrome://version (brave://version, edge://version)\n"
        "and copy the 'Executable Path' line."
    )
# HEADLESS=0 shows the browser window (useful when the site serves a challenge page headless)
HEADLESS = os.getenv("HEADLESS", "1") != "0"
AUTH_FILE = Path("auth.json")
PROFILE_DIR = Path(".brave-profile")
OUT_DIR = Path("images")
