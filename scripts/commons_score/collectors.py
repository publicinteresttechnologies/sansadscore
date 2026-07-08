import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

from .config import (
    BILLS_API_CANDIDATES,
    COMMITTEES_API_CANDIDATES,
    COMMONS_VOTES_SEARCH,
    GDELT_DOC_API,
    IPSA_SOURCE_URLS,
    MEDIA_TERMS,
    MEMBERS_API,
    MEMBERS_SEARCH,
    ORAL_QUESTIONS_API_CANDIDATES,
    OUTCOME_TERMS,
    WRITTEN_QUESTIONS_API,
)
from .http import get_json, get_text
from .interests_api import collect_interests_api_records
from .scoring import clean, constituency_tokens


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


def get_current_commons_mps():
    all_mps = []
    skip = 0
    take = 20

    while True:
        params = {
            "House": 1,
            "IsCurrentMember": "true",
            "skip": skip,
            "take": take,
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

            party = get_nested(value, "latestParty", "name") or value.get("party") or ""

            constituency = (
                get_nested(value, "latestHouseMembership", "membershipFrom")
                or get_nested(value, "latestHouseMembership", "membershipFromId")
                or ""
            )

            house = get_nested(value, "latestHouseMembership", "house") or value.get("house") or ""

            if not member_id or not name:
                continue

            if house and "commons" not in str(house).lower() and str(house) != "1":
                continue

            all_mps.append(
                {
                    "id": int(member_id),
                    "name": clean(name),
                    "party": clean(party),
                    "constituency": clean(constituency),
                }
            )

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
        "votes": f"{MEMBERS_API}/{member_id}/Voting",
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
        get_nested(value, "tablingMember", "id"),
    ]

    for candidate in candidates:
        if candidate is None:
            continue

        try:
            return int(candidate)
        except Exception:
            continue

    return None


def question_department(item):
    value = item.get("value", item)
    department = (
        value.get("answeringBodyName")
        or value.get("answeringBody")
        or get_nested(value, "answeringBody", "name")
        or get_nested(value, "answeringBody", "value")
        or "Unknown"
    )
    return clean(department) or "Unknown"


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
        "dateForAnswer",
    ]

    for key in possible_keys:
        if value.get(key):
            parts.append(str(value.get(key)))

    parts.append(json.dumps(value, ensure_ascii=False))

    return " ".join(parts)


def question_record(item):
    return {
        "text": question_text(item),
        "department": question_department(item),
    }


def fetch_written_questions_by_member(max_rows=5000):
    questions_by_member = {}
    skip = 0
    take = 100

    print("Fetching written questions...", flush=True)

    while skip < max_rows:
        params = {
            "house": "Commons",
            "skip": skip,
            "take": take,
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

            questions_by_member.setdefault(member_id, []).append(question_record(item))

        skip += take

        total = data.get("totalResults") or data.get("total") or data.get("totalCount") or 0

        if total and skip >= total:
            break

        print(f"Fetched {skip} written-question rows", flush=True)
        time.sleep(0.08)

    print(f"Written questions mapped for {len(questions_by_member)} MPs.", flush=True)
    return questions_by_member


def question_matches_constituency(question, constituency):
    if isinstance(question, dict):
        question = question.get("text", "")

    q = str(question).lower()
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
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    if extra:
        record.update(extra)

    return record


def classify_media_title(title):
    text = title.lower()

    if any(
        word in text
        for word in [
            "delivered",
            "opened",
            "completed",
            "approved",
            "secured",
            "funding",
            "funded",
            "saved",
            "launched",
        ]
    ):
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
        "sort": "datedesc",
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
        build_media_query(member, OUTCOME_TERMS),
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
                        "seen_date": seen_date,
                    },
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
        {"MemberId": member_id, "skip": 0, "take": 100},
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
                "params_used": params_used,
            },
        )
    ]


