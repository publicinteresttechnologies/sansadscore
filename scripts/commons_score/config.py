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
MEMBERS_DETAIL = "https://members-api.parliament.uk/api/Members/{member_id}"
MEMBERS_LOCATION_CONSTITUENCY_SEARCH = "https://members-api.parliament.uk/api/Location/Constituency/Search"
MEMBERS_LOCATION_CONSTITUENCY = "https://members-api.parliament.uk/api/Location/Constituency/{constituency_id}"
MEMBERS_LOCATION_CONSTITUENCY_SYNOPSIS = "https://members-api.parliament.uk/api/Location/Constituency/{constituency_id}/Synopsis"
MEMBERS_LOCATION_CONSTITUENCY_REPRESENTATIONS = "https://members-api.parliament.uk/api/Location/Constituency/{constituency_id}/Representations"
MEMBERS_LOCATION_CONSTITUENCY_GEOMETRY = "https://members-api.parliament.uk/api/Location/Constituency/{constituency_id}/Geometry"
MEMBERS_LOCATION_CONSTITUENCY_ELECTION_RESULTS = "https://members-api.parliament.uk/api/Location/Constituency/{constituency_id}/ElectionResults"
MEMBERS_LOCATION_CONSTITUENCY_LATEST_ELECTION_RESULT = "https://members-api.parliament.uk/api/Location/Constituency/{constituency_id}/ElectionResult/Latest"

INTERESTS_API = "https://interests-api.parliament.uk"
INTERESTS_API_SWAGGER = "https://interests-api.parliament.uk/swagger/v1/swagger.json"
WRITTEN_QUESTIONS_API = "https://questions-statements-api.parliament.uk/api/writtenquestions/questions"
ORAL_QUESTIONS_API_CANDIDATES = [
    "https://questions-statements-api.parliament.uk/api/oralquestions/questions",
    "https://questions-statements-api.parliament.uk/api/OralQuestions/Questions",
    "https://oralquestionsandmotions-api.parliament.uk",
]
STATUTORY_INSTRUMENTS_API = "https://statutoryinstruments-api.parliament.uk"
TREATIES_API = "https://treaties-api.parliament.uk"
ERSKINE_MAY_API = "https://erskinemay-api.parliament.uk"
PARLIAMENT_NOW_API = "https://now-api.parliament.uk"
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

PARLIAMENT_DEVELOPER_HUB_APIS = [
    {
        "key": "members",
        "name": "Members",
        "base_url": "https://members-api.parliament.uk",
        "status": "partial",
        "scope": "in_scope",
        "metric_use": ["Activity", "Local Focus", "Proof", "Boost/contact routing"],
    },
    {
        "key": "interests",
        "name": "Interests",
        "base_url": INTERESTS_API,
        "status": "missing_collector",
        "scope": "in_scope",
        "metric_use": ["Proof", "Public Value"],
    },
    {
        "key": "commons_votes",
        "name": "Commons Votes",
        "base_url": "https://commonsvotes-api.parliament.uk",
        "status": "partial",
        "scope": "in_scope",
        "metric_use": ["Activity", "Public Value"],
    },
    {
        "key": "oral_questions",
        "name": "Oral Questions",
        "base_url": "https://oralquestionsandmotions-api.parliament.uk",
        "status": "partial",
        "scope": "in_scope",
        "metric_use": ["Activity", "Local Focus", "Public Value"],
    },
    {
        "key": "statutory_instruments",
        "name": "Statutory Instruments",
        "base_url": STATUTORY_INSTRUMENTS_API,
        "status": "missing_collector",
        "scope": "context_only",
        "metric_use": ["Public Value"],
    },
    {
        "key": "treaties",
        "name": "Treaties",
        "base_url": TREATIES_API,
        "status": "missing_collector",
        "scope": "context_only",
        "metric_use": ["Public Value"],
    },
    {
        "key": "erskine_may",
        "name": "Erskine May",
        "base_url": ERSKINE_MAY_API,
        "status": "reference_only",
        "scope": "context_only",
        "metric_use": ["Sources & Methods context"],
    },
    {
        "key": "parliament_now",
        "name": "Parliament Now",
        "base_url": PARLIAMENT_NOW_API,
        "status": "missing_collector",
        "scope": "context_only",
        "metric_use": ["Activity context"],
    },
    {
        "key": "bills",
        "name": "Bills",
        "base_url": "https://bills-api.parliament.uk",
        "status": "partial",
        "scope": "in_scope",
        "metric_use": ["Activity", "Delivery", "Public Value"],
    },
    {
        "key": "written_questions",
        "name": "Written Questions",
        "base_url": "https://questions-statements-api.parliament.uk",
        "status": "wired",
        "scope": "in_scope",
        "metric_use": ["Activity", "Local Focus", "Public Value"],
    },
    {
        "key": "committees",
        "name": "Committees",
        "base_url": "https://committees-api.parliament.uk",
        "status": "partial",
        "scope": "in_scope",
        "metric_use": ["Activity", "Public Value", "Proof"],
    },
]

