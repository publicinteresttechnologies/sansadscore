from datetime import datetime, timezone

from .config import INTERESTS_API
from .http import get_json
from .scoring import clean

INTERESTS_ENDPOINT = f"{INTERESTS_API}/api/v1/Interests"


def extract_items(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["items", "value", "results", "data"]:
            if isinstance(data.get(key), list):
                return data[key]
    return []


def nested(data, *keys):
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def interest_summary(item):
    value = item.get("value", item) if isinstance(item, dict) else {}
    return clean(
        value.get("summary")
        or value.get("description")
        or nested(value, "category", "name")
        or "Published interest record"
    )


def interest_category(item):
    value = item.get("value", item) if isinstance(item, dict) else {}
    return clean(
        nested(value, "category", "name")
        or value.get("categoryName")
        or value.get("interestCategoryName")
        or "Unknown"
    )


def interest_id(item):
    value = item.get("value", item) if isinstance(item, dict) else {}
    return value.get("id")


def collect_interests_api_records(member, take=20):
    data = get_json(
        INTERESTS_ENDPOINT,
        params={
            "MemberId": member["id"],
            "Take": take,
            "Skip": 0,
            "ExpandChildInterests": "true",
        },
    )
    items = extract_items(data)
    records = []

    for item in items[:take]:
        item_id = interest_id(item)
        source_url = f"{INTERESTS_ENDPOINT}/{item_id}" if item_id else INTERESTS_ENDPOINT
        records.append(
            {
                "auto_collected": True,
                "member_id": member["id"],
                "mp_name": member["name"],
                "constituency": member["constituency"],
                "party": member["party"],
                "type": "trust",
                "summary": f"Interests API record: {interest_summary(item)}",
                "source_url": source_url,
                "source_type": "parliament",
                "evidence_type": "parliament",
                "score": 70,
                "source_connector": "interests_api",
                "interests_category": interest_category(item),
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    return records
