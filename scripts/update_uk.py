import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

OUTPUT_PATH = Path("data/ranked_mps.json")
SOURCE_RECORDS_PATH = Path("data/source_records.json")

MEMBERS_API = "https://members-api.parliament.uk/api/Members"
MEMBERS_SEARCH = "https://members-api.parliament.uk/api/Members/Search"
WRITTEN_QUESTIONS_API = "https://questions-statements-api.parliament.uk/api/writtenquestions/questions"

HEADERS = {
    "User-Agent": "Commons Score public-record updater"
}

COMMON_LOCAL_WORDS = {
    "and", "the", "of", "in", "upon", "north", "south", "east", "west",
    "central", "new", "city", "county", "shire", "borough"
}


def get_json(url, params=None):
    response = requests.get(url, params=params or {}, headers=HEADERS, timeout=40)
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
        if isinstance(data.get("data"), list):
            return data["data"]

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
    return re.sub(r"\s+", " ", str(value)).strip()


def norm(value):
    return clean(value).lower()


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
        time.sleep(0.25)

        total = data.get("totalResults") or data.get("total") or 0

        if total and skip >= total:
            break

        if skip > 1000:
            break

    return all_mps


def endpoint_count(url):
    try:
        data = get_json(url)
        items = extract_items(data)

        if isinstance(data, dict):
            for key in ["totalResults", "total", "totalCount", "resultCount"]:
                if isinstance(data.get(key), int):
                    return data[key], True

        return len(items), True
    except Exception:
        return 0, False


def get_member_public_record(member_id):
    endpoints = {
        "registered_interests": f"{MEMBERS_API}/{member_id}/RegisteredInterests",
        "edms": f"{MEMBERS_API}/{member_id}/Edms",
        "focus_items": f"{MEMBERS_API}/{member_id}/Focus",
        "votes": f"{MEMBERS_API}/{member_id}/Voting"
    }

    record = {}

    for key, url in endpoints.items():
        count, ok = endpoint_count(url)
        record[key] = count
        record[f"{key}_ok"] = ok
        time.sleep(0.12)

    return record


def get_question_member_id(item):
    value = item.get("value", item)

    candidates = [
        value.get("askingMemberId"),
        value.get("memberId"),
        value.get("tablingMemberId"),
        get_nested(value, "askingMember", "id"),
        get_nested(value, "member", "id"),
        get_nested(value, "tablingMember", "id")
    ]

    for candidate in candidates:
        if candidate is None:
            continue

        try:
            return int(candidate)
        except Exception:
            continue

    return None


def question_text(item):
    value = item.get("value", item)

    parts = []

    possible_keys = [
        "questionText",
        "question",
        "text",
        "heading",
        "uin",
        "answeringBody",
        "answeringBodyName",
        "dateTabled",
        "dateForAnswer"
    ]

    for key in possible_keys:
        if value.get(key):
            parts.append(str(value.get(key)))

    dumped = json.dumps(value, ensure_ascii=False)
    parts.append(dumped)

    return " ".join(parts)


def fetch_written_questions_by_member():
    questions_by_member = {}
    skip = 0
    take = 100
    max_rows = 12000

    print("Fetching written questions...", flush=True)

    while skip < max_rows:
        params = {
            "house": "Commons",
            "skip": skip,
            "take": take
        }

        try:
            data = get_json(WRITTEN_QUESTIONS_API, params=params)
        except Exception as error:
            print(f"Written Questions API failed at skip {skip}: {error}", flush=True)
            break

        items = extract_items(data)

        if not items:
            break

        for item in items:
            member_id = get_question_member_id(item)

            if member_id is None:
                continue

            questions_by_member.setdefault(member_id, []).append(question_text(item))

        skip += take

        total = data.get("totalResults") or data.get("total") or data.get("totalCount") or 0

        if total and skip >= total:
            break

        print(f"Fetched {skip} written-question rows", flush=True)
        time.sleep(0.15)

    print(f"Written questions mapped for {len(questions_by_member)} MPs.", flush=True)
    return questions_by_member


