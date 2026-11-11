"""Disposable-runner control: a missing source must not replace the active pair."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

import research_environment as environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    original = environment.verify(args.root)
    before = (args.root/'active.json').read_bytes()
    saved = args.root/'releases'/original['release']/'component-lock.json'
    candidate = json.loads(saved.read_text(encoding='utf-8'))
    # Explicit failure fixture, never a claimed source revision.
    candidate['components']['rapidmeta']['commit'] = '0'*40
    with tempfile.TemporaryDirectory(prefix='research-upgrade-control-') as temp:
        lock = Path(temp)/'missing-source.json'
        lock.write_text(json.dumps(candidate), encoding='utf-8')
        try:
            environment.install(args.root, lock)
        except environment.Refused:
            pass
        else:
            raise RuntimeError('missing-source candidate unexpectedly activated')
    if (args.root/'active.json').read_bytes() != before or environment.verify(args.root) != original:
        raise RuntimeError('failed candidate changed the active environment')
    print(json.dumps({'fixture_kind': 'deliberate_missing_source', 'active_release': original['release'],
                      'failed_candidate_refused': True, 'active_preserved': True}, sort_keys=True))


if __name__ == '__main__':
    main()
