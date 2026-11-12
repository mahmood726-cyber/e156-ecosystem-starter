"""Revalidate source-bound cohort/outcome decision records; all results retain HOLD."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import synthesis_replay as replay
from scripts import synthesis_review_runner as audit

SCHEMA = 'e156-adjudication-v1'
LIMIT = 256 * 1024
IDENTIFIER = re.compile(r'[a-z][a-z0-9_-]{0,63}')
SCOPES = {'cohort': {'definition', 'population', 'timepoint'},
          'outcome': {'definition', 'population', 'timepoint', 'measure'}}
KINDS = {'cohort_overlap': ('cohort', ('SAME', 'PARTIAL', 'DISJOINT', 'UNCLEAR')),
         'outcome_equivalence': ('outcome', ('EQUIVALENT', 'DIFFERENT', 'UNCLEAR'))}


class Refused(ValueError):
    """No current decision-record receipt can be established."""


def require(okay, message):
    if not okay: raise Refused(message)


def fields(value, keys, label):
    require(isinstance(value, dict) and set(value) == set(keys), 'unsupported ' + label + ' fields')


def identifier(value):
    require(isinstance(value, str) and IDENTIFIER.fullmatch(value), 'invalid local identifier')


def text(value, limit, label):
    require(isinstance(value, str) and 1 <= len(value) <= limit and value.strip(), 'invalid ' + label)
    try: value.encode('utf-8')
    except UnicodeError as exc: raise Refused('invalid Unicode scalar in ' + label) from exc


def anchor(value):
    require(isinstance(value, str) and replay.SHA.fullmatch(value), 'invalid SHA-256 anchor')


def code_profile():
    return {'adjudication_sha256': replay.digest(replay.read(Path(__file__), replay.JSON_LIMIT).replace(b'\r\n', b'\n')),
            'audit': audit.code_profile()}


def review_context(data, relation):
    """Hash a structurally validated relation's project, endpoints and report anchors.

    This is a binding for declarations, not a signature or proof of authorship.
    A verified receipt exposes the same hash for preparing subsequent ballots.
    """
    entities = sorted((e for e in data['entities'] if e['id'] in (relation['left'], relation['right'])),
                      key=lambda e: e['id'])
    aliases = {e['report'] for e in entities}
    context = {'project': data['project'], 'schema': data['schema'],
               'relation': {k: relation[k] for k in ('id', 'kind', 'left', 'right')},
               'entities': entities,
               'reports': sorted((r for r in data['reports'] if r['id'] in aliases), key=lambda r: r['id'])}
    return replay.digest(replay.canonical(context))


def _schema(data, project):
    fields(data, ('schema', 'project', 'reports', 'entities', 'relations'), 'dossier')
    require(data['schema'] == SCHEMA, 'unsupported dossier schema')
    identifier(project); identifier(data['project'])
    require(data['project'] == project, 'dossier belongs to another project')
    for name, lower, upper in (('reports', 1, 8), ('entities', 2, 32), ('relations', 1, 64)):
        items = data[name]
        require(isinstance(items, list) and lower <= len(items) <= upper, 'invalid ' + name + ' count')
        ids = []
        for item in items:
            require(isinstance(item, dict), 'invalid ' + name + ' record')
            identifier(item.get('id')); ids.append(item['id'])
        require(len(set(ids)) == len(ids), 'duplicate ' + name + ' identifier')
    reports = {r['id']: r for r in data['reports']}
    for r in reports.values():
        fields(r, ('id', 'manifest_sha256'), 'report'); anchor(r['manifest_sha256'])
    entities = {e['id']: e for e in data['entities']}
    for e in entities.values():
        fields(e, ('id', 'kind', 'report', 'scope'), 'entity')
        require(isinstance(e['kind'], str) and e['kind'] in SCOPES, 'unsupported entity kind')
        identifier(e['report']); require(e['report'] in reports, 'unknown report alias')
        fields(e['scope'], SCOPES[e['kind']], 'entity scope')
        require(e['scope']['definition'] is not None, 'source-bound definition required')
        for v in e['scope'].values():
            if v is None: continue
            fields(v, ('quote', 'locator'), 'source binding')
            text(v['quote'], 500, 'quote'); text(v['locator'], 200, 'locator')
            require(v['quote'] == ' '.join(v['quote'].split()), 'quote whitespace must be normalized')
    require({e['report'] for e in entities.values()} == set(reports), 'unused report alias')
    used, pairs = set(), set()
    for r in data['relations']:
        fields(r, ('id', 'kind', 'left', 'right', 'reviews', 'adjudication'), 'relation')
        require(isinstance(r['kind'], str) and r['kind'] in KINDS, 'unsupported relation kind')
        identifier(r['left']); identifier(r['right'])
        require(r['left'] in entities and r['right'] in entities and r['left'] != r['right'], 'invalid relation endpoints')
        require(all(entities[i]['kind'] == KINDS[r['kind']][0] for i in (r['left'], r['right'])), 'relation/entity type mismatch')
        pair = (r['kind'], *sorted((r['left'], r['right'])))
        require(pair not in pairs, 'duplicate symmetric relation'); pairs.add(pair)
        used.update((r['left'], r['right']))
        require(isinstance(r['reviews'], list) and len(r['reviews']) <= 2, 'at most two original reviews supported')
    require(used == set(entities), 'unused entity')


def _bind(spec, raw, source):
    try:
        captured = replay.capture.capture(raw, source['pmcid'], source['doi'],
                                          quotes=[spec['quote']], for_archive=True)
    except (ValueError, LookupError) as exc:
        raise Refused('source quotation cannot be captured') from exc
    matches = [b for b in captured.get('quote_bindings', {}).get(spec['quote'], [])
               if b['locator'] == spec['locator']]
    require(len(matches) == 1 and matches[0]['count_safe'] is True,
            'quote/locator missing, ambiguous or unsupported')
    return {**spec, **matches[0], 'snapshot_sha256': source['snapshot_sha256']}


def _ballot(record, relation, entities, context, *, adjudication=False):
    keys = {'reviewer', 'decision', 'rationale', 'context_sha256', 'evidence'}
    fields(record, keys | ({'review_sha256'} if adjudication else set()), 'review')
    identifier(record['reviewer']); anchor(record['context_sha256'])
    require(record['context_sha256'] == context, 'review context changed')
    require(isinstance(record['decision'], str) and record['decision'] in KINDS[relation['kind']][1],
            'decision is not valid for this relation kind')
    text(record['rationale'], 2000, 'review rationale')
    refs = record['evidence']
    require(isinstance(refs, list) and 2 <= len(refs) <= 8, 'review requires bounded evidence for both endpoints')
    observed = []
    for ref in refs:
        fields(ref, ('entity', 'field'), 'evidence reference')
        identifier(ref['entity']); identifier(ref['field'])
        observed.append((ref['entity'], ref['field']))
    required = {(i, f) for i in (relation['left'], relation['right'])
                for f, v in entities[i]['scope'].items() if v is not None}
    require(len(set(observed)) == len(observed) and set(observed) == required,
            'review must cite every available scope binding for both endpoints exactly once')


def _relation(data, relation, entities):
    context = review_context(data, relation)
    reviews = relation['reviews']; adjudication = relation['adjudication']
    reviewers = []
    for record in reviews:
        _ballot(record, relation, entities, context); reviewers.append(record['reviewer'])
    require(len(set(reviewers)) == len(reviewers), 'original reviewers must have distinct declared IDs')
    hashes = sorted(replay.digest(replay.canonical(r)) for r in reviews)
    if adjudication is not None:
        require(len(reviews) == 2, 'adjudication requires both original reviews')
        require(reviews[0]['decision'] != reviews[1]['decision'] or reviews[0]['decision'] == 'UNCLEAR',
                'adjudication cannot override an agreed definite decision')
        _ballot(adjudication, relation, entities, context, adjudication=True)
        require(adjudication['reviewer'] not in reviewers, 'adjudicator must have a distinct declared ID')
        require(isinstance(adjudication['review_sha256'], list)
                and adjudication['review_sha256'] == hashes, 'adjudication no longer binds both original ballots')
    decision = None
    if any(v is None for i in (relation['left'], relation['right']) for v in entities[i]['scope'].values()):
        state = 'INCOMPLETE_SCOPE'
    elif len(reviews) < 2:
        state = 'AWAITING_REVIEWS'
    elif adjudication is not None:
        decision = adjudication['decision']; state = 'ADJUDICATION_RECORDED'
    elif reviews[0]['decision'] == reviews[1]['decision']:
        decision = reviews[0]['decision']; state = 'AGREEMENT_RECORDED'
    else:
        state = 'DISAGREEMENT'
    if decision == 'UNCLEAR': decision, state = None, 'UNRESOLVED'
    return {**relation, 'state': state, 'decision': decision, 'context_sha256': context,
            'review_sha256': hashes, 'semantic_support': 'NOT_ASSESSED'}


def _verify(*, dossier, bundles, project, expected_sha256):
    anchor(expected_sha256)
    dossier = replay.guarded(dossier).resolve()
    raw = replay.read(dossier, LIMIT)
    require(replay.digest(raw) == expected_sha256, 'dossier differs from retained external anchor')
    data = replay.strict_json(raw); _schema(data, project)
    require(isinstance(bundles, dict) and set(bundles) == {r['id'] for r in data['reports']},
            'bundle aliases must exactly match reviewed reports')
    roots = {k: replay.guarded(v).resolve() for k, v in bundles.items()}
    require(all(p.is_dir() and not dossier.is_relative_to(p) for p in roots.values()),
            'bundle missing or dossier inside sealed evidence')
    before = {k: audit._bundle_snapshot(p) for k, p in roots.items()}
    profile = code_profile(); reports, sources = {}, {}
    seen = {key: set() for key in ('pmcid', 'doi', 'pmid')}
    for report in sorted(data['reports'], key=lambda r: r['id']):
        alias = report['id']; root = roots[alias]
        checked = replay.verify(root, report['manifest_sha256'])
        manifest_raw = replay.read(root / 'manifest.json', replay.JSON_LIMIT)
        require(replay.digest(manifest_raw) == report['manifest_sha256'], 'manifest changed after replay')
        manifest = replay.strict_json(manifest_raw)
        source = manifest['sources'][manifest['main_source']]
        source_raw = replay.read(root / manifest['main_source'], replay.capture.MAX_BYTES)
        require(replay.digest(source_raw) == source['snapshot_sha256'], 'source changed after replay')
        for key in seen:
            if key not in source: continue
            require(source[key] not in seen[key], 'duplicate primary report identity/version')
            seen[key].add(source[key])
        reports[alias] = {**report, 'source': source, 'replay': checked}
        sources[alias] = (source_raw, source)
    entities = {}
    cache = {}
    for entity in sorted(data['entities'], key=lambda e: e['id']):
        scope = {}
        for field, spec in sorted(entity['scope'].items()):
            if spec is None: scope[field] = None; continue
            key = (entity['report'], spec['quote'], spec['locator'])
            if key not in cache: cache[key] = _bind(spec, *sources[entity['report']])
            scope[field] = cache[key]
        entities[entity['id']] = {**entity, 'scope': scope}
    relations = [_relation(data, r, entities) for r in sorted(data['relations'], key=lambda r: r['id'])]
    require(replay.read(dossier, LIMIT) == raw and code_profile() == profile
            and {k: audit._bundle_snapshot(p) for k, p in roots.items()} == before,
            'dependency changed during verification')
    result = {'schema': 'e156-adjudication-receipt-v1', 'status': 'RECORDS_REVALIDATED', 'project': project,
              'dossier_sha256': expected_sha256, 'code_profile': profile,
              'reports': list(reports.values()), 'entities': list(entities.values()), 'relations': relations,
              'reviewer_identity': 'DECLARED_NOT_AUTHENTICATED', 'semantic_support': 'NOT_ASSESSED',
              'scientific_validity': 'NOT_ESTABLISHED', 'pooling_readiness': 'HOLD',
              'release_eligible': False, 'external_actions': 0}
    return {**result, 'receipt_id': replay.digest(replay.canonical(result))}


def verify(*, dossier, bundles, project, expected_sha256):
    """Read only: re-execute all source replays and validate anchored declarations."""
    try:
        return _verify(dossier=dossier, bundles=bundles, project=project, expected_sha256=expected_sha256)
    except replay.Refused as exc:
        raise Refused(str(exc)) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dossier', type=Path, required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--bundle', action='append', required=True, metavar='ALIAS=PATH')
    args = parser.parse_args(argv)
    try:
        bundles = {}
        for spec in args.bundle:
            alias, separator, path = spec.partition('=')
            identifier(alias)
            require(separator and path and alias not in bundles, 'invalid or duplicate bundle argument')
            bundles[alias] = Path(path)
        result = verify(dossier=args.dossier, bundles=bundles, project=args.project, expected_sha256=args.expected_sha256)
        code = 0
    except Refused as exc:
        result = {'status': 'REFUSED', 'reason': str(exc), 'receipt': None, 'release_eligible': False}; code = 2
    except OSError:
        result = {'status': 'ERROR', 'reason': 'storage failure; no current receipt', 'receipt': None,
                  'release_eligible': False}; code = 3
    # ASCII transport remains valid JSON on legacy Windows console encodings;
    # receipt hashes still use the canonical UTF-8 representation above.
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
