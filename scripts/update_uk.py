import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

OUTPUT_PATH = Path("data/ranked_mps.json")

MEMBERS_API = "https://members-api.parliament.uk/api/Members"
MEMBERS_SEARCH = "https://members-api.parliament.uk/api/Members/Search"

HEADERS = {
    "User-Agent": "Commons Score public-record updater"
}


def get_json(url, params=None):
    response = requests.get(url, params=params or {}, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


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

    return []


def get_nested(data, *keys):
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)

    return current


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def get_current_commons_mps():
    all_mps = []
    skip = 0
    take = 20

    while True:
        params = {
            "House": 1,
            "IsCurrentMember": "true",
            "skip": skip,
            "take": take
        }

        data = get_json(MEMBERS_SEARCH, params=params)
        items = extract_items(data)

        if not items:
            break

        for item in items:
            value = item.get("value", item)

            member_id = value.get("id")
            name = (
                value.get("nameDisplayAs")
                or value.get("nameFullTitle")
                or value.get("nameListAs")
                or value.get("name")
                or ""
            )

            party = (
                get_nested(value, "latestParty", "name")
                or value.get("party")
                or ""
            )

            constituency = (
                get_nested(value, "latestHouseMembership", "membershipFrom")
                or get_nested(value, "latestHouseMembership", "membershipFromId")
                or ""
            )

            house = (
                get_nested(value, "latestHouseMembership", "house")
                or value.get("house")
                or ""
            )

            if not member_id or not name:
                continue

            if house and "commons" not in str(house).lower() and str(house) != "1":
                continue

            all_mps.append({
                "id": member_id,
                "name": clean(name),
                "party": clean(party),
                "constituency": clean(constituency)
            })

        skip += take
        time.sleep(0.4)

        total = data.get("totalResults") or data.get("total") or 0
        if total and skip >= total:
            break

        if skip > 1000:
            break

    return all_mps


def count_endpoint_items(url):
    try:
        data = get_json(url)
        items = extract_items(data)

        if isinstance(data, dict):
            if isinstance(data.get("totalResults"), int):
                return data["totalResults"]
            if isinstance(data.get("total"), int):
                return data["total"]

        return len(items)
    except Exception:
        return 0


def get_member_public_record(member_id):
    record = {
        "registered_interests": 0,
        "edms": 0,
        "focus_items": 0,
        "votes": 0,
        "has_official_record": True
    }

    endpoints = {
        "registered_interests": f"{MEMBERS_API}/{member_id}/RegisteredInterests",
        "edms": f"{MEMBERS_API}/{member_id}/Edms",
        "focus_items": f"{MEMBERS_API}/{member_id}/Focus",
        "votes": f"{MEMBERS_API}/{member_id}/Voting"
    }

    for key, url in endpoints.items():
        record[key] = count_endpoint_items(url)
        time.sleep(0.2)

    return record


def clamp(value):
    return max(0, min(100, round(value)))


def count_score(count, cap):
    if cap <= 0:
        return 0
    return clamp((count / cap) * 100)


def grade_from_score(score):
    if score >= 95:
        return "A++"
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B++"
    if score >= 60:
        return "B"
    if score >= 50:
        return "C++"
    if score >= 40:
        return "C"
    if score >= 30:
        return "D++"
    if score >= 20:
        return "D"
    if score >= 10:
        return "F"
    if score >= 1:
        return "F-"
    return "F--"


def verdict_from_metrics(score, variables):
    if variables["Promise Follow-Through"] == 0:
        if score >= 40:
            return "Active enough to be visible. Still no verified promise-to-delivery trail."
        if score >= 20:
            return "The office is occupied. The delivery file remains thin."
        return "The title is doing more work than the evidence."

    if variables["Constituency Focus"] < 20:
        return "Westminster may have seen them. The constituency record is harder to spot."

    if variables["Parliamentary Work"] < 20:
        return "Local claims aside, the parliamentary engine looks underused."

    if variables["Trust & Evidence"] < 40:
        return "There is activity here, but the source trail is not strong enough."

    if score >= 85:
        return "The public record makes a strong case for visible service."
    if score >= 70:
        return "A substantial record, though the constituency benefit still needs reading carefully."
    if score >= 55:
        return "There is work on the file. Whether it reaches the doorstep is another matter."
    if score >= 40:
        return "Some public activity. Not yet a convincing case for energetic service."
    if score >= 25:
        return "The office is occupied. The evidence of public return is thin."
    if score > 0:
        return "A small public record, doing a large amount of reputational work."

    return "No meaningful public-service record detected from the available sources."


