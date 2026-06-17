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

The frontend reads two generated files:

- `data/ranked_mps.json`: ranked MP objects, visible metric scores, raw counts, role fields, and methodology metadata.
- `data/source_records.json`: matched source records, source policy metadata, connector counts, and when available a `source_audit` list describing sources that were used, diagnostic-only, context-only, discovery-only, skipped, failed, or not yet implemented.

These files are committed so the website remains static and inspectable.

## Validation

Run the lightweight validation checks with:

```bash
python scripts/validate_data.py
```

The validator checks that both data files exist, are valid JSON, contain the required MP fields, expose expected visible metric fields or compatible legacy aliases, keep scores between 0 and 100, and use only allowed source-audit statuses.

Syntax checks used by CI:

```bash
python -m py_compile scripts/update_uk.py scripts/commons_score/*.py scripts/validate_data.py
node --check script.js
```

## Methodology

See [METHODOLOGY.md](METHODOLOGY.md) for the current scoring model, source hierarchy, legal-safety guardrails, and known limitations.
