import json
import sys
from pathlib import Path

from commons_score.best_practice import PUBLIC_METRIC_ORDER

RANKED_MPS_PATH = Path("data/ranked_mps.json")
SOURCE_RECORDS_PATH = Path("data/source_records.json")
SOURCE_SHARDS_DIR = Path("data/sources")

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


def member_id_for(mp):
    raw = mp.get("raw", {}) if isinstance(mp, dict) else {}
    value = raw.get("member_id") or mp.get("member_id") or mp.get("id")
    return str(value) if value is not None else ""


def expects_evidence_shard(mp):
    raw = mp.get("raw", {}) if isinstance(mp, dict) else {}
    evidence_fields = [
        "manual_source_records_count",
        "official_source_records_count",
        "parliament_source_records_count",
        "written_questions_total",
        "registered_interests_total",
        "edms_signed",
    ]
    return any(is_number(raw.get(field)) and raw.get(field) > 0 for field in evidence_fields)


def validate_source_shard(path):
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    records = payload.get("records", [])
    audit = payload.get("source_audit", [])
    if not isinstance(records, list):
        raise ValueError(f"{path} records must be a list")
    if not isinstance(audit, list):
        raise ValueError(f"{path} source_audit must be a list")
    for index, entry in enumerate(audit):
        if entry.get("status") not in ALLOWED_AUDIT_STATUSES:
            raise ValueError(f"{path} source_audit entry {index} has invalid status {entry.get('status')!r}")
    return len(records), len(audit)


def validate_source_shards(mps):
    if not SOURCE_SHARDS_DIR.exists():
        raise ValueError(f"{SOURCE_SHARDS_DIR} is missing")
    shard_paths = sorted(SOURCE_SHARDS_DIR.glob("*.json"))
    if not shard_paths:
        raise ValueError(f"{SOURCE_SHARDS_DIR} contains no source shards")

    missing = []
    expected_missing = []
    required_sample_ids = {member_id_for(mp) for mp in mps[:10] if member_id_for(mp)}
    for mp in mps:
        member_id = member_id_for(mp)
        if not member_id:
            raise ValueError(f"{mp.get('name', 'MP')} missing member_id for source shard")
        path = SOURCE_SHARDS_DIR / f"{member_id}.json"
        if not path.exists():
            missing.append(member_id)
            if expects_evidence_shard(mp):
                expected_missing.append(member_id)

    if required_sample_ids.intersection(missing):
        raise ValueError("one or more sampled MP source shards are missing")
    if len(missing) / max(1, len(mps)) > 0.2:
        raise ValueError(f"{len(missing)} MPs lack source shards")
    if len(expected_missing) / max(1, len(mps)) > 0.2:
        raise ValueError(f"{len(expected_missing)} MPs with expected evidence lack source shards")

    record_count = 0
    audit_count = 0
    for path in shard_paths:
        records, audit = validate_source_shard(path)
        record_count += records
        audit_count += audit
    return len(shard_paths), record_count, audit_count


def main():
    try:
        ranked_payload = load_json(RANKED_MPS_PATH)
        mps = ranked_mps(ranked_payload)
        mp_count = validate_ranked(ranked_payload)
        shard_count, record_count, audit_count = validate_source_shards(mps)
        if SOURCE_RECORDS_PATH.exists():
            validate_sources(load_json(SOURCE_RECORDS_PATH))
    except (ValueError, json.JSONDecodeError) as error:
        return fail(str(error))
    print(f"Validated {mp_count} MPs in {RANKED_MPS_PATH}")
    print(f"Validated {shard_count} source shards in {SOURCE_SHARDS_DIR}")
    print(f"Validated {record_count} source records in source shards")
    print(f"Validated {audit_count} source audit entries in source shards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
