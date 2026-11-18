"""Restore only reference catalogue and study data into an empty application."""
import csv
import importlib.util
import io
from pathlib import Path
import zipfile
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from psycopg import sql


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument('bundle')

    def handle(self, *args, **options):
        path = Path(__file__).resolve().parents[5] / 'scripts/runtime_bundle.py'
        spec = importlib.util.spec_from_file_location('runtime_bundle', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            manifest = module.verify(options['bundle'])
            if manifest['tables'] != list(module.TABLES):
                raise ValueError('Unexpected table list')
            with zipfile.ZipFile(options['bundle']) as bundle, transaction.atomic():
                with connection.cursor() as cursor:
                    for table in module.TABLES:
                        cursor.execute(sql.SQL('SELECT EXISTS(SELECT 1 FROM {})').format(sql.Identifier(table)))
                        if cursor.fetchone()[0]:
                            raise ValueError(f'Restore requires empty reference tables: {table}')
                    for table in module.TABLES:
                        raw = bundle.read('catalog/' + table + '.csv').decode('utf8')
                        columns = next(csv.reader(io.StringIO(raw)))
                        cursor.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s', [table])
                        actual = {row[0] for row in cursor.fetchall()}
                        if set(columns) != actual:
                            raise ValueError(f'Schema does not match snapshot: {table}')
                        statement = sql.SQL('COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)').format(
                            sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, columns)))
                        with cursor.copy(statement) as copy:
                            copy.write(raw)
                        if 'id' in columns:
                            cursor.execute(sql.SQL("SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id),1), MAX(id) IS NOT NULL) FROM {}").format(sql.Identifier(table)), [table])
            self.stdout.write(self.style.SUCCESS('Reference data restored; no user accounts imported.'))
        except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
            raise CommandError(str(exc)) from exc