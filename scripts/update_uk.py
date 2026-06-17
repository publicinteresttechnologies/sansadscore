import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests

RANKED_OUTPUT_PATH = Path("data/ranked_mps.json")
SOURCE_RECORDS_PATH = Path("data/source_records.json")

MEMBERS_API = "https://members-api.parliament.uk/api/Members"
MEMBERS_SEARCH = "https://members-api.parliament.uk/api/Members/Search"

WRITTEN_QUESTIONS_API = "https://questions-statements-api.parliament.uk/api/writtenquestions/questions"
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
COMMONS_VOTES_SEARCH = "https://commonsvotes-api.parliament.uk/data/divisions.json/search"

COMMITTEES_API_CANDIDATES = [
    "https://committees-api.parliament.uk/api/Members/{member_id}/Committees",
    "https://committees-api.parliament.uk/api/Member/{member_id}/Committees",
    "https://committees-api.parliament.uk/api/Committees?memberId={member_id}",
    "https://committees-api.parliament.uk/api/Committees?MemberId={member_id}"
]

BILLS_API_CANDIDATES = [
    "https://bills-api.parliament.uk/api/v1/Bills?SearchTerm={query}",
    "https://bills-api.parliament.uk/api/v1/Bills?searchTerm={query}",
    "https://bills-api.parliament.uk/api/Bills?SearchTerm={query}",
    "https://bills-api.parliament.uk/api/Bills?searchTerm={query}"
]

IPSA_SOURCE_URLS = [
    "https://www.theipsa.org.uk/mp-staffing-business-costs",
    "https://www.theipsa.org.uk/mp-staffing-business-costs/annual-publications",
    "https://parliamentary-standards.org.uk/DataDownloads.aspx",
    "https://parliamentary-standards.org.uk/SearchFunction.aspx"
]

HEADERS = {
    "User-Agent": "Commons Score full public-record updater"
}

COMMON_LOCAL_WORDS = {
    "and", "the", "of", "in", "upon", "north", "south", "east", "west",
    "central", "new", "city", "county", "shire", "borough", "constituency"
}

MEDIA_TERMS = [
    "promise", "promised", "pledge", "pledged", "campaign", "called for",
    "urged", "pressed", "demanded", "secured", "funding", "funded",
    "delivered", "opened", "saved", "hospital", "school", "rail",
    "station", "road", "housing", "crime", "police", "NHS", "council",
    "bus", "transport", "planning", "flooding", "sewage", "water",
    "dentist", "GP", "local authority", "constituency"
]

OUTCOME_TERMS = [
    "delivered", "opened", "completed", "approved", "funded", "secured",
    "saved", "launched", "new hospital", "new school", "rail station",
    "bus route", "road upgrade", "NHS trust", "council approved",
    "government funding", "transport funding"
]


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


def get_json(url, params=None):
    response = requests.get(url, params=params or {}, headers=HEADERS, timeout=40)
    response.raise_for_status()
    return response.json()


def get_text(url, params=None):
    response = requests.get(url, params=params or {}, headers=HEADERS, timeout=40)
    response.raise_for_status()
    return response.text


def extract_items(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["items", "value", "results", "data"]:
            if isinstance(data.get(key), list):
                return data[key]

    return []


def get_nested(data, *keys):
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)

    return current


def text_dump(data):
    return json.dumps(data, ensure_ascii=False)


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
                "id": int(member_id),
                "name": clean(name),
                "party": clean(party),
                "constituency": clean(constituency)
            })

        skip += take
        time.sleep(0.2)

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
        time.sleep(0.08)

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
        "questionText", "question", "text", "heading", "uin",
        "answeringBody", "answeringBodyName", "dateTabled", "dateForAnswer"
    ]

    for key in possible_keys:
        if value.get(key):
            parts.append(str(value.get(key)))

    parts.append(json.dumps(value, ensure_ascii=False))

    return " ".join(parts)


def fetch_written_questions_by_member(max_rows=5000):
    questions_by_member = {}
    skip = 0
    take = 100

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
        time.sleep(0.08)

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

    for token in constituency_tokens(constituency):
        if token in q:
            return True

    return False


