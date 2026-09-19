from django.contrib import admin
from .models import Rating


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["user", "movie", "score", "review_hidden", "review_updated_at"]
    list_filter = ["review_hidden"]
    search_fields = ["user__username", "movie__title", "review_text"]
    readonly_fields = ["user", "movie", "score", "review_text", "review_digest", "review_updated_at", "created_at", "updated_at"]
    actions = ["hide_reviews", "restore_reviews"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Hide selected reviews")
    def hide_reviews(self, request, queryset):
        queryset.update(review_hidden=True)

    @admin.action(description="Restore selected reviews")
    def restore_reviews(self, request, queryset):
        queryset.update(review_hidden=False)
