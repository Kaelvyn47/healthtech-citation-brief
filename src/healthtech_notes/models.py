from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError as error:
    if error.name != "pydantic":
        raise

    class _FieldInfo:
        def __init__(self, default: Any = ...) -> None:
            self.default = default

    def Field(default: Any = ..., **_: Any) -> Any:
        return _FieldInfo(default)

    class BaseModel:
        def __init__(self, **values: Any) -> None:
            for name in self.__annotations__:
                field = getattr(type(self), name, _FieldInfo())
                default = field.default if isinstance(field, _FieldInfo) else field
                if name in values:
                    value = values[name]
                elif default is not ...:
                    value = default
                else:
                    raise TypeError(f"Missing required argument: {name}")
                setattr(self, name, value)

        def model_copy(self, *, update: dict[str, Any]) -> "BaseModel":
            values = {name: getattr(self, name) for name in self.__annotations__}
            values.update(update)
            return type(self)(**values)


class CitationInput(BaseModel):
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    abstract: str = Field(min_length=1)


class AppointmentState(StrEnum):
    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"


class AppointmentInput(BaseModel):
    appointment_id: str = Field(min_length=1)
    starts_at: datetime
    location: str = Field(min_length=1)
    state: AppointmentState


class CollectNotesRequest(BaseModel):
    research_question: str = Field(min_length=1)
    citations: list[CitationInput] = Field(min_length=1)
    appointment: AppointmentInput
    top_k: int = Field(default=3, ge=1, le=20)


class PatientNotice(BaseModel):
    appointment_id: str
    state: AppointmentState
    message: str
    requires_confirmation: bool


class CitationResult(BaseModel):
    citation_id: str
    title: str
    canonical_url: str
    score: float | None = None


class CollectNotesResponse(BaseModel):
    citations: list[CitationResult]
    duplicates_removed: int
    patient_notice: PatientNotice


def canonicalize_url(raw_url: str) -> str:
    parts = urlsplit(raw_url.strip())
    query = [(key, value) for key, value in parse_qsl(parts.query) if not key.lower().startswith("utm_")]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def dedupe_citations(citations: list[CitationInput]) -> list[CitationInput]:
    by_url: dict[str, CitationInput] = {}
    for citation in citations:
        canonical = canonicalize_url(citation.url)
        previous = by_url.get(canonical)
        if previous is None or len(citation.abstract) > len(previous.abstract):
            by_url[canonical] = citation.model_copy(update={"url": canonical})
    return list(by_url.values())


def build_patient_notice(appointment: AppointmentInput) -> PatientNotice:
    when = appointment.starts_at.isoformat()
    if appointment.state == AppointmentState.CONFIRMED:
        message = f"Appointment confirmed for {when} at {appointment.location}."
        confirmation = False
    elif appointment.state == AppointmentState.RESCHEDULED:
        message = f"Appointment moved to {when} at {appointment.location}. Please confirm the new time."
        confirmation = True
    else:
        message = "Appointment cancelled. Contact the clinic to arrange another time."
        confirmation = False
    return PatientNotice(
        appointment_id=appointment.appointment_id,
        state=appointment.state,
        message=message,
        requires_confirmation=confirmation,
    )
