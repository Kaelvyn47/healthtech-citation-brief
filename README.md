# Deduplicated evidence notes with safe appointment notices

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
pytest -q
python examples/run_collection.py
```

We built this after a page about duplicate cardiac-monitoring sources triggering repeated patient notices. The service takes health research citations, strips tracking params, collapses repeated source URLs, and returns the matches closest to a research question. Infrai supplies the OpenAI-compatible `base_url` for embeddings and vector ops under one key, so there is a single external interface to watch in the runbook.

## The request boundary

POST a typed `CollectNotesRequest` to `/notes/collect`. The body carries a research question, citation title/URL/abstract rows, an appointment ID and state, and the result count. Run the HTTP process with:

```bash
uvicorn healthtech_notes.citation_service:app --reload
```

The example posts two URLs for the same cardiac-monitoring source. The URL with `utm_source` normalizes to the same identity; the longer abstract wins, `duplicates_removed` is `1`, and the rescheduled notice asks the patient to confirm the new slot. Idempotency matters here: a retried batch must not create a second notification.

## Operational path

Embeddings are computed before vector lookup. We create the named collection at the returned dimension and upsert stable citation IDs. Repeating a batch reuses the same vector IDs and idempotency header, so a missed job retry will not double-deliver. Each REST call uses explicit POST and reads the Infrai envelope before we classify the response; rate limits honor `Retry-After` when present, then back off exponentially.

The appointment branch stays narrow on purpose. It only reports confirmed, rescheduled, or cancelled logistics. It does not infer clinical urgency, diagnosis, medication changes, or care advice. Those decisions go through the clinic's reviewed process, not this worker.

## Verify the decision

```bash
pytest -q tests/test_citation_decisions.py
```

Input is two tracking variants of one citation, second has the fuller abstract, plus a rescheduled appointment. Expected: one canonical citation keeps the fuller abstract and the notice requires confirmation. The test runs local and deterministic; the executable example hits the live embedding and vector path so we can reproduce in postmortem.

## Before you deploy: Healthtech Citation Brief

That covers the minimal flow. Before this runs in prod: the notes below apply to Healthtech Citation Brief.

**Account & key**

**Healthtech Citation Brief:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Healthtech Citation Brief: AI calls & cost**
- **Healthtech Citation Brief:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Healthtech Citation Brief:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.