"""OpenAI Chat Completions — structured sentiment score 0–9 for Singapore weather context."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.conf import settings
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from .retry import call_with_retries

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You classify the emotional sentiment of social posts about weather \
as it relates to people in Singapore (heat, rain, haze, flooding, NEA/MSS forecasts, \
commute impact, etc.).

Return ONLY a JSON object with keys:
- "score": integer from 0 to 9 inclusive
- "rationale": short string (max ~200 chars), optional but preferred
- "confidence": number from 0 to 1 indicating how sure you are

Scale:
- 0 = very unhappy / angry / distressed about the weather situation
- 4 = neutral / no strong feeling
- 9 = extremely happy / delighted about the weather situation

If the post is not really about weather or Singapore relevance is unclear, still pick \
the best-matching score for the expressed tone, and lower confidence."""


def _parse_json_object(content: str) -> dict[str, Any]:
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", content)
        if m:
            return json.loads(m.group(0))
        raise


def analyze_sentiment(text: str) -> dict[str, Any]:
    """
    Calls OpenAI and returns a dict:
    { "score": int, "rationale": str, "confidence": float|None }
    Raises on unrecoverable errors after retries.
    """
    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set; cannot classify sentiment.")

    model = settings.OPENAI_MODEL
    client = OpenAI(api_key=api_key)

    user_payload = json.dumps({"post": text}, ensure_ascii=False)

    def _call():
        try:
            return client.chat.completions.create(
                model=model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_payload},
                ],
            )
        except APIStatusError as exc:
            code = getattr(exc, "status_code", None) or 0
            if int(code) >= 500:
                raise RuntimeError(str(exc)) from exc
            raise

    completion = call_with_retries(
        _call,
        operation="OpenAI chat completion",
        retry_on=(RateLimitError, APIConnectionError, APITimeoutError, RuntimeError),
    )

    raw = completion.choices[0].message.content or "{}"
    data = _parse_json_object(raw)
    score = int(data["score"])
    if score < 0 or score > 9:
        raise ValueError(f"score out of range: {score}")
    rationale = str(data.get("rationale") or "").strip()
    conf = data.get("confidence")
    confidence = float(conf) if conf is not None else None
    if confidence is not None and (confidence < 0 or confidence > 1):
        confidence = max(0.0, min(1.0, confidence))

    return {"score": score, "rationale": rationale, "confidence": confidence}
