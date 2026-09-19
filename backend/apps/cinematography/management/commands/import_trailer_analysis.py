"""Import local evidence, keeping unavailable films visible in the selected 500."""
import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.movies.models import Movie
from apps.cinematography.models import TrailerAnalysis, StudyCard, Technique
from apps.cinematography.services.taxonomy import TECHNIQUES
from apps.cinematography.services.visual_analysis import VERSION
from apps.cinematography.services.source_review import review_error


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        base = root / 'data/phase8'
        rows = json.loads((base / 'trailer_manifest_500.json').read_text(encoding='utf-8'))['movies']
        if len(rows) != 500 or len({r['tmdb_id'] for r in rows}) != 500:
            raise CommandError('Exactly 500 original selected identities are required.')
        state = json.loads((root / 'data/raw/trailers/_download_status.json').read_text(encoding='utf-8'))['movies']
        audit = {r['tmdb_id']: r for r in json.loads((base / 'source_audit.json').read_text(encoding='utf-8'))['movies']}
        recovery = json.loads((base / 'recovery.json').read_text(encoding='utf-8')) if (base / 'recovery.json').exists() else {}
        decisions = json.loads((base / 'source_decisions.json').read_text(encoding='utf-8')) if (base / 'source_decisions.json').exists() else {}
        movies = {m.tmdb_id: m for m in Movie.objects.filter(tmdb_id__in=[r['tmdb_id'] for r in rows])}
        if len(movies) != 500 or any(not m.is_technique_source for m in movies.values()):
            raise CommandError('Selection must consist of actual scraped-source catalog movies.')
        counts = {}
        records, card_data = [], {}
        with transaction.atomic():
            taxonomy = {}
            for slug, name, category, description, automatic in TECHNIQUES:
                taxonomy[slug], _ = Technique.objects.update_or_create(slug=slug, defaults={'name': name, 'category': category, 'description': description, 'automatic': automatic})
            for row in rows:
                mid = row['tmdb_id']
                movie = movies[mid]
                analysis_path = base / f'analysis/{mid}.json'
                video = root / f'data/raw/trailers/{mid}.mp4'
                data = json.loads(analysis_path.read_text(encoding='utf-8')) if analysis_path.exists() else {}
                if data and data.get('tmdb_id') != mid:
                    raise CommandError(f'Analysis identity does not match selected movie {mid}.')
                status = 'ready' if data else 'failed' if video.exists() else 'missing'
                reason = '' if data else 'No usable analysis yet.' if video.exists() else 'No suitable trailer has been downloaded.'
                flags = audit.get(mid, {}).get('flags', [])
                decision = decisions.get(str(mid), {})
                recovered = recovery.get(str(mid), {}).get('status') == 'recovered'
                if mid == 496243 and recovered and data.get('color_mode') == 'color':
                    flags = [flag for flag in flags if flag != 'user_requested_color_replacement']
                if data and video.exists() and data.get('file_signature', [])[:2] != [video.stat().st_size, video.stat().st_mtime_ns]:
                    status, reason = 'review', 'Trailer changed; its analysis must be refreshed.'
                elif data and flags and decision.get('status') != 'accepted':
                    status, reason = 'review', 'Source requires review: ' + ', '.join(flags)
                if data and not data.get('text_masking'):
                    status, reason = 'review', 'Refreshing analysis to exclude detected text.'
                if data and (data.get('version') != VERSION or data.get('file_signature', [])[2:] != [VERSION]):
                    status, reason = 'review', 'Analysis must be refreshed with the current extraction method.'
                if decision.get('status') == 'rejected':
                    status, reason = 'review', decision.get('reason', 'Source rejected; replacement needed.')
                if data and (error := review_error(data, decision)):
                    status, reason = 'review', error
                if not video.exists():
                    status, reason = 'missing', 'No suitable trailer has been downloaded.'
                defaults = {'selection_rank': row['selection_rank'], 'status': status, 'reason': reason,
                            'version': data.get('version', ''), 'source_sha256': data.get('source_sha256', ''),
                            'source_url': data.get('source_url', state.get(str(mid), {}).get('source_url', '')),
                            'source_title': data.get('source_title', ''), 'duration': data.get('duration'),
                            'color_mode': data.get('color_mode', 'unknown'), 'palette': data.get('palette', []),
                            'metrics': data.get('metrics', {}), 'vector': data.get('vector', []),
                            'frames': data.get('frames', []),
                            'quality': {k: data[k] for k in ['sample_count', 'retained_count', 'excluded', 'screening', 'text_masking', 'source_review', 'source_components'] if k in data}}
                defaults['color_evidence'] = 'Sampled source footage; film edition not independently confirmed.'
                if Movie.Source.BLACKWHITE in movie.source_tags:
                    defaults['color_evidence'] = 'Film appears in the supplied Black and White list; source video color is measured separately.'
                if mid == 496243 and recovered:
                    defaults['color_evidence'] = 'Color trailer replaced the black-and-white edition at the project owner\'s request.'
                records.append(TrailerAnalysis(movie=movie, **defaults))
                card_data[movie.pk] = data
                counts[status] = counts.get(status, 0) + 1
            TrailerAnalysis.objects.bulk_create(records, update_conflicts=True, unique_fields=['movie'], update_fields=list(defaults) + ['updated_at'], batch_size=100)
            saved = {obj.movie_id: obj for obj in TrailerAnalysis.objects.only('pk', 'movie_id')}
            valid_images = {saved[pk].pk: {f['image'] for f in data.get('all_frames', [])} for pk, data in card_data.items()}
            measured_keys = {(saved[pk].pk, taxonomy[c['technique']].pk, c['image']) for pk, data in card_data.items() for c in data.get('study_cards', [])}
            stale = [pk for pk, analysis_id, image, technique_id, evidence in StudyCard.objects.values_list('pk', 'analysis_id', 'image', 'technique_id', 'evidence')
                     if image not in valid_images.get(analysis_id, set()) or (evidence == 'measured' and (analysis_id, technique_id, image) not in measured_keys)]
            StudyCard.objects.filter(pk__in=stale).delete()
            cards = []
            for pk, data in card_data.items():
                for card in data.get('study_cards', []):
                    cards.append(StudyCard(analysis=saved[pk], technique=taxonomy[card['technique']], image=card['image'], timestamp=card['timestamp'], explanation=card['explanation'], evidence='measured', approved=True))
            # Preserve moderator decisions on existing cards when resuming an import.
            StudyCard.objects.bulk_create(cards, ignore_conflicts=True, batch_size=200)
        self.stdout.write(str(counts))
