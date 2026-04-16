from django.db import models


class IngestCursor(models.Model):
    """Stores pagination / since_id cursors for incremental X ingestion."""

    name = models.CharField(max_length=64, unique=True)
    since_id = models.CharField(
        max_length=32,
        blank=True,
        help_text="X tweet id; next run requests tweets newer than this id.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (since_id={self.since_id or '—'})"


class SocialPost(models.Model):
    """Original X post plus LLM sentiment (0=unhappy … 4=neutral … 9=extremely happy)."""

    platform_post_id = models.CharField(max_length=32, unique=True, db_index=True)
    text = models.TextField()
    author_handle = models.CharField(max_length=255, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    post_url = models.URLField(max_length=512, blank=True)

    ingested_at = models.DateTimeField(auto_now_add=True)
    sentiment_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Integer 0–9 after successful analysis.",
    )
    analyzed_at = models.DateTimeField(null=True, blank=True)
    rationale = models.TextField(blank=True)
    confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Model-reported confidence in [0, 1] when provided.",
    )
    analysis_error = models.TextField(
        blank=True,
        help_text="Last classification failure message (rate limits, invalid JSON, etc.).",
    )

    class Meta:
        ordering = ["-posted_at", "-id"]
        indexes = [
            models.Index(fields=["-analyzed_at"]),
            models.Index(fields=["sentiment_score", "-analyzed_at"]),
        ]

    def __str__(self):
        return f"@{self.author_handle}: {self.text[:40]}…"
