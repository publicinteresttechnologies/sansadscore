SCORING_MODEL_VERSION = "0.3.3"
DATA_SCHEMA_VERSION = "0.3.1"
SOURCE_POLICY_VERSION = "0.3.0"
METHODOLOGY_VERSION = "0.3.3"

PUBLIC_METRIC_ORDER = ["Activity", "Local Focus", "Delivery", "Public Value", "Proof"]

PUBLIC_METRIC_RULES = {
    "Activity": "Parliamentary activity score combining formal activity metric, written questions, votes and auditable action records.",
    "Local Focus": "Local-facing score combining constituency work, constituency-linked written questions and visible issue alignment.",
    "Delivery": "Follow-through score combining delivery-track metric, follow-up records and verified official outcome records.",
    "Public Value": "Public-interest score combining public-value metric and breadth of visible public issue categories.",
    "Proof": "Source-backed proof score combining data completeness, official/parliamentary records, source diversity and source strength, with penalties for media/self-claim dependency.",
}

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
ROLE_EVIDENCE_CONNECTORS = {"members_experience", "contribution_summary", "committees_api"}
SPECIALIST_ROLES = {"Minister", "Whip", "Shadow Minister", "Committee Chair"}


def clamp_score(value):
    return max(0.0, min(100.0, float(value or 0)))


def round_score(value):
    return round(clamp_score(value), 2)


def normalize(value):
    return str(value or "").strip().lower()


def count_component(count, cap):
    if not cap:
        return 0.0
    try:
        count = float(count or 0)
    except Exception:
        count = 0.0
    return clamp_score((count / cap) * 100)


def metric_value(variables, name):
    try:
        return clamp_score(variables.get(name, 0))
    except Exception:
        return 0.0


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


def is_context_record(record):
    connector = source_connector(record)
    source_type = normalize(record.get("source_type") or record.get("evidence_type"))
    return connector in CONTEXT_CONNECTORS or "media" in source_type or record.get("context_only") is True


def is_activity_record(record):
    connector = source_connector(record)
    source_type = normalize(record.get("source_type") or record.get("evidence_type"))
    if connector in ACTIVITY_CONNECTORS:
        return True
    if "media" in source_type or "website" in source_type or record.get("context_only") is True:
        return False
    text = normalize(record.get("type") or record.get("record_type") or record.get("category"))
    return any(word in text for word in ["action", "question", "debate", "speech", "campaign", "meeting", "letter", "follow", "outcome", "delivery"])


def has_strong_role_evidence(member_records):
    for record in member_records or []:
        if source_connector(record) in ROLE_EVIDENCE_CONNECTORS:
            return True
    return False


def normalise_role(mp, member_records):
    role = mp.get("role")
    if role in SPECIALIST_ROLES and not has_strong_role_evidence(member_records):
        mp["role"] = "Backbench / standard MP"
        mp["role_note"] = "No specialist-role evidence retained after excluding written-question text."
        raw = mp.setdefault("raw", {})
        raw["role_corrected_from"] = role
        raw["role_correction_reason"] = "Written questions and department text are not allowed to prove ministerial or specialist role status."


def confidence_multiplier(raw):
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
    context_categories = sorted({record_category(record) for record in [*member_records, *member_audit] if record_category(record) and is_context_record(record)})
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
    score = 55 + (45 * ratio) if matched else 45
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
        "Base score uses visible public metrics and published weights.",
        "The public UI exposes five calculable metrics: Activity, Local Focus, Delivery, Public Value and Proof.",
        "Local conditions outside an MP's control are not directly scored.",
        "Need alignment only tests whether visible public activity matches visible public context.",
        "Role peer percentile compares MPs with broadly similar Commons roles.",
    ]
    if raw.get("role_corrected_from"):
        notes.append("Specialist role label was corrected because written-question text is not role evidence.")
    if raw.get("source_diversity_count", 0) <= 1:
        notes.append("Source diversity is thin; this is reflected in the Proof metric and methods panel.")
    if raw.get("media_dependency_ratio", 0) > 0.25:
        notes.append("A material share of records are media/discovery sources.")
    if raw.get("mp_self_claim_ratio", 0) > 0.20:
        notes.append("A material share of records are MP self-claim sources.")
    if raw.get("verified_outcome_records_count", 0) == 0:
        notes.append("No verified official outcome record has been detected yet.")
    return notes


