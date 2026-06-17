import re

from .config import COMMON_LOCAL_WORDS, MEMBERS_API, METRIC_WEIGHTS

ROLE_PARLIAMENTARY_WORK_FLOORS = {
    "Speaker": 35,
    "Minister": 35,
    "Whip": 35,
    "Shadow Minister": 30,
    "Committee Chair": 55,
    "Backbench / standard MP": 0,
}

ROLE_PEER_GROUPS = {
    "Speaker",
    "Minister",
    "Whip",
    "Shadow Minister",
    "Committee Chair",
    "Backbench / standard MP",
}

ISSUE_CATEGORY_KEYWORDS = {
    "health": [
        "nhs",
        "hospital",
        "gp",
        "doctor",
        "dentist",
        "ambulance",
        "mental health",
        "healthcare",
        "social care",
        "pharmacy",
    ],
    "crime_policing": [
        "crime",
        "police",
        "policing",
        "antisocial",
        "anti-social",
        "burglary",
        "knife crime",
        "violence",
        "safer streets",
    ],
    "housing": [
        "housing",
        "homes",
        "rent",
        "renter",
        "landlord",
        "homeless",
        "leasehold",
        "cladding",
        "affordable home",
    ],
    "transport": [
        "rail",
        "railway",
        "train",
        "station",
        "bus",
        "road",
        "pothole",
        "transport",
        "traffic",
        "cycling",
    ],
    "flooding_environment": [
        "flood",
        "flooding",
        "river",
        "climate",
        "environment",
        "pollution",
        "air quality",
        "nature",
        "biodiversity",
    ],
    "sewage_water": [
        "sewage",
        "wastewater",
        "storm overflow",
        "water quality",
        "water company",
        "water bill",
        "river discharge",
    ],
    "education": [
        "school",
        "education",
        "college",
        "university",
        "childcare",
        "send",
        "teacher",
        "pupil",
    ],
    "employment_income": [
        "jobs",
        "employment",
        "unemployment",
        "wages",
        "income",
        "cost of living",
        "poverty",
        "benefits",
        "universal credit",
    ],
    "planning_development": [
        "planning",
        "development",
        "green belt",
        "regeneration",
        "high street",
        "construction",
        "local plan",
    ],
}

ISSUE_CATEGORY_LABELS = {
    "health": "Health",
    "crime_policing": "Crime and policing",
    "housing": "Housing",
    "transport": "Transport",
    "flooding_environment": "Flooding and environment",
    "sewage_water": "Sewage and water",
    "education": "Education",
    "employment_income": "Employment and income",
    "planning_development": "Planning and development",
}


