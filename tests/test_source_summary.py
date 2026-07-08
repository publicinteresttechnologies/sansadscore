from commons_score.source_summary import build_source_summary


def test_build_source_summary_keeps_compact_member_records_and_audit():
    payload = {
        "last_source_collection": "01 July 2026",
        "records": [
            {
                "member_id": 1,
                "mp_name": "Example MP",
                "constituency": "Example Central",
                "source_connector": "written_questions_api",
                "source_type": "parliament",
                "summary": "Question about local hospital",
                "source_url": "https://example.test/question",
            }
        ],
        "source_audit": [
            {
                "member_id": 1,
                "mp_name": "Example MP",
                "constituency": "Example Central",
                "connector": "written_questions_api",
                "source_name": "Written Questions API",
                "status": "used_in_score",
                "records_found": 3,
                "scored": True,
            }
        ],
    }

    summary = build_source_summary(payload)

    assert summary["last_source_collection"] == "01 July 2026"
    assert summary["connector_counts"] == {"written_questions_api": 1}
    assert summary["audit_status_counts"] == {"used_in_score": 1}
    assert len(summary["members"]) == 1
    member = summary["members"][0]
    assert member["member_id"] == 1
    assert member["source_records_count"] == 1
    assert member["source_audit_count"] == 1
    assert member["sample_records"][0]["summary"] == "Question about local hospital"