NON_LORDS_OFFICIAL_API_AUDIT_CONNECTORS = [
    {
        "connector": "members_detail_api",
        "source_name": "Members API detail",
        "endpoint_or_url": MEMBERS_DETAIL,
        "control_tier": "context_only",
        "status": "todo_not_implemented",
        "scored": False,
        "diagnostic_only": True,
        "context_only": True,
        "reason": "Official API is in the inventory; collector not yet wired.",
    },
    {
        "connector": "members_location_constituency_search",
        "source_name": "Members Location Constituency Search",
        "endpoint_or_url": MEMBERS_LOCATION_CONSTITUENCY_SEARCH,
        "control_tier": "context_only",
        "status": "todo_not_implemented",
        "scored": False,
        "diagnostic_only": False,
        "context_only": True,
        "reason": "Needed for Local Focus constituency mapping; collector not yet wired.",
    },
    {
        "connector": "members_location_constituency_detail",
        "source_name": "Members Location Constituency detail/synopsis/representations/election results",
        "endpoint_or_url": ", ".join([
            MEMBERS_LOCATION_CONSTITUENCY,
            MEMBERS_LOCATION_CONSTITUENCY_SYNOPSIS,
            MEMBERS_LOCATION_CONSTITUENCY_REPRESENTATIONS,
            MEMBERS_LOCATION_CONSTITUENCY_GEOMETRY,
            MEMBERS_LOCATION_CONSTITUENCY_ELECTION_RESULTS,
            MEMBERS_LOCATION_CONSTITUENCY_LATEST_ELECTION_RESULT,
        ]),
        "control_tier": "context_only",
        "status": "todo_not_implemented",
        "scored": False,
        "diagnostic_only": False,
        "context_only": True,
        "reason": "Official constituency context endpoints are inventoried; collectors not yet wired.",
    },
    {
        "connector": "interests_api",
        "source_name": "Interests API",
        "endpoint_or_url": INTERESTS_API,
        "control_tier": "diagnostic_only",
        "status": "todo_not_implemented",
        "scored": False,
        "diagnostic_only": True,
        "context_only": False,
        "reason": "Dedicated Register of Members' Financial Interests API is inventoried; collector not yet wired.",
    },
    {
        "connector": "statutory_instruments_api",
        "source_name": "Statutory Instruments API",
        "endpoint_or_url": STATUTORY_INSTRUMENTS_API,
        "control_tier": "context_only",
        "status": "todo_not_implemented",
        "scored": False,
        "diagnostic_only": False,
        "context_only": True,
        "reason": "Official API is inventoried as public-value context; collector not yet wired.",
    },
    {
        "connector": "treaties_api",
        "source_name": "Treaties API",
        "endpoint_or_url": TREATIES_API,
        "control_tier": "context_only",
        "status": "todo_not_implemented",
        "scored": False,
        "diagnostic_only": False,
        "context_only": True,
        "reason": "Official API is inventoried as public-value context; collector not yet wired.",
    },
    {
        "connector": "erskine_may_api",
        "source_name": "Erskine May API",
        "endpoint_or_url": ERSKINE_MAY_API,
        "control_tier": "context_only",
        "status": "todo_not_implemented",
        "scored": False,
        "diagnostic_only": False,
        "context_only": True,
        "reason": "Official reference API is inventoried for Sources & Methods; not a scoring input.",
    },
    {
        "connector": "parliament_now_api",
        "source_name": "Parliament Now API",
        "endpoint_or_url": PARLIAMENT_NOW_API,
        "control_tier": "context_only",
        "status": "todo_not_implemented",
        "scored": False,
        "diagnostic_only": False,
        "context_only": True,
        "reason": "Official live business API is inventoried as activity context; collector not yet wired.",
    },
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
    "Interests API inventory",
    "Statutory Instruments API inventory",
    "Treaties API inventory",
    "Erskine May API inventory",
    "Parliament Now API inventory",
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
    "developer_hub_inventory": "All non-Lords official Parliament Developer Hub APIs must be tracked as wired, partial, missing_collector, reference_only or out_of_scope.",
}

CONNECTOR_TODOS = [
    "Full mode is disabled until it is sharded. One all-MP full scrape does not fit inside a single GitHub Actions job.",
    "IPSA CSV/download parsing: page discovery exists, but numeric spend fields remain diagnostic stubs until a stable downloadable schema is wired in.",
    "Hansard/speech counts: contribution summary is used as a lightweight signal; direct Hansard search should be added only if a reliable no-key endpoint is available.",
    "ONS/local constituency context: not scored until a stable public source and constituency mapping are added.",
    "Interests API: add dedicated collector before using financial interests beyond diagnostic/source completeness context.",
    "Statutory Instruments, Treaties and Parliament Now: add as context connectors before any metric impact.",
]
