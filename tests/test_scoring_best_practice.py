import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from commons_score.best_practice import apply_best_practice_calculation, confidence_multiplier, infer_need_alignment
from commons_score.scoring import is_verified_outcome_record, source_record_scores


def healthy_raw(member_id):
    return {
        "member_id": member_id,
        "source_diversity_count": 3,
        "media_dependency_ratio": 0.0,
        "mp_self_claim_ratio": 0.0,
        "official_source_records_count": 1,
        "parliament_source_records_count": 1,
        "data_completeness_score": 80,
        "verified_outcome_records_count": 1,
    }


def test_media_never_counts_as_verified_official_outcome():
    record = {
        "member_id": 1,
        "type": "verified outcome funded",
        "source_connector": "gdelt_media",
        "source_type": "media",
        "match_confidence": "strong",
        "outcome_linked_to_mp_action": True,
    }

    assert not is_verified_outcome_record(record)
    assert source_record_scores([record])["verified_outcome"] == 0


def test_mp_website_self_claim_never_counts_as_verified_outcome():
    record = {
        "member_id": 1,
        "type": "delivery completed",
        "source_connector": "mp_contact_website",
        "source_type": "mp_website",
        "match_confidence": "strong",
        "outcome_linked_to_mp_action": True,
    }

    assert not is_verified_outcome_record(record)
    assert source_record_scores([record])["verified_outcome"] == 0


def test_official_outcome_requires_visible_mp_action_chain():
    official_outcome = {
        "member_id": 1,
        "type": "official outcome funded",
        "source_connector": "gov_funding",
        "source_type": "official gov.uk",
        "match_confidence": "strong",
    }
    action = {
        "member_id": 1,
        "type": "parliamentary action question",
        "source_connector": "written_questions_api",
        "source_type": "parliament",
    }

    assert source_record_scores([official_outcome])["verified_outcome"] == 0
    assert source_record_scores([action, official_outcome])["verified_outcome"] >= 80


def test_delivery_weights_verified_outcome_above_action_only():
    action = {
        "member_id": 1,
        "type": "parliamentary action question",
        "source_connector": "written_questions_api",
        "source_type": "parliament",
    }
    outcome = {
        "member_id": 1,
        "type": "official outcome funded",
        "source_connector": "gov_funding",
        "source_type": "official gov.uk",
        "match_confidence": "strong",
        "outcome_linked_to_mp_action": True,
    }

    scores = source_record_scores([action, outcome])
    assert scores["verified_outcome"] > scores["action"]


def test_name_only_match_does_not_score_as_verified_outcome():
    record = {
        "member_id": 1,
        "type": "official outcome funded",
        "source_connector": "gov_funding",
        "source_type": "official gov.uk",
        "match_confidence": "weak",
        "match_basis": "name only",
        "outcome_linked_to_mp_action": True,
    }

    assert not is_verified_outcome_record(record)


def test_confidence_multiplier_can_reduce_but_never_boost():
    high_confidence = healthy_raw(1)
    low_confidence = {
        "source_diversity_count": 0,
        "media_dependency_ratio": 0.75,
        "mp_self_claim_ratio": 0.50,
        "official_source_records_count": 0,
        "parliament_source_records_count": 0,
        "data_completeness_score": 20,
    }

    assert confidence_multiplier(high_confidence) == 1.0
    assert 0.85 <= confidence_multiplier(low_confidence) < 1.0


def test_context_only_discovery_without_visible_activity_uses_low_alignment():
    records = [
        {
            "member_id": 1,
            "connector": "gdelt_media",
            "source_type": "media",
            "context_only": True,
            "summary": "Local hospital issue",
        }
    ]

    alignment = infer_need_alignment(records, [])
    assert alignment["need_alignment_score"] == 45.0


def test_high_confidence_context_can_reduce_only_for_no_visible_activity():
    audit = [
        {
            "member_id": 1,
            "connector": "ons_context",
            "source_name": "Official local context",
            "context_only": True,
            "status": "context_only",
            "endpoint_or_url": "https://www.ons.gov.uk/",
            "summary": "Official transport need context",
        }
    ]

    alignment = infer_need_alignment([], audit)
    assert alignment["need_alignment_score"] == 45.0


def test_final_score_fields_and_role_peer_ranks_are_consistent():
    mps = [
        {"name": "Alpha", "role": "Backbench / standard MP", "score": 60, "raw": healthy_raw(1)},
        {"name": "Beta", "role": "Backbench / standard MP", "score": 40, "raw": healthy_raw(2)},
    ]

    result = apply_best_practice_calculation(mps, source_records=[], source_audit=[])
    alpha = next(mp for mp in result if mp["name"] == "Alpha")
    beta = next(mp for mp in result if mp["name"] == "Beta")

    assert alpha["rank_within_role_peer_group"] == 1
    assert beta["rank_within_role_peer_group"] == 2
    assert alpha["role_peer_group_size"] == 2
    assert beta["role_peer_group_size"] == 2
    assert alpha["score"] == alpha["raw"]["final_score"]
    assert beta["score"] == beta["raw"]["final_score"]
    assert 0 <= alpha["score"] <= 100
    assert 0 <= beta["score"] <= 100
    assert len(str(alpha["score"]).split(".")[-1]) <= 2


def test_documented_final_score_blend_order():
    mps = [{"name": "Solo", "role": "Minister", "score": 80, "raw": healthy_raw(1)}]

    result = apply_best_practice_calculation(mps, source_records=[], source_audit=[])[0]

    assert result["raw"]["confidence_adjusted_score"] == 80
    assert result["raw"]["role_peer_percentile"] == 50
    assert result["raw"]["role_adjusted_score"] == 72.95
    assert result["raw"]["need_alignment_score"] == 50
    assert result["score"] == 72.95
