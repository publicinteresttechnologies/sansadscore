from contextlib import ExitStack
from unittest.mock import patch

from scripts.commons_score.collectors import collect_all_source_records_for_member
from scripts.commons_score.interests_api import collect_interests_api_records


def test_collect_interests_api_records_maps_member_records():
    member = {
        "id": 123,
        "name": "Example MP",
        "constituency": "Example Central",
        "party": "Example Party",
    }
    payload = {
        "items": [
            {
                "id": 456,
                "summary": "Payment from example source",
                "category": {"name": "Employment and earnings"},
            }
        ]
    }

    with patch("scripts.commons_score.interests_api.get_json", return_value=payload) as get_json:
        records = collect_interests_api_records(member)

    get_json.assert_called_once()
    assert records[0]["member_id"] == 123
    assert records[0]["source_connector"] == "interests_api"
    assert records[0]["interests_category"] == "Employment and earnings"
    assert records[0]["source_url"].endswith("/456")


def test_collect_interests_api_records_handles_empty_response():
    member = {
        "id": 123,
        "name": "Example MP",
        "constituency": "Example Central",
        "party": "Example Party",
    }

    with patch("scripts.commons_score.interests_api.get_json", return_value={"items": []}):
        assert collect_interests_api_records(member) == []


def test_normal_source_collection_calls_interests_api_collector():
    member = {
        "id": 123,
        "name": "Example MP",
        "constituency": "Example Central",
        "party": "Example Party",
    }
    interests_record = {
        "member_id": 123,
        "source_connector": "interests_api",
        "type": "trust",
        "summary": "Interests API record",
    }

    patches = [
        patch("scripts.commons_score.collectors.collect_interests_api_records", return_value=[interests_record]),
        patch("scripts.commons_score.collectors.collect_registered_interests_records", return_value=[]),
        patch("scripts.commons_score.collectors.collect_experience_records", return_value=[]),
        patch("scripts.commons_score.collectors.collect_oral_questions_records", return_value=[]),
        patch("scripts.commons_score.collectors.collect_contribution_summary_records", return_value=[]),
        patch("scripts.commons_score.collectors.collect_contact_website_records", return_value=[]),
        patch("scripts.commons_score.collectors.collect_committees_records", return_value=[]),
        patch("scripts.commons_score.collectors.collect_bills_records", return_value=[]),
        patch("scripts.commons_score.collectors.collect_commons_votes_records", return_value=[]),
        patch("scripts.commons_score.collectors.collect_hansard_like_records", return_value=[]),
        patch("scripts.commons_score.collectors.collect_media_records", return_value=[]),
        patch("scripts.commons_score.collectors.collect_ipsa_records", return_value=[]),
        patch("scripts.commons_score.collectors.time.sleep", return_value=None),
    ]

    with ExitStack() as stack:
        collect_interests = stack.enter_context(patches[0])
        for item in patches[1:]:
            stack.enter_context(item)
        records = collect_all_source_records_for_member(member, ipsa_pages=[])

    collect_interests.assert_called_once_with(member)
    assert records == [interests_record]
