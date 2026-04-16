from django.contrib import admin

from .models import IngestCursor, SocialPost


@admin.register(IngestCursor)
class IngestCursorAdmin(admin.ModelAdmin):
    list_display = ("name", "since_id", "updated_at")


@admin.register(SocialPost)
class SocialPostAdmin(admin.ModelAdmin):
    list_display = (
        "platform_post_id",
        "author_handle",
        "sentiment_score",
        "analyzed_at",
        "posted_at",
    )
    list_filter = ("sentiment_score",)
    search_fields = ("text", "author_handle", "platform_post_id")