def base_record(member, record_type, summary, source_url, source_type, score, extra=None):
    record = {
        "auto_collected": True,
        "member_id": member["id"],
        "mp_name": member["name"],
        "constituency": member["constituency"],
        "party": member["party"],
        "type": record_type,
        "summary": clean(summary),
        "source_url": clean(source_url),
        "source_type": source_type,
        "evidence_type": source_type,
        "score": score,
        "collected_at": datetime.now(timezone.utc).isoformat()
    }

    if extra:
        record.update(extra)

    return record


def classify_media_title(title):
    text = title.lower()

    if any(word in text for word in ["delivered", "opened", "completed", "approved", "secured", "funding", "funded", "saved", "launched"]):
        return "outcome", 45

    if any(word in text for word in ["promise", "promised", "pledge", "pledged", "vow", "vowed"]):
        return "promise", 35

    if any(word in text for word in ["campaign", "called for", "urged", "pressed", "demanded", "backed"]):
        return "action", 35

    return "media_claim", 25


def build_media_query(member, terms):
    term_query = " OR ".join([f'"{term}"' for term in terms])
    return f'"{member["name"]}" "{member["constituency"]}" ({term_query})'


def search_gdelt(query, maxrecords=4):
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": maxrecords,
        "sort": "datedesc"
    }

    try:
        data = get_json(GDELT_DOC_API, params=params)
    except Exception:
        return []

    return data.get("articles", [])


def collect_media_records(member):
    records = []

    queries = [
        build_media_query(member, MEDIA_TERMS),
        build_media_query(member, OUTCOME_TERMS)
    ]

    for query in queries:
        articles = search_gdelt(query, maxrecords=4)

        for article in articles:
            title = clean(article.get("title"))
            url = clean(article.get("url"))
            domain = clean(article.get("domain"))
            seen_date = clean(article.get("seendate"))

            if not title or not url:
                continue

            record_type, score = classify_media_title(title)

            records.append(
                base_record(
                    member=member,
                    record_type=record_type,
                    summary=title,
                    source_url=url,
                    source_type="local_news",
                    score=score,
                    extra={
                        "source_connector": "gdelt_media",
                        "source_domain": domain,
                        "seen_date": seen_date
                    }
                )
            )

        time.sleep(0.08)

    return records


def collect_commons_votes_records(member):
    member_id = member["id"]

    param_attempts = [
        {"memberId": member_id},
        {"MemberId": member_id},
        {"queryParameters.memberId": member_id},
        {"queryParameters.MemberId": member_id},
        {"memberId": member_id, "skip": 0, "take": 100},
        {"MemberId": member_id, "skip": 0, "take": 100}
    ]

    vote_count = 0
    params_used = None

    for params in param_attempts:
        try:
            data = get_json(COMMONS_VOTES_SEARCH, params=params)
        except Exception:
            continue

        items = extract_items(data)

        if isinstance(data, dict):
            vote_count = (
                data.get("totalResults")
                or data.get("total")
                or data.get("totalCount")
                or len(items)
            )
        else:
            vote_count = len(items)

        if vote_count:
            params_used = params
            break

    if not vote_count:
        return []

    score = min(100, max(20, round((vote_count / 250) * 100)))

    return [
        base_record(
            member=member,
            record_type="action",
            summary=f"Commons Votes API returned {vote_count} voting records for this MP.",
            source_url=COMMONS_VOTES_SEARCH,
            source_type="parliament",
            score=score,
            extra={
                "source_connector": "commons_votes_api",
                "raw_vote_count": vote_count,
                "params_used": params_used
            }
        )
    ]


