SCORING_MODEL_VERSION = "0.2.0"
DATA_SCHEMA_VERSION = "0.2.0"
SOURCE_POLICY_VERSION = "0.2.0"
METHODOLOGY_VERSION = "0.2.0"


def clamp_score(value):
    return max(0.0, min(100.0, float(value or 0)))


def round_score(value):
    return round(clamp_score(value), 2)


def confidence_multiplier(raw):
    """Mild uncertainty adjustment for public-record coverage.

    This is deliberately conservative: it can reduce an automated score when the
    evidence base is thin or media/self-claim dependent, but it cannot inflate a
    score above the base public-record calculation.
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


def confidence_notes(raw, multiplier):
    notes = [
        "Base score uses the four visible public metrics and published weights.",
        "Evidence confidence can reduce but never boost the public score.",
        "Local conditions outside an MP's control are not directly scored.",
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


def apply_best_practice_calculation(scored_mps):
    for mp in scored_mps:
        raw = mp.setdefault("raw", {})
        base_score = round_score(mp.get("score", 0))
        multiplier = confidence_multiplier(raw)
        confidence_adjusted = round_score(base_score * multiplier)

        raw["score_model_version"] = SCORING_MODEL_VERSION
        raw["data_schema_version"] = DATA_SCHEMA_VERSION
        raw["source_policy_version"] = SOURCE_POLICY_VERSION
        raw["methodology_version"] = METHODOLOGY_VERSION
        raw["base_public_score"] = base_score
        raw["evidence_confidence_multiplier"] = multiplier
        raw["confidence_adjusted_score"] = confidence_adjusted
        raw["final_score"] = confidence_adjusted
        raw["confidence_label"] = confidence_label(multiplier)
        raw["calculation_notes"] = confidence_notes(raw, multiplier)

        mp["score"] = confidence_adjusted
        mp["base_public_score"] = base_score
        mp["final_score"] = confidence_adjusted
        mp["confidence_label"] = raw["confidence_label"]
        mp["score_model_version"] = SCORING_MODEL_VERSION

    return scored_mps
