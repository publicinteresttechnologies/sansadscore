import json
import os
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
    ALLOWED_RUN_MODES,
    DEFAULT_RUN_MODE,
    FAST_MODE_SKIPPED_CONNECTORS,
    FAST_WRITTEN_QUESTION_MAX_ROWS,
    FULL_WRITTEN_QUESTION_MAX_ROWS,
    METHODOLOGY_WEIGHT_LABELS,
    RANKED_OUTPUT_PATH,
    RUN_MODE_ENV_VAR,
    SOURCE_POLICY,
    SOURCE_RECORDS_PATH,
    SOURCES_USED,
)
from .json_io import read_json, write_json
from .scoring import build_scored_mp


def get_run_mode():
    run_mode = os.environ.get(RUN_MODE_ENV_VAR, DEFAULT_RUN_MODE).strip().lower()

    if run_mode not in ALLOWED_RUN_MODES:
        allowed = ", ".join(sorted(ALLOWED_RUN_MODES))
        raise RuntimeError(f"Invalid {RUN_MODE_ENV_VAR}={run_mode!r}. Allowed values: {allowed}.")

    return run_mode


def written_question_max_rows(run_mode):
    if run_mode == "full":
        return FULL_WRITTEN_QUESTION_MAX_ROWS
    return FAST_WRITTEN_QUESTION_MAX_ROWS


def load_existing_source_records():
    try:
        payload = read_json(SOURCE_RECORDS_PATH)
    except FileNotFoundError:
        print(f"No existing {SOURCE_RECORDS_PATH}; fast mode will score without source records.", flush=True)
        return []
    except json.JSONDecodeError as error:
        print(f"Could not parse existing {SOURCE_RECORDS_PATH}: {error}", flush=True)
        return []

    records = payload.get("records", []) if isinstance(payload, dict) else []

    if not isinstance(records, list):
        print(f"Existing {SOURCE_RECORDS_PATH} has no records list; ignoring it.", flush=True)
        return []

    print(f"Loaded {len(records)} existing source records.", flush=True)
    return records


def records_by_member_id(records):
    grouped = {}

    for record in records:
        try:
            member_id = int(record.get("member_id"))
        except Exception:
            continue

        grouped.setdefault(member_id, []).append(record)

    return grouped


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
    run_mode = get_run_mode()
    print(f"Commons Score run mode: {run_mode}", flush=True)

    if run_mode == "fast":
        print("Fast mode skips expensive connectors:", flush=True)
        for connector in FAST_MODE_SKIPPED_CONNECTORS:
            print(f"- {connector}", flush=True)

    print("Fetching current House of Commons MPs...", flush=True)
    members = get_current_commons_mps()

    if len(members) < 500:
        raise RuntimeError(f"Only found {len(members)} MPs. Refusing to overwrite data.")

    print(f"Found {len(members)} MPs.", flush=True)

    max_question_rows = written_question_max_rows(run_mode)
    print(f"Written-question row cap: {max_question_rows}", flush=True)
    questions_by_member = fetch_written_questions_by_member(max_rows=max_question_rows)

    if run_mode == "full":
        ipsa_pages = fetch_ipsa_pages()
        existing_records = []
    else:
        ipsa_pages = []
        existing_records = dedupe_records(load_existing_source_records())

    existing_records_by_member = records_by_member_id(existing_records)
    all_source_records = [] if run_mode == "full" else list(existing_records)
    scored = []

    print("Collecting public counts and scoring MPs...", flush=True)

    for index, member in enumerate(members, start=1):
        print(f"{index}/{len(members)}: {member['name']}", flush=True)

        public_record = get_member_public_record(member["id"])

        if run_mode == "full":
            records = collect_all_source_records_for_member(member, ipsa_pages)
            all_source_records.extend(records)
        else:
            records = existing_records_by_member.get(member["id"], [])

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
