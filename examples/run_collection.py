from datetime import datetime, timezone

from healthtech_notes.citation_service import collect_notes
from healthtech_notes.infrai_client import InfraiClient
from healthtech_notes.models import AppointmentInput, AppointmentState, CitationInput, CollectNotesRequest


request = CollectNotesRequest(
    research_question="What evidence supports remote monitoring after cardiac discharge?",
    citations=[
        CitationInput(
            title="Remote monitoring after discharge",
            url="https://research.example.org/cardiac-monitoring?utm_source=notes",
            abstract="A cohort study of remote monitoring after cardiac discharge.",
        ),
        CitationInput(
            title="Remote monitoring after discharge",
            url="https://research.example.org/cardiac-monitoring",
            abstract="A larger cohort study of remote monitoring after cardiac discharge and readmission follow-up.",
        ),
    ],
    appointment=AppointmentInput(
        appointment_id="apt-2048",
        starts_at=datetime(2026, 9, 8, 9, 30, tzinfo=timezone.utc),
        location="Cardiology clinic, desk 2",
        state=AppointmentState.RESCHEDULED,
    ),
)

client = InfraiClient()
try:
    print(collect_notes(request, client).model_dump_json(indent=2))
finally:
    client.close()

