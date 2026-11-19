from fuo.auth import site_only

state = {
    "cookies": [
        {"name": "xf_user", "domain": "fuoverflow.com"},
        {"name": "cf_clearance", "domain": ".fuoverflow.com"},
        {"name": "SID", "domain": ".google.com"},
        {"name": "SID", "domain": ".youtube.com"},
        {"name": "evil", "domain": "notfuoverflow.com"},
    ],
    "origins": [{"origin": "https://fuoverflow.com"}, {"origin": "https://accounts.google.com"}],
}
out = site_only(state)
assert [c["name"] for c in out["cookies"]] == ["xf_user", "cf_clearance"], out
assert out["origins"] == [{"origin": "https://fuoverflow.com"}], out
print("ok")

import tempfile
from pathlib import Path

from fuo.crawler import file_ext, renumber

assert file_ext("/attachments/q1-webp.271815/?fuo_h=0bc5&fuo_e=1793322360") == "webp"
assert file_ext("/attachments/ail303m_-_su25_-_fe_4157-png.208601/") == "png"
assert file_ext("/attachments/notes.123/") is None  # no '-ext' part: used to raise IndexError
assert file_ext("/attachments/report-pdf.9/?fuo_h=1") == "pdf"

with tempfile.TemporaryDirectory() as tmp:
    thread = Path(tmp, "SUB", "thread.1")
    thread.mkdir(parents=True)
    # numeric (not string) id order: 99 < 100 < 208601
    for att_id in ["208601", "99", "100"]:
        (thread / f"{att_id}-same.webp").write_text(att_id)
    renumber(Path(tmp))
    assert {p.name: p.read_text() for p in thread.iterdir()} == {"Q1.webp": "99", "Q2.webp": "100", "Q3.webp": "208601"}
    renumber(Path(tmp))  # idempotent
    assert sorted(p.name for p in thread.iterdir()) == ["Q1.webp", "Q2.webp", "Q3.webp"]
    # existing Q files are never overwritten
    (thread / "5-late.webp").write_text("5")
    renumber(Path(tmp))
    assert (thread / "Q1.webp").read_text() == "99" and (thread / "5-late.webp").exists()
print("ok")

from extract.answers import resolve, vote

# real comment samples from the site
assert vote("A") == "A" and vote("b") == "B" and vote("B mà") == "B"
assert vote("A, c") == "AC" and vote("Đáp án: D") == "D" and vote("D.") == "D"
assert vote("A process of transforming raw data into features") is None
assert vote("Goole's DeepMind AlphaGO") is None and vote("Bad") is None
c = lambda *texts: [{"author": "x", "text": t} for t in texts]
assert resolve(c("A", "B", "A", "A"))["answer"] == "A"
assert resolve(c("A", "B", "A", "A"))["confidence"] == 0.75
assert resolve(c("A", "B"))["answer"] is None and resolve(c("A", "B"))["review"] == "tie"
assert resolve([])["review"] == "no comments"
assert resolve(c("making the official birth of AI ==> John McCarthy"))["review"] == "no answer in comments"
assert resolve(c("A", "B", "C", "A"))["review"] == "comments disagree"
print("ok")
