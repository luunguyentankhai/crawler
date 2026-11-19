"""Pick an answer for each question from the comments under its image (majority vote)."""

import json
import logging
import re
from collections import Counter
from pathlib import Path

log = logging.getLogger(__name__)

# Optional "đáp án:" prefix, then either joined capitals ("AC") or letters separated by , & / + ("a, c").
VOTE = re.compile(
    r"(?i:đáp án|đa|answer|ans)?[\s:=]*([A-F]{2,4}|[A-Fa-f](?:\s*[,&/+]\s*[A-Fa-f])*)\b(.*)", re.S
)
MIN_CONFIDENCE = 0.7


def vote(text: str) -> str | None:
    """'b' -> 'B', 'A, c' -> 'AC', 'B mà' -> 'B'; prose such as 'A process of ...' -> None."""
    m = VOTE.match(text.strip())
    if not m:
        return None
    rest = m[2].strip()
    # a long trailing sentence means the letter was just the first word of prose
    if rest and rest[0].isalnum() and len(rest) > 12:
        return None
    return "".join(sorted(set(m[1].upper()) - set(" ,&/+")))


def resolve(comments: list[dict]) -> dict:
    """Return answer (None when no votes or a tie), vote counts, confidence and a review reason."""
    votes = Counter(v for c in comments if (v := vote(c["text"])))
    result = {"answer": None, "votes": dict(votes), "confidence": 0.0, "review": None}
    if not votes:
        result["review"] = "no answer in comments" if comments else "no comments"
        return result
    (top, n), *others = votes.most_common()
    result["confidence"] = round(n / votes.total(), 2)
    if others and others[0][1] == n:
        result["review"] = "tie"
        return result
    result["answer"] = top
    if result["confidence"] < MIN_CONFIDENCE:
        result["review"] = "comments disagree"
    return result


def build(subject_dir: Path) -> None:
    """Write answers.json per thread and <subject>/review.md listing questions to check by hand."""
    review = []
    for comments_file in sorted(subject_dir.glob("*/comments.json")):
        folder = comments_file.parent
        answers = {}
        for q, comments in json.loads(comments_file.read_text()).items():
            answers[q] = resolve(comments) | {"comments": comments}
            if reason := answers[q]["review"]:
                image = next(folder.glob(f"{q}.*"), folder / q)
                texts = "; ".join(c["text"].replace("\n", " ").replace("|", "\\|")[:80] for c in comments[:5]) or "-"
                review.append(f"| {folder.name} | {q} | {reason} | {answers[q]['votes']} | "
                              f"[{image.name}]({image.relative_to(subject_dir)}) | {texts} |")
        (folder / "answers.json").write_text(json.dumps(answers, ensure_ascii=False, indent=1))
    header = ["# Questions to review", "", "| Thread | Q | Reason | Votes | Image | Comments |", "|---|---|---|---|---|---|"]
    (subject_dir / "review.md").write_text("\n".join(header + review) + "\n")
    log.info("%s: %d questions to review", subject_dir.name, len(review))
    print(f"{subject_dir.name}: {len(review)} questions to review in {subject_dir / 'review.md'}")
