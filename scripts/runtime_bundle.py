"""Create and verify a private, credential-free runtime handoff."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

TABLES = ('movies_genre', 'movies_person', 'movies_movie', 'movies_movie_genres',
          'movies_moviecredit', 'cinematography_technique',
          'cinematography_techniquesourcesnapshot', 'cinematography_techniquesourcecitation',
          'cinematography_traileranalysis', 'cinematography_studycard')
ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    p = PurePosixPath(name)
    return not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name


def verify(path):
    with zipfile.ZipFile(path) as bundle:
        manifest = json.loads(bundle.read('bundle-manifest.json'))
        if manifest['format'] != 1 or manifest['private_user_data'] is not False:
            raise ValueError('Unsupported or private database bundle')
        if len(bundle.namelist()) != len(set(bundle.namelist())):
            raise ValueError('Duplicate archive entries')
        expected = set(manifest['files']) | {'bundle-manifest.json'}
        if set(bundle.namelist()) != expected:
            raise ValueError('Unexpected archive entries')
        for name, checksum in manifest['files'].items():
            if not safe_name(name) or not (name.startswith('data/') or name in {f'catalog/{t}.csv' for t in TABLES}):
                raise ValueError('Invalid archive path')
            if digest(bundle.read(name)) != checksum:
                raise ValueError(f'Checksum mismatch: {name}')
        return manifest


def pack(output, backup):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Output already exists; choose a new filename')
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'format': 1, 'private_user_data': False,
                'database_source': Path(backup).name, 'tables': list(TABLES), 'files': {}}
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as dest:
        def add(name, data):
            dest.writestr(name, data)
            manifest['files'][name] = digest(data)
        for directory in ('data/film_frames', 'data/still-frame-dataset/colour-signatures'):
            for path in sorted((ROOT / directory).rglob('*')):
                if path.is_file():
                    add(path.relative_to(ROOT).as_posix(), path.read_bytes())
        for model in ('content', 'collaborative'):
            base = ROOT / 'data' / model
            pointer = base / 'current.json'
            config = json.loads(pointer.read_text())
            artifact = (base / config['directory']).resolve()
            artifact.relative_to(base.resolve())
            add(pointer.relative_to(ROOT).as_posix(), pointer.read_bytes())
            for path in sorted(artifact.rglob('*')):
                if path.is_file():
                    add(path.relative_to(ROOT).as_posix(), path.read_bytes())
        config = ROOT / 'data/tmdb/configuration.json'
        add(config.relative_to(ROOT).as_posix(), config.read_bytes())
        with zipfile.ZipFile(backup) as source:
            old = json.loads(source.read('manifest.json'))
            for table in TABLES:
                raw = source.read(table + '.csv')
                checksum = old['tables'][table].get('sha256')
                if checksum and digest(raw) != checksum:
                    raise ValueError(f'Source checksum mismatch: {table}')
                add('catalog/' + table + '.csv', raw)
        dest.writestr('bundle-manifest.json', json.dumps(manifest, indent=2))
    verify(output)
    print(f'Verified private runtime bundle: {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('pack')
    p.add_argument('--output', required=True)
    p.add_argument('--database-archive', required=True)
    p = sub.add_parser('verify')
    p.add_argument('bundle')
    p = sub.add_parser('install-assets')
    p.add_argument('bundle')
    args = parser.parse_args()
    if args.command == 'pack':
        pack(args.output, args.database_archive)
    else:
        manifest = verify(args.bundle)
        if args.command == 'install-assets':
            with zipfile.ZipFile(args.bundle) as bundle:
                for name in manifest['files']:
                    if name.startswith('data/'):
                        target = (ROOT / name).resolve()
                        target.relative_to(ROOT)
                        if target.exists() and digest(target.read_bytes()) != manifest['files'][name]:
                            raise ValueError(f'Conflicting local asset: {name}')
                for name in manifest['files']:
                    if name.startswith('data/'):
                        target = ROOT / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(bundle.read(name))
        print(f'Verified {len(manifest["files"])} files')


if __name__ == '__main__':
    main()