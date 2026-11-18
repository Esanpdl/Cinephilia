"""Bounded caching for explicitly public reads; never cache account responses."""
import hashlib
import uuid
from functools import wraps
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_save, post_delete, m2m_changed
from rest_framework.response import Response


def revision():
    value = cache.get('public-data-revision')
    if value is None:
        cache.add('public-data-revision', uuid.uuid4().hex, None)
        value = cache.get('public-data-revision')
    return value


def invalidate(**kwargs):
    transaction.on_commit(lambda: cache.set('public-data-revision', uuid.uuid4().hex, None))


def connect_signals():
    from apps.movies.models import Movie, Genre, MovieCredit
    from apps.ratings.models import Rating
    from apps.cinematography.models import TrailerAnalysis, StudyCard, TechniqueSubmission, Technique
    for model in (Movie, Genre, MovieCredit, Rating, TrailerAnalysis, StudyCard, TechniqueSubmission, Technique):
        for signal in (post_save, post_delete):
            signal.connect(invalidate, sender=model, weak=False, dispatch_uid=f'public-cache:{model._meta.label}:{id(signal)}')
    m2m_changed.connect(invalidate, sender=Movie.genres.through, weak=False, dispatch_uid='public-cache:genres')


def cached_public_get(function):
    @wraps(function)
    def wrapped(self, request, *args, **kwargs):
        identity = request.build_absolute_uri() + ':' + str(revision())
        key = 'public-response-v1:' + hashlib.sha256(identity.encode()).hexdigest()
        data = cache.get(key)
        if data is not None:
            return Response(data)
        response = function(self, request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(key, response.data, self.public_cache_seconds)
        return response
    return wrapped


class PublicReadCacheMixin:
    authentication_classes = []
    public_cache_seconds = 60

    @cached_public_get
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
