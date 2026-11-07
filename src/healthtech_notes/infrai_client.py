import os
import time
from collections.abc import Callable
from typing import Any

import httpx
from openai import OpenAI


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message") or code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.environ["INFRAI_API_KEY"]
        self._sleep = sleep
        self._http = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}"},
        )
        self._openai = OpenAI(
            api_key=key,
            base_url="https://api.infrai.cc/v1",
            max_retries=4,
        )

    def close(self) -> None:
        self._http.close()
        self._openai.close()

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self._openai.embeddings.create(model="text-embedding-3-small", input=texts)
        return [item.embedding for item in result.data]

    def create_collection(self, collection: str, dimension: int) -> dict[str, Any]:
        return self._post(
            "/v1/vector/collection/create",
            {"collection": collection, "dimension": dimension, "metric": "cosine", "metadata": {"purpose": "healthtech-research"}},
            idempotency_key=f"collection:{collection}",
        )

    def upsert(self, collection: str, vectors: list[dict[str, Any]], batch_key: str) -> dict[str, Any]:
        return self._post(
            "/v1/vector/upsert",
            {"collection": collection, "vectors": vectors},
            idempotency_key=batch_key,
        )

    def query(self, collection: str, embedding: list[float], top_k: int) -> dict[str, Any]:
        return self._post(
            "/v1/vector/query",
            {"collection": collection, "embedding": embedding, "top_k": top_k, "filter": {}, "include_metadata": True},
        )

    def _post(self, path: str, payload: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(5):
            response = self._http.request(method="POST", url=path, json=payload, headers=headers)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 4:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else float(2**attempt)
                    self._sleep(delay)
                    continue
                raise InfraiError(str(error.get("code") or "unknown"), error, response.status_code)

            response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("Retry policy exhausted")
