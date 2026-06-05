# SciHub — GitHub for science

A preprint server where a publication isn't just a paper: to publish, you bundle
everything needed to **reproduce** the result — manuscript, data, code, and protocol.
(Forking published work to continue on top of it is the next milestone.)

## Quickstart

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./run.sh            # serves on http://127.0.0.1:8000
```

## What works today

- **Upload a reproducibility bundle** — `/new` lets you attach files to five
  categories: `manuscript`, `data`, `code`, `protocol`, `environment`. Code can
  instead link an external repo (e.g. GitHub) via a URL.
- **Reproducibility checklist** — a publication is flagged *Reproducible* only
  when all four required categories (manuscript, data, code, protocol) are present.
- **Browse & download** — list view, detail page, and per-file downloads.

## Layout

- `app/main.py` — routes
- `app/models.py` — `Publication` + `Artifact`, and the category/required rules
- `app/storage.py` — on-disk file storage (`storage/<slug>/<category>/`)
- `app/templates/`, `app/static/` — UI

Data lives in `scihub.db` (SQLite) and `storage/`, both git-ignored.
