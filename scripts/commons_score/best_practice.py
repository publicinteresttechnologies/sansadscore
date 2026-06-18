SCORING_MODEL_VERSION = "0.3.1"
DATA_SCHEMA_VERSION = "0.3.0"
SOURCE_POLICY_VERSION = "0.3.0"
METHODOLOGY_VERSION = "0.3.1"

ISSUE_CATEGORY_KEYWORDS = {
    "health": ["nhs", "hospital", "gp", "doctor", "dentist", "ambulance", "mental health", "healthcare", "social care"],
    "crime_policing": ["crime", "police", "policing", "antisocial", "anti-social", "burglary", "knife crime", "violence"],
    "housing": ["housing", "homes", "rent", "renter", "landlord", "homeless", "leasehold", "cladding"],
    "transport": ["rail", "railway", "train", "station", "bus", "road", "pothole", "transport", "traffic"],
    "flooding_environment": ["flood", "flooding", "river", "climate", "environment", "pollution", "air quality", "biodiversity"],
    "sewage_water": ["sewage", "wastewater", "storm overflow", "water quality", "water company", "river discharge"],
    "education": ["school", "education", "college", "university", "childcare", "send", "teacher", "pupil"],
    "employment_income": ["jobs", "employment", "unemployment", "wages", "income", "cost of living", "poverty", "benefits"],
    "planning_development": ["planning", "development", "green belt", "regeneration", "high street", "construction", "local plan"],
}

CONTEXT_CONNECTORS = {"gdelt_media", "ipsa_public_costs", "mp_contact_website"}
ACTIVITY_CONNECTORS = {
    "written_questions_api",
    "oral_questions_api",
    "committees_api",
    "bills_api",
    "commons_votes_api",
    "contribution_summary",
    "hansard_like_contribution_summary",
    "members_api_focus",
}
DISCOVERY_ONLY_CONNECTORS = {"gdelt_media"}
SELF_CLAIM_CONTEXT_CONNECTORS = {"mp_contact_website"}


def clamp_score(value):
    return max(0.0, min(100.0, float(value or 0)))


def round_score(value):
    return round(clamp_score(value), 2)


def normalize(value):
    return str(value or "").strip().lower()


def classify_issue_text(text):
    lowered = normalize(text)
    if not lowered:
        return ""
    for category, keywords in ISSUE_CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return ""


def record_member_id(record):
    try:
        return int(record.get("member_id"))
    except Exception:
        return None


def group_by_member(records):
    grouped = {}
    for record in records or []:
        member_id = record_member_id(record)
        if member_id is not None:
            grouped.setdefault(member_id, []).append(record)
    return grouped


def record_category(record):
    return record.get("issue_category") or classify_issue_text(
        " ".join(
            str(value)
            for value in [
                record.get("type"),
                record.get("record_type"),
                record.get("category"),
                record.get("summary"),
                record.get("source_type"),
                record.get("source_connector"),
                record.get("source_name"),
                record.get("reason"),
            ]
            if value
        )
    )


def source_connector(record):
    return normalize(record.get("source_connector") or record.get("connector"))


def source_text(record):
    return normalize(
        " ".join(
            str(value)
            for value in [
                record.get("source_type"),
                record.get("evidence_type"),
                record.get("source_connector"),
                record.get("source_name"),
                record.get("endpoint_or_url"),
                record.get("source_url"),
            ]
            if value
        )
    )


def is_context_record(record):
    connector = source_connector(record)
    text = source_text(record)
    return connector in CONTEXT_CONNECTORS or "media" in text or record.get("context_only") is True


def is_activity_record(record):
    connector = source_connector(record)
    text = source_text(record)
    if connector in ACTIVITY_CONNECTORS:
        return True
    if "media" in text or "website" in text or record.get("context_only") is True:
        return False
    record_text = normalize(record.get("type") or record.get("record_type") or record.get("category"))
    return any(word in record_text for word in ["action", "question", "debate", "speech", "campaign", "meeting", "letter", "follow", "outcome", "delivery"])


