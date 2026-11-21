"""Step 4: keep results on disk as plain JSON files.

Layout inside the data directory (served as-is by GitHub Pages):

    seen.json          ids already processed, so nothing is paid for twice
    index.json         list of available dates, newest first
    YYYY-MM-DD.json    one file per day: {"date": ..., "items": [...]}
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEEN_KEEP_DAYS = 14   # longer than the lookback window, so repeats stay caught
DATE_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


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


def load_seen(data_dir):
    return read_json(Path(data_dir) / "seen.json", {})


def save_seen(data_dir, seen, today):
    """Record new ids, then drop entries older than SEEN_KEEP_DAYS."""
    cutoff = (datetime.fromisoformat(today) - timedelta(days=SEEN_KEEP_DAYS)).date().isoformat()
    kept = {k: v for k, v in seen.items() if v >= cutoff}
    write_json(Path(data_dir) / "seen.json", kept)


def merge_day(data_dir, today, new_items, cap, max_papers=None):
    """Add new items to today's file without removing anything already there.

    Stories already published today are locked in, so a story you read in
    the morning is still there in the evening. New items only fill the slots
    left under `cap`, best first, and papers stop at `max_papers` so blog
    posts always have room. Quiet days simply end up with fewer stories.
    """
    path = Path(data_dir) / f"{today}.json"
    day = read_json(path, {"date": today, "items": []})
    kept = list(day["items"])
    have = {i["id"] for i in kept}
    papers = sum(i.get("kind") == "paper" for i in kept)

    def sort_key(i):
        return (i["relevance"], i["published"])

    for item in sorted(new_items, key=sort_key, reverse=True):
        if len(kept) >= cap:
            break
        if item["id"] in have:
            continue
        if item.get("kind") == "paper":
            if max_papers is not None and papers >= max_papers:
                continue
            papers += 1
        kept.append(item)
        have.add(item["id"])

    kept.sort(key=sort_key, reverse=True)
    write_json(path, {"date": today, "items": kept})
    return len(kept)


def rebuild_index(data_dir, topics=None):
    """List every day file so the page knows which dates exist, plus the full
    topic list from interests.yml so the filter can always show every topic."""
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    dates = sorted(
        (p.stem for p in Path(data_dir).iterdir() if DATE_FILE.match(p.name)),
        reverse=True,
    )
    write_json(
        Path(data_dir) / "index.json",
        {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "topics": list(topics or []),
         "dates": dates},
    )
