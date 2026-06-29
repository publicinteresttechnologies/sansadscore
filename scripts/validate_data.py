import json
import sys
from collections import Counter
from pathlib import Path

from commons_score.best_practice import (
    DATA_SCHEMA_VERSION,
    METHODOLOGY_VERSION,
    SCORING_MODEL_VERSION,
    SOURCE_POLICY_VERSION,
)

RANKED_MPS_PATH = Path("data/ranked_mps.json")
SOURCE_RECORDS_PATH = Path("data/source_records.json")

EXPECTED_MP_MIN = 600
EXPECTED_MP_MAX = 700
MIN_SOURCE_RECORDS = 100
MIN_AUDIT_MULTIPLIER = 8
MAX_SINGLE_ROLE_SHARE = 0.95
MAX_SPECIALIST_ROLE_SHARE = 0.45
MAX_MINISTER_COUNT = 150
MIN_PUBLIC_SCORE_CEILING = 40
MIN_PUBLIC_SCORE_SPREAD = 15

REQUIRED_MP_FIELDS = [
    "name",
    "constituency",
    "party",
    "variables",
    "raw",
]

VISIBLE_METRIC_ALIASES = {
    "Constituency Work": ["Constituency Work", "Constituency Focus"],
    "Parliamentary Work": ["Parliamentary Work"],
    "Delivery Track": ["Delivery Track", "Promise Follow-Through"],
    "Public Value": ["Public Value"],
}

ALLOWED_AUDIT_STATUSES = {
    "used_in_score",
    "diagnostic_only",
    "context_only",
    "discovery_only",
    "no_match",
    "skipped_fast_mode",
    "failed",
    "todo_not_implemented",
}

SPECIALIST_ROLES = {
    "Minister",
    "Whip",
    "Shadow Minister",
    "Committee Chair",
    "Speaker",
}

EXPECTED_VERSIONS = {
    "scoring_model": SCORING_MODEL_VERSION,
    "data_schema": DATA_SCHEMA_VERSION,
    "source_policy": SOURCE_POLICY_VERSION,
    "methodology": METHODOLOGY_VERSION,
}


def fail(message):
    print(f"Validation error: {message}", file=sys.stderr)
    return 1


def load_json(path):
    if not path.exists():
        raise ValueError(f"{path} does not exist")

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not valid JSON: {error}") from error


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_score(value, label):
    if not is_number(value):
        raise ValueError(f"{label} must be numeric")

    if value < 0 or value > 100:
        raise ValueError(f"{label} must be between 0 and 100")


def ranked_mps(payload):
    if isinstance(payload, dict):
        mps = payload.get("mps")
    elif isinstance(payload, list):
        mps = payload
    else:
        raise ValueError("data/ranked_mps.json must contain an object or list")

    if not isinstance(mps, list):
        raise ValueError("data/ranked_mps.json must contain an mps list")

    if not mps:
        if isinstance(payload, dict) and payload.get("status") == "needs_generation":
            return []
        raise ValueError("data/ranked_mps.json mps list is empty")

    return mps


def validate_versions(payload):
    if not isinstance(payload, dict):
        return

    versions = payload.get("versions")
    if not isinstance(versions, dict):
        raise ValueError("data/ranked_mps.json must contain a versions object")

    for key, expected in EXPECTED_VERSIONS.items():
        actual = versions.get(key)
        if actual != expected:
            raise ValueError(f"version mismatch for {key}: data has {actual!r}, code expects {expected!r}")


def validate_metric(variables, canonical_name, aliases, mp_label):
    present = [key for key in aliases if key in variables]

    if not present:
        expected = " or ".join(aliases)
        raise ValueError(f"{mp_label} missing visible metric {canonical_name} ({expected})")

    for key in present:
        validate_score(variables[key], f"{mp_label} metric {key}")


def validate_mp(mp, index):
    if not isinstance(mp, dict):
        raise ValueError(f"MP at index {index} must be an object")

    mp_label = mp.get("name") or f"MP at index {index}"

    for field in REQUIRED_MP_FIELDS:
        if field not in mp:
            raise ValueError(f"{mp_label} missing required field {field}")

    for field in ["name", "constituency", "party"]:
        if not isinstance(mp[field], str):
            raise ValueError(f"{mp_label} field {field} must be a string")

    if not isinstance(mp["variables"], dict):
        raise ValueError(f"{mp_label} variables must be an object")

    if not isinstance(mp["raw"], dict):
        raise ValueError(f"{mp_label} raw must be an object")

    if "score" not in mp:
        raise ValueError(f"{mp_label} missing score")

    validate_score(mp["score"], f"{mp_label} score")

    for canonical_name, aliases in VISIBLE_METRIC_ALIASES.items():
        validate_metric(mp["variables"], canonical_name, aliases, mp_label)


def role_value(mp):
    return mp.get("role") or mp.get("role_peer_group") or mp.get("raw", {}).get("role_peer_group") or "Unknown"


