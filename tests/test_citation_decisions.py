from datetime import datetime, timezone

from healthtech_notes.models import AppointmentInput, AppointmentState, CitationInput, build_patient_notice, dedupe_citations


def test_deduplication_keeps_the_more_complete_note_and_marks_reschedule() -> None:
    citations = [
        CitationInput(title="Short", url="https://journal.example/study/?utm_campaign=roundup", abstract="Small cohort."),
        CitationInput(title="Complete", url="https://journal.example/study", abstract="Larger cohort with a twelve-month follow-up."),
    ]
    appointment = AppointmentInput(
        appointment_id="apt-7",
        starts_at=datetime(2026, 9, 8, 9, 30, tzinfo=timezone.utc),
        location="Clinic A",
        state=AppointmentState.RESCHEDULED,
    )

    unique = dedupe_citations(citations)
    notice = build_patient_notice(appointment)

    assert len(unique) == 1
    assert unique[0].title == "Complete"
    assert unique[0].url == "https://journal.example/study"
    assert notice.requires_confirmation is True
    assert "Please confirm the new time" in notice.message

