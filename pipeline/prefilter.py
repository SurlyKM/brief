"""Step 2: cheap keyword scoring, so we only pay to analyse likely matches.

This runs locally with no model call. The model makes the real relevance
judgement later; this step just throws away obvious misses (hundreds of
arXiv papers a day) and ranks the rest.
"""
import re


def compile_topics(topics):
    """Turn each topic's keyword list into one case-insensitive regex.

    The lookarounds make matches whole-word, so 'rop' does not fire on
    'property' and 'vr' does not fire on 'every'.
    """
    compiled = []
    for t in topics:
        patterns = [
            r"(?<![\w])" + re.escape(k.lower()) + r"(?![\w])"
            for k in t["keywords"]
        ]
        compiled.append({
            "label": t["label"],
            "weight": t.get("weight", 1),
            "regex": re.compile("|".join(patterns), re.IGNORECASE),
        })
    return compiled


def score_item(item, topics):
    """Return (score, matched_topic_labels).

    Per topic: number of distinct keywords found, capped at 3, times the topic
    weight. Title hits count double because titles are more deliberate than
    body text. The source bonus only applies if something matched at all.
    """
    title = item["title"].lower()
    body = item["text"].lower()
    total, labels = 0, []
    for t in topics:
        in_title = set(m.lower() for m in t["regex"].findall(title))
        in_body = set(m.lower() for m in t["regex"].findall(body))
        hits = len(in_title) * 2 + len(in_body - in_title)
        if hits:
            total += t["weight"] * min(hits, 3)
            labels.append(t["label"])
    if total == 0:
        return 0, []
    return total + item.get("bonus", 0), labels


def shortlist(items, topics, limit):
    """Score everything, drop zero-scorers, return the best `limit`."""
    scored = []
    for it in items:
        s, labels = score_item(it, topics)
        if s > 0:
            scored.append({**it, "prefilter": s, "hint_topics": labels})
    scored.sort(key=lambda x: (x["prefilter"], x["published"]), reverse=True)
    return scored[:limit]
