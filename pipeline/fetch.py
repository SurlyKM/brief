"""Step 1: pull raw items from arXiv (API) and blog feeds (RSS/Atom).

Every source is turned into the same simple dict, so later steps do not care
where an item came from:

    {id, title, url, source, kind, published, text, bonus}
"""
import hashlib
import html
import re
import socket
import sys
import time
from datetime import datetime, timezone

import feedparser

ARXIV_API = "https://export.arxiv.org/api/query"
USER_AGENT = "personal-brief/1.0 (reading list bot)"
TEXT_LIMIT = 2000          # characters of article text kept per item
ARXIV_DELAY_SECONDS = 3    # arXiv asks for no more than 1 request per 3 seconds

# feedparser has no timeout option of its own, so set one for all sockets.
socket.setdefaulttimeout(30)


def log(msg):
    print(msg, file=sys.stderr)


def clean(text):
    """Strip HTML tags, decode entities, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def item_id(url):
    """Stable short id so we can recognise an item we have already handled."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def entry_time(entry):
    """Best available timestamp for a feed entry, as an aware UTC datetime."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def canonical_arxiv_url(url):
    """http://arxiv.org/abs/2501.01234v2 -> https://arxiv.org/abs/2501.01234"""
    url = url.replace("http://", "https://")
    return re.sub(r"v\d+$", "", url)


def fetch_arxiv(cfg, cutoff):
    """One API call per category, newest first. Papers in several categories
    are de-duplicated by canonical URL."""
    items = {}
    cats = cfg.get("categories", [])
    for n, cat in enumerate(cats):
        if n:
            time.sleep(ARXIV_DELAY_SECONDS)
        url = (
            f"{ARXIV_API}?search_query=cat:{cat}"
            f"&sortBy=submittedDate&sortOrder=descending"
            f"&max_results={int(cfg.get('max_per_category', 60))}"
        )
        feed = feedparser.parse(url, agent=USER_AGENT)
        if not feed.entries:
            log(f"[arxiv] {cat}: no entries (bozo={feed.get('bozo')})")
            continue
        for e in feed.entries:
            when = entry_time(e)
            if when is None or when < cutoff:
                continue
            link = canonical_arxiv_url(e.get("id") or e.get("link", ""))
            if not link or link in items:
                continue
            items[link] = {
                "id": item_id(link),
                "title": clean(e.get("title")),
                "url": link,
                "source": "arXiv " + cat,
                "kind": "paper",
                "published": when.isoformat(),
                "text": clean(e.get("summary"))[:TEXT_LIMIT],
                "bonus": 0,
            }
        log(f"[arxiv] {cat}: {len(feed.entries)} fetched")
    return list(items.values())


def fetch_feeds(feeds, cutoff):
    """One request per blog feed. A broken feed is logged and skipped."""
    items = []
    for f in feeds:
        feed = feedparser.parse(f["url"], agent=USER_AGENT)
        if not feed.entries:
            log(f"[feed] {f['name']}: no entries (bozo={feed.get('bozo')}), skipped")
            continue
        kept = 0
        undated = 0
        for e in feed.entries:
            when = entry_time(e)
            link = e.get("link")
            if not link:
                continue
            if when is None:
                # No usable date, so we cannot tell new from old. Some feeds
                # (Objective-See) keep years-old posts at the bottom with no
                # date at all, so we skip these rather than pass them off as news.
                undated += 1
                continue
            if when < cutoff:
                continue
            # Prefer full content when the feed includes it, else the summary.
            body = ""
            if e.get("content"):
                body = e["content"][0].get("value", "")
            body = body or e.get("summary", "")
            items.append({
                "id": item_id(link),
                "title": clean(e.get("title")),
                "url": link,
                "source": f["name"],
                "kind": "article",
                "published": (when or datetime.now(timezone.utc)).isoformat(),
                "text": clean(body)[:TEXT_LIMIT],
                "bonus": int(f.get("bonus", 0)),
            })
            kept += 1
        log(f"[feed] {f['name']}: {kept} recent, {undated} undated skipped")
    return items
