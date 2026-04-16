import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from tracker.models import IngestCursor, SocialPost
from tracker.services.sentiment import analyze_sentiment
from tracker.services.twitter_client import fetch_all_recent

logger = logging.getLogger(__name__)

CURSOR_NAME = "x_recent_search"


class Command(BaseCommand):
    help = (
        "Fetch recent X posts for the configured Singapore-weather query, store new rows, "
        "and classify sentiment with OpenAI (unless --fetch-only)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fetch-only",
            action="store_true",
            help="Only call the X API and upsert posts; skip OpenAI.",
        )
        parser.add_argument(
            "--force-reanalyze",
            action="store_true",
            help="Re-run OpenAI for every stored post (expensive).",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Log each created tweet id.",
        )

    def handle(self, *args, **options):
        fetch_only = options["fetch_only"]
        force = options["force_reanalyze"]
        verbose = options["verbose"]

        cursor, _ = IngestCursor.objects.get_or_create(
            name=CURSOR_NAME,
            defaults={"since_id": ""},
        )
        since_id = cursor.since_id.strip() or None

        try:
            tweets, newest_id = fetch_all_recent(since_id=since_id)
        except Exception as exc:
            raise CommandError(f"X ingestion failed: {exc}") from exc

        created = 0
        for tw in tweets:
            obj, was_created = SocialPost.objects.get_or_create(
                platform_post_id=tw.id,
                defaults={
                    "text": tw.text,
                    "author_handle": tw.author_handle,
                    "posted_at": parse_datetime(tw.created_at) if tw.created_at else None,
                    "post_url": tw.url,
                },
            )
            if was_created:
                created += 1
                if verbose:
                    self.stdout.write(f"New post {tw.id} @{tw.author_handle}")

        if newest_id:
            cursor.since_id = newest_id
            cursor.save(update_fields=["since_id", "updated_at"])

        self.stdout.write(self.style.SUCCESS(f"X fetch complete: {created} new posts (batch size {len(tweets)})."))

        if fetch_only:
            return

        qs = SocialPost.objects.order_by("id")
        if not force:
            qs = qs.filter(sentiment_score__isnull=True)

        analyzed = 0
        failed = 0
        for post in qs.iterator():
            try:
                result = analyze_sentiment(post.text)
            except Exception as exc:
                failed += 1
                err = str(exc)
                post.analysis_error = err[:2000]
                post.save(update_fields=["analysis_error"])
                logger.warning("Sentiment failed for %s: %s", post.platform_post_id, err)
                continue

            post.sentiment_score = result["score"]
            post.rationale = result.get("rationale") or ""
            post.confidence = result.get("confidence")
            post.analyzed_at = timezone.now()
            post.analysis_error = ""
            post.save(
                update_fields=[
                    "sentiment_score",
                    "rationale",
                    "confidence",
                    "analyzed_at",
                    "analysis_error",
                ]
            )
            analyzed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"OpenAI classification: {analyzed} succeeded, {failed} failed"
                + (" (including reanalysis)" if force else "")
            )
        )
