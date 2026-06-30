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