def validate_role_distribution(mps):
    roles = Counter(role_value(mp) for mp in mps)
    total = len(mps)
    if not roles:
        raise ValueError("role distribution is empty")

    role, count = roles.most_common(1)[0]
    share = count / total
    if share > MAX_SINGLE_ROLE_SHARE:
        raise ValueError(
            f"role distribution collapsed: {count}/{total} MPs ({share:.1%}) are {role!r}; "
            "public data must retain meaningful role context before publication"
        )

    specialist_count = sum(count for role, count in roles.items() if role in SPECIALIST_ROLES)
    specialist_share = specialist_count / total
    if specialist_share > MAX_SPECIALIST_ROLE_SHARE:
        raise ValueError(
            f"specialist role share is implausibly high: {specialist_count}/{total} MPs ({specialist_share:.1%})"
        )

    minister_count = roles.get("Minister", 0)
    if minister_count > MAX_MINISTER_COUNT:
        raise ValueError(f"minister count is implausibly high: {minister_count} MPs")


def validate_score_distribution(mps):
    scores = [mp.get("score") for mp in mps if is_number(mp.get("score"))]
    if not scores:
        raise ValueError("no numeric MP scores found")

    score_min = min(scores)
    score_max = max(scores)
    score_spread = score_max - score_min

    if score_max < MIN_PUBLIC_SCORE_CEILING:
        raise ValueError(
            f"score ceiling collapsed: max score is {score_max:.2f}; "
            f"expected at least {MIN_PUBLIC_SCORE_CEILING} before public release"
        )

    if score_spread < MIN_PUBLIC_SCORE_SPREAD:
        raise ValueError(
            f"score distribution is too flat: spread is {score_spread:.2f}; "
            f"expected at least {MIN_PUBLIC_SCORE_SPREAD} before public release"
        )


def validate_ranked_mps(payload):
    validate_versions(payload)
    mps = ranked_mps(payload)

    if not mps:
        return 0

    mp_count = len(mps)
    if mp_count < EXPECTED_MP_MIN or mp_count > EXPECTED_MP_MAX:
        raise ValueError(
            f"MP count {mp_count} outside expected Commons range {EXPECTED_MP_MIN}-{EXPECTED_MP_MAX}"
        )

    for index, mp in enumerate(mps):
        validate_mp(mp, index)

    validate_role_distribution(mps)
    validate_score_distribution(mps)
    return mp_count


def source_records(payload):
    if isinstance(payload, dict):
        records = payload.get("records", [])
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError("data/source_records.json must contain an object or list")

    if records is None:
        return []

    if not isinstance(records, list):
        raise ValueError("records must be a list when present")

    return records


def source_audit_entries(payload):
    if isinstance(payload, dict):
        audit = payload.get("source_audit", [])
    elif isinstance(payload, list):
        audit = []
    else:
        raise ValueError("data/source_records.json must contain an object or list")

    if audit is None:
        return []

    if not isinstance(audit, list):
        raise ValueError("source_audit must be a list when present")

    return audit


def validate_source_records(payload, mp_count):
    records = source_records(payload)
    if mp_count and len(records) < MIN_SOURCE_RECORDS:
        raise ValueError(
            f"source_records.json has only {len(records)} records; expected at least {MIN_SOURCE_RECORDS} auditable records"
        )

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"source record {index} must be an object")

        if "member_id" not in record:
            raise ValueError(f"source record {index} missing member_id")

        if not (record.get("source_url") or record.get("endpoint_or_url")):
            raise ValueError(f"source record {index} missing source_url or endpoint_or_url")

    return len(records)


def validate_source_audit(payload, mp_count):
    audit = source_audit_entries(payload)

    if mp_count and len(audit) < mp_count * MIN_AUDIT_MULTIPLIER:
        raise ValueError(
            f"source_audit has only {len(audit)} entries for {mp_count} MPs; "
            f"expected at least {mp_count * MIN_AUDIT_MULTIPLIER} entries"
        )

    for index, entry in enumerate(audit):
        if not isinstance(entry, dict):
            raise ValueError(f"source_audit entry {index} must be an object")

        status = entry.get("status")
        if status not in ALLOWED_AUDIT_STATUSES:
            raise ValueError(f"source_audit entry {index} has invalid status {status!r}")

        if "records_found" in entry and not is_number(entry["records_found"]):
            raise ValueError(f"source_audit entry {index} records_found must be numeric")

    return len(audit)


def main():
    try:
        ranked_payload = load_json(RANKED_MPS_PATH)
        source_payload = load_json(SOURCE_RECORDS_PATH)
        mp_count = validate_ranked_mps(ranked_payload)
        record_count = validate_source_records(source_payload, mp_count)
        audit_count = validate_source_audit(source_payload, mp_count)
    except ValueError as error:
        return fail(str(error))

    print(f"Validated {mp_count} MPs in {RANKED_MPS_PATH}")
    print(f"Validated {record_count} source records in {SOURCE_RECORDS_PATH}")
    print(f"Validated {audit_count} source audit entries in {SOURCE_RECORDS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
