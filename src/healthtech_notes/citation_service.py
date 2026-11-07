import hashlib
from typing import Any

from fastapi import FastAPI, HTTPException

from .infrai_client import InfraiClient, InfraiError
from .models import (
    CitationResult,
    CollectNotesRequest,
    CollectNotesResponse,
    build_patient_notice,
    canonicalize_url,
    dedupe_citations,
)

COLLECTION = "healthtech-research-notes"
app = FastAPI(title="Healthtech citation brief")


def citation_id(url: str) -> str:
    return hashlib.sha256(canonicalize_url(url).encode()).hexdigest()[:24]


def collect_notes(request: CollectNotesRequest, client: InfraiClient) -> CollectNotesResponse:
    unique = dedupe_citations(request.citations)
    texts = [f"{item.title}\n{item.abstract}" for item in unique]
    embeddings = client.embed(texts + [request.research_question])
    client.create_collection(COLLECTION, len(embeddings[0]))

    ids = [citation_id(item.url) for item in unique]
    vectors: list[dict[str, Any]] = [
        {
            "id": item_id,
            "embedding": vector,
            "metadata": {"title": item.title, "url": item.url},
        }
        for item_id, item, vector in zip(ids, unique, embeddings[:-1], strict=True)
    ]
    batch_key = hashlib.sha256("|".join(sorted(ids)).encode()).hexdigest()
    client.upsert(COLLECTION, vectors, batch_key)
    query_data = client.query(COLLECTION, embeddings[-1], min(request.top_k, len(unique)))

    unique_by_id = {citation_id(item.url): item for item in unique}
    ranked: list[CitationResult] = []
    for match in query_data.get("matches", []):
        item_id = str(match.get("id", ""))
        item = unique_by_id.get(item_id)
        if item is not None:
            ranked.append(CitationResult(citation_id=item_id, title=item.title, canonical_url=item.url, score=match.get("score")))
    if not ranked:
        ranked = [CitationResult(citation_id=item_id, title=item.title, canonical_url=item.url) for item_id, item in zip(ids, unique, strict=True)]

    return CollectNotesResponse(
        citations=ranked,
        duplicates_removed=len(request.citations) - len(unique),
        patient_notice=build_patient_notice(request.appointment),
    )


@app.post("/notes/collect", response_model=CollectNotesResponse)
def collect_endpoint(request: CollectNotesRequest) -> CollectNotesResponse:
    client = InfraiClient()
    try:
        return collect_notes(request, client)
    except InfraiError as error:
        caller_status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(status_code=caller_status, detail={"code": error.code, "message": str(error)}) from error
    finally:
        client.close()

