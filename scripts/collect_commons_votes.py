import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

RANKED_MPS_PATH = Path("data/ranked_mps.json")
SOURCE_RECORDS_PATH = Path("data/source_records.json")

COMMONS_VOTES_SEARCH = "https://commonsvotes-api.parliament.uk/data/divisions.json/search"

HEADERS = {
    "User-Agent": "Commons Score Commons Votes collector"
}


def load_json(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def extract_items(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data.get("value"), list):
            return data["value"]
        if isinstance(data.get("results"), list):
            return data["results"]
        if isinstance(data.get("data"), list):
            return data["data"]

    return []


def member_id_from_mp(mp):
    raw = mp.get("raw", {})
    member_id = raw.get("member_id") or mp.get("member_id") or mp.get("id")

    if member_id is None:
        return None

    try:
        return int(member_id)
    except Exception:
        return None


def get_json(url, params=None):
    response = requests.get(url, params=params or {}, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def try_vote_search(member_id):
    param_attempts = [
        {"memberId": member_id},
        {"MemberId": member_id},
        {"queryParameters.memberId": member_id},
        {"queryParameters.MemberId": member_id},
        {"memberId": member_id, "skip": 0, "take": 100},
        {"MemberId": member_id, "skip": 0, "take": 100}
    ]

    for params in param_attempts:
        try:
            data = get_json(COMMONS_VOTES_SEARCH, params=params)
        except Exception:
            continue

        items = extract_items(data)

        total = (
            data.get("totalResults")
            or data.get("total")
            or data.get("totalCount")
            or len(items)
            if isinstance(data, dict)
            else len(items)
        )

        if total:
            return int(total), params

    return 0, None


def make_record(mp, vote_count, params_used):
    member_id = member_id_from_mp(mp)

    return {
        "auto_collected": True,
        "source_connector": "commons_votes_api",
        "member_id": member_id,
        "mp_name": mp.get("name"),
        "constituency": mp.get("constituency"),
        "party": mp.get("party"),
        "type": "parliamentary_work",
        "summary": f"Commons Votes API returned {vote_count} voting records for this MP.",
        "source_url": COMMONS_VOTES_SEARCH,
        "source_type": "parliament",
        "evidence_type": "official",
        "score": min(100, max(20, round((vote_count / 250) * 100))),
        "raw_vote_count": vote_count,
        "params_used": params_used,
        "collected_at": datetime.now(timezone.utc).isoformat()
    }


def dedupe_records(records):
    seen = set()
    output = []

    for record in records:
        key = (
            record.get("source_connector"),
            record.get("member_id"),
            record.get("source_url"),
            record.get("summary")
        )

        if key in seen:
            continue

        seen.add(key)
        output.append(record)

    return output


def main():
    ranked = load_json(RANKED_MPS_PATH, {"mps": []})
    mps = ranked.get("mps", [])

    if not mps:
        raise RuntimeError("No MPs found in data/ranked_mps.json. Run update_uk.py first.")

    existing = load_json(SOURCE_RECORDS_PATH, {"records": []})
    existing_records = existing.get("records", [])

    kept_records = [
        record for record in existing_records
        if record.get("source_connector") != "commons_votes_api"
    ]

    new_records = []

    print(f"Collecting Commons Votes API evidence for {len(mps)} MPs...", flush=True)

    for index, mp in enumerate(mps, start=1):
        member_id = member_id_from_mp(mp)

        if member_id is None:
            continue

        print(f"{index}/{len(mps)}: {mp.get('name')}", flush=True)

        vote_count, params_used = try_vote_search(member_id)

        if vote_count > 0:
            new_records.append(make_record(mp, vote_count, params_used))

        time.sleep(0.15)

    final_records = dedupe_records(kept_records + new_records)

    output = {
        "last_source_collection": datetime.now(timezone.utc).strftime("%d %B %Y"),
        "records": final_records
    }

    save_json(SOURCE_RECORDS_PATH, output)

    print(f"Wrote {len(new_records)} Commons Votes records.", flush=True)


if __name__ == "__main__":
    main()