def interest_category(item):
    value = item.get("value", item)
    category = (
        value.get("category")
        or value.get("interestCategory")
        or value.get("interestCategoryName")
        or get_nested(value, "category", "name")
        or get_nested(value, "interestCategory", "name")
        or "Unknown"
    )
    return clean(category) or "Unknown"


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
                    "source_connector": "register_interests",
                    "interests_category": "None returned",
                },
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
                    "source_connector": "register_interests",
                    "interests_category": interest_category(item),
                },
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
                extra={"source_connector": "members_experience"},
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
                extra={"source_connector": "contribution_summary"},
            )
        )

    if "debate" in lowered:
        records.append(
            base_record(
                member=member,
                record_type="speech",
                summary="Contribution summary includes debate activity.",
                source_url=url,
                source_type="parliament",
                score=60,
                extra={"source_connector": "contribution_summary"},
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
                extra={"source_connector": "contribution_summary"},
            )
        )

    return records


def collect_oral_questions_records(member):
    records = []
    member_id = member["id"]
    param_attempts = [
        {"askingMemberId": member_id, "skip": 0, "take": 100},
        {"memberId": member_id, "skip": 0, "take": 100},
        {"tablingMemberId": member_id, "skip": 0, "take": 100},
    ]

    for api_url in ORAL_QUESTIONS_API_CANDIDATES:
        for params in param_attempts:
            try:
                data = get_json(api_url, params=params)
            except Exception:
                continue

            items = extract_items(data)
            if not items:
                continue

            for item in items[:20]:
                summary = question_text(item)[:260]
                local_match = question_matches_constituency(question_record(item), member["constituency"])
                records.append(
                    base_record(
                        member=member,
                        record_type="action",
                        summary=f"Oral question record: {summary}",
                        source_url=api_url,
                        source_type="parliament",
                        score=60,
                        extra={
                            "source_connector": "oral_questions_api",
                            "question_department": question_department(item),
                            "local_match": local_match,
                            "params_used": params,
                        },
                    )
                )

            return records

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
                extra={"source_connector": "mp_contact_website"},
            )
        )

    return records


def committee_record_kind(item):
    dumped = text_dump(item).lower()
    if "inquiry" in dumped:
        return "inquiry"
    if "publication" in dumped or "report" in dumped:
        return "publication"
    return "membership"


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
                        "source_connector": "committees_api",
                        "committee_record_kind": committee_record_kind(item),
                    },
                )
            )

        break

    return records


def bill_role(item):
    dumped = text_dump(item).lower()
    if any(word in dumped for word in ["sponsor", "promoter", "member in charge"]):
        return "sponsor"
    if any(word in dumped for word in ["backer", "supporter", "co-sponsor", "cosponsor"]):
        return "backer"
    return "possible_link"


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
                        "source_connector": "bills_api",
                        "bill_role": bill_role(item),
                    },
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
                        "source_connector": "ipsa_public_costs",
                        "cost_context_available": False,
                        "cost_context_note": "TODO: parse stable IPSA CSV/download data before assigning numeric spend fields.",
                    },
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
            record_type="speech",
            summary="Hansard-like contribution evidence found through member contribution summary.",
            source_url=url,
            source_type="parliament",
            score=60,
            extra={
                "source_connector": "hansard_like_contribution_summary",
                "local_match": question_matches_constituency(dumped, member["constituency"]),
            },
        )
    ]


def collect_all_source_records_for_member(member, ipsa_pages):
    collectors = [
        collect_interests_api_records,
        collect_registered_interests_records,
        collect_experience_records,
        collect_oral_questions_records,
        collect_contribution_summary_records,
        collect_contact_website_records,
        collect_committees_records,
        collect_bills_records,
        collect_commons_votes_records,
        collect_hansard_like_records,
        collect_media_records,
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


def dedupe_records(records):
    seen = set()
    output = []

    for record in records:
        key = (
            record.get("source_connector"),
            record.get("member_id"),
            record.get("type"),
            record.get("source_url"),
            record.get("summary"),
        )

        if key in seen:
            continue

        seen.add(key)
        output.append(record)

    return output
