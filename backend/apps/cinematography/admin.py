from django.contrib import admin
from .models import TechniqueSourceCitation, TechniqueSourceSnapshot, TrailerAnalysis, StudyCard, Technique, TechniqueSubmission
from django.utils import timezone


class ReadOnlyProvenance(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TechniqueSourceSnapshot)
class SnapshotAdmin(ReadOnlyProvenance):
    list_display = ["source", "retrieved_at", "actual_count", "complete", "imported_at"]
    list_filter = ["source", "complete"]


@admin.register(TechniqueSourceCitation)
class CitationAdmin(ReadOnlyProvenance):
    list_display = ["source_title", "source_year", "rank", "snapshot", "movie", "status"]
    list_filter = ["snapshot__source", "status"]
    search_fields = ["source_title", "movie__title"]
    list_select_related = ["snapshot", "movie"]


@admin.register(TrailerAnalysis)
class AnalysisAdmin(ReadOnlyProvenance):
    list_display = ['movie', 'selection_rank', 'status', 'color_mode', 'updated_at']
    list_filter = ['status', 'color_mode']
    search_fields = ['movie__title']
    list_select_related = ['movie']


@admin.register(Technique)
class TechniqueAdmin(ReadOnlyProvenance):
    list_display = ['name', 'category', 'automatic']


@admin.register(StudyCard)
class StudyCardAdmin(admin.ModelAdmin):
    list_display = ['analysis', 'technique', 'timestamp', 'evidence', 'approved']
    list_filter = ['approved', 'evidence', 'technique']
    list_select_related = ['analysis__movie', 'technique']
    readonly_fields = ['analysis', 'technique', 'timestamp', 'image', 'evidence']

    def has_add_permission(self, request):
        return False


@admin.register(TechniqueSubmission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['movie', 'technique', 'user', 'status', 'created_at']
    list_filter = ['status', 'technique']
    list_select_related = ['movie', 'technique', 'user']
    readonly_fields = ['movie', 'technique', 'user', 'explanation', 'source_url', 'timestamp', 'scope', 'created_at', 'moderator', 'reviewed_at']

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data:
            obj.moderator, obj.reviewed_at = request.user, timezone.now()
        super().save_model(request, obj, form, change)
