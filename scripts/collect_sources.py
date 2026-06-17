import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests

RANKED_MPS_PATH = Path("data/ranked_mps.json")
SOURCE_RECORDS_PATH = Path("data/source_records.json")

MEMBERS_API = "https://members-api.parliament.uk/api/Members"
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

IPSA_SEARCH_CANDIDATES = [
    "https://www.theipsa.org.uk/mp-staffing-business-costs/your-mp",
    "https://parliamentary-standards.org.uk/SearchFunction.aspx"
]

HEADERS = {
    "User-Agent": "Commons Score all-source collector"
}

MEDIA_TERMS = [
    "promise",
    "promised",
    "pledge",
    "pledged",
    "campaign",
    "called for",
    "urged",
    "pressed",
    "demanded",
    "secured",
    "funding",
    "funded",
    "delivered",
    "opened",
    "saved",
    "hospital",
    "school",
    "rail",
    "station",
    "road",
    "housing",
    "crime",
    "police",
    "NHS",
    "council",
    "bus",
    "transport",
    "planning",
    "flooding",
    "sewage",
    "water",
    "dentist",
    "GP",
    "local authority",
    "constituency"
]

OUTCOME_TERMS = [
    "delivered",
    "opened",
    "completed",
    "approved",
    "funded",
    "secured",
    "saved",
    "launched",
    "new hospital",
    "new school",
    "rail station",
    "bus route",
    "road upgrade",
    "NHS trust",
    "council approved",
    "government funding",
    "transport funding"
]

