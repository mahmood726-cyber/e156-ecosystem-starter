"""Regression tests for structural refusals and elementary deterministic checks.

Synthetic examples are NOT evidence of real-world accuracy and contain no private
correspondence or manuscript source content.
"""
import copy
import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("synthesis_preflight",ROOT/"scripts"/"synthesis_preflight.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
PROMPT_SHA=mod.digest_bytes((ROOT/"docs"/"SYNTHESIS-PREFLIGHT-v1.1.md").read_bytes())


def default_packet():
    return {"schema_version":"1.1", "run":{"run_id":"SYNTHETIC-001","model_id":"none","model_provider":"manual","tool_versions":{},"prompt_sha256":PROMPT_SHA},
      "document":{"identifier":"SYNTHETIC-NOT-REAL","version":"v1"},
      "sources":[{"id":"S1","access":"ACCESSIBLE","full_text_checked":True,"version":"v1","retrieval_path":"synthetic/local","retrieved_at":"2026-10-31","locator":"Table 1"}],
      "claims":[{"id":"C1","text":"Synthetic claim 1","locator":"Table 1","source_ids":["S1"],"source_support":"SUPPORTED","problem_type":"none","evidence_maturity":"SCREENED","priority":"P4","impact":"none","proposed_disposition":"NO_FLAG","refutation":{"alternative":"same population","checked_against":"Table 1","result":"SUPPORTED"}}],
      "deterministic_checks":[]}


def audit(packet):
    return mod.review_packet(packet,PROMPT_SHA,mod.digest_bytes(json.dumps(packet,sort_keys=True).encode()))

class StructuralSafetyTests(unittest.TestCase):
    def test_baseline_claim_unflagged(self):
        r=audit(default_packet())
        self.assertTrue(r['intake_valid'])
        self.assertEqual(r['flag_count'],0)
        self.assertEqual(r['claim_count'],1)
        self.assertEqual(r['problems'],[])

    def test_prompt_digest_is_required(self):
        p=default_packet();p['run']['prompt_sha256']='0'*64
        r=audit(p)
        self.assertFalse(r['intake_valid'])
        self.assertIn('PROMPT_SHA_MISMATCH',[x['code'] for x in r['problems']])

    def test_flag_requires_complete_refutation(self):
        p=default_packet();c=p['claims'][0]
        c.update(source_support='CONTRADICTED',evidence_maturity='SOURCE_BACKED',proposed_disposition='FLAG',priority='P2')
        c.pop('refutation')
        r=audit(p)
        self.assertEqual(r['flag_count'],0)
        self.assertEqual(r['ledger'][0]['effective'],'HOLD')

    def test_source_backed_refuted_mismatch_is_flag_candidate_only(self):
        p=default_packet();c=p['claims'][0]
        c.update(source_support='CONTRADICTED',evidence_maturity='SOURCE_BACKED',proposed_disposition='FLAG',priority='P2',
                 refutation={'alternative':'different denominators','checked_against':'Table 1 full text','result':'NOT_SUPPORTED'})
        r=audit(p)
        self.assertEqual(r['flag_count'],1)
        self.assertIn('candidate',r['disclaimer'].lower()) if 'candidate' in r['disclaimer'].lower() else self.assertIn('no independent scientific accuracy',r['disclaimer'].lower())

    def test_no_false_positive_for_mitt_clarification(self):
        p=default_packet();c=p['claims'][0]
        c['refutation']={'alternative':'SAP declared modified ITT/no imputation','checked_against':'dated SAP','result':'SUPPORTED'}
        c['proposed_disposition']='RECONCILED'
        self.assertEqual(audit(p)['reconciled_count'],1)

    def test_km_vs_crude_should_not_raise_calculation_warning(self):
        p=default_packet();p['deterministic_checks']=[{'id':'KM','claim_id':'C1','kind':'count_percent','same_population':True,'same_time_window':True,'measure':'KM_cumulative_incidence','events':48,'denominator':1439,'reported_percent':1.2}]
        r=audit(p)
        self.assertEqual(r['checks'][0]['status'],'NOT_COMPARABLE')
        self.assertEqual(r['flag_count'],0)

    def test_proper_denominator_percentage_is_consistent(self):
        p=default_packet();p['deterministic_checks']=[{'id':'COUNT','claim_id':'C1','kind':'count_percent','same_population':True,'same_time_window':True,'measure':'raw_percent','events':16,'denominator':40,'reported_percent':40,'tolerance':0.05}]
        self.assertEqual(audit(p)['checks'][0]['status'],'CONSISTENT')

    def test_mismatch_is_review_not_auto_error(self):
        p=default_packet();p['deterministic_checks']=[{'id':'COUNT','claim_id':'C1','kind':'count_percent','same_population':True,'same_time_window':True,'measure':'raw_percent','events':168,'denominator':542,'reported_percent':27.4,'tolerance':0.1}]
        r=audit(p)
        self.assertEqual(r['checks'][0]['status'],'REVIEW')
        self.assertEqual(r['flag_count'],0)

    def test_source_unavailable_requires_access_failure(self):
        p=default_packet();c=p['claims'][0]
        c['source_support']='SOURCE_UNAVAILABLE';p['sources'][0]['access']='UNAVAILABLE';p['sources'][0]['full_text_checked']=False
        r=audit(p)
        self.assertIn('UNAVAILABLE_WITHOUT_ACCESS_LOG',[x['code'] for x in r['problems']])

    def test_not_enough_info_without_fulltext_is_held(self):
        p=default_packet();c=p['claims'][0]
        c['source_support']='NOT_ENOUGH_INFO';c['proposed_disposition']='HOLD'
        p['sources'][0]['full_text_checked']=False
        r=audit(p)
        self.assertIn('INSUFFICIENT_WITHOUT_FULLTEXT_LOG',[x['code'] for x in r['problems']])

    def test_not_enough_info_with_fulltext_and_stop_is_recorded(self):
        p=default_packet();c=p['claims'][0]
        c.update(source_support='NOT_ENOUGH_INFO',proposed_disposition='HOLD',checking_steps=['checked matched analysis set and figures'],stopped_at_step='private regression config',stalled_reason='not released')
        r=audit(p)
        self.assertNotIn('INSUFFICIENT_WITHOUT_FULLTEXT_LOG',[x['code'] for x in r['problems']])

    def test_independent_adjudication_needs_human_receipt(self):
        p=default_packet();p['claims'][0]['evidence_maturity']='INDEPENDENTLY_ADJUDICATED'
        r=audit(p)
        self.assertEqual(r['ledger'][0]['effective'],'HOLD')
        self.assertIn('UNVERIFIED_INDEPENDENCE',[x['code'] for x in r['problems']])

    def test_reproduced_requires_tool_receipt(self):
        p=default_packet();p['claims'][0]['evidence_maturity']='REPRODUCED'
        r=audit(p)
        self.assertEqual(r['ledger'][0]['effective'],'HOLD')
        self.assertIn('UNVERIFIED_REPRODUCTION',[x['code'] for x in r['problems']])

    def test_source_snapshot_failure_holds_candidate(self):
        p=default_packet();c=p['claims'][0]
        c.update(source_support='CONTRADICTED',evidence_maturity='SOURCE_BACKED',proposed_disposition='FLAG',priority='P2',
                 refutation={'alternative':'none','checked_against':'Table 1','result':'NOT_SUPPORTED'})
        p['sources'][0]['access']='UNKNOWN'
        self.assertEqual(audit(p)['ledger'][0]['effective'],'HOLD')

    def test_flag_with_missing_fulltext_provenance_is_held(self):
        p=default_packet();c=p['claims'][0]
        c.update(source_support='CONTRADICTED',evidence_maturity='SOURCE_BACKED',proposed_disposition='FLAG',priority='P2',
                 refutation={'alternative':'population mismatch','checked_against':'stated footnote','result':'NOT_SUPPORTED'})
        p['sources'][0]['full_text_checked']=False
        self.assertEqual(audit(p)['ledger'][0]['effective'],'HOLD')

    def test_crude_rr_must_not_substitute_adjusted(self):
        p=default_packet();p['deterministic_checks']=[{'id':'RR','claim_id':'C1','kind':'raw_rr','same_population':True,'same_time_window':True,'measure':'adjusted_rr','adjusted':True,'intervention_events':1,'intervention_n':69,'control_events':7,'control_n':71,'reported_rr':0.92}]
        self.assertEqual(audit(p)['checks'][0]['status'],'NOT_COMPARABLE')

    def test_raw_rr_detects_arithmetic_discrepancy(self):
        p=default_packet();p['deterministic_checks']=[{'id':'RR','claim_id':'C1','kind':'raw_rr','same_population':True,'same_time_window':True,'measure':'crude_unadjusted_rr','adjusted':False,'intervention_events':1,'intervention_n':69,'control_events':7,'control_n':71,'reported_rr':0.92,'tolerance':0.05}]
        self.assertEqual(audit(p)['checks'][0]['status'],'REVIEW')

    def test_unit_conversion_detects_factor_ten(self):
        p=default_packet();p['deterministic_checks']=[{'id':'RATE','claim_id':'C1','kind':'infusion_rate','same_population':True,'same_time_window':True,'concentration_mg_per_ml':250,'volume_ml_per_min':1,'reported_mg_per_min':25,'tolerance':0.1}]
        self.assertEqual(audit(p)['checks'][0]['status'],'REVIEW')

    def test_all_claims_are_retained_when_summary_five(self):
        p=default_packet();c=p['claims'][0];c.update(source_support='CONTRADICTED',evidence_maturity='SOURCE_BACKED',proposed_disposition='FLAG',priority='P2',refutation={'alternative':'different denominators','checked_against':'full manuscript','result':'NOT_SUPPORTED'})
        p['claims']=[dict(c,id=f'C{i}') for i in range(12)]
        r=audit(p)
        self.assertEqual(r['claim_count'],12)
        self.assertEqual(r['flag_count'],12)
        self.assertEqual(len(r['top_five']),5)
        self.assertIn('C11',mod._markdown(r))

    def test_no_orphan_calculation(self):
        p=default_packet();p['deterministic_checks']=[{'id':'X','claim_id':'MISSING','kind':'ci_bounds','same_population':True,'same_time_window':True,'interval_type':'conventional_two_sided','lower':0.1,'estimate':0.2,'upper':0.3}]
        self.assertIn('ORPHAN_CHECK',[x['code'] for x in audit(p)['problems']])

    def test_private_case_regression_map_not_a_diagnostic_test(self):
        coverage=json.loads((ROOT/'tests'/'fixtures'/'coverage_map.json').read_text())
        self.assertEqual(coverage['analysis_kind'],'retrospective_issue_to_check_coverage_only')
        self.assertEqual(len(coverage['case_classes']),46)
        counts={}
        for c in coverage['case_classes']:
            counts[c]=counts.get(c,0)+1
        self.assertEqual(counts,{'internal_arithmetic':17,'source_protocol':22,'visual':1,'private_code_data':4,'human_judgement':2})
        self.assertFalse(coverage['measured_detection'])

if __name__=='__main__': unittest.main()