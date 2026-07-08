from scripts.commons_score.scoring import evidence_diagnostics, interests_categories, source_record_scores


def interests_record(category="Employment and earnings"):
    return {
        "member_id": 123,
        "type": "trust",
        "summary": "Interests API record: published interest record",
        "source_connector": "interests_api",
        "source_type": "parliament",
        "evidence_type": "parliament",
        "score": 70,
        "interests_category": category,
    }


def test_interests_api_records_are_counted_in_proof_diagnostics():
    diagnostics = evidence_diagnostics(
        [interests_record()],
        public_record={},
        written_questions_count=0,
        local_questions_count=0,
    )

    assert diagnostics["interests_api_records_count"] == 1
    assert diagnostics["interests_api_categories"] == {"Employment and earnings": 1}
    assert diagnostics["interests_api_affects"] == "Proof only"
    assert diagnostics["parliament_source_records_count"] == 1


def test_interests_api_categories_are_included_with_registered_interests():
    records = [
        interests_record("Employment and earnings"),
        {
            "source_connector": "register_interests",
            "interests_category": "Gifts and hospitality",
        },
    ]

    assert interests_categories(records) == {
        "Employment and earnings": 1,
        "Gifts and hospitality": 1,
    }


def test_source_record_scores_ignore_interests_api_records():
    scores = source_record_scores([interests_record()])

    assert scores == {
        "promise": 0.0,
        "action": 0.0,
        "follow_up": 0.0,
        "verified_outcome": 0.0,
        "public_value": 0.0,
    }
