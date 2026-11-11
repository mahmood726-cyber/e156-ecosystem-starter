#!/usr/bin/env python3
"""Seal and replay source-bound Synthesis checks and study links offline.

REPLAY_MATCHED means the recorded calculation was reproduced. It never means
the paper, trial mapping, reviewer declarations or scientific claim is correct.
Keep the returned manifest SHA-256 separately in a trusted record.
"""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

if __package__:
    from scripts import synthesis_capture_evidence as capture
    from scripts import synthesis_preflight as preflight
else:
    import synthesis_capture_evidence as capture
    import synthesis_preflight as preflight

SCHEMA = 'e156-synthesis-replay-v1'
REGISTRY_SCHEMA = 'e156-synthesis-replay-v2'
LINK_SCHEMA = 'e156-study-links-v1'
SHA = re.compile(r'[0-9a-f]{64}')
SOURCE_PATH = re.compile(r'sources/[0-9a-f]{64}\.xml')
REGISTRY_PATH = re.compile(r'registries/[0-9a-f]{64}\.json')
NCT = re.compile(r'NCT[0-9]{8}')
PRINTED_NCT = re.compile(r'(?<![\w])NCT ?[0-9]{8}(?![\w])')
MAX_REGISTRIES = 8
JSON_LIMIT = 2 * 1024 * 1024
CODE = ('synthesis_replay.py', 'synthesis_preflight.py', 'synthesis_capture_evidence.py',
        'synthesis_participant_evidence.py', 'synthesis_v13_nma_preflight.py',
        'synthesis_five_journal_corrections.py', 'synthesis_intake_evidence.py',
        'synthesis_preflight_count_identity.py', 'synthesis_preflight_root_dedup.py',
        'synthesis_case_state.py')


class Refused(ValueError):
    """Inputs cannot establish the declared replay contract."""


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':'))+'\n').encode('utf-8')


def digest(raw):
    return sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise Refused(f'duplicate JSON key: {key}')
            result[key] = value
        return result
    def invalid(value): raise Refused(f'nonfinite JSON: {value}')
    def finite(value):
        number = float(value)
        if not math.isfinite(number): invalid(value)
        return number
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=invalid, parse_float=finite)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Refused(f'invalid JSON: {exc}') from exc


