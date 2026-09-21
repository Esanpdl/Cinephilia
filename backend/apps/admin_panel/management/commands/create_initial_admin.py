from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.users.services.profiles import get_or_create_profile

User = get_user_model()


class Command(BaseCommand):
    help = "Create or ensure initial admin user exists with username 'admin' and password 'ish@npoudel888'."

    def handle(self, *args, **options):
        username = "admin"
        password = "ish@npoudel888"
        email = "esan3125@gmail.com"

        user = User.objects.filter(email__iexact=email).first() or User.objects.filter(username__iexact=username).first()
        created = False
        if not user:
            user = User.objects.create_user(
                username=username,
                email=email,
                is_staff=True,
                is_superuser=True,
            )
            created = True
        else:
            user.is_staff = True
            user.is_superuser = True
            if not user.email:
                user.email = email

        user.set_password(password)
        user.save()

        profile = get_or_create_profile(user)
        profile.is_main_admin = True
        if not profile.display_name:
            profile.display_name = "Admin"
        profile.save(update_fields=["display_name", "is_main_admin", "updated_at"])

        action_word = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action_word} initial admin user '{user.username}' ({user.email}, is_staff=True, is_superuser=True, is_main_admin=True)."))