def constituency_tokens(constituency):
    words = re.split(r"[^a-zA-Z]+", constituency.lower())

    tokens = []

    for word in words:
        if len(word) < 5:
            continue
        if word in COMMON_LOCAL_WORDS:
            continue
        tokens.append(word)

    return list(dict.fromkeys(tokens))


def question_matches_constituency(question, constituency):
    q = question.lower()
    c = constituency.lower()

    if c and c in q:
        return True

    tokens = constituency_tokens(constituency)

    for token in tokens:
        if token in q:
            return True

    return False


def load_source_records():
    if not SOURCE_RECORDS_PATH.exists():
        return []

    try:
        data = json.loads(SOURCE_RECORDS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(data, dict) and isinstance(data.get("records"), list):
        return data["records"]

    if isinstance(data, list):
        return data

    return []


def record_matches_member(record, member):
    record_member_id = record.get("member_id") or record.get("mp_id")
    if record_member_id is not None:
        try:
            if int(record_member_id) == int(member["id"]):
                return True
        except Exception:
            pass

    record_name = norm(record.get("mp_name") or record.get("name"))
    record_constituency = norm(record.get("constituency"))

    if record_name and record_name == norm(member["name"]):
        return True

    if record_constituency and record_constituency == norm(member["constituency"]):
        return True

    return False


def source_strength(record):
    source_type = norm(record.get("source_type") or record.get("evidence_type") or record.get("source_kind"))

    url = norm(record.get("source_url") or record.get("url"))

    if "parliament" in source_type or "hansard" in source_type:
        return 80
    if "official" in source_type or "government" in source_type or "council" in source_type or "regulator" in source_type:
        return 85
    if "ipsa" in source_type:
        return 80
    if "local_news" in source_type or "news" in source_type:
        return 45
    if "mp_claim" in source_type or "mp website" in source_type or "social" in source_type:
        return 15

    if "parliament.uk" in url or "gov.uk" in url or "nhs.uk" in url or "theipsa.org.uk" in url:
        return 80
    if url:
        return 35

    return 0


def explicit_score(record):
    for key in ["score", "metric_score", "evidence_score"]:
        if key in record:
            try:
                return clamp(float(record[key]))
            except Exception:
                pass

    return None


def source_record_scores(records):
    result = {
        "promise": 0,
        "local_action": 0,
        "follow_up": 0,
        "outcome": 0,
        "public_value": 0,
        "trust_bonus": 0
    }

    if not records:
        return result

    strengths = [source_strength(record) for record in records]
    avg_strength = sum(strengths) / len(strengths) if strengths else 0
    result["trust_bonus"] = clamp(min(25, len(records) * 4) + avg_strength * 0.20)

    has_promise = False
    has_action = False
    has_follow_up = False
    has_outcome = False
    has_public_value = False

    for record in records:
        record_type = norm(record.get("type") or record.get("record_type") or record.get("category"))
        status = norm(record.get("status"))
        strength = source_strength(record)
        score = explicit_score(record)

        if score is None:
            score = strength

        if any(word in record_type for word in ["promise", "pledge", "manifesto"]):
            has_promise = True
            result["promise"] = max(result["promise"], max(20, score))

        if any(word in record_type for word in ["action", "question", "debate", "letter", "campaign", "meeting"]):
            has_action = True
            result["local_action"] = max(result["local_action"], max(25, score))

        if any(word in record_type for word in ["follow", "follow-up", "repeat", "pressure"]):
            has_follow_up = True
            result["follow_up"] = max(result["follow_up"], max(45, score))

        if any(word in record_type for word in ["outcome", "delivery", "result", "completed", "approved", "funded"]):
            has_outcome = True
            result["outcome"] = max(result["outcome"], max(60, score))

        if any(word in record_type for word in ["cost", "value", "ipsa", "expense", "funding", "public_value"]):
            has_public_value = True
            result["public_value"] = max(result["public_value"], max(35, score))

        if status in ["completed", "delivered", "approved", "funded"]:
            has_outcome = True
            result["outcome"] = max(result["outcome"], 80)

    if has_promise and not has_action and not has_follow_up and not has_outcome:
        result["follow_up"] = max(result["follow_up"], 10)

    if has_action and not has_follow_up and not has_outcome:
        result["follow_up"] = max(result["follow_up"], 35)

    if has_follow_up and not has_outcome:
        result["follow_up"] = max(result["follow_up"], 60)

    if has_outcome:
        result["follow_up"] = max(result["follow_up"], result["outcome"])

    if has_public_value and result["public_value"] < 50:
        result["public_value"] = 50

    return result


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


def build_scored_mp(member, public_record, questions_by_member, source_records):
    member_id = int(member["id"])

    member_questions = questions_by_member.get(member_id, [])
    written_questions_count = len(member_questions)

    local_questions_count = sum(
        1 for question in member_questions
        if question_matches_constituency(question, member["constituency"])
    )

    matched_records = [
        record for record in source_records
        if record_matches_member(record, member)
    ]

    record_scores = source_record_scores(matched_records)

    focus_score = count_score(public_record["focus_items"], 5)
    local_questions_score = count_score(local_questions_count, 10)
    written_questions_score = count_score(written_questions_count, 50)
    votes_score = count_score(public_record["votes"], 250)
    edms_score = count_score(public_record["edms"], 20)

    constituency_focus = clamp(
        local_questions_score * 0.45
        + focus_score * 0.25
        + record_scores["local_action"] * 0.30
    )

    parliamentary_work = clamp(
        written_questions_score * 0.45
        + votes_score * 0.25
        + edms_score * 0.15
        + focus_score * 0.15
    )

    promise_follow_through = clamp(
        record_scores["promise"] * 0.20
        + record_scores["follow_up"] * 0.50
        + record_scores["outcome"] * 0.30
    )

    trust_and_evidence = clamp(
        50
        + (10 if public_record.get("registered_interests_ok") else 0)
        + record_scores["trust_bonus"]
    )

    if record_scores["public_value"] > 0:
        public_value = record_scores["public_value"]
    else:
        public_value = clamp(
            constituency_focus * 0.35
            + parliamentary_work * 0.35
            + trust_and_evidence * 0.10
        )

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
            "registered_interests_count": public_record["registered_interests"],
            "edms_count": public_record["edms"],
            "focus_items_count": public_record["focus_items"],
            "votes_count": public_record["votes"],
            "written_questions_count": written_questions_count,
            "local_questions_count": local_questions_count,
            "manual_source_records_count": len(matched_records)
        }
    }


