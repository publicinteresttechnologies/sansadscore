import json
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

RANKED_MPS_PATH = Path("data/ranked_mps.json")
SOURCE_RECORDS_PATH = Path("data/source_records.json")

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

HEADERS = {
    "User-Agent": "Commons Score daily media scanner"
}

MEDIA_TERMS = [
    "promise",
    "promised",
    "pledge",
    "pledged",
    "campaign",
    "called for",
    "secured",
    "funding",
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
    "council"
]


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


def classify_article(title):
    text = title.lower()

    if any(word in text for word in ["delivered", "opened", "completed", "secured", "funding", "funded", "saved"]):
        return "outcome"

    if any(word in text for word in ["promise", "promised", "pledge", "pledged", "vow", "vowed"]):
        return "promise"

    if any(word in text for word in ["campaign", "called for", "urged", "pressed", "demanded", "backed"]):
        return "action"

    return "media_claim"


def build_query(mp):
    name = clean(mp.get("name"))
    constituency = clean(mp.get("constituency"))

    terms = " OR ".join([f'"{term}"' for term in MEDIA_TERMS])

    return f'"{name}" "{constituency}" ({terms})'


def search_gdelt(query):
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": 5,
        "sort": "datedesc"
    }

    response = requests.get(GDELT_DOC_API, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()

    data = response.json()

    return data.get("articles", [])


def article_to_record(mp, article):
    title = clean(article.get("title"))
    url = clean(article.get("url"))
    domain = clean(article.get("domain"))
    seendate = clean(article.get("seendate"))

    record_type = classify_article(title)

    return {
        "auto_media": True,
        "member_id": mp.get("raw", {}).get("member_id"),
        "mp_name": mp.get("name"),
        "constituency": mp.get("constituency"),
        "party": mp.get("party"),
        "type": record_type,
        "summary": title,
        "source_url": url,
        "source_domain": domain,
        "source_type": "local_news",
        "evidence_type": "local_news",
        "score": 35 if record_type in ["promise", "action"] else 45 if record_type == "outcome" else 25,
        "seen_date": seendate,
        "scanned_at": datetime.now(timezone.utc).isoformat()
    }


def main():
    ranked = load_json(RANKED_MPS_PATH, {"mps": []})
    mps = ranked.get("mps", [])

    if not mps:
        raise RuntimeError("No MPs found in data/ranked_mps.json. Run update_uk.py first.")

    existing = load_json(SOURCE_RECORDS_PATH, {"records": []})
    existing_records = existing.get("records", [])

    manual_records = [
        record for record in existing_records
        if not record.get("auto_media")
    ]

    media_records = []
    seen_urls = set()

    print(f"Scanning media for {len(mps)} MPs...", flush=True)

    for index, mp in enumerate(mps, start=1):
        name = clean(mp.get("name"))
        constituency = clean(mp.get("constituency"))

        if not name or not constituency:
            continue

        print(f"{index}/{len(mps)}: {name}", flush=True)

        query = build_query(mp)

        try:
            articles = search_gdelt(query)
        except Exception as error:
            print(f"Media scan failed for {name}: {error}", flush=True)
            continue

        for article in articles:
            url = clean(article.get("url"))

            if not url or url in seen_urls:
                continue

            seen_urls.add(url)
            media_records.append(article_to_record(mp, article))

        time.sleep(0.3)

    output = {
        "last_media_scan": datetime.now(timezone.utc).strftime("%d %B %Y"),
        "records": manual_records + media_records
    }

    save_json(SOURCE_RECORDS_PATH, output)

    print(f"Wrote {len(media_records)} media records to {SOURCE_RECORDS_PATH}", flush=True)


if __name__ == "__main__":
    main()
