#!/usr/bin/env python3
"""Measure real development exports with the pinned upstream RO-Crate validator.

Requires requirements-rocrate.lock. Only the two reviewed repository examples
are inputs. Standard JSON-LD contexts may be fetched; no article is downloaded.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from importlib.metadata import version
import json
from pathlib import Path
import re
import shutil
import sys
from tempfile import TemporaryDirectory

import synthesis_rocrate as crate
from synthesis_rocrate import replay

ROOT = Path(__file__).resolve().parents[1]


def dependencies():
    raw = replay.read(ROOT/'requirements-rocrate.lock', replay.JSON_LIMIT).replace(b'\r\n', b'\n')
    pins = {}
    for line in raw.decode('utf-8').splitlines():
        if not line or line.startswith('#'): continue
        match = re.fullmatch(r'([a-z0-9-]+)==([0-9.]+)(?: --hash=sha256:[0-9a-f]{64})+', line)
        if not match: raise replay.Refused('malformed validator dependency lock')
        name, expected = match.groups()
        if name in pins or version(name) != expected: raise replay.Refused('validator dependency version differs: '+name)
        pins[name] = expected
    if pins.get('roc-validator') != '0.13.1': raise replay.Refused('unsupported upstream validator version')
    return pins, replay.digest(raw)


def assess(root, cache):
    from rocrate_validator import models, services
    result = services.validate({
        'rocrate_uri': root, 'profile_identifier': 'process-run-crate-0.5',
        'requirement_severity': models.Severity.RECOMMENDED, 'cache_path': cache,
        'enable_profile_inheritance': True, 'enforce_availability': True,
        'packaging_mode': 'attached', 'metadata_only': False,
    })
    details = result.to_dict()
    if details['validation_settings']['profile_identifier'] != 'process-run-crate-0.5':
        raise replay.Refused('validator selected a different profile')
    executed = sorted(result.executed_checks, key=lambda c: c.identifier)
    required = [c for c in executed if c.severity == models.Severity.REQUIRED]
    if not required or result.skipped_checks_count: raise replay.Refused('profile validation incomplete or skipped')
    def clean(message):
        return message.replace(root.as_uri(), '<crate>').replace(str(root), '<crate>')
    return {'required_passed': result.passed(models.Severity.REQUIRED),
            'recommended_passed': result.passed(models.Severity.RECOMMENDED),
            'executed_checks': len(executed), 'required_checks': len(required), 'skipped_checks': result.skipped_checks_count,
            'checks': [{'id': c.identifier, 'name': c.name, 'severity': c.severity.name,
                        'passed': result.get_executed_check_result(c)} for c in executed],
            'issues': [{'check': i.check.identifier, 'name': i.check.name, 'severity': i.severity.name,
                        'message': clean(i.message)} for i in result.get_issues()]}


def contexts():
    from rocrate_validator.utils.http import HttpRequester
    lock = replay.strict_json(replay.read(ROOT/'schemas/rocrate-contexts.json', replay.JSON_LIMIT))
    expected_urls = {crate.BASE+'/context', 'https://w3id.org/ro/terms/workflow-run/context'}
    if set(lock['contexts']) != expected_urls: raise replay.Refused('unexpected context inventory')
    observed = {}
    for url, expected in lock['contexts'].items():
        response = HttpRequester().get(url, headers={'Accept': 'application/ld+json, application/json'})
        if response.status_code != 200 or replay.digest(response.content) != expected['sha256']:
            raise replay.Refused('standard context changed or unavailable: '+url)
        observed[url] = expected['sha256']
    return observed


def semantic_hash_check(root):
    """Check actual JSON-LD expansion preserves file digests (not just JSON keys)."""
    from rdflib import Graph, Literal, URIRef
    metadata = replay.strict_json(replay.read(root/crate.METADATA, replay.JSON_LIMIT))
    base = root.as_uri()+'/'
    graph = Graph().parse(data=json.dumps(metadata), format='json-ld', publicID=base)
    files = [n for n in metadata['@graph'] if 'File' in ([n['@type']] if isinstance(n['@type'], str) else n['@type'])]
    for node in files:
        if (URIRef(base+node['@id']), URIRef('http://schema.org/sha256'), Literal(node['sha256'])) not in graph:
            raise replay.Refused('file digest lost during JSON-LD expansion')
    return len(files)


def measure():
    pins, lock_hash = dependencies()
    cases = []
    with ExitStack() as stack:
        tmp = stack.enter_context(TemporaryDirectory(prefix='e156-rocrate-benchmark-'))
        from rocrate_validator.utils.http import HttpRequester
        stack.callback(HttpRequester.reset)  # Close SQLite handles before Windows directory cleanup.
        work = Path(tmp).resolve()
        cache = work/'http-cache'
        for name in ('stepwise', 'strokewalk'):
            source_receipt = replay.strict_json(replay.read(ROOT/'benchmarks/replay'/f'{name}.json', replay.JSON_LIMIT))
            source = ROOT/'examples'/('synthesis-replay-'+name)
            root = work/name
            exported = crate.export(source, source_receipt['manifest_sha256'], root)
            integrity = crate.verify(root, exported['metadata_sha256'])
            good = assess(root, cache)
            if not good['required_passed']: raise replay.Refused('required profile check failed: '+json.dumps(good['issues']))
            context_hashes = contexts()
            semantic_files = semantic_hash_check(root)
            controls = []
            for defect, token in (('missing_instrument', 'instrument'), ('missing_date', 'datePublished'), ('missing_file', None)):
                bad = work/(name+'-'+defect)
                shutil.copytree(root, bad)
                path = bad/crate.METADATA
                data = replay.strict_json(replay.read(path, replay.JSON_LIMIT))
                if defect == 'missing_instrument':
                    next(n for n in data['@graph'] if n['@type'] == 'CreateAction').pop('instrument')
                elif defect == 'missing_date':
                    next(n for n in data['@graph'] if n['@id'] == './').pop('datePublished')
                else:
                    (bad/'replay/packet.json').unlink()
                path.write_bytes(replay.canonical(data))
                observed = assess(bad, cache)
                issues = [i for i in observed['issues'] if i['severity'] == 'REQUIRED']
                detected = (any(i['check'] == 'ro-crate-1.1_12.1' for i in issues) if defect == 'missing_file'
                            else any(token.lower() in (i['name']+' '+i['message']).lower() for i in issues))
                if observed['required_passed'] or not detected:
                    raise replay.Refused('upstream validator did not reject intended defect: '+defect+'; '+json.dumps(issues))
                controls.append({'defect': defect, 'rejected': True, 'required_issues': issues})
            cases.append({'case': name, 'export': exported, 'integrity': integrity,
                          'run': replay.strict_json(replay.read(root/'run.json', replay.JSON_LIMIT)),
                          'validation': good, 'expanded_file_digests': semantic_files, 'negative_controls': controls})
    return {'schema': 'e156-rocrate-development-measurement-v1', 'status': 'REQUIRED_PROFILE_MATCHED',
            'fixture_kind': 'real_oa_development_examples_with_synthetic_mutations', 'held_out': False,
            'scientific_accuracy_measured': False, 'profile': crate.PROFILE, 'base_profile': crate.BASE,
            'checker_sha256': replay.digest(replay.read(Path(__file__), replay.JSON_LIMIT).replace(b'\r\n', b'\n')),
            'validator_dependencies': pins, 'dependency_lock_sha256': lock_hash, 'context_sha256': context_hashes, 'cases': cases}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New receipt file outside the source examples')
    args = parser.parse_args(argv)
    try:
        output = replay.guarded(args.output) if args.output else None
        if output and (output.exists() or ROOT/'examples' in output.parents):
            raise replay.Refused('receipt path exists or is inside source examples')
        measured = measure()
        if output:
            with output.open('xb') as stream: stream.write(replay.canonical(measured))
    except Exception as exc:
        # Any validator/import/network failure refuses this integration gate.
        print(json.dumps({'status': 'REFUSED', 'reason': str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({'status': measured['status'], 'cases': [
        {'case': c['case'], 'required_checks': c['validation']['required_checks'],
         'recommended_passed': c['validation']['recommended_passed'], 'controls_rejected': len(c['negative_controls']),
         'payload_sha256': c['export']['payload_sha256']} for c in measured['cases']]}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
