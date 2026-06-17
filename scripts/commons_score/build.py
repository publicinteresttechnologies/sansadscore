import time
from datetime import datetime, timezone

from .collectors import (
    collect_all_source_records_for_member,
    dedupe_records,
    fetch_ipsa_pages,
    fetch_written_questions_by_member,
    get_current_commons_mps,
    get_member_public_record,
    question_matches_constituency,
)
from .config import (
    METHODOLOGY_WEIGHT_LABELS,
    RANKED_OUTPUT_PATH,
    SOURCE_POLICY,
    SOURCE_RECORDS_PATH,
    SOURCES_USED,
)
from .json_io import write_json
from .scoring import build_scored_mp


def rank_mps(scored):
    scored.sort(
        key=lambda item: (
            item["score"],
            item["variables"]["Constituency Focus"],
            item["variables"]["Parliamentary Work"],
            item["variables"]["Promise Follow-Through"],
            item["variables"]["Public Value"],
            item["variables"]["Trust & Evidence"],
            item["raw"]["written_questions_count"],
            item["raw"]["local_questions_count"],
            item["raw"]["votes_count"],
            item["raw"]["edms_count"],
            item["raw"]["focus_items_count"],
            item["raw"]["manual_source_records_count"],
        ),
        reverse=True,
    )

    output_mps = []

    for rank, mp in enumerate(scored, start=1):
        mp["rank"] = rank
        output_mps.append(mp)

    return output_mps


def connector_counts(records):
    counts = {}

    for record in records:
        connector = record.get("source_connector") or "unknown"
        counts[connector] = counts.get(connector, 0) + 1

    return counts


def build_source_output(records):
    return {
        "last_source_collection": datetime.now(timezone.utc).strftime("%d %B %Y"),
        "source_policy": SOURCE_POLICY,
        "connector_counts": connector_counts(records),
        "records": records,
    }


def build_ranking_output(output_mps):
    return {
        "last_updated": datetime.now(timezone.utc).strftime("%d %B %Y"),
        "methodology": {
            "note": "Automated public-record score. It is not an endorsement, voting recommendation or claim about private intent.",
            "question": "Is this MP working for their constituency and doing the job of an MP?",
            "weights": METHODOLOGY_WEIGHT_LABELS,
            "sources_used": SOURCES_USED,
            "scoring_rule": "No source, no score. Scores are generated from available public records and should be read as source-backed indicators.",
        },
        "mps": output_mps,
    }


def main():
    print("Fetching current House of Commons MPs...", flush=True)
    members = get_current_commons_mps()

    if len(members) < 500:
        raise RuntimeError(f"Only found {len(members)} MPs. Refusing to overwrite data.")

    print(f"Found {len(members)} MPs.", flush=True)

    questions_by_member = fetch_written_questions_by_member()
    ipsa_pages = fetch_ipsa_pages()

    all_source_records = []
    scored = []

    print("Collecting all source evidence and scoring MPs...", flush=True)

    for index, member in enumerate(members, start=1):
        print(f"{index}/{len(members)}: {member['name']}", flush=True)

        public_record = get_member_public_record(member["id"])
        records = collect_all_source_records_for_member(member, ipsa_pages)

        all_source_records.extend(records)
        scored.append(
            build_scored_mp(
                member,
                public_record,
                questions_by_member,
                records,
                question_matches_constituency,
            )
        )

        time.sleep(0.08)

    all_source_records = dedupe_records(all_source_records)
    output_mps = rank_mps(scored)
    source_output = build_source_output(all_source_records)
    ranking_output = build_ranking_output(output_mps)

    write_json(SOURCE_RECORDS_PATH, source_output)
    write_json(RANKED_OUTPUT_PATH, ranking_output)

    print(f"Wrote {SOURCE_RECORDS_PATH}", flush=True)
    print(f"Wrote {RANKED_OUTPUT_PATH}", flush=True)
    print(f"Connector counts: {source_output['connector_counts']}", flush=True)
