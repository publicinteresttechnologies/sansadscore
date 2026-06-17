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
    BILLS_API_CANDIDATES,
    COMMITTEES_API_CANDIDATES,
    COMMONS_VOTES_SEARCH,
    CONNECTOR_TODOS,
    DEFAULT_RUN_MODE,
    FAST_MODE_SKIPPED_CONNECTORS,
    FAST_WRITTEN_QUESTION_MAX_ROWS,
    FULL_WRITTEN_QUESTION_MAX_ROWS,
    GDELT_DOC_API,
    IPSA_SOURCE_URLS,
    MEMBERS_API,
    METHODOLOGY_WEIGHT_LABELS,
    ORAL_QUESTIONS_API_CANDIDATES,
    RANKED_OUTPUT_PATH,
    RUN_MODE_ENV_VAR,
    SOURCE_POLICY,
    SOURCE_RECORDS_PATH,
    SOURCES_USED,
    WRITTEN_QUESTIONS_API,
)
from .json_io import read_json, write_json
from .scoring import build_scored_mp

EXPENSIVE_CONNECTORS = {
    "oral_questions_api",
    "members_experience",
    "contribution_summary",
    "mp_contact_website",
    "committees_api",
    "bills_api",
    "commons_votes_api",
    "ipsa_public_costs",
    "hansard_like_contribution_summary",
    "gdelt_media",
}

