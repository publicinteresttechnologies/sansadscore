from datetime import datetime, timezone


def short_text(value, limit=320):
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def written_question_records(member, questions, question_matcher):
    records = []

    for index, question in enumerate(questions or [], start=1):
        text = question.get("text", "") if isinstance(question, dict) else str(question)
        department = question.get("department", "Unknown") if isinstance(question, dict) else "Unknown"
        local_match = bool(question_matcher(question, member["constituency"]))
        record_type = "local_written_question" if local_match else "written_question"
        score = 45 if local_match else 28

        records.append(
            {
                "auto_collected": True,
                "member_id": member["id"],
                "mp_name": member["name"],
                "constituency": member["constituency"],
                "party": member["party"],
                "type": record_type,
                "summary": f"Written question to {department}: {short_text(text)}",
                "source_url": "https://questions-statements.parliament.uk/written-questions",
                "source_type": "official_parliament_written_question",
                "evidence_type": "official_parliament_written_question",
                "source_connector": "written_questions_api",
                "score": score,
                "question_department": department,
                "question_local_match": local_match,
                "written_question_text": text,
                "written_question_index_for_member": index,
                "official_record": True,
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    return records
