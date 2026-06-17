import json
import sys
from pathlib import Path

RANKED_MPS_PATH = Path("data/ranked_mps.json")
SOURCE_RECORDS_PATH = Path("data/source_records.json")

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
        raise ValueError("data/ranked_mps.json mps list is empty")

    return mps


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


def validate_ranked_mps(payload):
    mps = ranked_mps(payload)

    for index, mp in enumerate(mps):
        validate_mp(mp, index)

    return len(mps)


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


def validate_source_audit(payload):
    audit = source_audit_entries(payload)

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
        audit_count = validate_source_audit(source_payload)
    except ValueError as error:
        return fail(str(error))

    print(f"Validated {mp_count} MPs in {RANKED_MPS_PATH}")
    print(f"Validated {audit_count} source audit entries in {SOURCE_RECORDS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
