"""Meaningful extraction and API checks, with all test writes rolled back."""
import json
import os
from pathlib import Path
import sys
import unittest
import uuid
import tempfile
from copy import deepcopy
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction, connection
from django.core.management import call_command, CommandError
from rest_framework.test import APIRequestFactory, force_authenticate, APIClient
from apps.cinematography import views
from apps.cinematography.models import TrailerAnalysis, TechniqueSubmission, StudyCard
from apps.cinematography.services.visual_analysis import frame_metrics, crop_borders, color_mode, reject_frame, text_mask
from apps.cinematography.services.learning import palette_similarity, weekly_choice
from apps.cinematography.services.source_review import apply_review, review_error, review_fingerprint
from apps.movies.models import Movie
import numpy as np


class VisualTests(unittest.TestCase):
    def test_review_exclusions_recompute_colors_and_preserve_accounting(self):
        import cv2
        with tempfile.TemporaryDirectory() as directory:
            frames = []
            for index in range(6):
                gray = np.tile(np.arange(96, dtype=np.uint8), (80, 1)) + 40 + index * 5
                frame = np.repeat(gray[:, :, None], 3, axis=2)
                if index == 0:
                    frame[:, :, 2] = 240  # A promotional red graphic must not influence the new palette.
                filename = f'{index}.jpg'
                self.assertTrue(cv2.imwrite(str(Path(directory) / filename), frame))
                frames.append({'index': index, 'image': filename, 'timestamp': float(index)})
            data = {'source_sha256': 'a' * 64, 'all_frames': frames, 'sample_count': 6, 'excluded': {}}
            decision = {'status': 'accepted', 'source_sha256': 'a' * 64, 'source_kind': 'featurette',
                        'source_note': 'Synthetic overlay check.', 'excluded_frame_indices': [0]}
            # Exercise actual palette/metric recomputation, isolating it from OCR model inference.
            with patch('apps.cinematography.services.visual_analysis.text_mask',
                       side_effect=lambda frame: (np.ones(frame.shape[:2], dtype=bool), [])):
                result = apply_review(data, decision, directory)
            self.assertEqual(result['color_mode'], 'black_and_white')
            self.assertEqual(result['retained_count'], 5)
            self.assertEqual(result['retained_count'] + sum(result['excluded'].values()), data['sample_count'])
            self.assertAlmostEqual(sum(result['vector']), 1, places=5)
            for color in result['palette']:
                rgb = [int(color['hex'][i:i+2], 16) for i in (1, 3, 5)]
                self.assertLessEqual(max(rgb) - min(rgb), 3)
            self.assertTrue(all(f['index'] != 0 for key in ['all_frames', 'frames', 'study_cards'] for f in result[key]))
            self.assertEqual(len(data['all_frames']), 6)  # Original evidence remains recoverable.
            self.assertEqual(review_error(result, decision), '')
            self.assertIs(apply_review(result, decision, directory), result)
            contaminated = deepcopy(result)
            contaminated['study_cards'].append(frames[0])
            self.assertIn('exclusions', review_error(contaminated, decision))

    def test_accepted_review_cannot_follow_a_replacement_or_changed_recipe(self):
        decision = {'status': 'accepted', 'source_sha256': 'a' * 64, 'source_kind': 'trailer',
                    'excluded_frame_indices': []}
        data = {'source_sha256': 'b' * 64, 'all_frames': [],
                'source_review': {'recipe_sha256': review_fingerprint(decision)}}
        self.assertIn('different video', review_error(data, decision))
        with self.assertRaisesRegex(ValueError, 'checksum'):
            apply_review(data, decision, Path('.'))
        data['source_sha256'] = decision['source_sha256']
        decision['excluded_frame_indices'] = [5]
        self.assertIn('must be applied', review_error(data, decision))
        with self.assertRaisesRegex(ValueError, 'Review changed'):
            apply_review(data, decision, Path('.'))

    def test_detected_text_does_not_affect_color_measurement(self):
        import cv2
        frame = np.full((240, 640, 3), 100, np.uint8)
        cv2.putText(frame, 'COMING SOON', (35, 180), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 5)
        mask, boxes = text_mask(frame)
        self.assertGreater(len(boxes), 0)
        self.assertLess(frame_metrics(frame, mask)['colored_pixel_fraction'], frame_metrics(frame)['colored_pixel_fraction'])
        self.assertTrue(frame_metrics(frame, mask)['monochrome'])

    def test_color_and_bw_are_distinct(self):
        gray = np.full((100, 100, 3), 100, np.uint8)
        color = gray.copy()
        color[:, :, 2] = 220
        self.assertEqual(color_mode([frame_metrics(gray)] * 10), 'black_and_white')
        self.assertEqual(color_mode([frame_metrics(color)] * 10), 'color')
        self.assertEqual(color_mode([frame_metrics(gray)] * 5 + [frame_metrics(color)] * 5), 'mixed')

    def test_black_bars_and_cards(self):
        frame = np.full((100, 100, 3), 120, np.uint8)
        frame[:10] = frame[-10:] = 0
        cropped, bounds = crop_borders(frame)
        self.assertEqual(cropped.shape, (80, 100, 3))
        self.assertEqual(bounds, [0, 10, 100, 90])
        self.assertEqual(reject_frame(np.zeros((100, 100, 3), np.uint8)), 'black_or_fade')

    def test_similarity_is_bounded_and_weekly_choice_stable(self):
        self.assertEqual(palette_similarity([1, 0], [1, 0]), 100)
        self.assertEqual(palette_similarity([1, 0], [0, 1]), 0)
        self.assertIsNone(palette_similarity([], []))
        self.assertEqual(weekly_choice([1, 2, 3]), weekly_choice([3, 1, 2]))


