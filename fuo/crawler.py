import json
import logging
import mimetypes
import re
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn
from urllib.parse import urlparse

from playwright.sync_api import Page, Response
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from tqdm import tqdm

from fuo.auth import is_logged_in
from fuo.config import BASE_URL, OUT_DIR

DELAY = 1.0  # seconds between requests
RETRIES = 3  # page loads per URL before giving up
BACKOFF = 5.0  # seconds before the first retry, doubled each time
OLD_NAME = re.compile(
    r"^(\d+)-.*(\.\w+)$"
)  # '<attachment id>-<name>.<ext>' from earlier crawls

log = logging.getLogger(__name__)


def fail(msg: str) -> NoReturn:
    log.error(msg)
    sys.exit(msg)


def file_ext(href: str) -> str | None:
    """'/attachments/q1-webp.271815/?fuo_h=..' -> 'webp'; None when the slug has no '-<ext>' part."""
    slug = urlparse(href).path.rstrip("/").rsplit("/", 1)[-1]
    stem = slug.rsplit(".", 1)[0]
    return stem.rsplit("-", 1)[1] if "-" in stem else None


def goto_retry(page: Page, url: str) -> Response | None:
    """page.goto with exponential backoff (5s, 10s) on timeout; raises after the last try."""
    for attempt in range(RETRIES):
        try:
            return page.goto(url)
        except PlaywrightTimeout:
            if attempt == RETRIES - 1:
                raise
            wait = BACKOFF * 2**attempt
            log.warning("timeout on %s, retry in %.0fs", url, wait)
            time.sleep(wait)


def visit_pages(page: Page, url: str | None) -> Iterator[None]:
    """Open url and every following page of a paginated forum/thread."""
    while url:
        resp = goto_retry(page, url)
        time.sleep(DELAY)
        if resp and resp.status == 404:
            log.warning("not found: %s", url)
            tqdm.write(f"  not found: {url}")
            return
        if not is_logged_in(page):
            fail(f"Logged out at {page.url}. Run: uv run main.py login")
        yield
        nxt = page.locator("a.pageNav-jump--next").first
        url = BASE_URL + nxt.get_attribute("href") if nxt.count() else None


def thread_urls(page: Page, subject: str) -> list[str]:
    urls = []
    for _ in visit_pages(page, f"{BASE_URL}/forums/{subject}/"):
        links = page.locator(".structItem-title a[href*='/threads/']").all()
        urls += [BASE_URL + a.get_attribute("href") for a in links]
    return list(dict.fromkeys(urls))


def download_thread(page: Page, url: str, dest: Path) -> tuple[int, int]:
    """Save attachments as Q1, Q2, ... in page order (= upload order). Returns (new, found).

    Also writes meta.json mapping each Q<n> to its attachment and media (comments) page.
    """
    new = found = 0
    meta = []
    for _ in visit_pages(page, url):
        anchors = page.locator(".attachmentList a[href*='/attachments/']").all()
        # attachment href -> media page; media href may be missing on some anchors
        links = {}
        for a in anchors:
            media = a.get_attribute("data-lb-sidebar-href")
            links.setdefault(a.get_attribute("href"), media and media.split("?")[0])
        log.info("%s: %d attachments on %s", dest.name, len(links), page.url)
        for href, media in tqdm(links.items(), desc=dest.name, unit="img", leave=False):
            found += 1
            meta.append({"q": found, "attachment": href.split("?")[0], "media": media})
            ext = file_ext(href)
            if ext and (dest / f"Q{found}.{ext}").exists():
                continue
            resp = page.context.request.get(BASE_URL + href)
            ctype = resp.headers.get("content-type", "")
            # any file type is kept (images, PDFs, ...); an HTML page means a login/challenge page
            if not resp.ok or ctype.startswith("text/html"):
                log.warning("skipped %s: %s %s", href, resp.status, ctype)
                tqdm.write(f"  skipped Q{found}: {resp.status} {ctype}")
                continue
            if ext is None:  # slug has no '-<ext>': take it from the content type
                ext = (mimetypes.guess_extension(ctype.split(";")[0]) or ".bin")[1:]
            path = dest / f"Q{found}.{ext}"
            if path.exists():
                continue

            dest.mkdir(parents=True, exist_ok=True)
            body = resp.body()
            path.write_bytes(body)
            log.info("saved %s (%d bytes)", path, len(body))
            new += 1
            time.sleep(DELAY)
    if not found:
        log.warning("%s: no attachments", url)
    else:
        (dest / "meta.json").write_text(
            json.dumps({"url": url, "images": meta}, indent=1)
        )
    log.info("%s: new=%d skipped=%d found=%d", dest.name, new, found - new, found)
    return new, found


