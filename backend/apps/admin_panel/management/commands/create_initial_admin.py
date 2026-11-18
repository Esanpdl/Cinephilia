"""Create the first administrator without changing existing accounts."""
import getpass
import os
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.users.services.profiles import get_or_create_profile
from apps.users.validators import validate_custom_email, validate_custom_password, validate_custom_username


class Command(BaseCommand):
    help = 'Create the first main administrator. Existing administrators are never changed.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin')
        parser.add_argument('--email')
        parser.add_argument('--noinput', action='store_true', help='Read password from CINEPHILIA_INITIAL_ADMIN_PASSWORD.')

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        # Coordinate simultaneous bootstrap commands on the PostgreSQL database.
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [724190801])
        if User.objects.filter(profile__is_main_admin=True).exists():
            self.stdout.write('Main administrator already exists; no account or password changed.')
            return
        try:
            username = validate_custom_username(options['username'])
            email = options['email'] or ('' if options['noinput'] else input('Email: '))
            if not email:
                raise CommandError('Supply --email when creating the first administrator.')
            email = validate_custom_email(email)
            if User.objects.filter(username__iexact=username).exists() or User.objects.filter(email__iexact=email).exists():
                raise CommandError('An account already uses this username or email; no account was changed.')
            password = os.environ.get('CINEPHILIA_INITIAL_ADMIN_PASSWORD')
            if not password and not options['noinput']:
                password = getpass.getpass('Password: ')
                if password != getpass.getpass('Confirm password: '):
                    raise CommandError('Passwords do not match.')
            if not password:
                raise CommandError('Set CINEPHILIA_INITIAL_ADMIN_PASSWORD or run interactively.')
            candidate = User(username=username, email=email)
            validate_custom_password(password)
            password_validation.validate_password(password, candidate)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from None
        user = User.objects.create_user(username=username, email=email, password=password,
                                        is_staff=True, is_superuser=True)
        profile = get_or_create_profile(user)
        profile.is_main_admin = True
        profile.display_name = 'Admin'
        profile.save(update_fields=['is_main_admin', 'display_name', 'updated_at'])
        self.stdout.write(self.style.SUCCESS('Created the main administrator. Password is not logged.'))
