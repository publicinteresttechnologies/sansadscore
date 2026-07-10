# Commons Score / SansadScore

Commons Score is an evidence-linked public accountability dashboard for UK Members of Parliament. It collects public records, turns them into inspectable source records, and presents a static ranking interface that helps readers explore visible constituency work, parliamentary work, delivery signals, and public value.

This project is not a legal finding, factual verdict, endorsement, voting recommendation, or claim about an MP's private intent. Scores are automated indicators built from available public records. They should be read alongside the linked evidence and known limitations in [METHODOLOGY.md](METHODOLOGY.md).

Repository boundaries are documented in [PROJECT_REGISTRY.md](PROJECT_REGISTRY.md). This repository is only for Commons Score / SansadScore.

## Local Setup

Requirements:

- Python 3.11+
- Node.js, only for JavaScript syntax checks

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Run the static site locally with any simple static file server, for example:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000`.

## Updating Data

The updater writes static JSON files consumed by the frontend. It supports two run modes through `COMMONS_SCORE_RUN_MODE`.

Fast mode is the default and is intended for daily use:

```bash
python scripts/update_uk.py
```

or explicitly:

```bash
COMMONS_SCORE_RUN_MODE=fast python scripts/update_uk.py
```

Full mode runs slower discovery connectors and should be used deliberately:

```bash
COMMONS_SCORE_RUN_MODE=full python scripts/update_uk.py
```

Fast mode keeps the daily job lightweight. Full mode may probe slower or less predictable public sources such as media discovery, IPSA page discovery, Bills API, Committees API, Commons Votes probing, MP website/contact discovery, and contribution-summary/Hansard-like signals.

## Data Outputs

The frontend reads generated static JSON:

- `data/ranked_mps.json`: ranked MP objects, visible metric scores, raw counts, role fields, and methodology metadata.
- `data/sources/<member_id>.json`: full matched source records and full `source_audit` entries for one MP. These shards are lazy-loaded only when a reader opens "Sources & Methods".
- `data/source_summary.json`: lightweight aggregate counts for site-wide summaries. It is not the detailed source ledger.

The old single-file `data/source_records.json` is intentionally not used as a deployed static asset because the full ledger is too large for Cloudflare Pages' per-file limit. Evidence remains inspectable through the per-MP shards.

## Validation

Run the lightweight validation checks with:

```bash
python scripts/validate_data.py
```

The validator checks that ranked data exists, is valid JSON, contains the required MP fields, exposes expected visible metric fields or compatible legacy aliases, keeps scores between 0 and 100, and has deployable per-MP source shards with only allowed source-audit statuses.

Syntax checks used by CI:

```bash
python -m py_compile scripts/update_uk.py scripts/commons_score/*.py scripts/validate_data.py
node --check script.js
```

## Methodology

See [METHODOLOGY.md](METHODOLOGY.md) for the current scoring model, source hierarchy, legal-safety guardrails, and known limitations.