AUDIT_CONNECTORS = [
    {
        "connector": "members_api_public_counts",
        "source_name": "Members API public counts",
        "endpoint_or_url": MEMBERS_API,
        "control_tier": "direct_mp_control",
        "status_with_records": "used_in_score",
        "scored": True,
        "diagnostic_only": False,
        "context_only": False,
    },
    {
        "connector": "written_questions_api",
        "source_name": "Written Questions API",
        "endpoint_or_url": WRITTEN_QUESTIONS_API,
        "control_tier": "direct_mp_control",
        "status_with_records": "used_in_score",
        "scored": True,
        "diagnostic_only": False,
        "context_only": False,
    },
    {
        "connector": "register_interests",
        "source_name": "Registered Interests",
        "endpoint_or_url": f"{MEMBERS_API}/{{member_id}}/RegisteredInterests",
        "control_tier": "diagnostic_only",
        "status_with_records": "diagnostic_only",
        "scored": False,
        "diagnostic_only": True,
        "context_only": False,
    },
    {
        "connector": "members_api_edms",
        "source_name": "EDMs",
        "endpoint_or_url": f"{MEMBERS_API}/{{member_id}}/Edms",
        "control_tier": "direct_mp_control",
        "status_with_records": "used_in_score",
        "scored": True,
        "diagnostic_only": False,
        "context_only": False,
    },
    {
        "connector": "members_api_focus",
        "source_name": "Focus",
        "endpoint_or_url": f"{MEMBERS_API}/{{member_id}}/Focus",
        "control_tier": "direct_mp_control",
        "status_with_records": "used_in_score",
        "scored": True,
        "diagnostic_only": False,
        "context_only": False,
    },
    {
        "connector": "members_api_voting",
        "source_name": "Voting",
        "endpoint_or_url": f"{MEMBERS_API}/{{member_id}}/Voting",
        "control_tier": "direct_mp_control",
        "status_with_records": "used_in_score",
        "scored": True,
        "diagnostic_only": False,
        "context_only": False,
    },
    {
        "connector": "oral_questions_api",
        "source_name": "Oral Questions",
        "endpoint_or_url": ", ".join(ORAL_QUESTIONS_API_CANDIDATES),
        "control_tier": "direct_mp_control",
        "status_with_records": "used_in_score",
        "scored": True,
        "diagnostic_only": False,
        "context_only": False,
    },
    {
        "connector": "members_experience",
        "source_name": "Experience",
        "endpoint_or_url": f"{MEMBERS_API}/{{member_id}}/Experience",
        "control_tier": "context_only",
        "status_with_records": "context_only",
        "scored": False,
        "diagnostic_only": False,
        "context_only": True,
    },
    {
        "connector": "contribution_summary",
        "source_name": "Contribution Summary",
        "endpoint_or_url": f"{MEMBERS_API}/{{member_id}}/ContributionSummary",
        "control_tier": "shared_influence",
        "status_with_records": "used_in_score",
        "scored": True,
        "diagnostic_only": False,
        "context_only": False,
    },
    {
        "connector": "mp_contact_website",
        "source_name": "MP contact/website",
        "endpoint_or_url": f"{MEMBERS_API}/{{member_id}}/Contact",
        "control_tier": "diagnostic_only",
        "status_with_records": "diagnostic_only",
        "scored": False,
        "diagnostic_only": True,
        "context_only": False,
    },
    {
        "connector": "committees_api",
        "source_name": "Committees",
        "endpoint_or_url": ", ".join(COMMITTEES_API_CANDIDATES),
        "control_tier": "shared_influence",
        "status_with_records": "used_in_score",
        "scored": True,
        "diagnostic_only": False,
        "context_only": False,
    },
    {
        "connector": "bills_api",
        "source_name": "Bills",
        "endpoint_or_url": ", ".join(BILLS_API_CANDIDATES),
        "control_tier": "shared_influence",
        "status_with_records": "used_in_score",
        "scored": True,
        "diagnostic_only": False,
        "context_only": False,
    },
    {
        "connector": "commons_votes_api",
        "source_name": "Commons Votes",
        "endpoint_or_url": COMMONS_VOTES_SEARCH,
        "control_tier": "direct_mp_control",
        "status_with_records": "used_in_score",
        "scored": True,
        "diagnostic_only": False,
        "context_only": False,
    },
    {
        "connector": "ipsa_public_costs",
        "source_name": "IPSA page discovery",
        "endpoint_or_url": ", ".join(IPSA_SOURCE_URLS),
        "control_tier": "diagnostic_only",
        "status_with_records": "diagnostic_only",
        "scored": False,
        "diagnostic_only": True,
        "context_only": False,
    },
    {
        "connector": "hansard_like_contribution_summary",
        "source_name": "Hansard-like summary",
        "endpoint_or_url": f"{MEMBERS_API}/{{member_id}}/ContributionSummary",
        "control_tier": "shared_influence",
        "status_with_records": "used_in_score",
        "scored": True,
        "diagnostic_only": False,
        "context_only": False,
    },
    {
        "connector": "gdelt_media",
        "source_name": "GDELT media",
        "endpoint_or_url": GDELT_DOC_API,
        "control_tier": "context_only",
        "status_with_records": "discovery_only",
        "scored": False,
        "diagnostic_only": False,
        "context_only": True,
    },
    {
        "connector": "ipsa_csv_downloads",
        "source_name": "IPSA CSV/download data",
        "endpoint_or_url": "TODO: stable IPSA downloadable schema",
        "control_tier": "diagnostic_only",
        "status_with_records": "todo_not_implemented",
        "scored": False,
        "diagnostic_only": True,
        "context_only": False,
        "todo": True,
    },
]


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
            item["variables"]["Constituency Work"],
            item["variables"]["Parliamentary Work"],
            item["variables"]["Delivery Track"],
            item["variables"]["Public Value"],
            item["raw"]["written_questions_total"],
            item["raw"]["written_questions_local"],
            item["raw"]["commons_votes_total"],
            item["raw"]["edms_signed"],
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


def audit_endpoint(metadata, member):
    return metadata["endpoint_or_url"].replace("{member_id}", str(member["id"]))