def public_metrics(mp):
    raw = mp.get("raw", {})
    variables = mp.get("variables", {})
    activity = (
        metric_value(variables, "Parliamentary Work") * 0.55
        + count_component(raw.get("written_questions_total"), 40) * 0.25
        + count_component(raw.get("commons_votes_total"), 200) * 0.10
        + count_component(raw.get("action_records_count"), 40) * 0.10
    )
    local_focus = (
        metric_value(variables, "Constituency Work") * 0.50
        + count_component(raw.get("written_questions_local"), 15) * 0.25
        + clamp_score(raw.get("need_alignment_score", 50)) * 0.25
    )
    delivery = (
        metric_value(variables, "Delivery Track") * 0.65
        + count_component(raw.get("follow_up_records_count"), 8) * 0.15
        + count_component(raw.get("verified_outcome_records_count"), 5) * 0.20
    )
    issue_breadth = count_component(len(raw.get("mp_activity_categories", []) or []), 5)
    public_value = metric_value(variables, "Public Value") * 0.70 + issue_breadth * 0.30
    official_and_parliament = (raw.get("official_source_records_count", 0) or 0) + (raw.get("parliament_source_records_count", 0) or 0)
    proof = (
        clamp_score(raw.get("data_completeness_score", 0)) * 0.35
        + count_component(raw.get("source_diversity_count"), 4) * 0.20
        + count_component(official_and_parliament, 20) * 0.25
        + clamp_score(raw.get("evidence_strength_average", 0)) * 0.20
    )
    proof -= clamp_score(raw.get("media_dependency_ratio", 0) * 100) * 0.10
    proof -= clamp_score(raw.get("mp_self_claim_ratio", 0) * 100) * 0.10
    return {
        "Activity": round_score(activity),
        "Local Focus": round_score(local_focus),
        "Delivery": round_score(delivery),
        "Public Value": round_score(public_value),
        "Proof": round_score(proof),
    }


def attach_public_metrics(mp):
    metrics = public_metrics(mp)
    mp["public_metric_order"] = PUBLIC_METRIC_ORDER
    mp["public_metrics"] = metrics
    mp["public_metric_rules"] = PUBLIC_METRIC_RULES
    mp["boost_url"] = mp.get("source_url")
    raw = mp.setdefault("raw", {})
    raw["public_metrics"] = metrics
    raw["public_metric_order"] = PUBLIC_METRIC_ORDER
    return mp


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
        ranked = sorted(members, key=lambda item: (item.get("_pre_peer_score", item.get("score", 0)), item.get("name", "")), reverse=True)
        size = len(ranked)
        for index, mp in enumerate(ranked, start=1):
            percentile = 50.0 if size == 1 else round_score(((size - index) / (size - 1)) * 100)
            pre_peer = mp.get("_pre_peer_score", mp.get("score", 0))
            final_score = round_score((pre_peer * 0.90) + (percentile * 0.10))
            raw = mp.setdefault("raw", {})
            raw["role_peer_group"] = group
            raw["role_peer_percentile"] = percentile
            raw["rank_within_role_peer_group"] = index
            raw["role_peer_group_size"] = size
            raw["role_adjusted_score"] = final_score
            raw["final_score"] = final_score
            mp["role_peer_group"] = group
            mp["role_peer_percentile"] = percentile
            mp["rank_within_role_peer_group"] = index
            mp["role_peer_group_size"] = size
            mp["final_score"] = final_score
            mp["score"] = final_score
            mp.pop("_pre_peer_score", None)
            attach_public_metrics(mp)
    return scored_mps


def apply_best_practice_calculation(scored_mps, source_records=None, source_audit=None):
    records_by_member = group_by_member(source_records or [])
    audit_by_member = group_by_member(source_audit or [])
    for mp in scored_mps:
        raw = mp.setdefault("raw", {})
        member_id = raw.get("member_id") or mp.get("member_id")
        member_records = records_by_member.get(member_id, [])
        member_audit = audit_by_member.get(member_id, [])
        normalise_role(mp, member_records)
        base_score = round_score(mp.get("score", 0))
        multiplier = confidence_multiplier(raw)
        confidence_adjusted = round_score(base_score * multiplier)
        alignment = infer_need_alignment(member_records, member_audit)
        pre_peer_score = round_score((confidence_adjusted * 0.85) + (alignment["need_alignment_score"] * 0.15))
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
        raw["pre_peer_score"] = pre_peer_score
        raw["confidence_label"] = confidence_label(multiplier)
        raw["calculation_notes"] = confidence_notes(raw, multiplier)
        mp["base_public_score"] = base_score
        mp["confidence_adjusted_score"] = confidence_adjusted
        mp["need_alignment_score"] = alignment["need_alignment_score"]
        mp["need_alignment_label"] = alignment["need_alignment_label"]
        mp["confidence_label"] = raw["confidence_label"]
        mp["score_model_version"] = SCORING_MODEL_VERSION
        mp["_pre_peer_score"] = pre_peer_score
    return apply_role_peer_percentiles(scored_mps)
