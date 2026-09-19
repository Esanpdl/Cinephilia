"""Evidence retrieval and palette-only similarity, independent of core ranking."""
from datetime import date
import hashlib
import math
from django.db.models import Prefetch
from apps.cinematography.models import TrailerAnalysis, StudyCard


def analyses():
    return TrailerAnalysis.objects.select_related('movie').defer('vector').prefetch_related(
        Prefetch('study_cards', queryset=StudyCard.objects.filter(approved=True).select_related('technique', 'analysis__movie')))


def palette_similarity(a, b):
    if not a or len(a) != len(b):
        return None
    return round(min(100, sum(math.sqrt(max(0, x) * max(0, y)) for x, y in zip(a, b)) * 100), 1)


def week_key(today=None):
    iso = (today or date.today()).isocalendar()
    return f'{iso.year}-W{iso.week:02}'


def weekly_choice(ids, today=None):
    if not ids:
        return None
    # Deterministic for a given ISO week and eligible set, without fake engagement.
    return min(ids, key=lambda mid: hashlib.sha256(f'{week_key(today)}:{mid}'.encode()).hexdigest())
