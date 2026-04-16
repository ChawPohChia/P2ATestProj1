"""X (Twitter) API v2 recent search client (Bearer token)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings

from .retry import call_with_retries

logger = logging.getLogger(__name__)


class XAPIClientError(Exception):
    """Non-retryable X API failure (4xx other than handled rate limits)."""


_TRANSIENT_HTTPX = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.ConnectTimeout,
    httpx.RemoteProtocolError,
)

RECENT_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"


@dataclass
class NormalizedTweet:
    id: str
    text: str
    author_handle: str
    created_at: str | None
    url: str


def _build_url(post_id: str) -> str:
    return f"https://x.com/i/web/status/{post_id}"


def fetch_recent_page(
    *,
    query: str,
    bearer_token: str,
    max_results: int,
    since_id: str | None = None,
    next_token: str | None = None,
) -> dict[str, Any]:
    """One GET to recent search; returns parsed JSON."""

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent": "weather-sentiment-django/1.0",
    }
    params: dict[str, str | int] = {
        "query": query,
        "max_results": max(10, min(100, max_results)),
        "tweet.fields": "created_at,author_id",
        "expansions": "author_id",
        "user.fields": "username",
    }
    if since_id:
        params["since_id"] = since_id
    if next_token:
        params["next_token"] = next_token

    def _request() -> dict[str, Any]:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(RECENT_SEARCH_URL, headers=headers, params=params)
            if r.status_code == 429:
                retry_after = r.headers.get("x-rate-limit-reset")
                raise RuntimeError(f"X API rate limited (429); reset={retry_after} body={r.text[:500]}")
            if r.status_code >= 500:
                raise RuntimeError(f"X API server error {r.status_code}: {r.text[:500]}")
            if r.status_code != 200:
                raise XAPIClientError(f"X API error {r.status_code}: {r.text[:500]}")
            return r.json()

    return call_with_retries(
        _request,
        operation="X recent search",
        retry_on=(RuntimeError, *_TRANSIENT_HTTPX),
    )


def normalize_response(payload: dict[str, Any]) -> tuple[list[NormalizedTweet], dict[str, Any]]:
    """Split API JSON into tweets + meta (newest_id, oldest_id, next_token, result_count)."""
    data = payload.get("data") or []
    includes = payload.get("includes") or {}
    users_by_id = {u["id"]: u.get("username", "") for u in includes.get("users", [])}
    meta = payload.get("meta") or {}

    out: list[NormalizedTweet] = []
    for row in data:
        tid = row["id"]
        author_id = row.get("author_id") or ""
        handle = users_by_id.get(author_id, "")
        out.append(
            NormalizedTweet(
                id=tid,
                text=row.get("text") or "",
                author_handle=handle,
                created_at=row.get("created_at"),
                url=_build_url(tid),
            )
        )
    return out, meta


def fetch_all_recent(
    *,
    query: str | None = None,
    bearer_token: str | None = None,
    since_id: str | None = None,
    max_results_per_page: int | None = None,
    max_pages: int | None = None,
) -> tuple[list[NormalizedTweet], str | None]:
    """
    Paginate recent search up to ``max_pages``. Returns (tweets, newest_id for cursor).
    """
    q = query or settings.X_SEARCH_QUERY
    token = bearer_token or settings.X_BEARER_TOKEN
    per_page = max_results_per_page or settings.INGEST_MAX_RESULTS
    pages = max_pages or settings.INGEST_MAX_PAGES

    if not token.strip():
        raise RuntimeError("X_BEARER_TOKEN is not set; cannot call the X API.")

    all_rows: list[NormalizedTweet] = []
    next_token: str | None = None
    newest_id: str | None = None

    for page in range(pages):
        payload = fetch_recent_page(
            query=q,
            bearer_token=token,
            max_results=per_page,
            since_id=since_id if page == 0 and not next_token else None,
            next_token=next_token,
        )
        batch, meta = normalize_response(payload)
        all_rows.extend(batch)
        newest_id = meta.get("newest_id") or newest_id
        next_token = meta.get("next_token")
        if not next_token:
            break

    logger.info("Fetched %s tweets from X across %s page(s)", len(all_rows), page + 1)
    return all_rows, newest_id
