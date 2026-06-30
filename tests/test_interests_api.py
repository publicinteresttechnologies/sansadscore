from unittest.mock import patch

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