def is_high_confidence_context(record):
    connector = source_connector(record)
    text = source_text(record)
    status = normalize(record.get("status"))

    if status in {"failed", "todo_not_implemented", "skipped_fast_mode", "no_match"}:
        return False
    if connector in DISCOVERY_ONLY_CONNECTORS or connector in SELF_CLAIM_CONTEXT_CONNECTORS:
        return False
    if "media" in text or "website" in text or "self-claim" in text:
        return False
    if record.get("high_confidence_context") is True:
        return True
    return any(marker in text for marker in ["official", "gov.uk", "nhs", "council", "ons", "regulator", "parliament"])


def confidence_multiplier(raw):
    """Mild uncertainty adjustment for public-record coverage.

    It can reduce an automated score when the evidence base is thin or
    media/self-claim dependent, but it cannot inflate a score above the base
    public-record calculation.
    """
    multiplier = 1.0

    source_diversity = raw.get("source_diversity_count", 0) or 0
    media_dependency = raw.get("media_dependency_ratio", 0) or 0
    self_claim_dependency = raw.get("mp_self_claim_ratio", 0) or 0
    official_records = raw.get("official_source_records_count", 0) or 0
    parliament_records = raw.get("parliament_source_records_count", 0) or 0
    completeness = raw.get("data_completeness_score", 0) or 0

    if source_diversity == 0:
        multiplier -= 0.08
    elif source_diversity == 1:
        multiplier -= 0.04

    if media_dependency > 0.50:
        multiplier -= 0.04
    elif media_dependency > 0.25:
        multiplier -= 0.02

    if self_claim_dependency > 0.40:
        multiplier -= 0.04
    elif self_claim_dependency > 0.20:
        multiplier -= 0.02

    if official_records == 0 and parliament_records == 0:
        multiplier -= 0.04

    if completeness < 40:
        multiplier -= 0.03

    return round(max(0.85, min(1.0, multiplier)), 2)


def confidence_label(multiplier):
    if multiplier >= 0.97:
        return "High confidence"
    if multiplier >= 0.91:
        return "Moderate confidence"
    return "Lower confidence"


def infer_need_alignment(member_records, member_audit):
    context_records = [record for record in [*member_records, *member_audit] if record_category(record) and is_context_record(record)]
    high_confidence_context_records = [record for record in context_records if is_high_confidence_context(record)]
    context_categories = sorted({record_category(record) for record in context_records})
    high_confidence_context_categories = sorted({record_category(record) for record in high_confidence_context_records})
    activity_categories = sorted({record_category(record) for record in member_records if record_category(record) and is_activity_record(record)})

    if not context_categories:
        return {
            "constituency_need_categories": [],
            "mp_activity_categories": activity_categories,
            "category_alignment_count": 0,
            "category_alignment_ratio": 0.0,
            "need_alignment_score": 50.0,
            "need_alignment_label": "Neutral: no reliable context data",
        }

    matched = sorted(set(context_categories).intersection(activity_categories))
    ratio = len(matched) / len(context_categories)

    if matched:
        score = 55 + (45 * ratio)
    elif high_confidence_context_categories:
        score = 45
    else:
        score = 50

    if score >= 75:
        label = "Strong visible alignment"
    elif score > 50:
        label = "Some visible alignment"
    elif score < 50:
        label = "Low visible alignment"
    else:
        label = "Neutral visible alignment"

    return {
        "constituency_need_categories": context_categories,
        "mp_activity_categories": activity_categories,
        "category_alignment_count": len(matched),
        "category_alignment_ratio": round(ratio, 2),
        "need_alignment_score": round_score(score),
        "need_alignment_label": label,
    }


def confidence_notes(raw, multiplier):
    notes = [
        "Base score uses the four visible public metrics and published weights.",
        "Evidence confidence can reduce but never boost the public score.",
        "Local conditions outside an MP's control are not directly scored.",
        "Need alignment only tests whether visible public activity matches visible public context.",
        "Role peer percentile compares MPs with broadly similar Commons roles.",
    ]

    if raw.get("source_diversity_count", 0) <= 1:
        notes.append("Source diversity is thin, so uncertainty is higher.")
    if raw.get("media_dependency_ratio", 0) > 0.25:
        notes.append("A material share of records are media/discovery sources.")
    if raw.get("mp_self_claim_ratio", 0) > 0.20:
        notes.append("A material share of records are MP self-claim sources.")
    if raw.get("verified_outcome_records_count", 0) == 0:
        notes.append("No verified official outcome record has been detected yet.")
    if multiplier < 1.0:
        notes.append("The final score has been mildly adjusted down for evidence uncertainty.")

    return notes