def crawl(page: Page, subject: str, limit: int | None = None) -> None:
    """Download every thread attachment of /forums/<subject>/ into images/<subject>/<thread>/."""
    urls = thread_urls(page, subject)[:limit]
    log.info("%s: %d threads", subject, len(urls))
    if not urls:
        msg = f"{subject}: 0 threads, check the subject code (case-sensitive) at {BASE_URL}/categories/subjects/"
        log.warning(msg)
        print(msg)
        return
    total_new = total_found = 0
    for url in tqdm(urls, desc=subject, unit="thread"):
        thread = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
        try:
            new, found = download_thread(page, url, OUT_DIR / subject / thread)
        except PlaywrightTimeout:  # no meta.json is written, so a rerun redoes this thread
            log.error("gave up on %s after %d timeouts", url, RETRIES)
            tqdm.write(f"  FAILED {thread}: timeout, rerun to retry")
            continue
        total_new += new
        total_found += found
        tqdm.write(f"  {thread}: {new} new / {found} images")
    log.info(
        "%s done: threads=%d new=%d found=%d",
        subject,
        len(urls),
        total_new,
        total_found,
    )


def media_comments(page: Page, media: str) -> list[dict]:
    comments = []
    for _ in visit_pages(page, BASE_URL + media):
        for c in page.locator("article.js-comment").all():
            body = c.locator(".bbWrapper").first
            comments.append(
                {
                    "author": c.get_attribute("data-author"),
                    "text": body.inner_text().strip() if body.count() else "",
                }
            )
    return comments


def fetch_comments(page: Page, subject: str) -> None:
    """Write comments.json ({"Q1": [{author, text}], ...}) for every crawled thread of a subject."""
    threads = sorted(
        p.parent
        for p in (OUT_DIR / subject).glob("*/meta.json")
        if not (p.parent / "comments.json").exists()
    )
    log.info("%s: %d threads need comments", subject, len(threads))
    for folder in tqdm(threads, desc=f"{subject} comments", unit="thread"):
        images = json.loads((folder / "meta.json").read_text())["images"]
        comments = {}
        try:
            for img in tqdm(images, desc=folder.name, unit="img", leave=False):
                comments[f"Q{img['q']}"] = (
                    media_comments(page, img["media"]) if img["media"] else []
                )
        except PlaywrightTimeout:  # no comments.json is written, so a rerun redoes this thread
            log.error("gave up on comments of %s after %d timeouts", folder.name, RETRIES)
            tqdm.write(f"  FAILED {folder.name}: timeout, rerun to retry")
            continue
        (folder / "comments.json").write_text(
            json.dumps(comments, ensure_ascii=False, indent=1)
        )
        empty = sum(not c for c in comments.values())
        log.info(
            "%s: comments for %d images, %d without comments",
            folder.name,
            len(comments),
            empty,
        )
        tqdm.write(
            f"  {folder.name}: {len(comments) - empty}/{len(comments)} images have comments"
        )


def renumber(root: Path) -> None:
    """Rename '<id>-<name>.<ext>' files from earlier crawls to Q1, Q2, ... in attachment-id order."""
    for folder in sorted({p.parent for p in root.rglob("*") if OLD_NAME.match(p.name)}):
        files = sorted(
            (p for p in folder.iterdir() if OLD_NAME.match(p.name)),
            key=lambda p: int(OLD_NAME.match(p.name)[1]),
        )
        targets = [
            folder / f"Q{i}{OLD_NAME.match(p.name)[2]}" for i, p in enumerate(files, 1)
        ]
        if clash := [t.name for t in targets if t.exists()]:
            log.error("%s: skipped, already has %s", folder, clash[:3])
            print(f"skipped {folder}: already has {clash[:3]}")
            continue
        for src, dst in zip(files, targets):
            src.rename(dst)
            log.info("renamed %s -> %s", src, dst.name)
        print(f"{folder}: renamed {len(files)} files")