class APITests(unittest.TestCase):
    def setUp(self):
        self.atomic = transaction.atomic()
        self.atomic.__enter__()
        self.user = get_user_model().objects.create_user(username='visual_test_' + uuid.uuid4().hex[:12])
        self.staff = get_user_model().objects.create_user(username='visual_staff_' + uuid.uuid4().hex[:12], is_staff=True)

    def tearDown(self):
        transaction.set_rollback(True)
        self.atomic.__exit__(None, None, None)

    def call(self, view, method='get', data=None, user=None, **kwargs):
        req = getattr(APIRequestFactory(), method)('/api/v1/cinematography/', data or {}, format='json', HTTP_HOST='127.0.0.1')
        if user:
            force_authenticate(req, user)
        return view.as_view()(req, **kwargs)

    def test_selected_500_and_hidden_unavailable_evidence(self):
        response = self.call(views.StudentFilmsView)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 500)
        entry = TrailerAnalysis.objects.first()
        entry.status = 'review'
        entry.save()
        result = self.call(views.StudentFilmView, tmdb_id=entry.movie.tmdb_id).data
        self.assertEqual(result['frames'], [])
        self.assertEqual(result['metrics'], {})
        self.assertEqual(result['study_cards'], [])
        self.assertEqual(result['playback_sources'], [])

    def test_import_withholds_old_masked_analysis_and_rejects_wrong_identity(self):
        path = ROOT / 'data/phase8/analysis/15.json'
        original_read = Path.read_text
        data = json.loads(original_read(path, encoding='utf-8'))
        self.assertTrue(data['text_masking'])
        data['version'] = 'superseded-extraction'
        data['file_signature'][2] = data['version']

        def read_analysis(file, *args, **kwargs):
            return json.dumps(data) if file == path else original_read(file, *args, **kwargs)

        with patch.object(Path, 'read_text', read_analysis):
            call_command('import_trailer_analysis')
            response = self.call(views.StudentFilmView, tmdb_id=15)
            self.assertEqual(response.data['status'], 'review')
            self.assertEqual(response.data['frames'], [])
            self.assertEqual(response.data['study_cards'], [])
            data['tmdb_id'] = 238
            with self.assertRaisesRegex(CommandError, 'identity does not match'):
                call_command('import_trailer_analysis')

    def test_comparison_validation_and_frame_access(self):
        self.assertEqual(self.call(views.CompareView, data={'left': 15, 'right': 15}).status_code, 400)
        response = self.call(views.CompareView, data={'left': 15, 'right': 238})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(0 <= response.data['palette_similarity'] <= 100)
        self.assertNotIn('vector', response.data['left'])
        frame = response.data['left']['frames'][0]
        mid, digest, filename = frame['image'].split('/')
        image = self.call(views.FrameView, tmdb_id=int(mid), digest=digest, filename=filename)
        self.assertEqual(image.status_code, 200)
        image.close()
        self.assertEqual(self.call(views.FrameView, tmdb_id=int(mid), digest=digest, filename='../secret').status_code, 404)

    def test_full_catalog_tag_is_pending_until_staff_approval(self):
        movie = Movie.objects.exclude(trailer_analysis__isnull=False).first()
        payload = {'tmdb_id': movie.tmdb_id, 'technique': 'symmetry', 'explanation': 'Test evidence describing visible balance around the central axis.', 'scope': 'film'}
        self.assertEqual(self.call(views.TagsView, 'post', payload).status_code, 403)
        created = self.call(views.TagsView, 'post', payload, user=self.user)
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data['status'], 'pending')
        self.assertEqual(self.call(views.PublicTagsView, tmdb_id=movie.tmdb_id).data['count'], 0)
        self.assertEqual(self.call(views.ModerateTagView, 'patch', {'status': 'approved'}, user=self.user, pk=created.data['id']).status_code, 403)
        self.assertEqual(self.call(views.ModerateTagView, 'patch', {'status': 'approved'}, user=self.staff, pk=created.data['id']).status_code, 200)
        self.assertEqual(self.call(views.PublicTagsView, tmdb_id=movie.tmdb_id).data['count'], 1)
        self.assertEqual(self.call(views.TagsView, 'post', payload, user=self.user).status_code, 400)

    def test_csrf_and_untrusted_submission_fields(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post('/api/v1/cinematography/tags/', {'tmdb_id': 15, 'technique': 'symmetry', 'scope': 'film', 'explanation': 'A test description of symmetrical framing.'}, format='json', HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 403)
        payload = {'tmdb_id': 15, 'technique': 'symmetry', 'scope': 'film', 'explanation': 'A test description of symmetrical framing.', 'status': 'approved', 'user': self.staff.pk}
        result = self.call(views.TagsView, 'post', payload, user=self.user)
        self.assertEqual(result.status_code, 201)
        obj = TechniqueSubmission.objects.get(pk=result.data['id'])
        self.assertEqual(obj.user_id, self.user.pk)
        self.assertEqual(obj.status, 'pending')

    def test_quiz_spotlight_and_invalid_filters(self):
        question = self.call(views.QuizView).data['question']
        self.assertIsNotNone(question)
        self.assertNotIn('answer', question)
        card = StudyCard.objects.get(pk=question['card_id'])
        response = self.call(views.QuizView, 'post', {'card_id': card.pk, 'answer': card.technique.slug})
        self.assertTrue(response.data['correct'])
        self.assertEqual(self.call(views.SpotlightView).data['film']['tmdb_id'], self.call(views.SpotlightView).data['film']['tmdb_id'])
        self.assertEqual(self.call(views.StudentFilmsView, data={'page': -1}).status_code, 400)


if __name__ == '__main__':
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in [VisualTests, APITests]])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'passed': result.wasSuccessful()}
    (ROOT / 'data/phase8/api-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    connection.close()
    raise SystemExit(not result.wasSuccessful())