def collect_registered_interests_records(member):
    url = f"{MEMBERS_API}/{member['id']}/RegisteredInterests"

    try:
        data = get_json(url)
    except Exception:
        return []

    items = extract_items(data)
    records = []

    if not items:
        records.append(
            base_record(
                member=member,
                record_type="trust",
                summary="Register of Interests endpoint checked; no returned items.",
                source_url=url,
                source_type="parliament",
                score=60,
                extra={
                    "source_connector": "register_interests"
                }
            )
        )
        return records

    for item in items[:25]:
        dumped = text_dump(item)

        records.append(
            base_record(
                member=member,
                record_type="trust",
                summary=f"Registered interest record: {dumped[:260]}",
                source_url=url,
                source_type="parliament",
                score=70,
                extra={
                    "source_connector": "register_interests"
                }
            )
        )

    return records


def collect_experience_records(member):
    url = f"{MEMBERS_API}/{member['id']}/Experience"

    try:
        data = get_json(url)
    except Exception:
        return []

    items = extract_items(data)
    records = []

    for item in items[:20]:
        dumped = text_dump(item)
        lowered = dumped.lower()

        if "committee" in lowered:
            summary = f"Committee/experience record: {dumped[:260]}"
            score = 65
        elif "minister" in lowered or "secretary of state" in lowered:
            summary = f"Government/parliamentary role record: {dumped[:260]}"
            score = 60
        else:
            summary = f"Parliamentary experience record: {dumped[:260]}"
            score = 40

        records.append(
            base_record(
                member=member,
                record_type="action",
                summary=summary,
                source_url=url,
                source_type="parliament",
                score=score,
                extra={
                    "source_connector": "members_experience"
                }
            )
        )

    return records


def collect_contribution_summary_records(member):
    url = f"{MEMBERS_API}/{member['id']}/ContributionSummary"

    try:
        data = get_json(url)
    except Exception:
        return []

    dumped = text_dump(data)
    lowered = dumped.lower()

    records = []

    if "bill" in lowered:
        records.append(
            base_record(
                member=member,
                record_type="action",
                summary="Contribution summary includes bill-related activity.",
                source_url=url,
                source_type="parliament",
                score=65,
                extra={
                    "source_connector": "contribution_summary"
                }
            )
        )

    if "debate" in lowered:
        records.append(
            base_record(
                member=member,
                record_type="action",
                summary="Contribution summary includes debate activity.",
                source_url=url,
                source_type="parliament",
                score=60,
                extra={
                    "source_connector": "contribution_summary"
                }
            )
        )

    if "question" in lowered:
        records.append(
            base_record(
                member=member,
                record_type="action",
                summary="Contribution summary includes question activity.",
                source_url=url,
                source_type="parliament",
                score=60,
                extra={
                    "source_connector": "contribution_summary"
                }
            )
        )

    return records


def collect_contact_website_records(member):
    url = f"{MEMBERS_API}/{member['id']}/Contact"

    try:
        data = get_json(url)
    except Exception:
        return []

    dumped = text_dump(data)
    records = []

    website_candidates = re.findall(r"https?://[^\"\\\s<>]+", dumped)

    for website in website_candidates[:8]:
        if "parliament.uk" in website:
            continue

        records.append(
            base_record(
                member=member,
                record_type="promise",
                summary=f"MP website/contact source discovered: {website}",
                source_url=website,
                source_type="mp_website",
                score=15,
                extra={
                    "source_connector": "mp_contact_website"
                }
            )
        )

    return records


def collect_committees_records(member):
    records = []

    for template in COMMITTEES_API_CANDIDATES:
        url = template.format(member_id=member["id"])

        try:
            data = get_json(url)
        except Exception:
            continue

        items = extract_items(data)

        if not items:
            continue

        for item in items[:15]:
            dumped = text_dump(item)

            records.append(
                base_record(
                    member=member,
                    record_type="action",
                    summary=f"Committees API record: {dumped[:260]}",
                    source_url=url,
                    source_type="parliament",
                    score=70,
                    extra={
                        "source_connector": "committees_api"
                    }
                )
            )

        break

    return records