def linked(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def guarded(path):
    path = Path(path).absolute()
    if any(linked(p) for p in (path, *path.parents)):
        raise Refused('linked paths are not supported')
    return path


def read(path, limit):
    path = guarded(path)
    if not path.is_file(): raise Refused(f'missing regular artifact: {path.name}')
    with path.open('rb') as stream:
        raw = stream.read(limit+1)
    if len(raw) > limit: raise Refused(f'artifact exceeds size limit: {path.name}')
    return raw


def code_profile():
    # Source hashes use LF so ordinary Git CRLF conversion is portable.
    return {name: digest(read(Path(__file__).with_name(name), JSON_LIMIT).replace(b'\r\n', b'\n'))
            for name in CODE}


def source_record(raw):
    try:
        entries = capture.article_entries(raw)
        if len(entries) != 1: raise Refused('each snapshot must contain exactly one article')
        pmcid = capture.article_id(entries[0].find('front/article-meta'), 'pmcid')
        result = capture.capture(raw, pmcid, for_archive=True)
    except (ValueError, LookupError, AttributeError, ET.ParseError, RecursionError) as exc:
        raise Refused(f'snapshot identity/licence refused: {exc}') from exc
    return {**result['source'], 'source_url': f'https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/',
            'origin_status': 'ARCHIVED_XML_NOT_NETWORK_AUTHENTICATED'}


def validate_scope(packet):
    if not isinstance(packet, dict): raise Refused('packet must be an object')
    doc, sources, claims = (packet.get(k) for k in ('document', 'sources', 'claims'))
    if not isinstance(doc, dict) or not isinstance(sources, list) or len(sources) != 1:
        raise Refused('replay requires one primary PMC document/source')
    source = sources[0]
    if (not isinstance(source, dict) or source.get('version') != doc.get('version')
            or source.get('access') != 'ACCESSIBLE'):
        raise Refused('source version/access differs from the primary document')
    if not isinstance(claims, list) or not 1 <= len(claims) <= 40:
        raise Refused('replay requires 1 to 40 source-bound claims')
    if packet.get('deterministic_checks', []) != []:
        raise Refused('unbound deterministic checks are outside the replay contract')
    for claim in claims:
        if not isinstance(claim, dict) or claim.get('source_ids') != [source.get('id')]:
            raise Refused('each claim must reference the primary source exactly once')
        if 'evidence_checks' in claim:
            raise Refused('intake evidence checks are outside the bounded replay contract')
        spec = claim.get('participant_count_check')
        if 'registered_trial' in claim:
            if 'participant_count_check' in claim or not isinstance(claim['registered_trial'], str) or not NCT.fullmatch(claim['registered_trial']):
                raise Refused('a registration claim must identify one canonical NCT, without a participant check')
        elif not isinstance(spec, dict) or spec.get('kind') not in {'UNIQUE_ARMS', 'RESTRICTED'}:
            raise Refused('each claim requires a supported participant check or registered trial binding')


def study_links(packet, main_raw, registry_raw):
    """Bind article registration mentions to typed archived registry references.

    A reciprocal bibliographic link does not resolve cohorts, outcomes, overlap,
    source authenticity or independent study weighting.
    """
    spec = packet.get('study_links')
    if 'study_links' not in packet and not registry_raw:
        return None
    if (not isinstance(spec, dict) or set(spec) != {'schema', 'links'}
            or spec['schema'] != LINK_SCHEMA or not isinstance(spec['links'], list)
            or not 1 <= len(spec['links']) <= MAX_REGISTRIES):
        raise Refused('invalid study-link contract or unused registry snapshots')
    registries = {digest(raw): strict_json(raw) for raw in registry_raw}
    if len(registries) != len(registry_raw): raise Refused('duplicate registry snapshots')
    declarations = {}
    for link in spec['links']:
        if not isinstance(link, dict) or set(link) != {'nct_id', 'registry_sha256', 'reference_type', 'registration'}:
            raise Refused('study link requires exactly NCT, registry hash, reference type and registration binding')
        nct, quote = link['nct_id'], link['registration']
        if not isinstance(nct, str) or not NCT.fullmatch(nct) or nct in declarations:
            raise Refused('invalid or duplicate canonical NCT identifier')
        if (not isinstance(link['registry_sha256'], str) or link['registry_sha256'] not in registries
                or link['reference_type'] not in ('RESULT', 'DERIVED')):
            raise Refused('registry snapshot or result-reference type not established')
        if (not isinstance(quote, dict) or set(quote) != {'quote', 'locator'}
                or not isinstance(quote['quote'], str) or not 1 <= len(quote['quote']) <= 500
                or not isinstance(quote['locator'], str) or not 1 <= len(quote['locator']) <= 200):
            raise Refused('registration needs an exact quote and locator')
        declarations[nct] = link
    if {l['registry_sha256'] for l in declarations.values()} != set(registries):
        raise Refused('unused registry snapshots')
    doc = packet['document']
    evidence = capture.capture(main_raw, doc['pmcid'], doc['identifier'],
                               quotes=[l['registration']['quote'] for l in declarations.values()], for_archive=True)
    source = evidence['source']
    if 'pmid' not in source: raise Refused('an unambiguous source PMID is required for registry linkage')
    report_id = 'pmc:'+source['version']
    trials, links = [], []
    for nct, declaration in sorted(declarations.items()):
        quote = ' '.join(declaration['registration']['quote'].split())
        literals = PRINTED_NCT.findall(quote)
        if len(literals) != 1 or literals[0].replace(' ', '') != nct:
            raise Refused('registration quote must contain exactly the selected NCT identifier')
        bindings = [b for b in evidence.get('quote_bindings', {}).get(quote, [])
                    if b['locator'] == declaration['registration']['locator']]
        if len(bindings) != 1 or bindings[0]['count_safe'] is not True:
            raise Refused('registration quote is missing, ambiguous or has unsupported markup')
        raw_hash = declaration['registry_sha256']
        try:
            protocol = registries[raw_hash]['protocolSection']
            recorded_nct = protocol['identificationModule']['nctId']
            posted = protocol['statusModule']['lastUpdatePostDateStruct']['date']
            references = protocol['referencesModule']['references']
        except (KeyError, TypeError) as exc:
            raise Refused('registry identity/date/reference schema incomplete') from exc
        if recorded_nct != nct: raise Refused('registry primary NCT differs from article link')
        if not isinstance(posted, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', posted):
            raise Refused('registry update-posted date must be a complete source date')
        try: date.fromisoformat(posted)
        except ValueError as exc: raise Refused('invalid registry update-posted date') from exc
        if not isinstance(references, list) or any(not isinstance(ref, dict) for ref in references):
            raise Refused('invalid registry references')
        matched = [(i, ref) for i, ref in enumerate(references) if ref.get('pmid') == source['pmid']]
        if len(matched) != 1 or matched[0][1].get('type') != declaration['reference_type']:
            raise Refused('registry PMID/reference type missing, conflicting or ambiguous')
        trial_id = 'clinicaltrials.gov:'+nct
        trials.append({'id': trial_id, 'nct_id': nct, 'registry_sha256': raw_hash,
                       'source_url': 'https://clinicaltrials.gov/study/'+nct,
                       'protocol_last_update_posted': posted,
                       'origin_status': 'ARCHIVED_JSON_NOT_NETWORK_AUTHENTICATED'})
        links.append({'report': report_id, 'trial': trial_id, 'nct_id': nct,
                      'status': 'REPORT_AND_REGISTRY_LINKED', 'reference_type': declaration['reference_type'],
                      'registry_reference_locator': f'/protocolSection/referencesModule/references/{matched[0][0]}',
                      'registration': {'quote': quote, **bindings[0]}, 'registration_literal': literals[0]})
    return {'schema': LINK_SCHEMA, 'report': {'id': report_id, **source}, 'trials': trials, 'links': links,
            'cohort_overlap': 'UNASSESSED', 'outcome_equivalence': 'UNASSESSED', 'pooling_readiness': 'HOLD'}


def execute(packet_raw, prompt_raw, main_raw, correction_raw, registry_raw=()):
    """Run the existing validator from frozen bytes; never fetch or run bundle code."""
    packet = strict_json(packet_raw)
    validate_scope(packet)
    records = {}
    for raw in (main_raw, *correction_raw):
        path = f'sources/{digest(raw)}.xml'
        record = source_record(raw)
        if path in records or any(r['pmcid'] == record['pmcid'] for r in records.values()):
            raise Refused('duplicate article snapshots are ambiguous')
        records[path] = record
    with TemporaryDirectory(prefix='synthesis-replay-') as temporary:
        root = Path(temporary)
        paths = []
        for index, raw in enumerate((main_raw, *correction_raw)):
            path = root/f'{index}.xml'
            path.write_bytes(raw)
            paths.append(path)
        try:
            result = preflight.review_packet(packet, digest(prompt_raw), digest(packet_raw),
                                             pmc_xml=paths[0], pmc_linked_xml=tuple(paths[1:]))
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
            raise Refused(f'packet cannot be replayed: {exc}') from exc
    if result.get('intake_valid') is not True:
        raise Refused('preflight intake refused: '+','.join(p['code'] for p in result.get('problems', [])))
    evidence = result.get('pmc_evidence', {})
    if evidence.get('status') != 'CAPTURED': raise Refused('no captured PMC source')
    if (any(link.get('resolution') != 'CAPTURED' for link in evidence['correction_links']
            if link['relation'] == 'correction-forward')
            or any(item.get('status') != 'CAPTURED' for item in evidence.get('linked_corrections', []))):
        raise Refused('unresolved correction evidence')
    findings = result.get('participant_count_findings', [])
    participant_claims = [c for c in packet['claims'] if 'participant_count_check' in c]
    if len(findings) != len(participant_claims): raise Refused('incomplete source-to-claim coverage')
    for claim, finding in zip(participant_claims, findings):
        if finding.get('status') not in {'NO_FLAG', 'REVIEW_CANDIDATE'}:
            raise Refused('participant source binding unresolved: '+finding.get('reason', 'unknown'))
        if claim.get('locator') != finding.get('context', {}).get('locator'):
            raise Refused('claim locator must match the resolved context quote')
    graph = study_links(packet, main_raw, registry_raw)
    for claim in packet['claims']:
        if 'registered_trial' not in claim: continue
        matches = [l for l in graph['links'] if l['nct_id'] == claim['registered_trial']] if graph else []
        if (len(matches) != 1 or claim['locator'] != matches[0]['registration']['locator']
                or claim['text'] != matches[0]['registration']['quote']):
            raise Refused('registration claim is not bound to the linked source passage')
    if graph is not None: result['study_links'] = graph
    return canonical(result), records


def summary(manifest, raw_manifest, status):
    return {'status': status, 'manifest_sha256': digest(raw_manifest),
            'payload_sha256': manifest['artifacts']['result.json']['sha256'],
            'scope': ('source_bound_preflight_with_study_links' if manifest['schema'] == REGISTRY_SCHEMA
                      else 'source_bound_participant_preflight'),
            'scientific_validity': 'NOT_ESTABLISHED'}


def seal(packet: Path, prompt: Path, xml: Path, output: Path, linked_xml=(), registry_json=()):
    if len(linked_xml) > capture.MAX_LINKED_CORRECTIONS: raise Refused('too many correction snapshots')
    if len(registry_json) > MAX_REGISTRIES: raise Refused('too many registry snapshots')
    output = guarded(output)
    if output.exists(): raise Refused('output already exists; never overwrite a recorded bundle')
    profile = code_profile()
    packet_raw, prompt_raw = read(packet, JSON_LIMIT), read(prompt, JSON_LIMIT)
    main_raw = read(xml, capture.MAX_BYTES)
    corrections = sorted((read(p, capture.MAX_BYTES) for p in linked_xml), key=digest)
    registries = sorted((read(p, JSON_LIMIT) for p in registry_json), key=digest)
    result_raw, records = execute(packet_raw, prompt_raw, main_raw, corrections, registries)
    if len(result_raw) > capture.MAX_BYTES: raise Refused('result exceeds replay size limit')
    if profile != code_profile(): raise Refused('verifier changed during recording')
    files = {'packet.json': packet_raw, 'prompt.md': prompt_raw, 'result.json': result_raw,
             **{f'sources/{digest(raw)}.xml': raw for raw in (main_raw, *corrections)},
             **{f'registries/{digest(raw)}.json': raw for raw in registries}}
    manifest = {'schema': REGISTRY_SCHEMA if registries else SCHEMA, 'verifiers': profile,
                'main_source': f'sources/{digest(main_raw)}.xml',
                'correction_sources': [f'sources/{digest(raw)}.xml' for raw in corrections],
                'sources': records,
                'artifacts': {name: {'sha256': digest(raw), 'size': len(raw)} for name, raw in files.items()}}
    if registries: manifest['registry_sources'] = [f'registries/{digest(raw)}.json' for raw in registries]
    raw_manifest = canonical(manifest)
    # Publish a completion marker last. On disk failure an incomplete directory
    # remains for inspection and cannot verify; existing bundles are never changed.
    output.mkdir(parents=False, exist_ok=False)
    (output/'sources').mkdir()
    if registries: (output/'registries').mkdir()
    for name, raw in {**files, 'manifest.json': raw_manifest}.items():
        with (output/name).open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return summary(manifest, raw_manifest, 'REPLAY_RECORDED')


def verify(root: Path, expected_sha256: str):
    if not isinstance(expected_sha256, str) or not SHA.fullmatch(expected_sha256):
        raise Refused('an external lowercase SHA-256 manifest trust anchor is required')
    root = guarded(root)
    raw_manifest = read(root/'manifest.json', JSON_LIMIT)
    if digest(raw_manifest) != expected_sha256: raise Refused('manifest differs from trusted digest')
    manifest = strict_json(raw_manifest)
    keys = {'schema', 'verifiers', 'main_source', 'correction_sources', 'sources', 'artifacts'}
    if isinstance(manifest, dict) and manifest.get('schema') == REGISTRY_SCHEMA: keys.add('registry_sources')
    if not isinstance(manifest, dict) or set(manifest) != keys or manifest['schema'] not in (SCHEMA, REGISTRY_SCHEMA):
        raise Refused('unsupported manifest schema/fields')
    if manifest['verifiers'] != code_profile(): raise Refused('verifier profile changed; use the recorded code revision')
    main, corrections = manifest['main_source'], manifest['correction_sources']
    if not isinstance(corrections, list) or len(corrections) > capture.MAX_LINKED_CORRECTIONS:
        raise Refused('invalid correction inventory')
    names = [main, *corrections]
    if (any(not isinstance(n, str) or not SOURCE_PATH.fullmatch(n) for n in names)
            or len(set(names)) != len(names) or corrections != sorted(corrections)):
        raise Refused('invalid source paths or duplicate sources')
    registry_names = manifest.get('registry_sources', [])
    if (not isinstance(registry_names, list) or len(registry_names) > MAX_REGISTRIES
            or (manifest['schema'] == REGISTRY_SCHEMA and not registry_names)
            or any(not isinstance(n, str) or not REGISTRY_PATH.fullmatch(n) for n in registry_names)
            or registry_names != sorted(set(registry_names))):
        raise Refused('invalid registry inventory')
    expected = {'packet.json', 'prompt.md', 'result.json', *names, *registry_names}
    artifacts = manifest['artifacts']
    if not isinstance(artifacts, dict) or set(artifacts) != expected:
        raise Refused('artifact inventory differs from the replay contract')
    observed = set()
    for folder, directories, files in os.walk(root, followlinks=False):
        for name in [*directories, *files]: guarded(Path(folder)/name)
        allowed_dirs = {'sources', 'registries'} if registry_names else {'sources'}
        if any((Path(folder)/d).relative_to(root).as_posix() not in allowed_dirs for d in directories):
            raise Refused('unexpected directory in artifact inventory')
        observed.update((Path(folder)/f).relative_to(root).as_posix() for f in files)
    if observed != expected | {'manifest.json'}: raise Refused('bundle file inventory differs from manifest')
    data = {}
    for name, entry in artifacts.items():
        if (not isinstance(entry, dict) or set(entry) != {'sha256', 'size'}
                or not isinstance(entry['sha256'], str) or not SHA.fullmatch(entry['sha256'])
                or type(entry['size']) is not int or entry['size'] < 0):
            raise Refused('invalid artifact digest/size')
        limit = capture.MAX_BYTES if name == 'result.json' or name in names else JSON_LIMIT
        raw = read(root/name, limit)
        if len(raw) != entry['size'] or digest(raw) != entry['sha256']:
            raise Refused('artifact bytes differ from manifest: '+name)
        if name in names and name != f'sources/{digest(raw)}.xml': raise Refused('source filename is not its content hash')
        if name in registry_names and name != f'registries/{digest(raw)}.json': raise Refused('registry filename is not its content hash')
        data[name] = raw
    result_raw, records = execute(data['packet.json'], data['prompt.md'], data[main], [data[n] for n in corrections],
                                  [data[n] for n in registry_names])
    if records != manifest['sources']: raise Refused('source metadata differs from parsed snapshots')
    if result_raw != data['result.json']: raise Refused('replayed payload differs from recorded result')
    if manifest['verifiers'] != code_profile(): raise Refused('verifier changed during replay')
    return summary(manifest, raw_manifest, 'REPLAY_MATCHED')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('seal')
    for name in ('packet', 'prompt', 'xml', 'output'): create.add_argument('--'+name, type=Path, required=True)
    create.add_argument('--linked-xml', type=Path, action='append', default=[])
    create.add_argument('--registry-json', type=Path, action='append', default=[])
    check = commands.add_parser('verify')
    check.add_argument('root', type=Path)
    check.add_argument('--expected-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'seal':
            result = seal(args.packet, args.prompt, args.xml, args.output, args.linked_xml, args.registry_json)
        else:
            result = verify(args.root, args.expected_sha256)
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'REFUSED', 'reason': str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
