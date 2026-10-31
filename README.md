# The Daily Brief

A personal reading dashboard. Twice a day a scheduled job collects recent
research papers and blog posts, ranks them against a list of topics, writes a
short summary and one takeaway for the best ones, and publishes the result as a
static page.

## How it works

1. `pipeline/fetch.py` pulls recent items from arXiv and a list of blog feeds.
2. `pipeline/prefilter.py` scores them locally against keywords in `interests.yml`.
3. `pipeline/summarise.py` sends the best candidates in small batches for scoring and summarising.
4. `pipeline/store.py` saves one JSON file per day under `docs/data/`.
5. `docs/index.html` reads those files and renders the page.

## Setup

1. Create a new public repository and push these files to the `main` branch.
2. Add a repository secret called `FEED_TOKEN` (Settings, Secrets and variables, Actions).
3. Turn on Pages: Settings, Pages, Source "Deploy from a branch", branch `main`, folder `/docs`.
4. Run the workflow once by hand: Actions, "Update feed", "Run workflow".

## Customising

- `sources.yml`: arXiv categories and blog feeds.
- `interests.yml`: topics, keywords, weights, and how many items appear per day.
- `.github/workflows/update.yml`: schedule (cron, in UTC).

## Testing locally without network access or a key

```
pip install -r requirements.txt
python -m pipeline.main --fixture tests/fixture_items.json --fake-llm --data-dir /tmp/brief-data
python -m pytest tests
```
