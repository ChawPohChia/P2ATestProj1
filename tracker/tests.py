from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from tracker.models import SocialPost


class DedupTests(TestCase):
    def test_unique_platform_post_id(self):
        SocialPost.objects.create(
            platform_post_id="1",
            text="a",
            author_handle="u",
            posted_at=timezone.now(),
            sentiment_score=4,
            analyzed_at=timezone.now(),
        )
        with self.assertRaises(IntegrityError):
            SocialPost.objects.create(
                platform_post_id="1",
                text="b",
                author_handle="v",
            )
