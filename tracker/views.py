from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from .models import SocialPost


def _score_histogram(*, start, end):
    """
    Count posts per sentiment_score (0–9) where ``analyzed_at`` falls in [start, end] inclusive.
    Missing scores in the range appear as 0.
    """
    rows = (
        SocialPost.objects.filter(
            analyzed_at__gte=start,
            analyzed_at__lte=end,
            sentiment_score__isnull=False,
        )
        .values("sentiment_score")
        .annotate(c=Count("id"))
    )
    by_score = {r["sentiment_score"]: r["c"] for r in rows}
    return [by_score.get(i, 0) for i in range(10)]


def dashboard(request):
    """
    Dashboard charts use a **rolling window in the active Django timezone** (default
    ``Asia/Singapore``): posts are included iff ``analyzed_at`` is within the last
    1 hour or last 24 hours respectively, measured from "now" on each page load.
    """
    now = timezone.now()
    hour_start = now - timedelta(hours=1)
    day_start = now - timedelta(hours=24)

    hour_counts = _score_histogram(start=hour_start, end=now)
    day_counts = _score_histogram(start=day_start, end=now)

    hour_total = sum(hour_counts)
    day_total = sum(day_counts)

    return render(
        request,
        "tracker/dashboard.html",
        {
            "hour_counts": hour_counts,
            "day_counts": day_counts,
            "hour_total": hour_total,
            "day_total": day_total,
            "now": now,
            "hour_start": hour_start,
            "day_start": day_start,
            "ingest_interval_minutes": settings.INGEST_INTERVAL_MINUTES,
        },
    )
