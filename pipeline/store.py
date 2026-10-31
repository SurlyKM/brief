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


def merge_day(data_dir, today, new_items, cap):
    """Add new items to today's file, re-rank, and keep the best `cap`."""
    path = Path(data_dir) / f"{today}.json"
    day = read_json(path, {"date": today, "items": []})
    combined = {i["id"]: i for i in day["items"]}
    for i in new_items:
        combined[i["id"]] = i
    ranked = sorted(
        combined.values(),
        key=lambda i: (i["relevance"], i["published"]),
        reverse=True,
    )[:cap]
    write_json(path, {"date": today, "items": ranked})
    return len(ranked)


def rebuild_index(data_dir):
    """List every day file so the page knows which dates exist."""
    dates = sorted(
        (p.stem for p in Path(data_dir).iterdir() if DATE_FILE.match(p.name)),
        reverse=True,
    )
    write_json(
        Path(data_dir) / "index.json",
        {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "dates": dates},
    )
