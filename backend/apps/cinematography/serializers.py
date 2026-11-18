from urllib.parse import urlparse
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Technique, TechniqueSubmission, TrailerAnalysis, StudyCard
from .services.source_review import SOURCE_LABELS
from apps.movies.services.media import image_url
from apps.movies.services.presentation import media_context


def frame_url(frame) -> str:
    return '/api/v1/cinematography/frames/' + frame['image']


class PaletteColorSerializer(serializers.Serializer):
    hex = serializers.CharField()
    weight = serializers.FloatField(min_value=0, max_value=1)


class VisualMetricsSerializer(serializers.Serializer):
    # Unavailable analyses intentionally return an empty measurements object.
    brightness = serializers.FloatField(required=False)
    saturation = serializers.FloatField(required=False)
    contrast = serializers.FloatField(required=False)
    colored_pixel_fraction = serializers.FloatField(required=False)
    monochrome = serializers.BooleanField(required=False)
    mean_chroma = serializers.FloatField(required=False)
    vivid_pixel_fraction = serializers.FloatField(required=False)
    colour_evidence_fraction = serializers.FloatField(required=False)
    local_contrast = serializers.FloatField(required=False)
    lightness_std = serializers.FloatField(required=False)


class EvidenceFrameSerializer(serializers.Serializer):
    technique_analysis = serializers.JSONField(required=False)
    index = serializers.IntegerField()
    timestamp = serializers.FloatField(allow_null=True)
    image = serializers.CharField()
    image_url = serializers.CharField()
    crop = serializers.ListField(child=serializers.IntegerField(), required=False)
    metrics = VisualMetricsSerializer()
    text_excluded_fraction = serializers.FloatField()
    text_regions = serializers.ListField(child=serializers.ListField(child=serializers.ListField(child=serializers.FloatField())))


class PlaybackSourceSerializer(serializers.Serializer):
    source_url = serializers.CharField(allow_blank=True)
    title = serializers.CharField()
    start = serializers.FloatField()
    end = serializers.FloatField()


class TechniqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Technique
        fields = ['slug', 'name', 'category', 'description', 'automatic']


class CardSerializer(serializers.ModelSerializer):
    timestamp = serializers.SerializerMethodField()
    technique = TechniqueSerializer()
    tmdb_id = serializers.IntegerField(source='analysis.movie.tmdb_id')
    title = serializers.CharField(source='analysis.movie.title')
    image_url = serializers.SerializerMethodField()
    source_url = serializers.CharField(source='analysis.source_url')

    def get_image_url(self, obj) -> str:
        return frame_url({'image': obj.image})

    def get_timestamp(self, obj) -> float | None:
        return None if obj.analysis.version.startswith('supplied-stills') else obj.timestamp

    class Meta:
        model = StudyCard
        fields = ['id', 'tmdb_id', 'title', 'technique', 'timestamp', 'image_url', 'explanation', 'evidence', 'source_url']


class PublishedCardSerializer(serializers.Serializer):
    id = serializers.CharField()
    tmdb_id = serializers.IntegerField()
    title = serializers.CharField()
    technique = TechniqueSerializer()
    timestamp = serializers.FloatField(allow_null=True)
    image_url = serializers.CharField()
    explanation = serializers.CharField()
    evidence = serializers.CharField()
    source_url = serializers.CharField(allow_blank=True)


class AnalysisSummarySerializer(serializers.ModelSerializer):
    tmdb_id = serializers.IntegerField(source='movie.tmdb_id')
    title = serializers.CharField(source='movie.title')
    year = serializers.SerializerMethodField()
    preview = serializers.SerializerMethodField()
    poster_url = serializers.SerializerMethodField()
    palette = serializers.SerializerMethodField()
    color_mode = serializers.SerializerMethodField()

    def get_year(self, obj) -> int | None:
        return obj.movie.release_date.year if obj.movie.release_date else None

    def get_preview(self, obj) -> str | None:
        if hasattr(obj, 'preview_frame'):
            return frame_url(obj.preview_frame) if obj.status == 'ready' and obj.preview_frame else None
        return frame_url(obj.frames[0]) if obj.status == 'ready' and obj.frames else None

    def get_poster_url(self, obj) -> str | None:
        if not obj.movie.poster_path:
            return None
        return image_url(obj.movie.poster_path, media_context()['tmdb_configuration'])

    @extend_schema_field(PaletteColorSerializer(many=True))
    def get_palette(self, obj):
        return obj.palette if obj.status == 'ready' else []

    def get_color_mode(self, obj) -> str:
        return obj.color_mode if obj.status == 'ready' else 'unknown'

    class Meta:
        model = TrailerAnalysis
        fields = ['tmdb_id', 'title', 'year', 'selection_rank', 'status', 'reason', 'color_mode', 'palette', 'preview', 'poster_url']


