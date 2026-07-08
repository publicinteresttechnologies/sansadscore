from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .config import SOURCE_RECORDS_PATH
from .json_io import read_json, write_json

SOURCE_SUMMARY_PATH = Path("data/source_summary.json")
MAX_RECORDS_PER_MEMBER = 5


def member_key(item):
    member_id = item.get("member_id")
    if member_id is not None:
        return str(member_id)
    return f"{item.get('mp_name') or item.get('name') or ''}|{item.get('constituency') or ''}"


def compact_record(record):
    return {
        "member_id": record.get("member_id"),
        "mp_name": record.get("mp_name") or record.get("name"),
        "constituency": record.get("constituency"),
        "source_connector": record.get("source_connector"),
        "source_type": record.get("source_type") or record.get("evidence_type"),
        "summary": record.get("summary") or record.get("type") or "Source record",
        "source_url": record.get("source_url") or record.get("endpoint_or_url"),
    }


def compact_audit(entry):
    return {
        "member_id": entry.get("member_id"),
        "mp_name": entry.get("mp_name"),
        "constituency": entry.get("constituency"),
        "connector": entry.get("connector"),
        "source_name": entry.get("source_name"),
        "status": entry.get("status"),
        "records_found": entry.get("records_found", 0),
        "scored": bool(entry.get("scored")),
        "diagnostic_only": bool(entry.get("diagnostic_only")),
        "context_only": bool(entry.get("context_only")),
    }


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
    records_by_member = defaultdict(list)
    audit_by_member = defaultdict(list)

    for record in records:
        key = member_key(record)
        member_rows.setdefault(key, first_member_record(record))
        if len(records_by_member[key]) < MAX_RECORDS_PER_MEMBER:
            records_by_member[key].append(compact_record(record))

    for entry in audit:
        key = member_key(entry)
        member_rows.setdefault(key, first_member_record(entry))
        audit_by_member[key].append(compact_audit(entry))

    members = []
    for key in sorted(member_rows, key=lambda value: (member_rows[value].get("mp_name") or "")):
        members.append(
            {
                **member_rows[key],
                "sample_records": records_by_member.get(key, []),
                "source_audit": audit_by_member.get(key, []),
                "source_records_count": sum(1 for record in records if member_key(record) == key),
                "source_audit_count": len(audit_by_member.get(key, [])),
            }
        )

    return {
        "last_source_collection": source_payload.get("last_source_collection") or datetime.now(timezone.utc).strftime("%d %B %Y"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary_note": "Compact deploy-safe source summary. The full source ledger is retained in history when available but not deployed as a large static asset.",
        "connector_counts": connector_counts(records),
        "audit_status_counts": status_counts(audit),
        "members": members,
    }


def write_public_source_summary():
    if not SOURCE_RECORDS_PATH.exists():
        return None
    payload = read_json(SOURCE_RECORDS_PATH)
    summary = build_source_summary(payload)
    write_json(SOURCE_SUMMARY_PATH, summary)
    return SOURCE_SUMMARY_PATH
