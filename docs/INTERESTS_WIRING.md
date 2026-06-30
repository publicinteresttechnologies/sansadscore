# Interests API Wiring

The official Interests API collector is wired into the updater runtime through `scripts/sitecustomize.py`.

When `python scripts/update_uk.py` runs, Python loads `scripts/sitecustomize.py` automatically because the `scripts/` directory is on `sys.path`. The hook patches `commons_score.collectors.collect_all_source_records_for_member` so the Interests API collector runs before the existing source collectors.

This keeps the integration small and avoids a broad rewrite of the large collectors module.

Status:

- Collector module: `scripts/commons_score/interests_api.py`
- Runtime hook: `scripts/sitecustomize.py`
- Connector name: `interests_api`
- Scoring impact: source/proof context only until explicit scoring rules are reviewed
