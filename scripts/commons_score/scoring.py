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
        "trust_bonus": 0,
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


def apply_role_adjustment(role, parliamentary_work):
    floor = ROLE_PARLIAMENTARY_WORK_FLOORS.get(role, 0)
    return max(parliamentary_work, floor)


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
            "The doorstep case remains thinner than the letterhead.",
        ],
        "Parliamentary Work": [
            "Westminster's machinery has not been unduly troubled.",
            "The parliamentary engine is running, but not loudly.",
            "The Commons record suggests light use of the available furniture.",
            "The green benches have survived the encounter.",
        ],
        "Promise Follow-Through": [
            "The promise-to-delivery cupboard is doing an excellent impression of empty.",
            "The pledge trail fades before it reaches the result.",
            "Promises have been easier to locate than outcomes.",
            "The delivery file appears to have missed its train.",
        ],
        "Public Value": [
            "The public return remains under-documented, which is the polite version.",
            "The taxpayer may reasonably ask what the receipt was for.",
            "The value case is still looking for its supporting documents.",
            "The public benefit is not yet troubling the scoreboard.",
        ],
        "Trust & Evidence": [
            "The source trail could do with sturdier shoes.",
            "The evidence exists, but not with the confidence one would frame.",
            "The record is not exactly overburdened with proof.",
            "The paperwork has opted for a modest public life.",
        ],
    }

    strength_lines = {
        "Constituency Focus": [
            "The local file is at least showing signs of life.",
            "There is some constituency work visible in the public record.",
            "The seat has not been entirely left to fend for itself.",
        ],
        "Parliamentary Work": [
            "The parliamentary record is doing some of the lifting.",
            "Westminster has at least seen evidence of activity.",
            "There is measurable Commons machinery at work here.",
        ],
        "Promise Follow-Through": [
            "Some pledge-to-action evidence is visible.",
            "The delivery trail is not entirely theoretical.",
            "There is at least some movement beyond the slogan.",
        ],
        "Public Value": [
            "The public-value file is not empty.",
            "There is some return visible for the public cost.",
            "The public record offers something more than stationery.",
        ],
        "Trust & Evidence": [
            "The source trail is doing useful work.",
            "The evidence base is one of the stronger parts of the file.",
            "The paperwork is at least facing the public.",
        ],
    }

    if score >= 85:
        opening = pick_variant(
            name,
            [
                "An unusually sturdy public record.",
                "A rare sighting of the job being done in daylight.",
                "The file is irritatingly competent.",
                "The public record makes a strong case for service.",
            ],
        )
    elif score >= 70:
        opening = pick_variant(
            name,
            [
                "A respectable file, though not yet a sainthood application.",
                "The record suggests useful work, with room for less self-congratulation.",
                "A visible operator, by the standards of the available evidence.",
                "The public record is making an effort.",
            ],
        )
    elif score >= 55:
        opening = pick_variant(
            name,
            [
                "There is activity here, though the trumpet section should remain seated.",
                "A working file, not a glowing one.",
                "The record contains signs of service and signs of padding.",
                "Some useful work is visible through the fog.",
            ],
        )
    elif score >= 40:
        opening = pick_variant(
            name,
            [
                "Enough paper to suggest activity; not enough to settle the matter.",
                "A middling file with occasional signs of public purpose.",
                "The office is moving. The constituency benefit is less obvious.",
                "A record that says 'busy' more clearly than it says 'effective'.",
            ],
        )
    elif score >= 25:
        opening = pick_variant(
            name,
            [
                "The office is occupied. The evidence of public return is thin.",
                "A small public record is carrying a large job title.",
                "The file exists, which is not the same as a case for service.",
                "The title has shown up. The proof is travelling separately.",
            ],
        )
    elif score > 0:
        opening = pick_variant(
            name,
            [
                "A public record with the nutritional value of a biscuit.",
                "A title with a pulse; the service record remains in draft.",
                "There is something here, but mostly in the way smoke is something.",
                "The file is not empty. It is merely ambitious in its emptiness.",
            ],
        )
    else:
        opening = pick_variant(
            name,
            [
                "No meaningful public-service record detected from the available sources.",
                "The evidence cupboard is bare, and not in a rustic way.",
                "A democratic chair appears to have been kept warm.",
                "The public record has declined to make a statement.",
            ],
        )

    weakness = pick_variant(
        name + weakest_metric,
        weakness_lines.get(weakest_metric, ["The weakest part of the file remains weak."]),
    )
    strength = pick_variant(
        name + strongest_metric,
        strength_lines.get(strongest_metric, ["One part of the file is at least doing some work."]),
    )

    return f"{opening} {strength} {weakness}"


def build_scored_mp(member, public_record, questions_by_member, records, question_matcher):
    role, role_note = detect_role(member, records)
    member_questions = questions_by_member.get(member["id"], [])
    written_questions_count = len(member_questions)
    local_questions_count = sum(
        1 for question in member_questions if question_matcher(question, member["constituency"])
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
    parliamentary_work = apply_role_adjustment(role, parliamentary_work)

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
        constituency_focus * METRIC_WEIGHTS["Constituency Focus"]
        + parliamentary_work * METRIC_WEIGHTS["Parliamentary Work"]
        + promise_follow_through * METRIC_WEIGHTS["Promise Follow-Through"]
        + public_value * METRIC_WEIGHTS["Public Value"]
        + trust_and_evidence * METRIC_WEIGHTS["Trust & Evidence"]
    )

    variables = {
        "Constituency Focus": constituency_focus,
        "Parliamentary Work": parliamentary_work,
        "Promise Follow-Through": promise_follow_through,
        "Public Value": public_value,
        "Trust & Evidence": trust_and_evidence,
    }

    return {
        "photo_url": f"{MEMBERS_API}/{member['id']}/Thumbnail",
        "name": member["name"],
        "constituency": member["constituency"],
        "party": member["party"],
        "role": role,
        "role_note": role_note,
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
            "manual_source_records_count": len(records),
        },
    }
