"""Read-only verification of the configured Supabase PostgreSQL connection."""
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection


class Command(BaseCommand):
    help = "Verify PostgreSQL connectivity and encrypted transport without changing data."

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    raise CommandError("Database probe returned an unexpected result.")
                if not connection.connection.pgconn.ssl_in_use:
                    raise CommandError("Database connection did not negotiate TLS.")
        except DatabaseError:
            raise CommandError(
                "PostgreSQL connection failed. Check DATABASE_URL, the database password, "
                "project availability and network access. Credentials were not printed."
            ) from None
        finally:
            connection.close()
        self.stdout.write(self.style.SUCCESS("PostgreSQL connection verified; TLS is active."))
