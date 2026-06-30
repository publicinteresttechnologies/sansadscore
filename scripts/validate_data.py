import json
import sys
from pathlib import Path

from commons_score.best_practice import PUBLIC_METRIC_ORDER

RANKED_MPS_PATH = Path("data/ranked_mps.json")
SOURCE_RECORDS_PATH = Path("data/source_records.json")

BASE_FIELDS = ["name", "constituency", "party", "variables", "raw", "score"]
VISIBLE_METRICS = ["Constituency Work", "Parliamentary Work", "Delivery Track", "Public Value"]
ALLOWED_AUDIT_STATUSES = {"used_in_score", "diagnostic_only", "context_only", "discovery_only", "no_match", "skipped_fast_mode", "failed", "todo_not_implemented"}


def fail(message):
    print(f"Validation error: {message}", file=sys.stderr)
    return 1


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_score(value, label):
    if not is_number(value):
        raise ValueError(f"{label} must be numeric")
    if value < 0 or value > 100:
        raise ValueError(f"{label} must be between 0 and 100")


def ranked_mps(payload):
    mps = payload.get("mps") if isinstance(payload, dict) else payload
    if not isinstance(mps, list) or not mps:
        raise ValueError("ranked_mps.json must contain a non-empty mps list")
    return mps


def has_public_contract(mps):
    return all("public_metrics" in mp and "public_metric_order" in mp and "boost_url" in mp for mp in mps[:10])


def validate_public_metrics(mp):
    if mp.get("public_metric_order") != PUBLIC_METRIC_ORDER:
        raise ValueError(f"{mp.get('name', 'MP')} has invalid public_metric_order")
    metrics = mp.get("public_metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"{mp.get('name', 'MP')} public_metrics must be an object")
    if list(metrics.keys()) != PUBLIC_METRIC_ORDER:
        raise ValueError(f"{mp.get('name', 'MP')} public_metrics keys do not match public contract")
    for metric in PUBLIC_METRIC_ORDER:
        validate_score(metrics[metric], f"{mp.get('name', 'MP')} public metric {metric}")
    if not str(mp.get("boost_url", "")).startswith("http"):
        raise ValueError(f"{mp.get('name', 'MP')} boost_url must be an http URL")


def validate_mp(mp, require_public_contract):
    for field in BASE_FIELDS:
        if field not in mp:
            raise ValueError(f"{mp.get('name', 'MP')} missing required field {field}")
    if not isinstance(mp["variables"], dict):
        raise ValueError(f"{mp.get('name', 'MP')} variables must be an object")
    if not isinstance(mp["raw"], dict):
        raise ValueError(f"{mp.get('name', 'MP')} raw must be an object")
    validate_score(mp["score"], f"{mp.get('name', 'MP')} score")
    for metric in VISIBLE_METRICS:
        if metric not in mp["variables"]:
            raise ValueError(f"{mp.get('name', 'MP')} missing visible metric {metric}")
        validate_score(mp["variables"][metric], f"{mp.get('name', 'MP')} metric {metric}")
    if require_public_contract:
        validate_public_metrics(mp)


def validate_ranked(payload):
    mps = ranked_mps(payload)
    if len(mps) < 600 or len(mps) > 700:
        raise ValueError(f"MP count {len(mps)} outside expected Commons range")
    require_public_contract = has_public_contract(mps)
    for mp in mps:
        validate_mp(mp, require_public_contract)
    scores = [mp["score"] for mp in mps]
    if max(scores) - min(scores) < 10:
        raise ValueError("score distribution is too flat")
    return len(mps)


def validate_sources(payload):
    records = payload.get("records", []) if isinstance(payload, dict) else []
    audit = payload.get("source_audit", []) if isinstance(payload, dict) else []
    for index, entry in enumerate(audit):
        if entry.get("status") not in ALLOWED_AUDIT_STATUSES:
            raise ValueError(f"source_audit entry {index} has invalid status {entry.get('status')!r}")
    return len(records), len(audit)


def main():
    try:
        mp_count = validate_ranked(load_json(RANKED_MPS_PATH))
        if SOURCE_RECORDS_PATH.exists():
            record_count, audit_count = validate_sources(load_json(SOURCE_RECORDS_PATH))
        else:
            record_count, audit_count = 0, 0
    except (ValueError, json.JSONDecodeError) as error:
        return fail(str(error))
    print(f"Validated {mp_count} MPs in {RANKED_MPS_PATH}")
    print(f"Validated {record_count} source records in {SOURCE_RECORDS_PATH}")
    print(f"Validated {audit_count} source audit entries in {SOURCE_RECORDS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
