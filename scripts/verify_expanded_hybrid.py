"""Verify refreshed model coverage and real-profile hybrid inclusion."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.conf import settings
from django.db import connection
from apps.movies.services.tmdb import write_json
from apps.recommendations.services.hybrid.registry import get_hybrid_service, catalog_snapshot

try:
    service = get_hybrid_service()
    catalog = catalog_snapshot()
    ids = {row["tmdb_id"] for row in catalog}
    assert len(ids) == 11066
    assert service.content is not None and service.collaborative is not None
    assert all(service.content.contains(mid) for mid in ids)
    assert len(service.collaborative.ids) == 8656
    pointer = json.loads(Path(settings.COLLABORATIVE_MODEL_POINTER).read_text(encoding="utf-8"))
    evaluation = json.loads((Path(pointer["directory"]) / "evaluation.json").read_text(encoding="utf-8"))
    history = {row["tmdb_id"]: row["score"] for row in evaluation["authentic_demo_profile"]["ratings"]}
    ranked, profile = service.rank(history, catalog)
    assert {row.tmdb_id for row in ranked} == ids - set(history)
    cf_ids = set(map(int, service.collaborative.ids))
    assert all(row.components["content"] is not None for row in ranked)
    assert all((row.components["collaborative"] is not None) == (row.tmdb_id in cf_ids) for row in ranked)
    report = {"passed": True, "catalog_movies": len(ids), "content_coverage": 11066, "collaborative_coverage": len(cf_ids), "hybrid_candidates": len(ranked), "profile": profile, "unsupported_collaborative_scores_absent": True, "all_unseen_movies_eligible": True}
    write_json(ROOT / "data/expansion/hybrid-verification.json", report)
    print(json.dumps(report, indent=2))
finally:
    connection.close()
