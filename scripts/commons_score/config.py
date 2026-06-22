from pathlib import Path

RANKED_OUTPUT_PATH = Path("data/ranked_mps.json")
SOURCE_RECORDS_PATH = Path("data/source_records.json")

RUN_MODE_ENV_VAR = "COMMONS_SCORE_RUN_MODE"
DEFAULT_RUN_MODE = "fast"
ALLOWED_RUN_MODES = {"fast"}
FAST_WRITTEN_QUESTION_MAX_ROWS = 5000
FULL_WRITTEN_QUESTION_MAX_ROWS = 20000
FAST_MODE_SKIPPED_CONNECTORS = [
    "GDELT media/outcome discovery",
    "IPSA page discovery",
    "Bills API",
    "Committees API",
    "Commons Votes probing",
    "MP website/contact discovery",
    "Oral Questions API probing",
    "Contribution summary / Hansard-like scraping",
]

MEMBERS_API = "https://members-api.parliament.uk/api/Members"
MEMBERS_SEARCH = "https://members-api.parliament.uk/api/Members/Search"

WRITTEN_QUESTIONS_API = "https://questions-statements-api.parliament.uk/api/writtenquestions/questions"
ORAL_QUESTIONS_API_CANDIDATES = [
    "https://questions-statements-api.parliament.uk/api/oralquestions/questions",
    "https://questions-statements-api.parliament.uk/api/OralQuestions/Questions",
]
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
COMMONS_VOTES_SEARCH = "https://commonsvotes-api.parliament.uk/data/divisions.json/search"

COMMITTEES_API_CANDIDATES = [
    "https://committees-api.parliament.uk/api/Members/{member_id}/Committees",
    "https://committees-api.parliament.uk/api/Member/{member_id}/Committees",
    "https://committees-api.parliament.uk/api/Committees?memberId={member_id}",
    "https://committees-api.parliament.uk/api/Committees?MemberId={member_id}",
]

BILLS_API_CANDIDATES = [
    "https://bills-api.parliament.uk/api/v1/Bills?SearchTerm={query}",
    "https://bills-api.parliament.uk/api/v1/Bills?searchTerm={query}",
    "https://bills-api.parliament.uk/api/Bills?SearchTerm={query}",
    "https://bills-api.parliament.uk/api/Bills?searchTerm={query}",
]

IPSA_SOURCE_URLS = [
    "https://www.theipsa.org.uk/mp-staffing-business-costs",
    "https://www.theipsa.org.uk/mp-staffing-business-costs/annual-publications",
    "https://parliamentary-standards.org.uk/DataDownloads.aspx",
    "https://parliamentary-standards.org.uk/SearchFunction.aspx",
]

USER_AGENT = "Commons Score public-record updater"
REQUEST_TIMEOUT_SECONDS = 10
RETRY_TOTAL = 1
RETRY_BACKOFF_FACTOR = 0.25

COMMON_LOCAL_WORDS = {
    "and",
    "the",
    "of",
    "in",
    "upon",
    "north",
    "south",
    "east",
    "west",
    "central",
    "new",
    "city",
    "county",
    "shire",
    "borough",
    "constituency",
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
    "delivered",
    "opened",
    "completed",
]

OUTCOME_TERMS = [
    "funding",
    "station",
    "hospital",
    "school",
    "road",
    "rail",
    "bus",
    "police",
    "nhs",
    "housing",
    "flooding",
    "sewage",
    "jobs",
]

METRIC_WEIGHTS = {
    "Constituency Work": 0.30,
    "Parliamentary Work": 0.30,
    "Delivery Track": 0.25,
    "Public Value": 0.15,
}

METHODOLOGY_WEIGHT_LABELS = {
    "Constituency Work": "30%",
    "Parliamentary Work": "30%",
    "Delivery Track": "25%",
    "Public Value": "15%",
}

SOURCES_USED = [
    "UK Parliament Members API",
    "UK Parliament member focus, voting, EDM and registered-interests endpoints",
    "UK Parliament Written Questions API",
    "UK Parliament Oral Questions API best-effort connector",
    "Commons Votes API",
    "Committees API best-effort connector",
    "Bills API best-effort connector",
    "IPSA public cost source discovery",
    "Member contribution summary / Hansard-like signal",
    "MP website/contact discovery",
    "GDELT media and outcome discovery",
]

SOURCE_POLICY = {
    "official_parliament_sources": "High evidence value",
    "registered_interests": "High evidence value for transparency, not automatic wrongdoing",
    "mp_websites": "Low evidence value unless confirmed elsewhere",
    "media": "Discovery source only; does not prove delivery",
    "ipsa": "Public value source; must be interpreted against role, geography and office needs",
    "evidence_quality": "Diagnostic context only; evidence quality is not a public scoring metric",
    "ons_local_context": "TODO: add reliable ONS/local constituency context before scoring it",
    "council_nhs_transport_outcomes": "Currently discovered through media/outcome search; direct official connectors should be added later",
}

CONNECTOR_TODOS = [
    "Full mode is disabled until it is sharded. One all-MP full scrape does not fit inside a single GitHub Actions job.",
    "IPSA CSV/download parsing: page discovery exists, but numeric spend fields remain diagnostic stubs until a stable downloadable schema is wired in.",
    "Hansard/speech counts: contribution summary is used as a lightweight signal; direct Hansard search should be added only if a reliable no-key endpoint is available.",
    "ONS/local constituency context: not scored until a stable public source and constituency mapping are added.",
]