def source_audit_entry(member, metadata, run_mode, records_found, status, reason, error=""):
    scored = metadata["scored"] and status == "used_in_score"
    diagnostic_only = metadata["diagnostic_only"] or status == "diagnostic_only"
    context_only = metadata["context_only"] or status in ["context_only", "discovery_only"]

    return {
        "member_id": member["id"],
        "mp_name": member["name"],
        "constituency": member["constituency"],
        "connector": metadata["connector"],
        "source_name": metadata["source_name"],
        "endpoint_or_url": audit_endpoint(metadata, member),
        "control_tier": metadata["control_tier"],
        "status": status,
        "run_mode": run_mode,
        "records_found": records_found,
        "scored": scored,
        "diagnostic_only": diagnostic_only,
        "context_only": context_only,
        "reason": reason,
        "error": error,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def connector_record_count(records, connector):
    return sum(1 for record in records if record.get("source_connector") == connector)


def public_count_for_connector(public_record, connector):
    if connector == "members_api_public_counts":
        return sum(
            public_record.get(key, 0)
            for key in ["registered_interests", "edms", "focus_items", "votes"]
        )
    if connector == "members_api_edms":
        return public_record.get("edms", 0)
    if connector == "members_api_focus":
        return public_record.get("focus_items", 0)
    if connector == "members_api_voting":
        return public_record.get("votes", 0)
    return None


def build_source_audit_for_member(member, public_record, questions_by_member, records, run_mode):
    audit = []
    written_questions = questions_by_member.get(member["id"], [])

    for metadata in AUDIT_CONNECTORS:
        connector = metadata["connector"]
        error = ""

        if metadata.get("todo"):
            audit.append(
                source_audit_entry(
                    member,
                    metadata,
                    run_mode,
                    0,
                    "todo_not_implemented",
                    "Connector is documented as a TODO and is not scored until reliable public data is implemented.",
                )
            )
            continue

        if run_mode == "fast" and connector in EXPENSIVE_CONNECTORS:
            audit.append(
                source_audit_entry(
                    member,
                    metadata,
                    run_mode,
                    0,
                    "skipped_fast_mode",
                    "Skipped in fast mode to keep the daily updater lightweight.",
                )
            )
            continue

        if connector == "written_questions_api":
            records_found = len(written_questions)
        elif connector == "register_interests":
            records_found = public_record.get("registered_interests", 0)
        else:
            records_found = public_count_for_connector(public_record, connector)
            if records_found is None:
                records_found = connector_record_count(records, connector)

        if records_found > 0:
            status = metadata["status_with_records"]
            reason = "Source returned public records for this MP."
        else:
            status = "no_match"
            reason = "Source was considered but returned no matching public record for this MP."

        audit.append(
            source_audit_entry(
                member,
                metadata,
                run_mode,
                records_found,
                status,
                reason,
                error=error,
            )
        )

    return audit


def build_source_output(records, source_audit):
    return {
        "last_source_collection": datetime.now(timezone.utc).strftime("%d %B %Y"),
        "source_policy": SOURCE_POLICY,
        "connector_todos": CONNECTOR_TODOS,
        "connector_counts": connector_counts(records),
        "source_audit": source_audit,
        "records": records,
    }


def build_ranking_output(output_mps):
    return {
        "last_updated": datetime.now(timezone.utc).strftime("%d %B %Y"),
        "methodology": {
            "note": "Automated public-record score. It is not an endorsement, voting recommendation or claim about private intent.",
            "question": "How visible is this MP's public record of constituency work, parliamentary work, delivery and public value?",
            "weights": METHODOLOGY_WEIGHT_LABELS,
            "diagnostics_note": "Evidence quality, source diversity, media dependency and MP self-claim dependency are diagnostic context in raw data, not public scoring metrics.",
            "sources_used": SOURCES_USED,
            "scoring_rule": "Scores are generated from available public records. Promise-only evidence receives low credit, action receives more credit, repeated follow-up receives more credit, and verified official outcomes receive the strongest delivery credit.",
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
    source_audit = []
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

        source_audit.extend(
            build_source_audit_for_member(
                member,
                public_record,
                questions_by_member,
                records,
                run_mode,
            )
        )

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
    source_output = build_source_output(all_source_records, source_audit)
    ranking_output = build_ranking_output(output_mps)

    write_json(SOURCE_RECORDS_PATH, source_output)
    write_json(RANKED_OUTPUT_PATH, ranking_output)

    print(f"Wrote {SOURCE_RECORDS_PATH}", flush=True)
    print(f"Wrote {RANKED_OUTPUT_PATH}", flush=True)
    print(f"Connector counts: {source_output['connector_counts']}", flush=True)
    print(f"Source audit entries: {len(source_audit)}", flush=True)
