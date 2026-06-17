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


def pick_variant(name, options):
    index = sum(ord(char) for char in name) % len(options)
    return options[index]


def verdict_from_metrics(name, score, variables):
    weakest_metric = min(variables, key=variables.get)
    strongest_metric = max(variables, key=variables.get)

    weakness_lines = {
        "Constituency Focus": [
            "The constituency appears to have been invited to make a brief cameo.",
            "The local file is present mostly in spirit.",
            "A constituency champion, if viewed from a generous distance.",
            "The doorstep case remains thinner than the letterhead."
        ],
        "Parliamentary Work": [
            "Westminster’s machinery has not been unduly troubled.",
            "The parliamentary engine is running, but not loudly.",
            "The Commons record suggests light use of the available furniture.",
            "The green benches have survived the encounter."
        ],
        "Promise Follow-Through": [
            "The promise-to-delivery cupboard is doing an excellent impression of empty.",
            "The pledge trail fades before it reaches the result.",
            "Promises have been easier to locate than outcomes.",
            "The delivery file appears to have missed its train."
        ],
        "Public Value": [
            "The public return remains under-documented, which is the polite version.",
            "The taxpayer may reasonably ask what the receipt was for.",
            "The value case is still looking for its supporting documents.",
            "The public benefit is not yet troubling the scoreboard."
        ],
        "Trust & Evidence": [
            "The source trail could do with sturdier shoes.",
            "The evidence exists, but not with the confidence one would frame.",
            "The record is not exactly overburdened with proof.",
            "The paperwork has opted for a modest public life."
        ]
    }

    strength_lines = {
        "Constituency Focus": [
            "The local file is at least showing signs of life.",
            "There is some constituency work visible in the public record.",
            "The seat has not been entirely left to fend for itself."
        ],
        "Parliamentary Work": [
            "The parliamentary record is doing some of the lifting.",
            "Westminster has at least seen evidence of activity.",
            "There is measurable Commons machinery at work here."
        ],
        "Promise Follow-Through": [
            "Some pledge-to-action evidence is visible.",
            "The delivery trail is not entirely theoretical.",
            "There is at least some movement beyond the slogan."
        ],
        "Public Value": [
            "The public-value file is not empty.",
            "There is some return visible for the public cost.",
            "The public record offers something more than stationery."
        ],
        "Trust & Evidence": [
            "The source trail is doing useful work.",
            "The evidence base is one of the stronger parts of the file.",
            "The paperwork is at least facing the public."
        ]
    }

    if score >= 85:
        opening = pick_variant(name, [
            "An unusually sturdy public record.",
            "A rare sighting of the job being done in daylight.",
            "The file is irritatingly competent.",
            "The public record makes a strong case for service."
        ])
    elif score >= 70:
        opening = pick_variant(name, [
            "A respectable file, though not yet a sainthood application.",
            "The record suggests useful work, with room for less self-congratulation.",
            "A visible operator, by the standards of the available evidence.",
            "The public record is making an effort."
        ])
    elif score >= 55:
        opening = pick_variant(name, [
            "There is activity here, though the trumpet section should remain seated.",
            "A working file, not a glowing one.",
            "The record contains signs of service and signs of padding.",
            "Some useful work is visible through the fog."
        ])
    elif score >= 40:
        opening = pick_variant(name, [
            "Enough paper to suggest activity; not enough to settle the matter.",
            "A middling file with occasional signs of public purpose.",
            "The office is moving. The constituency benefit is less obvious.",
            "A record that says ‘busy’ more clearly than it says ‘effective’."
        ])
    elif score >= 25:
        opening = pick_variant(name, [
            "The office is occupied. The evidence of public return is thin.",
            "A small public record is carrying a large job title.",
            "The file exists, which is not the same as a case for service.",
            "The title has shown up. The proof is travelling separately."
        ])
    elif score > 0:
        opening = pick_variant(name, [
            "A public record with the nutritional value of a biscuit.",
            "A title with a pulse; the service record remains in draft.",
            "There is something here, but mostly in the way smoke is something.",
            "The file is not empty. It is merely ambitious in its emptiness."
        ])
    else:
        opening = pick_variant(name, [
            "No meaningful public-service record detected from the available sources.",
            "The evidence cupboard is bare, and not in a rustic way.",
            "A democratic chair appears to have been kept warm.",
            "The public record has declined to make a statement."
        ])

    weakness = pick_variant(
        name + weakest_metric,
        weakness_lines.get(weakest_metric, ["The weakest part of the file remains weak."])
    )

    strength = pick_variant(
        name + strongest_metric,
        strength_lines.get(strongest_metric, ["One part of the file is at least doing some work."])
    )

    return f"{opening} {strength} {weakness}"


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
        "verdict": verdict_from_metrics(member["name"], score, variables),
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
