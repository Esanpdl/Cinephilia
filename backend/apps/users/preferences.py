"""Catalogue-backed taste preferences. Registration alone opts users into setup."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.movies.models import Genre, Movie, Person
from .models import Profile
from .services.profiles import get_or_create_profile


def eras():
    year = timezone.now().year
    ranges = [(1885, 1920)] + [(start, start+9) for start in range(1921, year+1, 10)]
    return [{'id': f'{start}-{end}', 'name': f'{start}\u2013{min(end, year)}',
             'start': start, 'end': min(end, year)} for start, end in ranges]


class PreferenceSerializer(serializers.Serializer):
    favorite_genres = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=5, default=list)
    favorite_actors = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=5, default=list)
    favorite_directors = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=5, default=list)
    favorite_movies = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=10, default=list)
    favorite_eras = serializers.ListField(child=serializers.CharField(max_length=9), max_length=5, default=list)
    exploration = serializers.ChoiceField(choices=['familiar', 'balanced', 'adventurous'], default='balanced')
    language_openness = serializers.ChoiceField(choices=['any', 'prefer'], default='any')
    preferred_languages = serializers.ListField(child=serializers.CharField(max_length=20), max_length=5, default=list)

    def validate(self, data):
        sources = {
            'favorite_genres': Genre.objects.filter(movies__isnull=False),
            'favorite_actors': Person.objects.filter(credits__role='cast'),
            'favorite_directors': Person.objects.filter(credits__role='director'),
            'favorite_movies': Movie.objects.all(),
        }
        for field, query in sources.items():
            values = data[field]
            if len(values) != len(set(values)):
                raise serializers.ValidationError({field: 'Choose each item only once.'})
            if set(query.filter(tmdb_id__in=values).values_list('tmdb_id', flat=True)) != set(values):
                raise serializers.ValidationError({field: 'Choose items available in this catalogue and category.'})
        for field, valid in [('favorite_eras', {e['id'] for e in eras()}),
                             ('preferred_languages', set(Movie.objects.exclude(original_language__in=['', 'xx', 'zxx']).values_list('original_language', flat=True)) )]:
            if len(data[field]) != len(set(data[field])) or not set(data[field]).issubset(valid):
                raise serializers.ValidationError({field: 'Choose different options available in this catalogue.'})
        if not any(data[k] for k in [*sources, 'favorite_eras']):
            raise serializers.ValidationError('Choose at least one genre, actor, director, era or film to personalize your recommendations.')
        if data['language_openness']=='prefer' and not data['preferred_languages']:
            raise serializers.ValidationError({'preferred_languages': 'Choose a preferred language or select any language.'})
        return data


def preference_data(profile):
    data = {key: getattr(profile, key) for key in ['favorite_eras', 'exploration', 'language_openness', 'preferred_languages', 'onboarding_status']}
    data['selections'] = {}
    for kind in ['genres', 'actors', 'directors', 'movies']:
        objects = list(getattr(profile, 'favorite_'+kind).all().order_by('tmdb_id'))
        data['favorite_'+kind] = [o.tmdb_id for o in objects]
        data['selections'][kind] = [{'id': o.tmdb_id, 'name': o.title if kind=='movies' else o.name,
                                    'detail': str(o.release_date.year) if kind=='movies' and o.release_date else ''} for o in objects]
    return data


class PreferenceResponseSerializer(PreferenceSerializer):
    onboarding_status = serializers.CharField(read_only=True)
    selections = serializers.DictField(read_only=True)


class PreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=PreferenceResponseSerializer)
    def get(self, request):
        return Response(preference_data(get_or_create_profile(request.user)))

    @extend_schema(request=PreferenceSerializer, responses=PreferenceResponseSerializer)
    def put(self, request):
        serializer = PreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        get_or_create_profile(request.user)
        with transaction.atomic():
            profile = Profile.objects.select_for_update().get(user=request.user)
            values = serializer.validated_data.copy()
            for kind, model in [('genres', Genre), ('actors', Person), ('directors', Person), ('movies', Movie)]:
                getattr(profile, 'favorite_'+kind).set(model.objects.filter(tmdb_id__in=values.pop('favorite_'+kind)))
            for key, value in values.items():
                setattr(profile, key, value)
            profile.onboarding_status = 'completed'
            profile.save(update_fields=[*values, 'onboarding_status', 'updated_at'])
            result = preference_data(profile)
        response = Response(result)
        response['Cache-Control'] = 'private, no-store'
        return response


class OptionQuerySerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=['movie', 'actor', 'director', 'genre', 'era', 'language'])
    q = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    page = serializers.IntegerField(min_value=1, max_value=100000, default=1)


class OptionResponseSerializer(serializers.Serializer):
    results = serializers.ListField(child=serializers.DictField())
    page = serializers.IntegerField()
    has_more = serializers.BooleanField()


class PreferenceOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(parameters=[OptionQuerySerializer], responses=OptionResponseSerializer)
    def get(self, request):
        serializer = OptionQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        kind, query, page = (serializer.validated_data[k] for k in ['kind', 'q', 'page'])
        start, size = (page-1)*24, 24
        if kind == 'era':
            all_options = [{'id': e['id'], 'name': e['name']} for e in eras() if query.casefold() in (e['name']+' '+e['id']).casefold()]
            items = all_options[start:start+size+1]
        elif kind == 'language':
            codes = Movie.objects.exclude(original_language__in=['', 'xx', 'zxx']).order_by('original_language').values_list('original_language', flat=True).distinct()
            # Django's translated language names are a useful display fallback;
            # the client may localize further with Intl.DisplayNames.
            from django.conf import settings
            names = dict(settings.LANGUAGES)
            all_options = [{'id': code, 'name': str(names.get(code, code))} for code in codes]
            items = [o for o in all_options if query.casefold() in (o['id']+' '+o['name']).casefold()][start:start+size+1]
        else:
            if kind == 'movie':
                qs = Movie.objects.filter(Q(title__icontains=query) | Q(original_title__icontains=query)).order_by('title', 'tmdb_id')
                items = [{'id': m.tmdb_id, 'name': m.title, 'detail': str(m.release_date.year) if m.release_date else ''} for m in qs.only('tmdb_id', 'title', 'release_date')[start:start+size+1]]
            else:
                qs = Genre.objects.filter(movies__isnull=False) if kind=='genre' else Person.objects.filter(credits__role='cast' if kind=='actor' else 'director')
                qs = qs.filter(name__icontains=query).order_by('name', 'tmdb_id').values('tmdb_id', 'name').distinct()
                items = [{'id': o['tmdb_id'], 'name': o['name']} for o in qs[start:start+size+1]]
        response = Response({'results': items[:size], 'page': page, 'has_more': len(items)>size})
        response['Cache-Control'] = 'private, no-store'
        return response
