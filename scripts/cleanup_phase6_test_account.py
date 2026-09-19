"""Delete only the uniquely named browser-test account and its own sessions."""
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"phase6_browser_[0-9a-f]{16}", sys.argv[1]):
        raise SystemExit("Only an exact, generated Phase 6 browser-test username is accepted.")
    with transaction.atomic():
        user = get_user_model().objects.filter(username=sys.argv[1], is_staff=False, is_superuser=False).first()
        if user is None:
            print("No browser-test account remains.")
            return
        own_sessions = [session.session_key for session in Session.objects.filter(expire_date__gt=timezone.now()) if session.get_decoded().get("_auth_user_id") == str(user.pk)]
        Session.objects.filter(session_key__in=own_sessions).delete()
        user.delete()
    print("Removed the temporary browser-test account and its own data.")

if __name__ == "__main__":
    main()