COMMON_LOCAL_WORDS = {
    "and", "the", "of", "in", "upon", "north", "south", "east", "west",
    "central", "new", "city", "county", "shire", "borough", "constituency"
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
    return re.sub(r"\s+", " ", str(value)).strip()


def norm(value):
    return clean(value).lower()


def get_json(url, params=None):
    response = requests.get(url, params=params or {}, headers=HEADERS, timeout=35)
    response.raise_for_status()
    return response.json()


def get_text(url, params=None):
    response = requests.get(url, params=params or {}, headers=HEADERS, timeout=35)
    response.raise_for_status()
    return response.text


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


def text_dump(data):
    return json.dumps(data, ensure_ascii=False)


def member_id_from_mp(mp):
    raw = mp.get("raw", {})
    member_id = raw.get("member_id") or mp.get("member_id") or mp.get("id")

    if member_id is None:
        return None

    try:
        return int(member_id)
    except Exception:
        return None


def base_record(mp, record_type, summary, source_url, source_type, score, extra=None):
    record = {
        "auto_collected": True,
        "member_id": member_id_from_mp(mp),
        "mp_name": mp.get("name"),
        "constituency": mp.get("constituency"),
        "party": mp.get("party"),
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


def classify_media_title(title):
    text = title.lower()

    if any(word in text for word in ["delivered", "opened", "completed", "approved", "secured", "funding", "funded", "saved", "launched"]):
        return "outcome", 45

    if any(word in text for word in ["promise", "promised", "pledge", "pledged", "vow", "vowed"]):
        return "promise", 35

    if any(word in text for word in ["campaign", "called for", "urged", "pressed", "demanded", "backed"]):
        return "action", 35

    return "media_claim", 25


def build_media_query(mp, terms):
    name = clean(mp.get("name"))
    constituency = clean(mp.get("constituency"))
    term_query = " OR ".join([f'"{term}"' for term in terms])
    return f'"{name}" "{constituency}" ({term_query})'


def search_gdelt(query, maxrecords=5):
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


def collect_media_records(mp):
    records = []

    queries = [
        build_media_query(mp, MEDIA_TERMS),
        build_media_query(mp, OUTCOME_TERMS)
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
                    mp=mp,
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

        time.sleep(0.15)

    return records


def collect_commons_votes_records(mp):
    member_id = member_id_from_mp(mp)

    if not member_id:
        return []

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
            mp=mp,
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


def collect_registered_interests_records(mp):
    member_id = member_id_from_mp(mp)

    if not member_id:
        return []

    url = f"{MEMBERS_API}/{member_id}/RegisteredInterests"

    try:
        data = get_json(url)
    except Exception:
        return []

    items = extract_items(data)
    records = []

    if not items:
        records.append(
            base_record(
                mp=mp,
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

    for item in items[:30]:
        dumped = text_dump(item)

        records.append(
            base_record(
                mp=mp,
                record_type="trust",
                summary=f"Registered interest record: {dumped[:300]}",
                source_url=url,
                source_type="parliament",
                score=70,
                extra={
                    "source_connector": "register_interests"
                }
            )
        )

    return records


def collect_experience_records(mp):
    member_id = member_id_from_mp(mp)

    if not member_id:
        return []

    url = f"{MEMBERS_API}/{member_id}/Experience"

    try:
        data = get_json(url)
    except Exception:
        return []

    items = extract_items(data)
    records = []

    for item in items[:30]:
        dumped = text_dump(item)
        lowered = dumped.lower()

        if "committee" in lowered:
            summary = f"Committee/experience record: {dumped[:300]}"
            score = 65
        elif "minister" in lowered or "secretary of state" in lowered:
            summary = f"Government/parliamentary role record: {dumped[:300]}"
            score = 60
        else:
            summary = f"Parliamentary experience record: {dumped[:300]}"
            score = 40

        records.append(
            base_record(
                mp=mp,
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


def collect_contribution_summary_records(mp):
    member_id = member_id_from_mp(mp)

    if not member_id:
        return []

    url = f"{MEMBERS_API}/{member_id}/ContributionSummary"

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
                mp=mp,
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
                mp=mp,
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
                mp=mp,
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


def collect_contact_website_records(mp):
    member_id = member_id_from_mp(mp)

    if not member_id:
        return []

    url = f"{MEMBERS_API}/{member_id}/Contact"

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
                mp=mp,
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


def collect_committees_records(mp):
    member_id = member_id_from_mp(mp)

    if not member_id:
        return []

    records = []

    for template in COMMITTEES_API_CANDIDATES:
        url = template.format(member_id=member_id)

        try:
            data = get_json(url)
        except Exception:
            continue

        items = extract_items(data)

        if not items:
            continue

        for item in items[:20]:
            dumped = text_dump(item)

            records.append(
                base_record(
                    mp=mp,
                    record_type="action",
                    summary=f"Committees API record: {dumped[:300]}",
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


def collect_bills_records(mp):
    name = clean(mp.get("name"))

    if not name:
        return []

    records = []
    encoded_name = quote_plus(name)

    for template in BILLS_API_CANDIDATES:
        url = template.format(query=encoded_name)

        try:
            data = get_json(url)
        except Exception:
            continue

        items = extract_items(data)

        if not items:
            continue

        for item in items[:20]:
            dumped = text_dump(item)

            if name.lower().split()[-1] not in dumped.lower():
                continue

            records.append(
                base_record(
                    mp=mp,
                    record_type="action",
                    summary=f"Bills API possible member-linked record: {dumped[:300]}",
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


def collect_ipsa_records(mp):
    name = clean(mp.get("name"))
    constituency = clean(mp.get("constituency"))

    if not name:
        return []

    records = []

    for url in IPSA_SEARCH_CANDIDATES:
        try:
            page = get_text(url)
        except Exception:
            continue

        page_lower = page.lower()

        if name.lower() in page_lower or constituency.lower() in page_lower:
            records.append(
                base_record(
                    mp=mp,
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

        time.sleep(0.10)

    return records


def collect_hansard_like_records(mp):
    member_id = member_id_from_mp(mp)

    if not member_id:
        return []

    url = f"{MEMBERS_API}/{member_id}/ContributionSummary"

    try:
        data = get_json(url)
    except Exception:
        return []

    dumped = text_dump(data)
    lowered = dumped.lower()

    records = []

    debate_markers = [
        "debate",
        "spoken",
        "contribution",
        "hansard",
        "commons",
        "question"
    ]

    if any(marker in lowered for marker in debate_markers):
        records.append(
            base_record(
                mp=mp,
                record_type="action",
                summary="Hansard-like contribution evidence found through member contribution summary.",
                source_url=url,
                source_type="parliament",
                score=60,
                extra={
                    "source_connector": "hansard_like_contribution_summary"
                }
            )
        )

    return records


def collect_outcome_records(mp):
    records = []

    query = build_media_query(mp, OUTCOME_TERMS)
    articles = search_gdelt(query, maxrecords=5)

    for article in articles:
        title = clean(article.get("title"))
        url = clean(article.get("url"))
        domain = clean(article.get("domain"))
        seen_date = clean(article.get("seendate"))

        if not title or not url:
            continue

        record_type, score = classify_media_title(title)

        if record_type != "outcome":
            continue

        records.append(
            base_record(
                mp=mp,
                record_type="outcome",
                summary=title,
                source_url=url,
                source_type="local_news",
                score=max(score, 45),
                extra={
                    "source_connector": "outcome_discovery_media",
                    "source_domain": domain,
                    "seen_date": seen_date
                }
            )
        )

    return records


def collect_records_for_mp(mp):
    records = []

    collectors = [
        collect_commons_votes_records,
        collect_registered_interests_records,
        collect_experience_records,
        collect_contribution_summary_records,
        collect_contact_website_records,
        collect_committees_records,
        collect_bills_records,
        collect_ipsa_records,
        collect_hansard_like_records,
        collect_media_records,
        collect_outcome_records
    ]

    for collector in collectors:
        try:
            records.extend(collector(mp))
        except Exception as error:
            print(f"{collector.__name__} failed for {mp.get('name')}: {error}", flush=True)

        time.sleep(0.08)

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

    manual_records = [
        record for record in existing_records
        if not record.get("auto_collected") and not record.get("auto_media")
    ]

    collected_records = []

    print(f"Collecting all source evidence for {len(mps)} MPs...", flush=True)

    for index, mp in enumerate(mps, start=1):
        print(f"{index}/{len(mps)}: {mp.get('name')}", flush=True)

        try:
            collected_records.extend(collect_records_for_mp(mp))
        except Exception as error:
            print(f"Source collection failed for {mp.get('name')}: {error}", flush=True)

    final_records = dedupe_records(manual_records + collected_records)

    connector_counts = {}

    for record in final_records:
        connector = record.get("source_connector") or "manual"
        connector_counts[connector] = connector_counts.get(connector, 0) + 1

    output = {
        "last_source_collection": datetime.now(timezone.utc).strftime("%d %B %Y"),
        "source_policy": {
            "official_parliament_sources": "High evidence value",
            "registered_interests": "High evidence value for transparency, not automatic wrongdoing",
            "mp_websites": "Low evidence value unless confirmed elsewhere",
            "media": "Discovery source only; does not prove delivery",
            "ipsa": "Public value source; must be interpreted against role, geography and office needs",
            "council_nhs_transport_outcomes": "Currently discovered through media/outcome search; official direct connectors should be added later"
        },
        "connector_counts": connector_counts,
        "records": final_records
    }

    save_json(SOURCE_RECORDS_PATH, output)

    print(f"Wrote {len(final_records)} source records to {SOURCE_RECORDS_PATH}", flush=True)
    print(f"Connector counts: {connector_counts}", flush=True)


if __name__ == "__main__":
    main()
