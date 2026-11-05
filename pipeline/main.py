"""Entry point. Run with:  python -m pipeline.main

Flow: fetch -> skip already-seen -> keyword shortlist -> model analysis ->
filter by relevance -> merge into today's file -> update index.

Testing flags (no network or API key needed):
    --fixture FILE   read raw items from a JSON file instead of fetching
    --fake-llm       use a fake analyser instead of the real model
    --data-dir DIR   write output somewhere other than docs/data
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from . import fetch, prefilter, store, summarise

ROOT = Path(__file__).resolve().parent.parent


def log(msg):
    print(msg, file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--fake-llm", action="store_true")
    ap.add_argument("--data-dir", default=str(ROOT / "docs" / "data"))
    args = ap.parse_args()

    sources = yaml.safe_load((ROOT / "sources.yml").read_text())
    interests = yaml.safe_load((ROOT / "interests.yml").read_text())
    sel = interests["selection"]
    topics = prefilter.compile_topics(interests["topics"])
    labels = [t["label"] for t in interests["topics"]]

    now = datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo(sel["timezone"])).date().isoformat()
    cutoff = now - timedelta(hours=sources.get("lookback_hours", 72))

    # 1. Fetch
    if args.fixture:
        raw = json.loads(Path(args.fixture).read_text())
    else:
        raw = fetch.fetch_arxiv(sources.get("arxiv", {}), cutoff)
        raw += fetch.fetch_feeds(sources.get("feeds", []), cutoff)
    log(f"fetched {len(raw)} items")

    # 2. Drop anything already processed on an earlier run
    seen = store.load_seen(args.data_dir)
    fresh = [i for i in raw if i["id"] not in seen]
    log(f"{len(fresh)} not seen before")

    # 3. Cheap local shortlist
    short = prefilter.shortlist(fresh, topics, sel["candidates_per_run"],
                                sel.get("candidates_per_kind"))
    log(f"{len(short)} shortlisted for analysis")
    if not short:
        store.rebuild_index(args.data_dir, labels)
        return

    # 4. Model analysis
    if args.fake_llm:
        analysis = summarise.fake_analyse(short, labels)
    else:
        analysis = summarise.analyse(
            short, labels, sel["batch_size"], summarise.make_client()
        )

    # 5. Keep only items that clear the relevance bar
    keep, scored_ids = [], []
    for it in short:
        a = analysis.get(it["id"])
        if a is None:
            continue                      # model failed: retry next run
        scored_ids.append(it["id"])
        if a["relevance"] >= sel["min_relevance"]:
            keep.append({
                "id": it["id"], "title": it["title"], "url": it["url"],
                "source": it["source"], "kind": it["kind"],
                "published": it["published"], "topics": a["topics"],
                "relevance": a["relevance"], "summary": a["summary"],
                "takeaway": a["takeaway"],
            })
    log(f"{len(keep)} cleared the relevance bar ({len(scored_ids)} scored)")

    # 6. Save
    total = store.merge_day(args.data_dir, today, keep, sel["max_items_per_day"],
                            sel.get("min_papers_per_day", 0))
    for i in scored_ids:
        seen[i] = today
    store.save_seen(args.data_dir, seen, today)
    store.rebuild_index(args.data_dir, labels)
    log(f"{today}: {total} items in today's brief")


if __name__ == "__main__":
    main()