def collect_bills_records(member):
    name = clean(member["name"])
    encoded_name = quote_plus(name)
    records = []

    for template in BILLS_API_CANDIDATES:
        url = template.format(query=encoded_name)

        try:
            data = get_json(url)
        except Exception:
            continue

        items = extract_items(data)

        if not items:
            continue

        surname = name.lower().split()[-1]

        for item in items[:15]:
            dumped = text_dump(item)

            if surname not in dumped.lower():
                continue

            records.append(
                base_record(
                    member=member,
                    record_type="action",
                    summary=f"Bills API possible member-linked record: {dumped[:260]}",
                    source_url=url,
                    source_type="parliament",
                    score=65,
                    extra={
                        "source_connector": "bills_api"
                    }
                )
            )

        break

    return records


def fetch_ipsa_pages():
    pages = []

    for url in IPSA_SOURCE_URLS:
        try:
            pages.append((url, get_text(url)))
        except Exception:
            continue

        time.sleep(0.05)

    return pages


def collect_ipsa_records(member, ipsa_pages):
    records = []
    name = member["name"].lower()
    constituency = member["constituency"].lower()

    for url, page in ipsa_pages:
        page_lower = page.lower()

        if name in page_lower or constituency in page_lower:
            records.append(
                base_record(
                    member=member,
                    record_type="cost",
                    summary="IPSA business-cost source appears to contain this MP or constituency.",
                    source_url=url,
                    source_type="ipsa",
                    score=45,
                    extra={
                        "source_connector": "ipsa_public_costs"
                    }
                )
            )

    return records


def collect_hansard_like_records(member):
    url = f"{MEMBERS_API}/{member['id']}/ContributionSummary"

    try:
        data = get_json(url)
    except Exception:
        return []

    dumped = text_dump(data)
    lowered = dumped.lower()

    debate_markers = ["debate", "spoken", "contribution", "hansard", "commons", "question"]

    if not any(marker in lowered for marker in debate_markers):
        return []

    return [
        base_record(
            member=member,
            record_type="action",
            summary="Hansard-like contribution evidence found through member contribution summary.",
            source_url=url,
            source_type="parliament",
            score=60,
            extra={
                "source_connector": "hansard_like_contribution_summary"
            }
        )
    ]


def collect_all_source_records_for_member(member, ipsa_pages):
    collectors = [
        collect_registered_interests_records,
        collect_experience_records,
        collect_contribution_summary_records,
        collect_contact_website_records,
        collect_committees_records,
        collect_bills_records,
        collect_commons_votes_records,
        collect_hansard_like_records,
        collect_media_records
    ]

    records = []

    for collector in collectors:
        try:
            records.extend(collector(member))
        except Exception as error:
            print(f"{collector.__name__} failed for {member['name']}: {error}", flush=True)

        time.sleep(0.04)

    try:
        records.extend(collect_ipsa_records(member, ipsa_pages))
    except Exception as error:
        print(f"collect_ipsa_records failed for {member['name']}: {error}", flush=True)

    return records


def source_strength(record):
    source_type = norm(record.get("source_type") or record.get("evidence_type") or record.get("source_connector"))
    url = norm(record.get("source_url") or "")

    if "parliament" in source_type or "hansard" in source_type:
        return 80
    if "official" in source_type or "government" in source_type or "council" in source_type or "regulator" in source_type:
        return 85
    if "ipsa" in source_type:
        return 80
    if "local_news" in source_type or "news" in source_type:
        return 45
    if "mp_claim" in source_type or "mp_website" in source_type or "social" in source_type:
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
    result["trust_bonus"] = clamp(min(25, len(records) * 3) + avg_strength * 0.20)

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

        if any(word in record_type for word in ["action", "question", "debate", "letter", "campaign", "meeting", "parliamentary"]):
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


def question_matches_constituency(question, constituency):
    q = question.lower()
    c = constituency.lower()

    if c and c in q:
        return True

    for token in constituency_tokens(constituency):
        if token in q:
            return True

    return False


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

    weakness = pick_variant(name + weakest_metric, weakness_lines.get(weakest_metric, ["The weakest part of the file remains weak."]))
    strength = pick_variant(name + strongest_metric, strength_lines.get(strongest_metric, ["One part of the file is at least doing some work."]))

    return f"{opening} {strength} {weakness}"


