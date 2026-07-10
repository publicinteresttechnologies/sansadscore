from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .config import SOURCE_RECORDS_PATH
from .json_io import read_json, write_json

SOURCE_SUMMARY_PATH = Path("data/source_summary.json")


def member_key(item):
    member_id = item.get("member_id")
    if member_id is not None:
        return str(member_id)
    return f"{item.get('mp_name') or item.get('name') or ''}|{item.get('constituency') or ''}"


def connector_counts(records):
    counts = defaultdict(int)
    for record in records:
        counts[record.get("source_connector") or "unknown"] += 1
    return dict(sorted(counts.items()))


def status_counts(audit):
    counts = defaultdict(int)
    for entry in audit:
        counts[entry.get("status") or "unknown"] += 1
    return dict(sorted(counts.items()))


def first_member_record(item):
    return {
        "member_id": item.get("member_id"),
        "mp_name": item.get("mp_name") or item.get("name"),
        "constituency": item.get("constituency"),
    }


def build_source_summary(source_payload):
    records = source_payload.get("records", []) if isinstance(source_payload, dict) else []
    audit = source_payload.get("source_audit", []) if isinstance(source_payload, dict) else []
    member_rows = {}
    record_counts = defaultdict(int)
    audit_counts = defaultdict(int)

    for record in records:
        key = member_key(record)
        member_rows.setdefault(key, first_member_record(record))
        record_counts[key] += 1

    for entry in audit:
        key = member_key(entry)
        member_rows.setdefault(key, first_member_record(entry))
        audit_counts[key] += 1

    members = []
    for key in sorted(member_rows, key=lambda value: (member_rows[value].get("mp_name") or "")):
        members.append(
            {
                **member_rows[key],
                "source_records_count": record_counts[key],
                "source_audit_count": audit_counts[key],
            }
        )

    return {
        "last_source_collection": source_payload.get("last_source_collection") or datetime.now(timezone.utc).strftime("%d %B %Y"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary_note": "Compact deploy-safe aggregate counts only. Full per-MP evidence is deployed in data/sources/<member_id>.json shards and is loaded only when a user opens Sources & Methods.",
        "connector_counts": connector_counts(records),
        "audit_status_counts": status_counts(audit),
        "members": members,
    }


def write_public_source_summary(source_payload=None):
    if source_payload is None and not SOURCE_RECORDS_PATH.exists():
        return None
    payload = source_payload if source_payload is not None else read_json(SOURCE_RECORDS_PATH)
    summary = build_source_summary(payload)
    write_json(SOURCE_SUMMARY_PATH, summary)
    return SOURCE_SUMMARY_PATH
