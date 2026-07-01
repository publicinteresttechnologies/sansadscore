"""Runtime wiring for Commons Score updater.

Python imports this module automatically when running scripts from the
`scripts/` directory. Keep this file small and explicit.
"""

try:
    from commons_score import collectors
    from commons_score.interests_api import collect_interests_api_records
except Exception:
    collectors = None
    collect_interests_api_records = None

if collectors is not None and collect_interests_api_records is not None:
    _base_collect_all_source_records_for_member = collectors.collect_all_source_records_for_member

    def collect_all_source_records_for_member_with_interests(member, ipsa_pages):
        records = []
        try:
            records.extend(collect_interests_api_records(member))
        except Exception as error:
            print(f"collect_interests_api_records failed for {member['name']}: {error}", flush=True)
        records.extend(_base_collect_all_source_records_for_member(member, ipsa_pages))
        return records

    collectors.collect_all_source_records_for_member = collect_all_source_records_for_member_with_interests

try:
    from commons_score import scoring
except Exception:
    scoring = None

if scoring is not None:
    _base_interests_categories = scoring.interests_categories
    _base_evidence_diagnostics = scoring.evidence_diagnostics

    def _interests_api_records(records):
        return scoring.records_with_connector(records, "interests_api")

    def interests_categories_with_interests_api(records):
        counts = dict(_base_interests_categories(records))
        for record in _interests_api_records(records):
            category = scoring.clean(record.get("interests_category")) or "Unknown"
            counts[category] = counts.get(category, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def evidence_diagnostics_with_interests_api(records, public_record, written_questions_count, local_questions_count):
        diagnostics = _base_evidence_diagnostics(records, public_record, written_questions_count, local_questions_count)
        interests_records = _interests_api_records(records)
        diagnostics["interests_api_records_count"] = len(interests_records)
        diagnostics["interests_api_categories"] = interests_categories_with_interests_api(records)
        diagnostics["interests_api_affects"] = "Proof only"
        if interests_records:
            base = float(diagnostics.get("data_completeness_score", 0) or 0)
            diagnostics["data_completeness_score"] = round(min(100.0, base + 5.0), 2)
        return diagnostics

    scoring.interests_categories = interests_categories_with_interests_api
    scoring.evidence_diagnostics = evidence_diagnostics_with_interests_api