def build_scored_mp(member, record):
    constituency_focus = count_score(record["focus_items"], 5)

    parliamentary_work = clamp(
        count_score(record["votes"], 250) * 0.45
        + count_score(record["edms"], 20) * 0.25
        + constituency_focus * 0.30
    )

    promise_follow_through = 0

    public_value = clamp(
        parliamentary_work * 0.65
        + constituency_focus * 0.35
    )

    trust_and_evidence = 60
    if record["registered_interests"] > 0:
        trust_and_evidence = 70

    score = clamp(
        constituency_focus * 0.25
        + parliamentary_work * 0.25
        + promise_follow_through * 0.25
        + public_value * 0.15
        + trust_and_evidence * 0.10
    )

    variables = {
        "Constituency Focus": constituency_focus,
        "Parliamentary Work": parliamentary_work,
        "Promise Follow-Through": promise_follow_through,
        "Public Value": public_value,
        "Trust & Evidence": trust_and_evidence
    }

    return {
        "photo_url": f"https://members-api.parliament.uk/api/Members/{member['id']}/Thumbnail",
        "name": member["name"],
        "constituency": member["constituency"],
        "party": member["party"],
        "grade": grade_from_score(score),
        "score": score,
        "variables": variables,
        "legal_flag": "",
        "verdict": verdict_from_metrics(score, variables),
        "source_url": f"https://members.parliament.uk/member/{member['id']}/contact",
        "raw": {
            "member_id": member["id"],
            "registered_interests_count": record["registered_interests"],
            "edms_count": record["edms"],
            "focus_items_count": record["focus_items"],
            "votes_count": record["votes"]
        }
    }


def main():
    print("Fetching current House of Commons MPs...", flush=True)
    members = get_current_commons_mps()

    if len(members) < 500:
        raise RuntimeError(f"Only found {len(members)} MPs. Refusing to overwrite data.")

    print(f"Found {len(members)} MPs.", flush=True)

    scored = []

    for index, member in enumerate(members, start=1):
        print(f"{index}/{len(members)}: {member['name']}", flush=True)
        record = get_member_public_record(member["id"])
        scored.append(build_scored_mp(member, record))
        time.sleep(0.2)

    scored.sort(
        key=lambda item: (
            item["score"],
            item["variables"]["Constituency Focus"],
            item["variables"]["Parliamentary Work"],
            item["variables"]["Public Value"],
            item["variables"]["Trust & Evidence"],
            item["raw"]["votes_count"],
            item["raw"]["edms_count"],
            item["raw"]["focus_items_count"],
            item["raw"]["registered_interests_count"]
        ),
        reverse=True
    )

    output_mps = []

    for rank, mp in enumerate(scored, start=1):
        mp["rank"] = rank
        output_mps.append(mp)

    output = {
        "last_updated": datetime.now(timezone.utc).strftime("%d %B %Y"),
        "methodology": {
            "note": "Automated public-record score. It is not an endorsement, voting recommendation or claim about private intent.",
            "question": "Is this MP working for their constituency and doing the job of an MP?",
            "weights": {
                "Constituency Focus": "25%",
                "Parliamentary Work": "25%",
                "Promise Follow-Through": "25%",
                "Public Value": "15%",
                "Trust & Evidence": "10%"
            },
            "scoring_rule": "No source, no score. Scores are generated from available public records and should be read as source-backed indicators."
        },
        "mps": output_mps
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
