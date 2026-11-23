"""Step 4: keep results on disk as plain JSON files.

Layout inside the data directory (served as-is by GitHub Pages):

    seen.json                     ids already processed, so nothing is paid for twice
    index.json                    every edition, newest first, plus the topic list
    editions/2026-11-22T2007Z.json   one file per run: {"published": ..., "items": [...]}

Why editions and not days: a "day" depends on where the reader is. Each run
is saved with its exact UTC publish time, and the page groups editions into
days using the reader's own time zone, so Sydney and Denver both see the
right "Today".
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEEN_KEEP_DAYS = 14   # longer than the lookback window, so repeats stay caught
EDITIONS = "editions"
STAMP = "%Y-%m-%dT%H%MZ"                       # file name, e.g. 2026-11-22T2007Z
LEGACY_DAY_FILE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )


# ---------- Seen ids ----------

def load_seen(data_dir):
    return read_json(Path(data_dir) / "seen.json", {})


def save_seen(data_dir, seen, today):
    """Record new ids, then drop entries older than SEEN_KEEP_DAYS."""
    cutoff = (datetime.fromisoformat(today) - timedelta(days=SEEN_KEEP_DAYS)).date().isoformat()
    kept = {k: v for k, v in seen.items() if v >= cutoff}
    write_json(Path(data_dir) / "seen.json", kept)


# ---------- Editions ----------

def select_for_edition(items, cap, max_papers=None):
    """Best items first, up to `cap`, with at most `max_papers` papers so blog
    posts always get room."""
    picked, papers = [], 0
    for it in sorted(items, key=lambda i: (i["relevance"], i["published"]), reverse=True):
        if len(picked) >= cap:
            break
        if it.get("kind") == "paper":
            if max_papers is not None and papers >= max_papers:
                continue
            papers += 1
        picked.append(it)
    return picked


def write_edition(data_dir, when, items):
    """Save one run's stories. Nothing is written for an empty run, so the
    page never shows a blank day."""
    if not items:
        return None
    when = when.astimezone(timezone.utc)
    eid = when.strftime(STAMP)
    path = Path(data_dir) / EDITIONS / f"{eid}.json"
    if path.exists():                      # two runs in the same minute: merge
        items = read_json(path, {"items": []})["items"] + items
    write_json(path, {"published": when.isoformat(timespec="seconds"), "items": items})
    return eid


def list_editions(data_dir):
    """[{id, published, count}] newest first."""
    out = []
    for p in sorted((Path(data_dir) / EDITIONS).glob("*.json"), reverse=True):
        d = read_json(p, None)
        if d and d.get("items"):
            out.append({"id": p.stem, "published": d["published"], "count": len(d["items"])})
    return out


def editions_between(data_dir, start, end):
    """All stories from editions published in [start, end), as aware datetimes."""
    items, seen = [], set()
    for e in reversed(list_editions(data_dir)):
        when = datetime.fromisoformat(e["published"])
        if start <= when < end:
            for it in read_json(Path(data_dir) / EDITIONS / f"{e['id']}.json", {"items": []})["items"]:
                if it["id"] not in seen:
                    seen.add(it["id"])
                    items.append({**it, "edition": e["published"]})
    return items


def migrate_legacy(data_dir):
    """One-off: turn old YYYY-MM-DD.json day files into editions, then delete
    them. Each is stamped at 12:00 UTC on its date, which is late evening in
    Sydney and early morning in US Mountain time, so it lands on the same
    calendar date for readers in both places. Empty day files are dropped."""
    moved = 0
    for p in sorted(Path(data_dir).glob("*.json")):
        m = LEGACY_DAY_FILE.match(p.name)
        if not m:
            continue
        items = read_json(p, {"items": []}).get("items", [])
        if items:
            when = datetime.fromisoformat(m.group(1) + "T12:00:00+00:00")
            write_edition(data_dir, when, items)
            moved += 1
        p.unlink()
    return moved


def rebuild_index(data_dir, topics=None):
    """Every edition (newest first) plus the full topic list from interests.yml."""
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    write_json(
        Path(data_dir) / "index.json",
        {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "topics": list(topics or []),
         "editions": list_editions(data_dir)},
    )
