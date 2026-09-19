"""Create the private application schema before running Django migrations."""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Create the cinephilia PostgreSQL schema if missing; run before migrate."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS cinephilia")
        self.stdout.write(self.style.SUCCESS("Application schema is ready: cinephilia."))