class AnalysisDetailSerializer(AnalysisSummarySerializer):
    frames = serializers.SerializerMethodField()
    metrics = serializers.SerializerMethodField()
    study_cards = serializers.SerializerMethodField()
    scope = serializers.SerializerMethodField()
    playback_sources = serializers.SerializerMethodField()
    motion = serializers.SerializerMethodField()
    quality = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField())
    def get_quality(self, obj):
        # Motion has its own source/status guard; do not leak an unguarded duplicate.
        return {key: value for key, value in obj.quality.items() if key != 'motion'}

    @extend_schema_field(serializers.DictField())
    def get_motion(self, obj):
        if obj.status != 'ready':
            return {'status': 'unavailable'}
        data = obj.quality.get('motion')
        if not data:
            return {'status': 'not_analyzed'}
        if data.get('source_sha256') != obj.source_sha256:
            return {'status': 'stale'}
        return {key: value for key, value in data.items() if key not in {'signature', 'source_sha256', 'tmdb_id'}}

    @extend_schema_field(PlaybackSourceSerializer(many=True))
    def get_playback_sources(self, obj):
        if obj.status != 'ready' or obj.quality.get('source_kind') == 'owner-supplied-stills':
            return []
        parts = obj.quality.get('source_components', [])
        if not parts:
            return [{'source_url': obj.source_url, 'title': obj.source_title,
                     'start': 0, 'end': obj.duration or 0}]
        return [{'source_url': part.get('source_url', ''), 'title': part['original_filename'],
                 'start': part['start'], 'end': parts[i+1]['start'] if i+1 < len(parts) else obj.duration or 0}
                for i, part in enumerate(parts)]

    def get_scope(self, obj) -> str:
        if obj.quality.get('source_kind') == 'owner-supplied-stills':
            return 'Measurements use all supplied still frames, including frames hidden from this gallery. They describe this image collection, not the entire film.'
        review = obj.quality.get('source_review', {})
        label = SOURCE_LABELS.get(review.get('source_kind'), 'Source video')
        note = review.get('source_note', '')
        return f'{label}: sampled footage only; these measurements do not describe the entire film.' + (f' {note}' if note else '')

    @extend_schema_field(EvidenceFrameSerializer(many=True))
    def get_frames(self, obj):
        return [{**frame, 'image_url': frame_url(frame)} for frame in obj.frames] if obj.status == 'ready' else []

    @extend_schema_field(VisualMetricsSerializer)
    def get_metrics(self, obj):
        return obj.metrics if obj.status == 'ready' else {}

    @extend_schema_field(CardSerializer(many=True))
    def get_study_cards(self, obj):
        return CardSerializer([c for c in obj.study_cards.all() if c.approved], many=True).data if obj.status == 'ready' else []

    class Meta(AnalysisSummarySerializer.Meta):
        fields = AnalysisSummarySerializer.Meta.fields + ['frames', 'metrics', 'study_cards', 'source_url', 'playback_sources', 'source_title', 'duration', 'color_evidence', 'quality', 'scope', 'version', 'motion']


class StudentQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, max_length=150)
    page = serializers.IntegerField(required=False, min_value=1)
    color_mode = serializers.ChoiceField(choices=['color', 'black_and_white', 'mixed'], required=False)
    status = serializers.ChoiceField(choices=['ready', 'review', 'missing', 'failed'], required=False)
    technique = serializers.SlugField(required=False)
    source = serializers.ChoiceField(choices=['all', 'human', 'model', 'measured'], default='all')
    category = serializers.ChoiceField(choices=['all', 'framing', 'color'], default='all')


class CompareQuerySerializer(serializers.Serializer):
    left = serializers.IntegerField(min_value=1)
    right = serializers.IntegerField(min_value=1)

    def validate(self, data):
        if data['left'] == data['right']:
            raise serializers.ValidationError('Choose two different films.')
        return data


class TagWriteSerializer(serializers.Serializer):
    tmdb_id = serializers.IntegerField(min_value=1)
    technique = serializers.SlugRelatedField(slug_field='slug', queryset=Technique.objects.all())
    explanation = serializers.CharField(min_length=30, max_length=2000)
    source_url = serializers.URLField(required=False, allow_blank=True, max_length=2000)
    timestamp = serializers.FloatField(min_value=0, max_value=100000, required=False, allow_null=True)
    scope = serializers.ChoiceField(choices=['film', 'trailer'])

    def validate_source_url(self, value):
        if value and urlparse(value).scheme not in ['https', 'http']:
            raise serializers.ValidationError('Use an HTTP or HTTPS evidence link.')
        return value

    def validate_explanation(self, value):
        if any(ord(c) < 32 and c not in '\n\t' for c in value):
            raise serializers.ValidationError('Control characters are not permitted.')
        return value

    def validate(self, data):
        import math
        if data.get('timestamp') is not None and not math.isfinite(data['timestamp']):
            raise serializers.ValidationError('Timestamp must be finite.')
        if data.get('timestamp') is not None and not data.get('source_url'):
            raise serializers.ValidationError('A timestamp needs a source link so its meaning is clear.')
        return data


class TagSerializer(serializers.ModelSerializer):
    technique = TechniqueSerializer()
    tmdb_id = serializers.IntegerField(source='movie.tmdb_id')
    title = serializers.CharField(source='movie.title')

    class Meta:
        model = TechniqueSubmission
        fields = ['id', 'tmdb_id', 'title', 'technique', 'explanation', 'source_url', 'timestamp', 'scope', 'status', 'created_at']


class ModerationSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['approved', 'rejected'])
    expected_status = serializers.ChoiceField(choices=['pending', 'approved', 'rejected'], required=False)
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class QuizAnswerSerializer(serializers.Serializer):
    card_id = serializers.CharField(max_length=80)
    answer = serializers.SlugField()
