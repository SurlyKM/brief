"""Unit tests for the pure logic. Run with:  python -m pytest tests"""
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import prefilter, store, summarise  # noqa: E402

INTERESTS = yaml.safe_load((ROOT / "interests.yml").read_text())
TOPICS = prefilter.compile_topics(INTERESTS["topics"])
LABELS = [t["label"] for t in INTERESTS["topics"]]


def item(title, text="", bonus=0):
    return {"title": title, "text": text, "bonus": bonus, "published": "2026-10-30T00:00:00+00:00"}


def test_irrelevant_item_scores_zero_even_with_bonus():
    score, labels = prefilter.score_item(item("Sourdough tips", "flour and water", bonus=5), TOPICS)
    assert score == 0 and labels == []


def test_whole_word_matching():
    # 'rop' and 'vr' must not match inside 'property' or 'every'
    score, _ = prefilter.score_item(item("Every property matters"), TOPICS)
    assert score == 0


def test_macos_exploit_scores_high_and_tags_topics():
    score, labels = prefilter.score_item(
        item("macOS XNU use-after-free exploit", "sandbox escape", bonus=3), TOPICS)
    assert score > 10
    assert "Exploits" in labels and "macOS and iOS" in labels


def test_parse_response_validates_and_cleans():
    raw = ('Here you go: [{"id":"a","relevance":15,"topics":["Exploits","Bogus"],'
           '"summary":"One — two.","takeaway":"Learn this."},'
           '{"id":"zzz","relevance":9,"topics":[],"summary":"x","takeaway":"y"}]')
    out = summarise.parse_response(raw, {"a"}, set(LABELS))
    assert set(out) == {"a"}                       # unknown id ignored
    assert out["a"]["relevance"] == 10             # clamped
    assert out["a"]["topics"] == ["Exploits"]      # bogus topic dropped
    assert "—" not in out["a"]["summary"]     # dash removed


def test_parse_response_rejects_non_json():
    with pytest.raises(ValueError):
        summarise.parse_response("sorry, no", {"a"}, set(LABELS))


def test_merge_day_caps_and_ranks(tmp_path):
    def mk(i, rel):
        return {"id": str(i), "relevance": rel, "published": f"2026-10-30T0{i}:00:00+00:00"}
    store.merge_day(tmp_path, "2026-10-30", [mk(1, 5), mk(2, 9)], cap=2)
    store.merge_day(tmp_path, "2026-10-30", [mk(3, 7)], cap=2)
    day = json.loads((tmp_path / "2026-10-30.json").read_text())
    assert [i["id"] for i in day["items"]] == ["2", "3"]


def test_seen_pruning(tmp_path):
    store.save_seen(tmp_path, {"old": "2026-01-01", "new": "2026-10-29"}, "2026-10-30")
    assert set(store.load_seen(tmp_path)) == {"new"}
