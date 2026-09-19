"""Scraped-list provenance, independent of recommendation and CV artifacts."""
from django.db import models
from django.conf import settings
from apps.movies.models import Movie

SOURCE_CHOICES = [
    (Movie.Source.LETTERBOXD, "Letterboxd Top 1000"),
    (Movie.Source.TSPDT, "TSPDT Top 1000"),
    (Movie.Source.ANIMATION, "Letterboxd Top 250 Animation"),
    (Movie.Source.BLACKWHITE, "Letterboxd Black and White"),
]


class TechniqueSourceSnapshot(models.Model):
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    sha256 = models.CharField(max_length=64)
    source_list_url = models.URLField(max_length=2000)
    retrieved_at = models.DateTimeField()
    actual_count = models.PositiveIntegerField()
    complete = models.BooleanField()
    raw_payload = models.JSONField()
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "sha256"], name="unique_technique_snapshot"),
            models.CheckConstraint(condition=models.Q(actual_count__gte=1, actual_count__lte=1000), name="technique_snapshot_count"),
        ]


class TechniqueSourceCitation(models.Model):
    class Status(models.TextChoices):
        RESOLVED = "resolved", "Matched to a movie"
        EXCLUDED = "excluded", "Reviewed: not a TMDB movie"
        UNMATCHED = "unmatched", "Reviewed: no matching complete movie"

    snapshot = models.ForeignKey(TechniqueSourceSnapshot, on_delete=models.PROTECT, related_name="citations")
    rank = models.PositiveIntegerField()
    source_title = models.CharField(max_length=500)
    source_year = models.PositiveIntegerField(null=True, blank=True)
    source_director = models.CharField(max_length=1000, blank=True)
    source_page_url = models.URLField(max_length=2000)
    source_item_url = models.URLField(max_length=2000, blank=True)
    movie = models.ForeignKey(Movie, on_delete=models.PROTECT, null=True, blank=True, related_name="technique_citations")
    status = models.CharField(max_length=16, choices=Status.choices)
    match_evidence = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["snapshot", "rank"], name="unique_technique_source_rank"),
            models.CheckConstraint(condition=models.Q(rank__gte=1, rank__lte=1000), name="technique_citation_rank"),
            models.CheckConstraint(condition=(models.Q(status="resolved", movie__isnull=False) | models.Q(status__in=["excluded", "unmatched"], movie__isnull=True)), name="technique_citation_identity"),
        ]


class TrailerAnalysis(models.Model):
    """The exact curated subset, including entries whose evidence is unavailable."""
    movie = models.OneToOneField(Movie, on_delete=models.PROTECT, related_name='trailer_analysis')
    selection_rank = models.PositiveIntegerField(unique=True)
    status = models.CharField(max_length=16, choices=[('ready', 'Available'), ('review', 'Needs source review'), ('missing', 'Trailer unavailable'), ('failed', 'Analysis failed')], db_index=True)
    reason = models.TextField(blank=True)
    version = models.CharField(max_length=40, blank=True)
    source_sha256 = models.CharField(max_length=64, blank=True)
    source_url = models.URLField(max_length=2000, blank=True)
    source_title = models.CharField(max_length=1000, blank=True)
    duration = models.FloatField(null=True)
    color_mode = models.CharField(max_length=20, default='unknown', db_index=True)
    color_evidence = models.CharField(max_length=300, default='Sampled trailer frames; film edition not independently confirmed.')
    palette = models.JSONField(default=list)
    metrics = models.JSONField(default=dict)
    vector = models.JSONField(default=list)
    frames = models.JSONField(default=list)
    quality = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['selection_rank']
        constraints = [models.CheckConstraint(condition=models.Q(selection_rank__gte=1, selection_rank__lte=500), name='analysis_selection_rank')]


class Technique(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=30)
    description = models.TextField()
    automatic = models.BooleanField(default=False)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class StudyCard(models.Model):
    analysis = models.ForeignKey(TrailerAnalysis, on_delete=models.CASCADE, related_name='study_cards')
    technique = models.ForeignKey(Technique, on_delete=models.PROTECT, related_name='study_cards')
    timestamp = models.FloatField()
    image = models.CharField(max_length=200)
    explanation = models.TextField()
    evidence = models.CharField(max_length=16, choices=[('measured', 'Measured color observation'), ('reviewed', 'Reviewed visual observation')])
    approved = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['analysis__selection_rank', 'timestamp', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['analysis', 'technique', 'image'], name='unique_frame_technique'),
            models.CheckConstraint(condition=models.Q(timestamp__gte=0), name='study_timestamp_nonnegative'),
        ]


class TechniqueSubmission(models.Model):
    """Community evidence across the full catalog; publication requires moderation."""
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='technique_submissions')
    technique = models.ForeignKey(Technique, on_delete=models.PROTECT, related_name='submissions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    explanation = models.TextField()
    source_url = models.URLField(max_length=2000, blank=True)
    timestamp = models.FloatField(null=True, blank=True)
    scope = models.CharField(max_length=10, choices=[('film', 'Film'), ('trailer', 'Trailer')])
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', db_index=True)
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='technique_moderations')
    moderation_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['user', 'movie', 'technique'], name='unique_user_movie_technique'),
            models.CheckConstraint(condition=models.Q(timestamp__isnull=True) | models.Q(timestamp__gte=0), name='submission_timestamp_nonnegative'),
        ]