def role_peer_group(mp):
    role = mp.get("role") or mp.get("raw", {}).get("role_peer_group") or "Unknown / mixed role"
    if role in {"Speaker", "Minister", "Whip", "Shadow Minister", "Committee Chair", "Backbench / standard MP"}:
        return role
    return "Unknown / mixed role"


def apply_role_peer_percentiles(scored_mps):
    groups = {}
    for mp in scored_mps:
        groups.setdefault(role_peer_group(mp), []).append(mp)

    for group, members in groups.items():
        ranked = sorted(members, key=lambda item: (item.get("_role_peer_input_score", item.get("score", 0)), item.get("name", "")), reverse=True)
        size = len(ranked)

        for index, mp in enumerate(ranked, start=1):
            percentile = 50.0 if size == 1 else round_score(((size - index) / (size - 1)) * 100)
            confidence_adjusted = mp.get("_role_peer_input_score", mp.get("confidence_adjusted_score", mp.get("score", 0)))
            need_alignment = mp.get("_need_alignment_score", mp.get("need_alignment_score", 50))
            role_adjusted = round_score((confidence_adjusted * 0.80) + (percentile * 0.20))
            final_score = round_score((role_adjusted * 0.85) + (need_alignment * 0.15))
            raw = mp.setdefault("raw", {})
            raw["role_peer_group"] = group
            raw["role_peer_percentile"] = percentile
            raw["rank_within_role_peer_group"] = index
            raw["role_peer_group_size"] = size
            raw["role_adjusted_score"] = role_adjusted
            raw["final_score"] = final_score
            mp["role_peer_group"] = group
            mp["role_peer_percentile"] = percentile
            mp["rank_within_role_peer_group"] = index
            mp["role_peer_group_size"] = size
            mp["role_adjusted_score"] = role_adjusted
            mp["final_score"] = final_score
            mp["score"] = final_score
            mp.pop("_role_peer_input_score", None)
            mp.pop("_need_alignment_score", None)

    return scored_mps


def apply_best_practice_calculation(scored_mps, source_records=None, source_audit=None):
    records_by_member = group_by_member(source_records or [])
    audit_by_member = group_by_member(source_audit or [])

    for mp in scored_mps:
        raw = mp.setdefault("raw", {})
        member_id = raw.get("member_id") or mp.get("member_id")
        member_records = records_by_member.get(member_id, [])
        member_audit = audit_by_member.get(member_id, [])

        base_score = round_score(mp.get("score", 0))
        multiplier = confidence_multiplier(raw)
        confidence_adjusted = round_score(base_score * multiplier)
        alignment = infer_need_alignment(member_records, member_audit)

        raw["score_model_version"] = SCORING_MODEL_VERSION
        raw["data_schema_version"] = DATA_SCHEMA_VERSION
        raw["source_policy_version"] = SOURCE_POLICY_VERSION
        raw["methodology_version"] = METHODOLOGY_VERSION
        raw["base_public_score"] = base_score
        raw["evidence_confidence_multiplier"] = multiplier
        raw["confidence_adjusted_score"] = confidence_adjusted
        raw["need_alignment_score"] = alignment["need_alignment_score"]
        raw["need_alignment_label"] = alignment["need_alignment_label"]
        raw["constituency_need_categories"] = alignment["constituency_need_categories"]
        raw["mp_activity_categories"] = alignment["mp_activity_categories"]
        raw["category_alignment_count"] = alignment["category_alignment_count"]
        raw["category_alignment_ratio"] = alignment["category_alignment_ratio"]
        raw["confidence_label"] = confidence_label(multiplier)
        raw["calculation_notes"] = confidence_notes(raw, multiplier)

        mp["base_public_score"] = base_score
        mp["confidence_adjusted_score"] = confidence_adjusted
        mp["need_alignment_score"] = alignment["need_alignment_score"]
        mp["need_alignment_label"] = alignment["need_alignment_label"]
        mp["confidence_label"] = raw["confidence_label"]
        mp["score_model_version"] = SCORING_MODEL_VERSION
        mp["_role_peer_input_score"] = confidence_adjusted
        mp["_need_alignment_score"] = alignment["need_alignment_score"]

    return apply_role_peer_percentiles(scored_mps)