def clean(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def norm(value):
    return clean(value).lower()


def clamp(value):
    return max(0, min(100, round(value)))


def clamp_float(value):
    return max(0.0, min(100.0, float(value)))


def round_score(value):
    return round(clamp_float(value), 2)


def count_score(count, cap):
    if cap <= 0:
        return 0
    return clamp((count / cap) * 100)


def count_score_float(count, cap):
    if cap <= 0:
        return 0.0
    return clamp_float((count / cap) * 100)


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


def classify_issue_category_text(text):
    lowered = norm(text)

    if not lowered:
        return ""

    for category, keywords in ISSUE_CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category

    return ""


def record_issue_category(record):
    if record.get("issue_category"):
        return clean(record.get("issue_category"))

    return classify_issue_category_text(
        " ".join(
            str(value)
            for value in [
                record.get("type"),
                record.get("record_type"),
                record.get("category"),
                record.get("summary"),
                record.get("source_connector"),
                record.get("source_type"),
                record.get("question_department"),
            ]
            if value
        )
    )


def question_issue_category(question):
    if isinstance(question, dict):
        text = " ".join(str(value) for value in [question.get("text"), question.get("department")] if value)
    else:
        text = str(question)

    return classify_issue_category_text(text)


def record_type(record):
    return norm(record.get("type") or record.get("record_type") or record.get("category"))


def record_status(record):
    return norm(record.get("status"))


def record_source_text(record):
    return norm(
        " ".join(
            str(value)
            for value in [
                record.get("source_type"),
                record.get("evidence_type"),
                record.get("source_connector"),
                record.get("source_url"),
            ]
            if value
        )
    )


def is_parliament_record(record):
    text = record_source_text(record)
    return "parliament" in text or "hansard" in text or "commons" in text


def is_media_record(record):
    text = record_source_text(record)
    return "local_news" in text or "news" in text or "media" in text or "gdelt" in text


def is_mp_website_record(record):
    text = record_source_text(record)
    return "mp_website" in text or "mp_claim" in text or "social" in text


def is_official_record(record):
    text = record_source_text(record)
    return any(
        marker in text
        for marker in [
            "official",
            "government",
            "council",
            "regulator",
            "ipsa",
            "gov.uk",
            "nhs.uk",
            "theipsa.org.uk",
        ]
    )


def is_context_record(record):
    connector = norm(record.get("source_connector"))
    return connector == "gdelt_media" or is_media_record(record) or norm(record.get("control_tier")) == "context_only"


def is_activity_record(record):
    connector = norm(record.get("source_connector"))
    text = record_type(record)
    activity_connectors = {
        "oral_questions_api",
        "written_questions_api",
        "committees_api",
        "bills_api",
        "contribution_summary",
        "hansard_like_contribution_summary",
        "commons_votes_api",
        "members_api_focus",
    }

    if connector in activity_connectors:
        return True

    if is_media_record(record) or is_mp_website_record(record):
        return False

    return any(
        word in text
        for word in [
            "action",
            "question",
            "debate",
            "speech",
            "campaign",
            "meeting",
            "letter",
            "follow",
            "outcome",
            "delivery",
        ]
    )


def source_strength(record):
    if is_parliament_record(record):
        return 80
    if is_official_record(record):
        return 85
    if is_media_record(record):
        return 35
    if is_mp_website_record(record):
        return 15

    if record.get("source_url"):
        return 30

    return 0


def explicit_score(record):
    for key in ["score", "metric_score", "evidence_score"]:
        if key in record:
            try:
                return clamp_float(float(record[key]))
            except Exception:
                pass

    return None


def weighted_record_score(record):
    score = explicit_score(record)
    strength = source_strength(record)

    if score is None:
        score = strength

    if is_media_record(record):
        return min(score, 35)

    if is_mp_website_record(record):
        return min(score, 15)

    return max(score, strength * 0.75)


def is_verified_outcome_record(record):
    text = record_type(record)
    status = record_status(record)
    outcome_words = ["outcome", "delivery", "result", "completed", "approved", "funded"]
    has_outcome = any(word in text for word in outcome_words) or status in [
        "completed",
        "delivered",
        "approved",
        "funded",
    ]
    return has_outcome and (is_parliament_record(record) or is_official_record(record)) and not is_media_record(record)


def source_record_scores(records):
    result = {
        "promise": 0.0,
        "action": 0.0,
        "follow_up": 0.0,
        "verified_outcome": 0.0,
        "public_value": 0.0,
    }

    for record in records:
        text = record_type(record)
        score = weighted_record_score(record)

        if any(word in text for word in ["promise", "pledge", "manifesto"]):
            result["promise"] = max(result["promise"], min(score, 30))

        if any(word in text for word in ["action", "question", "debate", "letter", "campaign", "meeting", "parliamentary", "speech"]):
            result["action"] = max(result["action"], min(max(score, 35), 80))

        if any(word in text for word in ["follow", "follow-up", "repeat", "pressure"]):
            result["follow_up"] = max(result["follow_up"], min(max(score, 50), 85))

        if is_verified_outcome_record(record):
            result["verified_outcome"] = max(result["verified_outcome"], min(max(score, 75), 100))

        if any(word in text for word in ["cost", "value", "ipsa", "expense", "funding", "public_value"]):
            if is_media_record(record) or is_mp_website_record(record):
                public_value_score = min(score, 30)
            else:
                public_value_score = min(max(score, 45), 85)
            result["public_value"] = max(result["public_value"], public_value_score)

    return result


def role_evidence_text(member, records):
    parts = [member.get("party", "")]

    for record in records:
        parts.extend(
            [
                record.get("summary", ""),
                record.get("source_connector", ""),
                record.get("type", ""),
                record.get("source_type", ""),
                record.get("evidence_type", ""),
            ]
        )

    return norm(" ".join(str(part) for part in parts if part))


def has_phrase(text, phrases):
    return any(phrase in text for phrase in phrases)


def detect_role(member, records):
    text = role_evidence_text(member, records)
    party = norm(member.get("party"))

    if party == "speaker" or has_phrase(text, ["speaker of the house", "speaker's office", "mr speaker", "madam speaker"]):
        return "Speaker", "Role detected from public party or parliamentary source-record evidence."

    if has_phrase(
        text,
        [
            "shadow minister",
            "shadow secretary of state",
            "shadow chancellor",
            "shadow home secretary",
            "shadow foreign secretary",
            "shadow cabinet",
            "opposition frontbench",
        ],
    ):
        return "Shadow Minister", "Role detected from public source-record evidence."

    if has_phrase(
        text,
        [
            "chief whip",
            "deputy chief whip",
            "government whip",
            "opposition whip",
            "party whip",
            "assistant whip",
            "whip",
            "lord commissioner of hm treasury",
            "treasurer of hm household",
            "comptroller of hm household",
            "vice-chamberlain of hm household",
            "parliamentary secretary to the treasury",
        ],
    ):
        return "Whip", "Role detected from public source-record evidence."

    if has_phrase(
        text,
        [
            "secretary of state",
            "minister of state",
            "parliamentary under-secretary",
            "parliamentary under secretary",
            "parliamentary secretary",
            "cabinet minister",
            "prime minister",
            "deputy prime minister",
            "chancellor of the exchequer",
            "lord chancellor",
            "attorney general",
            "solicitor general",
            "minister without portfolio",
            "government minister",
        ],
    ) or re.search(r"\bminister\b", text):
        return "Minister", "Role detected from public source-record evidence."

    if (
        has_phrase(text, ["committee chair", "select committee chair", "chair of the", "chairman of the", "chairwoman of the"])
        or ("committee" in text and re.search(r"\b(chair|chairman|chairwoman)\b", text))
    ):
        return "Committee Chair", "Role detected from public committee or member-experience evidence."

    return "Backbench / standard MP", "No public role evidence matched a specialist Commons role."


def role_peer_group(role):
    if role in ROLE_PEER_GROUPS:
        return role
    return "Unknown / mixed role"


def apply_role_adjustment(role, parliamentary_work):
    floor = ROLE_PARLIAMENTARY_WORK_FLOORS.get(role, 0)
    return max(parliamentary_work, floor)


def records_matching(records, predicate):
    return [record for record in records if predicate(record)]


def count_record_type(records, words):
    return len([record for record in records if any(word in record_type(record) for word in words)])


def records_with_connector(records, connector):
    return [record for record in records if norm(record.get("source_connector")) == connector]


def written_question_departments(member_questions):
    counts = {}

    for question in member_questions:
        department = "Unknown"
        if isinstance(question, dict):
            department = clean(question.get("department")) or "Unknown"

        counts[department] = counts.get(department, 0) + 1

    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def interests_categories(records):
    counts = {}

    for record in records_with_connector(records, "register_interests"):
        category = clean(record.get("interests_category")) or "Unknown"
        counts[category] = counts.get(category, 0) + 1

    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def source_diversity(records):
    values = set()

    for record in records:
        value = record.get("source_connector") or record.get("source_type") or record.get("evidence_type")
        if value:
            values.add(norm(value))

    return len(values)


def ratio(part, total):
    if total <= 0:
        return 0.0
    return round(part / total, 2)


def evidence_diagnostics(records, public_record, written_questions_count, local_questions_count):
    total_records = len(records)
    strengths = [source_strength(record) for record in records]
    media_records = records_matching(records, is_media_record)
    mp_website_records = records_matching(records, is_mp_website_record)
    official_records = records_matching(records, is_official_record)
    parliament_records = records_matching(records, is_parliament_record)
    verified_outcomes = records_matching(records, is_verified_outcome_record)

    fields_present = [
        written_questions_count > 0,
        local_questions_count > 0,
        public_record.get("votes", 0) > 0,
        public_record.get("edms", 0) > 0,
        public_record.get("focus_items", 0) > 0,
        bool(public_record.get("registered_interests_ok")),
        total_records > 0,
        bool(official_records),
        bool(parliament_records),
        source_diversity(records) > 1,
    ]

    return {
        "official_source_records_count": len(official_records),
        "parliament_source_records_count": len(parliament_records),
        "media_source_records_count": len(media_records),
        "mp_website_records_count": len(mp_website_records),
        "promise_records_count": count_record_type(records, ["promise", "pledge", "manifesto"]),
        "action_records_count": count_record_type(records, ["action", "question", "debate", "campaign", "meeting", "letter", "speech"]),
        "follow_up_records_count": count_record_type(records, ["follow", "follow-up", "repeat", "pressure"]),
        "verified_outcome_records_count": len(verified_outcomes),
        "public_value_records_count": count_record_type(records, ["cost", "value", "ipsa", "expense", "funding", "public_value"]),
        "evidence_strength_average": round(sum(strengths) / len(strengths), 2) if strengths else 0.0,
        "source_diversity_count": source_diversity(records),
        "data_completeness_score": round((sum(1 for present in fields_present if present) / len(fields_present)) * 100, 2),
        "media_dependency_ratio": ratio(len(media_records), total_records),
        "mp_self_claim_ratio": ratio(len(mp_website_records), total_records),
    }


def evidence_confidence_multiplier(diagnostics):
    multiplier = 1.0

    if diagnostics["source_diversity_count"] == 0:
        multiplier -= 0.08
    elif diagnostics["source_diversity_count"] == 1:
        multiplier -= 0.04

    if diagnostics["media_dependency_ratio"] > 0.50:
        multiplier -= 0.04
    elif diagnostics["media_dependency_ratio"] > 0.25:
        multiplier -= 0.02

    if diagnostics["mp_self_claim_ratio"] > 0.40:
        multiplier -= 0.04
    elif diagnostics["mp_self_claim_ratio"] > 0.20:
        multiplier -= 0.02

    if diagnostics["official_source_records_count"] == 0 and diagnostics["parliament_source_records_count"] == 0:
        multiplier -= 0.04

    if diagnostics["data_completeness_score"] < 40:
        multiplier -= 0.03

    return round(max(0.85, min(1.0, multiplier)), 2)


def confidence_label(multiplier):
    if multiplier >= 0.97:
        return "High confidence"
    if multiplier >= 0.91:
        return "Moderate confidence"
    return "Lower confidence"


def category_counts(categories):
    counts = {}

    for category in categories:
        if not category:
            continue
        counts[category] = counts.get(category, 0) + 1

    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def issue_categories_from_audit(source_audit):
    categories = []

    for entry in source_audit or []:
        category = entry.get("issue_category") or classify_issue_category_text(
            " ".join(
                str(value)
                for value in [
                    entry.get("source_name"),
                    entry.get("connector"),
                    entry.get("reason"),
                    entry.get("endpoint_or_url"),
                ]
                if value
            )
        )
        if category and (entry.get("context_only") or entry.get("status") in ["context_only", "discovery_only"]):
            categories.append(category)

    return categories


def need_alignment(records, member_questions, source_audit):
    context_categories = [record_issue_category(record) for record in records if is_context_record(record)]
    context_categories.extend(issue_categories_from_audit(source_audit))
    need_categories = sorted(set(category for category in context_categories if category))

    activity_categories = [record_issue_category(record) for record in records if is_activity_record(record)]
    activity_categories.extend(question_issue_category(question) for question in member_questions)
    activity_categories = sorted(set(category for category in activity_categories if category))

    if not need_categories:
        return {
            "constituency_need_categories": [],
            "mp_activity_categories": activity_categories,
            "category_alignment_count": 0,
            "category_alignment_ratio": 0.0,
            "need_alignment_score": 50.0,
            "need_alignment_label": "Neutral: no reliable context data",
            "high_confidence_context_available": False,
        }

    aligned = sorted(set(need_categories).intersection(activity_categories))
    alignment_ratio = len(aligned) / len(need_categories) if need_categories else 0.0
    high_confidence_context = any(
        record_issue_category(record) in need_categories and (is_official_record(record) or is_parliament_record(record))
        for record in records
        if is_context_record(record)
    )

    if aligned:
        score = 55 + (45 * alignment_ratio)
    elif high_confidence_context:
        score = 40
    else:
        score = 50

    if score >= 75:
        label = "Strong alignment"
    elif score > 50:
        label = "Some alignment"
    elif score < 50:
        label = "Low visible alignment"
    else:
        label = "Neutral alignment"

    return {
        "constituency_need_categories": need_categories,
        "mp_activity_categories": activity_categories,
        "category_alignment_count": len(aligned),
        "category_alignment_ratio": round(alignment_ratio, 2),
        "need_alignment_score": round_score(score),
        "need_alignment_label": label,
        "high_confidence_context_available": high_confidence_context,
    }


def verified_delivery_score(records, need_categories):
    verified_outcomes = [record for record in records if is_verified_outcome_record(record)]

    if not verified_outcomes:
        return 0.0

    if not need_categories:
        return round_score(max(weighted_record_score(record) for record in verified_outcomes))

    matching_outcomes = [record for record in verified_outcomes if record_issue_category(record) in need_categories]

    if not matching_outcomes:
        return round_score(max(weighted_record_score(record) for record in verified_outcomes))

    chain_records = [
        record
        for record in records
        if record_issue_category(record) in need_categories
        and any(word in record_type(record) for word in ["promise", "action", "follow", "campaign", "question"])
        and not is_media_record(record)
    ]

    if chain_records:
        return 100.0

    return 90.0


def delivery_matches_need_chain(records, need_categories):
    if not need_categories:
        return False

    has_verified_outcome = any(
        is_verified_outcome_record(record) and record_issue_category(record) in need_categories
        for record in records
    )
    has_activity = any(
        record_issue_category(record) in need_categories
        and is_activity_record(record)
        and not is_media_record(record)
        for record in records
    )

    return has_verified_outcome and has_activity


def pick_variant(name, options):
    index = sum(ord(char) for char in name) % len(options)
    return options[index]


def verdict_from_metrics(name, score, variables):
    weakest_metric = min(variables, key=variables.get)
    strongest_metric = max(variables, key=variables.get)
    return (
        f"Public score reflects strongest visible metric: {strongest_metric}. "
        f"Weakest visible metric: {weakest_metric}."
    )


def build_scored_mp(member, public_record, questions_by_member, records, question_matcher, source_audit=None):
    role, role_note = detect_role(member, records)
    member_questions = questions_by_member.get(member["id"], [])
    written_questions_count = len(member_questions)
    local_questions_count = sum(
        1 for question in member_questions if question_matcher(question, member["constituency"])
    )

    record_scores = source_record_scores(records)
    alignment = need_alignment(records, member_questions, source_audit)

    focus_score = count_score_float(public_record["focus_items"], 5)
    local_questions_score = count_score_float(local_questions_count, 10)
    written_questions_score = count_score_float(written_questions_count, 50)
    votes_score = count_score_float(public_record["votes"], 250)
    edms_score = count_score_float(public_record["edms"], 20)

    constituency_work_base = round_score(
        local_questions_score * 0.45
        + focus_score * 0.20
        + record_scores["action"] * 0.35
    )
    constituency_work = round_score(
        constituency_work_base * 0.70
        + alignment["need_alignment_score"] * 0.30
    )

    parliamentary_work = round_score(
        written_questions_score * 0.40
        + votes_score * 0.20
        + edms_score * 0.15
        + focus_score * 0.10
        + record_scores["action"] * 0.15
    )
    parliamentary_work = round_score(apply_role_adjustment(role, parliamentary_work))

    delivery_base = round_score(
        record_scores["promise"] * 0.15
        + record_scores["action"] * 0.30
        + record_scores["follow_up"] * 0.25
        + record_scores["verified_outcome"] * 0.30
    )
    verified_delivery = verified_delivery_score(records, alignment["constituency_need_categories"])

    if delivery_matches_need_chain(records, alignment["constituency_need_categories"]):
        delivery_track = round_score(delivery_base + max(0, verified_delivery - delivery_base) * 0.15)
    else:
        delivery_track = delivery_base

    if record_scores["public_value"] > 0:
        public_value = round_score(record_scores["public_value"])
    else:
        public_value = round_score(
            constituency_work * 0.35
            + parliamentary_work * 0.35
        )

    variables = {
        "Constituency Work": constituency_work,
        "Parliamentary Work": parliamentary_work,
        "Delivery Track": delivery_track,
        "Public Value": public_value,
    }

    base_public_score = round_score(
        constituency_work * METRIC_WEIGHTS["Constituency Work"]
        + parliamentary_work * METRIC_WEIGHTS["Parliamentary Work"]
        + delivery_track * METRIC_WEIGHTS["Delivery Track"]
        + public_value * METRIC_WEIGHTS["Public Value"]
    )

    oral_records = records_with_connector(records, "oral_questions_api")
    bill_records = records_with_connector(records, "bills_api")
    committee_records = records_with_connector(records, "committees_api")
    speech_records = records_matching(
        records,
        lambda record: "speech" in record_type(record) or norm(record.get("source_connector")) == "hansard_like_contribution_summary",
    )
    cost_records = records_matching(records, lambda record: "cost" in record_type(record) or norm(record.get("source_type")) == "ipsa")
    diagnostics = evidence_diagnostics(records, public_record, written_questions_count, local_questions_count)
    confidence_multiplier = evidence_confidence_multiplier(diagnostics)
    confidence_adjusted_score = round_score(base_public_score * confidence_multiplier)
    provisional_final_score = round_score(confidence_adjusted_score * 0.85 + alignment["need_alignment_score"] * 0.15)
    peer_group = role_peer_group(role)

    calculation_notes = [
        "Local conditions are not scored against an MP directly; context only tests whether visible activity matches major constituency needs.",
        "Evidence confidence can reduce but never boost the base public score.",
        "Role peer percentile is applied after all MPs are scored so MPs are compared with broadly similar Commons roles.",
    ]

    fairness_notes = [
        "No direct penalty is applied for constituency conditions outside an MP's control.",
        "Media is treated as discovery evidence, not verified delivery.",
        "MP website claims remain weak unless confirmed by parliament or official sources.",
    ]

    raw = {
        "member_id": member["id"],
        "registered_interests_count": public_record["registered_interests"],
        "edms_count": public_record["edms"],
        "focus_items_count": public_record["focus_items"],
        "votes_count": public_record["votes"],
        "written_questions_count": written_questions_count,
        "local_questions_count": local_questions_count,
        "manual_source_records_count": len(records),
        "written_questions_total": written_questions_count,
        "written_questions_local": local_questions_count,
        "written_questions_by_department": written_question_departments(member_questions),
        "oral_questions_total": len(oral_records),
        "oral_questions_local": len([record for record in oral_records if record.get("local_match")]),
        "commons_votes_total": public_record["votes"],
        "edms_signed": public_record["edms"],
        "bill_sponsor_count": len([record for record in bill_records if record.get("bill_role") == "sponsor"]),
        "bill_backer_count": len([record for record in bill_records if record.get("bill_role") == "backer"]),
        "committee_memberships_count": len([record for record in committee_records if record.get("committee_record_kind") == "membership"]),
        "committee_inquiries_count": len([record for record in committee_records if record.get("committee_record_kind") == "inquiry"]),
        "committee_publications_count": len([record for record in committee_records if record.get("committee_record_kind") == "publication"]),
        "registered_interests_total": public_record["registered_interests"],
        "registered_interests_categories": interests_categories(records),
        "speech_count": len(speech_records),
        "local_speech_mentions": len([record for record in speech_records if record.get("local_match")]),
        "total_office_spend": None,
        "staffing_spend": None,
        "travel_costs": None,
        "accommodation_costs": None,
        "cost_context_available": any(record.get("cost_context_available") for record in cost_records),
        "constituency_work_base_score": constituency_work_base,
        "constituency_need_categories": alignment["constituency_need_categories"],
        "mp_activity_categories": alignment["mp_activity_categories"],
        "category_alignment_count": alignment["category_alignment_count"],
        "category_alignment_ratio": alignment["category_alignment_ratio"],
        "need_alignment_score": alignment["need_alignment_score"],
        "need_alignment_label": alignment["need_alignment_label"],
        "verified_delivery_score": verified_delivery,
        "base_public_score": base_public_score,
        "evidence_confidence_multiplier": confidence_multiplier,
        "confidence_adjusted_score": confidence_adjusted_score,
        "role_peer_group": peer_group,
        "role_peer_percentile": 50.0,
        "rank_within_role_peer_group": None,
        "role_peer_group_size": None,
        "role_adjusted_score": confidence_adjusted_score,
        "final_score": provisional_final_score,
        "confidence_label": confidence_label(confidence_multiplier),
        "fairness_notes": fairness_notes,
        "calculation_notes": calculation_notes,
    }
    raw.update(diagnostics)

    output = {
        "photo_url": f"{MEMBERS_API}/{member['id']}/Thumbnail",
        "name": member["name"],
        "constituency": member["constituency"],
        "party": member["party"],
        "role": role,
        "role_note": role_note,
        "grade": grade_from_score(provisional_final_score),
        "score": provisional_final_score,
        "variables": variables,
        "legal_flag": "",
        "verdict": verdict_from_metrics(member["name"], provisional_final_score, variables),
        "source_url": f"https://members.parliament.uk/member/{member['id']}/contact",
        "raw": raw,
    }
    sync_calculation_fields(output)
    return output


def sync_calculation_fields(mp):
    raw = mp.get("raw", {})
    for key in [
        "base_public_score",
        "confidence_adjusted_score",
        "role_adjusted_score",
        "final_score",
        "need_alignment_score",
        "verified_delivery_score",
        "evidence_confidence_multiplier",
        "role_peer_group",
        "role_peer_percentile",
        "rank_within_role_peer_group",
        "role_peer_group_size",
        "need_alignment_label",
        "confidence_label",
        "fairness_notes",
        "calculation_notes",
    ]:
        if key in raw:
            mp[key] = raw[key]


def apply_role_peer_adjustments(scored):
    groups = {}

    for mp in scored:
        group = mp.get("raw", {}).get("role_peer_group") or role_peer_group(mp.get("role"))
        groups.setdefault(group, []).append(mp)

    for group, members in groups.items():
        ranked = sorted(
            members,
            key=lambda item: (
                item.get("raw", {}).get("confidence_adjusted_score", 0),
                item.get("raw", {}).get("base_public_score", 0),
                item.get("name", ""),
            ),
            reverse=True,
        )
        size = len(ranked)

        for index, mp in enumerate(ranked, start=1):
            raw = mp["raw"]
            percentile = 50.0 if size == 1 else round_score(((size - index) / (size - 1)) * 100)
            confidence_score = raw["confidence_adjusted_score"]
            need_score = raw["need_alignment_score"]
            role_adjusted = round_score(confidence_score * 0.80 + percentile * 0.20)
            final_score = round_score(role_adjusted * 0.85 + need_score * 0.15)

            raw["role_peer_group"] = group
            raw["role_peer_percentile"] = percentile
            raw["rank_within_role_peer_group"] = index
            raw["role_peer_group_size"] = size
            raw["role_adjusted_score"] = role_adjusted
            raw["final_score"] = final_score
            raw["calculation_notes"] = list(raw.get("calculation_notes", [])) + [
                f"Role peer calculation compares this MP within {group} ({index} of {size})."
            ]

            mp["score"] = final_score
            mp["grade"] = grade_from_score(final_score)
            sync_calculation_fields(mp)

    return scored
