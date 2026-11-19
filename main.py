import argparse
import logging
import sys
import time
from pathlib import Path

from fuo.auth import login, open_session
from fuo.config import OUT_DIR
from extract.answers import build
from fuo.crawler import crawl, fetch_comments, renumber

SUBJECTS_FILE = Path("subjects.txt")


def setup_logging() -> None:
    """One log file per run in logs/; the console keeps only the tqdm bars."""
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        filename=f"logs/crawl-{time.strftime('%Y%m%d-%H%M%S')}.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def check(args: argparse.Namespace) -> None:
    with open_session() as page:
        print(f"Logged in: {page.title()}")


def run_crawl(args: argparse.Namespace) -> None:
    setup_logging()
    with open_session() as page:
        for subject in args.subjects:
            crawl(page, subject, args.limit)


def run_comments(args: argparse.Namespace) -> None:
    setup_logging()
    with open_session() as page:
        for subject in args.subjects:
            fetch_comments(page, subject)


def run_answers(args: argparse.Namespace) -> None:
    setup_logging()
    for subject in args.subjects:
        build(OUT_DIR / subject)


def run_all(args: argparse.Namespace) -> None:
    """crawl -> comments -> answers in one session; no subjects given = read SUBJECTS_FILE."""
    subjects = args.subjects
    if not subjects:
        if not SUBJECTS_FILE.exists():
            sys.exit(f"Give subject codes, or create {SUBJECTS_FILE} (one per line, # comments)")
        lines = (line.strip() for line in SUBJECTS_FILE.read_text().splitlines())
        subjects = [line for line in lines if line and not line.startswith("#")]
    setup_logging()
    with open_session() as page:
        for subject in subjects:
            crawl(page, subject, args.limit)
        for subject in subjects:
            fetch_comments(page, subject)
    for subject in subjects:
        build(OUT_DIR / subject)


def run_renumber(args: argparse.Namespace) -> None:
    setup_logging()
    renumber(args.root)


def main() -> None:
    parser = argparse.ArgumentParser(description="fuoverflow.com image crawler")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="manual Google login, saves auth.json").set_defaults(func=lambda _: login())
    sub.add_parser("check", help="verify the saved session still works").set_defaults(func=check)
    p = sub.add_parser("crawl", help="download images of subjects, e.g. crawl CSI106 PRF192")
    p.add_argument("subjects", nargs="+", help="subject codes as in /forums/<CODE>/")
    p.add_argument("--limit", type=int, help="max threads per subject")
    p.set_defaults(func=run_crawl)
    p = sub.add_parser("comments", help="download image comments of crawled subjects (needs meta.json)")
    p.add_argument("subjects", nargs="+")
    p.set_defaults(func=run_comments)
    p = sub.add_parser("answers", help="offline: pick answers from comments, write answers.json + review.md")
    p.add_argument("subjects", nargs="+")
    p.set_defaults(func=run_answers)
    p = sub.add_parser("all", help="crawl + comments + answers; no subjects = every code in subjects.txt")
    p.add_argument("subjects", nargs="*")
    p.add_argument("--limit", type=int, help="max threads per subject")
    p.set_defaults(func=run_all)
    p = sub.add_parser("renumber", help="rename '<id>-name' files from older crawls to Q1, Q2, ...")
    p.add_argument("root", nargs="?", type=Path, default=OUT_DIR)
    p.set_defaults(func=run_renumber)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
