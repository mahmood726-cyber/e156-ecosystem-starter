"""Exercise explicit synthetic AACT files; never discover a user's snapshot."""
from __future__ import annotations

import argparse
from contextlib import closing
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import zipfile

BACKENDS = ['csv', 'tsv', 'zip', 'sqlite']
CHECKS = ['load', 'projection', 'drug_filter_then_limit', 'empty_filter', 'missing_column_refused']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exercise(source):
    source = source.resolve(strict=True)
    sys.path.insert(0, str(source/'src'))
    import aact_kit as kit
    import numpy
    import pandas
    require(Path(kit.__file__).resolve() == source/'src/aact_kit/__init__.py', 'imported a different AACT package')
    # These are conspicuously synthetic identifiers, not registry records.
    tables = {
        'studies': [
            {'nct_id': 'fixture-a', 'brief_title': 'SYNTHETIC FIXTURE A'},
            {'nct_id': 'fixture-b', 'brief_title': 'SYNTHETIC FIXTURE B'},
        ],
        'interventions': [
            {'nct_id': 'fixture-a', 'intervention_type': 'drug', 'name': 'OtherSyntheticAgent'},
            {'nct_id': 'fixture-b', 'intervention_type': 'drug', 'name': 'SyntheticAgent'},
        ],
    }
    with tempfile.TemporaryDirectory(prefix='aact-synthetic-check-') as temp:
        root = Path(temp).resolve()
        for folder in ('csv', 'tsv'):
            (root/folder).mkdir()
        archive = root/'synthetic.zip'
        database = root/'synthetic.sqlite'
        with zipfile.ZipFile(archive, 'w') as bundle, closing(sqlite3.connect(database)) as db, db:
            for name, records in tables.items():
                columns = list(records[0])
                for folder, separator, extension in (('csv', ',', 'csv'), ('tsv', '|', 'txt')):
                    stream = io.StringIO(newline='')
                    writer = csv.DictWriter(stream, fieldnames=columns, delimiter=separator, lineterminator='\n')
                    writer.writeheader()
                    writer.writerows(records)
                    value = stream.getvalue()
                    (root/folder/f'{name}.{extension}').write_text(value, encoding='utf-8', newline='\n')
                    if folder == 'tsv':
                        bundle.writestr(f'export/{name}.txt', value)
                # Only fixed fixture table/column names enter this SQL.
                db.execute(f'CREATE TABLE {name} ({", ".join(c+" TEXT" for c in columns)})')
                db.executemany(f'INSERT INTO {name} VALUES ({", ".join("?" for _ in columns)})',
                               [[row[c] for c in columns] for row in records])
        reports = []
        for name, path in zip(BACKENDS, [root/'csv', root/'tsv', archive, database], strict=True):
            location = kit.location_from_path(path)
            studies = kit.load_table('studies', location=location, parse_dates=False)
            checked = kit.validate_columns(studies, 'studies', ['nct_id', 'brief_title'])
            rows = checked.sort_values('nct_id').to_dict(orient='records')
            require(rows == tables['studies'], f'{name}: study rows changed')
            projected = kit.load_table('studies', location=location, columns=['nct_id'], parse_dates=False)
            require(list(projected.columns) == ['nct_id'] and len(projected) == 2, f'{name}: projection mismatch')
            filtered = kit.load_table('interventions', location=location,
                                     where={'name': 'SyntheticAgent', 'intervention_type': 'drug'}, nrows=1)
            require(filtered.to_dict(orient='records') == [tables['interventions'][1]], f'{name}: filter/limit mismatch')
            empty = kit.load_table('studies', location=location, where={'nct_id': 'fixture-absent'})
            require(empty.empty, f'{name}: empty filter mismatch')
            try:
                kit.validate_columns(studies, 'studies', ['nct_id', 'absent_fixture_column'])
            except kit.AACTSchemaError:
                pass
            else:
                raise ValueError(f'{name}: missing column was accepted')
            reports.append({'backend': name, 'checks': CHECKS,
                            'payload_sha256': hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()})
    require(len({row['payload_sha256'] for row in reports}) == 1, 'backend payloads differ')
    return {'schema': 'e156-aact-canary-v1', 'fixture_kind': 'synthetic_install_check',
            'runtime_verified': True, 'backends': reports, 'postgres_verified': False,
            'scientific_accuracy_measured': False,
            'versions': {'python': sys.version.split()[0], 'pandas': pandas.__version__, 'numpy': numpy.__version__}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(exercise(args.source), sort_keys=True))


if __name__ == '__main__':
    main()
