from scripts.commons_score.best_practice import (
    PUBLIC_METRIC_ORDER,
    attach_public_metrics,
)


def test_attach_public_metrics_adds_exact_public_scoreboard_fields():
    mp = {
        "name": "Example MP",
        "source_url": "https://members.parliament.uk/member/1/contact",
        "variables": {
            "Constituency Work": 40,
            "Parliamentary Work": 60,
            "Delivery Track": 20,
            "Public Value": 50,
        },
        "raw": {
            "written_questions_total": 20,
            "written_questions_local": 5,
            "commons_votes_total": 50,
            "action_records_count": 4,
            "follow_up_records_count": 2,
            "verified_outcome_records_count": 1,
            "mp_activity_categories": ["health", "housing"],
            "data_completeness_score": 70,
            "source_diversity_count": 3,
            "official_source_records_count": 5,
            "parliament_source_records_count": 10,
            "evidence_strength_average": 75,
            "media_dependency_ratio": 0.0,
            "mp_self_claim_ratio": 0.0,
            "need_alignment_score": 55,
        },
    }

    attach_public_metrics(mp)

    assert mp["public_metric_order"] == PUBLIC_METRIC_ORDER
    assert list(mp["public_metrics"].keys()) == PUBLIC_METRIC_ORDER
    assert mp["boost_url"] == "https://members.parliament.uk/member/1/contact"

    for value in mp["public_metrics"].values():
        assert isinstance(value, float)
        assert 0 <= value <= 100


def test_public_metrics_are_not_confidence_marker():
    mp = {
        "source_url": "https://members.parliament.uk/member/1/contact",
        "variables": {
            "Constituency Work": 0,
            "Parliamentary Work": 0,
            "Delivery Track": 0,
            "Public Value": 0,
        },
        "raw": {},
    }

    attach_public_metrics(mp)

    assert "Confidence" not in mp["public_metrics"]
    assert "Proof" in mp["public_metrics"]