def main():
    print("Fetching current House of Commons MPs...", flush=True)
    members = get_current_commons_mps()

    if len(members) < 500:
        raise RuntimeError(f"Only found {len(members)} MPs. Refusing to overwrite data.")

    print(f"Found {len(members)} MPs.", flush=True)

    questions_by_member = fetch_written_questions_by_member()
    source_records = load_source_records()

    print(f"Loaded {len(source_records)} manual/source records.", flush=True)

    scored = []

    for index, member in enumerate(members, start=1):
        print(f"{index}/{len(members)}: {member['name']}", flush=True)
        public_record = get_member_public_record(member["id"])
        scored.append(build_scored_mp(member, public_record, questions_by_member, source_records))
        time.sleep(0.12)

    scored.sort(
        key=lambda item: (
            item["score"],
            item["variables"]["Constituency Focus"],
            item["variables"]["Parliamentary Work"],
            item["variables"]["Promise Follow-Through"],
            item["variables"]["Public Value"],
            item["variables"]["Trust & Evidence"],
            item["raw"]["written_questions_count"],
            item["raw"]["local_questions_count"],
            item["raw"]["votes_count"],
            item["raw"]["edms_count"],
            item["raw"]["focus_items_count"],
            item["raw"]["manual_source_records_count"]
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
            "sources_used": [
                "UK Parliament Members API",
                "UK Parliament member focus, voting, EDM and registered-interests endpoints",
                "UK Parliament Written Questions API",
                "Constituency keyword matching",
                "Optional data/source_records.json for local promises, delivery evidence, outcomes and public-value records"
            ],
            "scoring_rule": "No source, no score. Scores are generated from available public records and should be read as source-backed indicators."
        },
        "mps": output_mps
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