def build_scored_mp(member, public_record, questions_by_member, records):
    member_questions = questions_by_member.get(member["id"], [])
    written_questions_count = len(member_questions)

    local_questions_count = sum(
        1 for question in member_questions
        if question_matches_constituency(question, member["constituency"])
    )

    record_scores = source_record_scores(records)

    focus_score = count_score(public_record["focus_items"], 5)
    local_questions_score = count_score(local_questions_count, 10)
    written_questions_score = count_score(written_questions_count, 50)
    votes_score = count_score(public_record["votes"], 250)
    edms_score = count_score(public_record["edms"], 20)

    constituency_focus = clamp(
        local_questions_score * 0.45
        + focus_score * 0.20
        + record_scores["local_action"] * 0.35
    )

    parliamentary_work = clamp(
        written_questions_score * 0.40
        + votes_score * 0.20
        + edms_score * 0.15
        + focus_score * 0.10
        + record_scores["local_action"] * 0.15
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
            "manual_source_records_count": len(records)
        }
    }


def dedupe_records(records):
    seen = set()
    output = []

    for record in records:
        key = (
            record.get("source_connector"),
            record.get("member_id"),
            record.get("type"),
            record.get("source_url"),
            record.get("summary")
        )

        if key in seen:
            continue

        seen.add(key)
        output.append(record)

    return output


def main():
    print("Fetching current House of Commons MPs...", flush=True)
    members = get_current_commons_mps()

    if len(members) < 500:
        raise RuntimeError(f"Only found {len(members)} MPs. Refusing to overwrite data.")

    print(f"Found {len(members)} MPs.", flush=True)

    questions_by_member = fetch_written_questions_by_member()
    ipsa_pages = fetch_ipsa_pages()

    all_source_records = []
    scored = []

    print("Collecting all source evidence and scoring MPs...", flush=True)

    for index, member in enumerate(members, start=1):
        print(f"{index}/{len(members)}: {member['name']}", flush=True)

        public_record = get_member_public_record(member["id"])
        records = collect_all_source_records_for_member(member, ipsa_pages)

        all_source_records.extend(records)
        scored.append(build_scored_mp(member, public_record, questions_by_member, records))

        time.sleep(0.08)

    all_source_records = dedupe_records(all_source_records)

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

    source_connector_counts = {}

    for record in all_source_records:
        connector = record.get("source_connector") or "unknown"
        source_connector_counts[connector] = source_connector_counts.get(connector, 0) + 1

    source_output = {
        "last_source_collection": datetime.now(timezone.utc).strftime("%d %B %Y"),
        "source_policy": {
            "official_parliament_sources": "High evidence value",
            "registered_interests": "High evidence value for transparency, not automatic wrongdoing",
            "mp_websites": "Low evidence value unless confirmed elsewhere",
            "media": "Discovery source only; does not prove delivery",
            "ipsa": "Public value source; must be interpreted against role, geography and office needs",
            "council_nhs_transport_outcomes": "Currently discovered through media/outcome search; direct official connectors should be added later"
        },
        "connector_counts": source_connector_counts,
        "records": all_source_records
    }

    ranking_output = {
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
                "Commons Votes API",
                "Committees API best-effort connector",
                "Bills API best-effort connector",
                "IPSA public cost source discovery",
                "Member contribution summary / Hansard-like signal",
                "MP website/contact discovery",
                "GDELT media and outcome discovery"
            ],
            "scoring_rule": "No source, no score. Scores are generated from available public records and should be read as source-backed indicators."
        },
        "mps": output_mps
    }

    SOURCE_RECORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_RECORDS_PATH.write_text(json.dumps(source_output, indent=2, ensure_ascii=False), encoding="utf-8")

    RANKED_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RANKED_OUTPUT_PATH.write_text(json.dumps(ranking_output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {SOURCE_RECORDS_PATH}", flush=True)
    print(f"Wrote {RANKED_OUTPUT_PATH}", flush=True)
    print(f"Connector counts: {source_connector_counts}", flush=True)


if __name__ == "__main__":
    main()
