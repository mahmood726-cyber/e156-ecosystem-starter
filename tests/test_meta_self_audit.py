"""Tests for scripts/meta-self-audit.py.

House rule, learned the hard way: a gate that can only report "alive" is not a
gate. So every detector gets BOTH directions -- a known-bad fixture that must
fire and a known-good fixture that must not. A detector with only a positive
test would pass CI while silently matching everything.

The other thing under test is the verdict algebra, because the specific bug this
whole layer exists to prevent is a green badge over a number nobody checked:
  - a fired detector must never yield CLEAN
  - an INCONCLUSIVE must never yield CLEAN, and must exit non-zero
  - a SKIPped Overmind witness must never be read as a pass
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "meta-self-audit.py"


@pytest.fixture(scope="module")
def msa():
    spec = importlib.util.spec_from_file_location("meta_self_audit", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register before exec: the module uses `from __future__ import annotations`
    # with @dataclass, and dataclasses resolves string annotations through
    # sys.modules[cls.__module__]. Without this the import raises.
    sys.modules["meta_self_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


def doc(msa, body: str, scripts: str = ""):
    html = f"<html><body>{body}</body>"
    if scripts:
        html += f"<script>{scripts}</script>"
    html += "</html>"
    return msa.Dashboard(Path("fixture.html"), html)


def run(msa, detector_name: str, body: str, scripts: str = ""):
    fn = getattr(msa, detector_name)
    return fn(doc(msa, body, scripts))


# ---------------------------------------------------------------- MEL-01
BAD_01 = "<p>Primary outcome: change from baseline in systolic blood pressure (mmHg). " \
         "Pooled risk ratio 0.82 (95% CI 0.71 to 0.95). Number needed to treat: 14.</p>"
GOOD_01 = "<p>Primary outcome: all-cause mortality. Pooled risk ratio 0.82 (95% CI 0.71 to 0.95).</p>"


def test_mel01_fires_on_continuous_outcome_in_ratio_model(msa):
    r = run(msa, "d01_continuous_in_ratio_model", BAD_01)
    assert r.status == msa.FIRED
    assert "mmhg" in r.findings[0].title.lower()
    # the fix text must name the ratio-only machinery still on the page
    assert "NNT" in r.findings[0].fix


def test_mel01_quiet_on_a_genuine_binary_outcome(msa):
    assert run(msa, "d01_continuous_in_ratio_model", GOOD_01).status == msa.NOT_APPLICABLE


def test_mel01_does_not_fire_on_percent_of_patients(msa):
    """'%' is a legitimate binary proportion -- it must not be a continuous unit."""
    body = "<p>Outcome: 40% of patients responded. Risk ratio 1.4 (95% CI 1.1 to 1.8).</p>"
    assert run(msa, "d01_continuous_in_ratio_model", body).status == msa.NOT_APPLICABLE


# ---------------------------------------------------------------- MEL-02
def test_mel02_fires_when_means_are_pooled_as_a_ratio(msa):
    body = "<table><tr><th>Trial</th><th>Mean (SD)</th></tr><tr><td>A</td><td>12.1 (3.4)</td></tr></table>" \
           "<p>Pooled odds ratio 1.30.</p>"
    r = run(msa, "d02_measure_vs_data_type", body)
    assert r.status == msa.FIRED


def test_mel02_fires_when_counts_are_pooled_as_a_mean_difference(msa):
    body = "<table><tr><th>Trial</th><th>Events/Total</th></tr><tr><td>A</td><td>12/104</td></tr></table>" \
           "<p>Pooled mean difference -2.1.</p>"
    assert run(msa, "d02_measure_vs_data_type", body).status == msa.FIRED


def test_mel02_quiet_when_measure_matches_the_data(msa):
    body = "<table><tr><th>Trial</th><th>Events/Total</th></tr><tr><td>A</td><td>12/104</td></tr></table>" \
           "<p>Pooled risk ratio 0.80.</p>"
    assert run(msa, "d02_measure_vs_data_type", body).status == msa.CLEAN_


def test_mel02_not_applicable_without_extractable_data(msa):
    assert run(msa, "d02_measure_vs_data_type", "<p>Risk ratio 0.8.</p>").status == msa.NOT_APPLICABLE


# ---------------------------------------------------------------- MEL-03
# The real U.S. Carvedilol Program double-count: a pooled row plus its own four
# component trials. 345+278+366+105 = 1094 exactly.
BAD_03 = """<table>
<tr><th>Trial</th><th>N</th></tr>
<tr><td>US Carvedilol Program</td><td>1094</td></tr>
<tr><td>MOCHA</td><td>345</td></tr>
<tr><td>PRECISE</td><td>278</td></tr>
<tr><td>Colucci</td><td>366</td></tr>
<tr><td>Cohn</td><td>105</td></tr>
</table>"""
GOOD_03 = """<table>
<tr><th>Trial</th><th>N</th></tr>
<tr><td>MOCHA</td><td>345</td></tr>
<tr><td>PRECISE</td><td>278</td></tr>
<tr><td>Colucci</td><td>366</td></tr>
<tr><td>Cohn</td><td>105</td></tr>
</table>"""


def test_mel03_catches_the_carvedilol_double_count(msa):
    r = run(msa, "d03_double_count_sum_of_subsets", BAD_03)
    assert r.status == msa.FIRED
    assert "1094" in r.findings[0].title
    assert "= 1094" in r.findings[0].evidence


def test_mel03_quiet_on_a_clean_trials_table(msa):
    assert run(msa, "d03_double_count_sum_of_subsets", GOOD_03).status == msa.CLEAN_


def test_mel03_not_applicable_without_an_n_column(msa):
    body = "<table><tr><th>Trial</th><th>Drug</th></tr><tr><td>A</td><td>x</td></tr>" \
           "<tr><td>B</td><td>y</td></tr><tr><td>C</td><td>z</td></tr></table>"
    assert run(msa, "d03_double_count_sum_of_subsets", body).status == msa.NOT_APPLICABLE


def test_mel03_is_inconclusive_not_clean_on_an_oversized_table(msa):
    """Bounded search: too big to clear must say so, not report clean."""
    rows = "".join(f"<tr><td>T{i}</td><td>{100 + i}</td></tr>" for i in range(msa.SUBSET_MAX_ROWS + 5))
    body = f"<table><tr><th>Trial</th><th>N</th></tr>{rows}</table>"
    r = run(msa, "d03_double_count_sum_of_subsets", body)
    assert r.status == msa.INCONCLUSIVE_


# ---------------------------------------------------------------- MEL-04
def test_mel04_catches_a_point_estimate_outside_its_interval(msa):
    # Real shape: a published review printed "1.08 (CrI 0.61; 0.91)".
    r = run(msa, "d04_interval_containment", "<p>Pooled 1.08 (CrI 0.61; 0.91)</p>")
    assert r.status == msa.FIRED
    assert "outside" in r.findings[0].title.lower()


def test_mel04_catches_inverted_bounds(msa):
    r = run(msa, "d04_interval_containment", "<p>HR 0.80 (95% CI 1.10 to 0.60)</p>")
    assert r.status == msa.FIRED
    assert "inverted" in r.findings[0].title.lower()


def test_mel04_quiet_on_a_well_formed_estimate(msa):
    assert run(msa, "d04_interval_containment", "<p>HR 0.80 (95% CI 0.66 to 0.97)</p>").status == msa.CLEAN_


# ---------------------------------------------------------------- MEL-05
def test_mel05_catches_a_negative_hazard_ratio(msa):
    r = run(msa, "d05_arithmetic_impossibility", "<p>Hazard ratio -0.35 (95% CI -0.60 to -0.10)</p>")
    assert r.status == msa.FIRED


def test_mel05_quiet_on_a_positive_ratio(msa):
    assert run(msa, "d05_arithmetic_impossibility",
               "<p>Hazard ratio 0.35 (95% CI 0.20 to 0.60)</p>").status == msa.CLEAN_


def test_mel05_not_applicable_to_a_mean_difference(msa):
    """A negative mean difference is normal and must never be flagged."""
    r = run(msa, "d05_arithmetic_impossibility", "<p>Mean difference -3.5 (95% CI -6.0 to -1.0)</p>")
    assert r.status == msa.NOT_APPLICABLE


# ---------------------------------------------------------------- MEL-06
def test_mel06_catches_a_pass_badge_over_a_failing_status(msa):
    body = '<span class="badge">INTERNAL CHECKS PASSED</span>' \
           '<p>Numerical witness: UNVERIFIED (baseline missing).</p>'
    r = run(msa, "d06_false_green_badge", body)
    assert r.status == msa.FIRED
    assert "unverified" in r.findings[0].evidence.lower()


def test_mel06_catches_a_hardcoded_green_with_no_verdict_logic(msa):
    body = '<span style="background:#28a745">INTERNAL CHECKS PASSED</span>'
    r = run(msa, "d06_false_green_badge", body)
    assert r.status == msa.FIRED
    assert "hardcoded green" in r.findings[0].title.lower()


def test_mel06_quiet_when_colour_is_derived_from_the_verdict(msa):
    body = '<span id="b">INTERNAL CHECKS PASSED</span>'
    scripts = 'el.style.background = verdict === "PASS" ? "#28a745" : "#d73a49";'
    assert run(msa, "d06_false_green_badge", body, scripts).status == msa.CLEAN_


def test_mel06_not_applicable_without_a_badge(msa):
    assert run(msa, "d06_false_green_badge", "<p>Results.</p>").status == msa.NOT_APPLICABLE


# ---------------------------------------------------------------- MEL-07
def test_mel07_fires_when_the_headline_reads_the_laxer_path(msa):
    body = "<h1>Pooled DerSimonian-Laird estimate 0.78</h1>" \
           "<p>The prespecified analysis used the Hartung-Knapp adjustment.</p>"
    r = run(msa, "d07_prespecified_vs_display_path", body)
    assert r.status == msa.FIRED


def test_mel07_is_inconclusive_when_the_headline_is_unlabelled(msa):
    """Two paths computed, headline unlabelled -- refuse to bless it."""
    body = "<h1>Pooled estimate 0.78</h1>" \
           "<p>Prespecified: Hartung-Knapp. Sensitivity: DerSimonian-Laird.</p>"
    assert run(msa, "d07_prespecified_vs_display_path", body).status == msa.INCONCLUSIVE_


def test_mel07_not_applicable_without_hksj(msa):
    assert run(msa, "d07_prespecified_vs_display_path",
               "<p>Random-effects pooling.</p>").status == msa.NOT_APPLICABLE


# ---------------------------------------------------------------- MEL-08
def test_mel08_fires_on_egger_below_k10(msa):
    body = "<p>We included 4 studies. Egger's test p = 0.31.</p>"
    r = run(msa, "d08_k_inappropriate_machinery", body)
    assert r.status == msa.FIRED
    assert "k=4" in r.findings[0].title


def test_mel08_catches_the_k_ge_3_gate_bug(msa):
    """The specific bug from the corpus: Egger gated at k>=3 instead of k>=10."""
    body = "<p>Publication bias assessed.</p>"
    scripts = "if (k >= 3) { renderEggerTest(studies); }"
    r = run(msa, "d08_k_inappropriate_machinery", body, scripts)
    assert r.status == msa.FIRED
    assert any("k>=3" in f.title for f in r.findings)


def test_mel08_quiet_when_k_is_large_enough(msa):
    body = "<p>We included 14 studies. Egger's test p = 0.31.</p>"
    assert run(msa, "d08_k_inappropriate_machinery", body).status == msa.CLEAN_


def test_mel08_is_inconclusive_when_k_cannot_be_read(msa):
    body = "<p>Egger's test p = 0.31.</p>"
    assert run(msa, "d08_k_inappropriate_machinery", body).status == msa.INCONCLUSIVE_


def test_mel08_flags_nnt_on_a_continuous_estimand(msa):
    body = "<p>We included 12 studies. Pooled mean difference -2.4. Number needed to treat: 9.</p>"
    r = run(msa, "d08_k_inappropriate_machinery", body)
    assert r.status == msa.FIRED


# ---------------------------------------------------------------- MEL-09
def test_mel09_catches_a_flow_that_does_not_reconcile(msa):
    body = ("<p>Records identified: 1200. Duplicates removed: 200. Records screened: 900. </p>")
    r = run(msa, "d09_prisma_arithmetic", body)
    assert r.status == msa.FIRED
    assert "1000" in r.findings[0].evidence


def test_mel09_catches_included_exceeding_identified(msa):
    body = "<p>Records identified: 40. Studies included: 55.</p>"
    r = run(msa, "d09_prisma_arithmetic", body)
    assert r.status == msa.FIRED
    assert any("identified" in f.title for f in r.findings)


def test_mel09_catches_a_zero_stage(msa):
    body = "<p>Records identified: 0. Records screened: 120. Studies included: 8.</p>"
    assert run(msa, "d09_prisma_arithmetic", body).status == msa.FIRED


def test_mel09_quiet_on_a_reconciling_flow(msa):
    body = ("<p>Records identified: 1200. Duplicates removed: 200. Records screened: 1000. "
            "Records excluded: 940. Full-text articles assessed: 60. "
            "Full-text articles excluded: 48. Studies included: 12. k = 12.</p>")
    assert run(msa, "d09_prisma_arithmetic", body).status == msa.CLEAN_


def test_mel09_not_applicable_without_a_flow(msa):
    assert run(msa, "d09_prisma_arithmetic", "<p>Results.</p>").status == msa.NOT_APPLICABLE


# ---------------------------------------------------------------- MEL-10
def test_mel10_catches_fi_zero_called_robust(msa):
    body = "<p>The fragility index is 0, so the finding is robust to a single event change.</p>"
    r = run(msa, "d10_fragility_misread", body)
    assert r.status == msa.FIRED
    assert "WEAKEST" in r.findings[0].fix


def test_mel10_quiet_on_a_nonzero_fragility_index(msa):
    assert run(msa, "d10_fragility_misread",
               "<p>The fragility index is 7; the result is reasonably robust.</p>").status == msa.CLEAN_


def test_mel10_not_applicable_without_fragility(msa):
    assert run(msa, "d10_fragility_misread", "<p>Results.</p>").status == msa.NOT_APPLICABLE


# ---------------------------------------------------------------- MEL-11
def test_mel11_fires_when_only_efficacy_is_synthesised(msa):
    body = "<p>Primary outcome pooled effect: RR 0.78. Forest plot below.</p>"
    r = run(msa, "d11_missing_harms", body)
    assert r.status == msa.FIRED


def test_mel11_quiet_when_harms_are_synthesised(msa):
    body = "<p>Primary outcome pooled effect: RR 0.78. Serious adverse events: RR 1.02.</p>"
    assert run(msa, "d11_missing_harms", body).status == msa.CLEAN_


def test_mel11_catches_discontinuation_dressed_as_an_adverse_event(msa):
    body = ("<p>Primary outcome pooled effect: RR 0.78. "
            "Safety outcome: all-cause discontinuation, RR 1.10.</p>")
    r = run(msa, "d11_missing_harms", body)
    assert r.status == msa.FIRED
    assert any("discontinuation" in f.title.lower() for f in r.findings)


def test_mel11_accepts_a_labelled_tolerability_proxy(msa):
    body = ("<p>Primary outcome pooled effect: RR 0.78. Serious adverse events: RR 1.02. "
            "All-cause discontinuation is reported as a tolerability proxy, not an adverse event.</p>")
    assert run(msa, "d11_missing_harms", body).status == msa.CLEAN_


# ---------------------------------------------------------------- MEL-12
def test_mel12_catches_studies_dated_after_the_search_end(msa):
    body = ("<p>We searched MEDLINE from 1987 to 2020.</p>"
            "<p>Included: Packer 1996, Zannad 2011, Anker 2021.</p>")
    r = run(msa, "d12_search_window", body)
    assert r.status == msa.FIRED
    assert "2021" in r.findings[0].evidence


def test_mel12_quiet_when_all_studies_fall_inside_the_window(msa):
    body = ("<p>We searched MEDLINE from 1987 to 2020.</p>"
            "<p>Included: Packer 1996, Zannad 2011.</p>")
    assert run(msa, "d12_search_window", body).status == msa.CLEAN_


def test_mel12_not_applicable_without_a_stated_window(msa):
    assert run(msa, "d12_search_window", "<p>Included: Packer 1996.</p>").status == msa.NOT_APPLICABLE


# ---------------------------------------------------------------- MEL-13
def test_mel13_catches_donor_template_bleed_through(msa):
    body = "<p>This drug is a non-steroidal MRA studied across CKD trials.</p>"
    r = run(msa, "d13_template_contamination", body)
    assert r.status == msa.FIRED


def test_mel13_catches_python_none_leaking_into_output(msa):
    body = "<p>This review aggregates 12 trials and None participants.</p>"
    assert run(msa, "d13_template_contamination", body).status == msa.FIRED


def test_mel13_catches_python_none_in_a_js_object_literal(msa):
    """The leak that kills the page: JS has no `None`, so this is a ReferenceError."""
    r = run(msa, "d13_template_contamination", "<p>Report.</p>", 'const d = {k: 12, n: None};')
    assert r.status == msa.FIRED


def test_mel13_quiet_on_clean_prose(msa):
    body = "<p>This review aggregates 12 trials and 4,182 participants.</p>"
    assert run(msa, "d13_template_contamination", body).status == msa.NOT_APPLICABLE


def test_mel13_does_not_flag_none_declared_as_valid_english(msa):
    """Real false positive from a corpus dashboard: 'Conflicts of interest: None declared'."""
    body = "<p>Conflicts of Interest: None declared. Funding: None.</p>"
    assert run(msa, "d13_template_contamination", body).status == msa.NOT_APPLICABLE


def test_mel13_does_not_flag_nan_inside_javascript_source(msa):
    """Real false positive: NaN is ordinary JS. Only a rendered NaN is a leak."""
    scripts = "function tau2CI(){ if (df < 1) return {lo: NaN, hi: NaN}; }"
    assert run(msa, "d13_template_contamination", "<p>Report.</p>", scripts).status == msa.NOT_APPLICABLE


# ---------------------------------------------------------------- MEL-14
def test_mel14_catches_the_timestamp_equals_prospero_claim(msa):
    body = ("<p>The commit timestamp is equivalent to PROSPERO registration, "
            "providing prospective registration of the protocol.</p>")
    assert run(msa, "d14_prospero_overclaim", body).status == msa.FIRED


def test_mel14_accepts_an_honest_timestamp_claim(msa):
    body = ("<p>The commit timestamp is a tamper-evident record of when the protocol existed. "
            "This review is not registered on PROSPERO.</p>")
    assert run(msa, "d14_prospero_overclaim", body).status == msa.CLEAN_


def test_mel14_not_applicable_without_a_registration_claim(msa):
    assert run(msa, "d14_prospero_overclaim", "<p>Results.</p>").status == msa.NOT_APPLICABLE


# ---------------------------------------------------------------- MEL-15
def test_mel15_catches_an_unjustified_date_floor(msa):
    body = "<p>Eligibility: we excluded trials published before 2015.</p>"
    assert run(msa, "d15_exclusion_mis_scoping", body).status == msa.FIRED


def test_mel15_accepts_a_justified_date_floor(msa):
    body = ("<p>Eligibility: we excluded trials published before 2015, because the 2015 guideline "
            "changed the standard of care and earlier trials are not transitive with later ones.</p>")
    assert run(msa, "d15_exclusion_mis_scoping", body).status == msa.CLEAN_


def test_mel15_catches_a_placebo_only_comparator_filter(msa):
    body = "<p>Trials with warfarin comparators were reviewed.</p>"
    scripts = 'const eligible = trials.filter(t => t.comparator === "placebo");'
    r = run(msa, "d15_exclusion_mis_scoping", body, scripts)
    assert r.status == msa.FIRED
    assert "warfarin" in r.findings[0].evidence


def test_mel15_not_applicable_without_filters(msa):
    assert run(msa, "d15_exclusion_mis_scoping", "<p>Results.</p>").status == msa.NOT_APPLICABLE


# ---------------------------------------------------------------- MEL-16
def test_mel16_catches_a_stale_search_sold_as_current(msa):
    body = ("<p>Last search run: 2022. Report generated: 2026. "
            "This provides the most up-to-date evidence available.</p>")
    r = run(msa, "d16_search_currency", body)
    assert r.status == msa.FIRED
    assert "up-to-date" in r.findings[0].evidence


def test_mel16_quiet_on_a_current_search(msa):
    body = "<p>Last search run: 2026. Report generated: 2026.</p>"
    assert run(msa, "d16_search_currency", body).status == msa.CLEAN_


def test_mel16_reads_the_end_of_a_search_range_not_the_start(msa):
    """Real false positive: 'searched from 2010 to 2026' is current, not 16 years stale."""
    body = ("<p>We searched MEDLINE, Embase and CENTRAL from 2010 to 2026. "
            "Report generated: 2026.</p>")
    assert run(msa, "d16_search_currency", body).status == msa.CLEAN_


def test_mel16_is_inconclusive_without_a_report_date(msa):
    assert run(msa, "d16_search_currency", "<p>Last search run: 2022.</p>").status == msa.INCONCLUSIVE_


# ---------------------------------------------------------------- MEL-17
GOOD_17_SCRIPT = ("var studies = ['ARISTOTLE','ROCKET-AF','RE-LY','ENGAGE'];"
                  "var estimates = [0.79, 0.88, 0.91, 0.87];")


def test_mel17_fires_when_label_and_value_arrays_differ_in_length(msa):
    scripts = "var studies = ['A-TRIAL','B-TRIAL','C-TRIAL','D-TRIAL']; var estimates = [0.8, 0.9, 1.1];"
    r = run(msa, "d17_reversed_forest_labels", "<p>Forest plot</p>", scripts)
    assert r.status == msa.FIRED
    assert "different lengths" in r.findings[0].title


def test_mel17_fires_when_plot_labels_reverse_the_table_order(msa):
    body = ("<table><tr><th>Study</th><th>Events</th></tr>"
            "<tr><td>ALPHA</td><td>10/50</td></tr>"
            "<tr><td>BETA</td><td>12/50</td></tr>"
            "<tr><td>GAMMA</td><td>14/50</td></tr>"
            "<tr><td>DELTA</td><td>16/50</td></tr></table>")
    scripts = "var labels = ['DELTA','GAMMA','BETA','ALPHA'];"
    r = run(msa, "d17_reversed_forest_labels", body, scripts)
    assert r.status == msa.FIRED
    assert "reversal" in r.findings[0].title


def test_mel17_fires_when_both_axis_ends_favour_the_same_arm(msa):
    body = "<p>Favours treatment</p><p>Favours treatment</p>"
    r = run(msa, "d17_reversed_forest_labels", body)
    assert r.status == msa.FIRED
    assert "same arm" in r.findings[0].title


def test_mel17_quiet_on_aligned_arrays(msa):
    assert run(msa, "d17_reversed_forest_labels", "<p>Forest plot</p>",
               GOOD_17_SCRIPT).status == msa.CLEAN_


def test_mel17_quiet_on_a_correctly_labelled_axis(msa):
    body = "<p>Favours intervention</p><p>Favours control</p>"
    r = run(msa, "d17_reversed_forest_labels", body)
    assert r.status != msa.FIRED


def test_mel17_is_not_applicable_when_there_is_nothing_machine_readable(msa):
    """A canvas-drawn plot is unverifiable, and must say so rather than pass."""
    r = run(msa, "d17_reversed_forest_labels", "<p>See the forest plot image below.</p>")
    assert r.status == msa.NOT_APPLICABLE
    assert "canvas" in r.detail


def test_mel17_same_order_is_not_a_permutation(msa):
    body = ("<table><tr><th>Study</th><th>N</th></tr>"
            "<tr><td>ALPHA</td><td>50</td></tr><tr><td>BETA</td><td>50</td></tr>"
            "<tr><td>GAMMA</td><td>50</td></tr></table>")
    scripts = "var labels = ['ALPHA','BETA','GAMMA'];"
    assert run(msa, "d17_reversed_forest_labels", body, scripts).status != msa.FIRED


# ---------------------------------------------------------------- MEL-18
def test_mel18_fires_on_a_short_nct_number(msa):
    body = "<p>ARISTOTLE (NCT0041290) reported 2011.</p>"
    r = run(msa, "d18_registry_identifier", body)
    assert r.status == msa.FIRED
    assert "7 digits" in r.findings[0].title


def _reg_table(rows: str) -> str:
    return ("<table><tr><th>Trial</th><th>NCT</th><th>Year</th></tr>" + rows + "</table>")


def test_mel18_fires_when_one_nct_carries_two_trial_names(msa):
    body = _reg_table("<tr><td>ALPHA</td><td>NCT04576988</td><td>2023</td></tr>"
                      "<tr><td>BRAVO</td><td>NCT04576988</td><td>2024</td></tr>")
    r = run(msa, "d18_registry_identifier", body)
    assert r.status == msa.FIRED
    assert any("more than one trial name" in f.title for f in r.findings)


def test_mel18_allows_one_publication_to_report_two_trials(msa):
    """Real false positive: 'Siegal 2015' covers ANNEXA-A and ANNEXA-R.

    One paper reporting two registered trials is ordinary, so an author-year
    label spanning two NCTs must not be called a contradiction.
    """
    body = _reg_table("<tr><td>Siegal 2015</td><td>NCT02220725</td><td>2015</td></tr>"
                      "<tr><td>Siegal 2015</td><td>NCT01758432</td><td>2015</td></tr>")
    assert run(msa, "d18_registry_identifier", body).status == msa.CLEAN_


def test_mel18_does_not_split_one_name_across_two_encodings(msa):
    """Real false positive: 'explorer\\u21224' vs its decoded form read as two trials."""
    scripts = ('var a=[{"nct":"NCT03196284","name":"explorer\\u21224"}];'
               'var b={"nct":"NCT03196284","name":"explorer™4"};')
    r = run(msa, "d18_registry_identifier", "<p>trials</p>", scripts)
    assert not any("more than one trial name" in f.title for f in r.findings)


def test_mel18_ignores_an_undecodable_name_rather_than_calling_it_a_conflict(msa):
    scripts = ('var a=[{"nct":"NCT03196284","name":"explorer4"}];'
               'var b=[{"nct":"NCT03196284","name":"explorer�4"}];')
    r = run(msa, "d18_registry_identifier", "<p>trials</p>", scripts)
    assert not any("more than one trial name" in f.title for f in r.findings)


def test_mel18_tolerates_a_longer_form_of_the_same_name(msa):
    body = _reg_table("<tr><td>ASTRAEA</td><td>NCT01860976</td><td>2017</td></tr>"
                      "<tr><td>ASTRAEA trial</td><td>NCT01860976</td><td>2017</td></tr>")
    assert run(msa, "d18_registry_identifier", body).status == msa.CLEAN_


def test_mel18_fires_when_the_id_postdates_the_study_year(msa):
    """An NCT06 number cannot label a trial that reported in 2005."""
    body = _reg_table("<tr><td>OLDTRIAL</td><td>NCT06123456</td><td>2005</td></tr>")
    r = run(msa, "d18_registry_identifier", body)
    assert r.status == msa.FIRED
    assert any("before that ID block was issued" in f.title for f in r.findings)


def test_mel18_reads_the_year_from_its_column_not_from_a_sample_size(msa):
    """Real false positive: the N column's '1912' was read as a publication year."""
    body = ("<table><tr><th>Trial</th><th>NCT</th><th>N</th><th>Year</th></tr>"
            "<tr><td>ALPHA</td><td>NCT00286455</td><td>1912</td><td>2007</td></tr></table>")
    r = run(msa, "d18_registry_identifier", body)
    assert not any("before that ID block" in f.title for f in r.findings)


def test_mel18_does_not_manufacture_a_conflict_from_repeated_mentions(msa):
    """Real false positive: one NCT recurring in prose and JS bound to AUTO/TRIALS/AACT.

    Binding is structural now, so an ID repeated in narrative text and script
    state cannot disagree with itself.
    """
    body = _reg_table("<tr><td>ASTRAEA</td><td>NCT01860976</td><td>2017</td></tr>")
    scripts = ('var TRIALS=[{"id":"NCT01860976","name":"ASTRAEA"}];'
               'var AUTO_INCLUDE_TRIAL_IDS=new Set(["NCT01860976"]);'
               'var src="AACT RANDOMIZED QUADRUPLE NCT01860976";')
    r = run(msa, "d18_registry_identifier", body, scripts)
    assert r.status == msa.CLEAN_


def test_mel18_fires_on_a_malformed_doi(msa):
    r = run(msa, "d18_registry_identifier", "<p>NCT04576988. doi: 10.1016</p>")
    assert r.status == msa.FIRED
    assert any("Malformed DOI" in f.title for f in r.findings)


def test_mel18_fires_on_a_pmid_with_letters(msa):
    r = run(msa, "d18_registry_identifier", "<p>NCT04576988 PMID: 3950A078</p>")
    assert r.status == msa.FIRED
    assert any("Malformed PMID" in f.title for f in r.findings)


def test_mel18_quiet_on_well_formed_consistent_identifiers(msa):
    body = ("<p>ALPHA (NCT04576988), published 2023, PMID: 37256748, "
            "doi: 10.1056/NEJMoa2213558.</p>"
            "<p>BRAVO (NCT04811092), published 2025.</p>")
    assert run(msa, "d18_registry_identifier", body).status == msa.CLEAN_


def test_mel18_does_not_fire_on_a_plausible_block_year_pairing(msa):
    """NCT04 with a 2020 date is ordinary and must stay quiet."""
    body = "<p>RECENT (NCT04576988), published 2020.</p>"
    assert run(msa, "d18_registry_identifier", body).status == msa.CLEAN_


def test_mel18_does_not_fire_on_adjacent_xml_tag_text(msa):
    """Real false positive: pages carrying PubMed XML reported PMID 'DataBankList'.

    The old pattern allowed a zero-length separator after 'PMID', so the tag name
    that followed it in the markup was read as the PMID's value.
    """
    body = "<p>NCT04576988 PMID DataBankList DataBankName ClinicalTrials.gov</p>"
    r = run(msa, "d18_registry_identifier", body)
    assert not any("Malformed PMID" in f.title for f in r.findings)


def test_mel18_does_not_fire_on_the_word_doi_in_prose(msa):
    body = "<p>NCT04576988. Each record was checked against its doi-based citation.</p>"
    r = run(msa, "d18_registry_identifier", body)
    assert not any("Malformed DOI" in f.title for f in r.findings)


def test_mel18_is_not_applicable_without_identifiers(msa):
    r = run(msa, "d18_registry_identifier", "<p>Four trials were pooled.</p>")
    assert r.status == msa.NOT_APPLICABLE


# ---------------------------------------------------------------- verdict algebra
def test_a_fired_detector_can_never_yield_clean(msa):
    reports = [msa.DetectorReport("MEL-01", "x", msa.CRITICAL, msa.FIRED),
               msa.DetectorReport("MEL-02", "y", msa.HIGH, msa.CLEAN_)]
    assert msa.verdict(reports) == "DEFECTS-FOUND"
    assert msa.EXIT[msa.verdict(reports)] == 1


def test_an_inconclusive_detector_can_never_yield_clean(msa):
    reports = [msa.DetectorReport("MEL-01", "x", msa.CRITICAL, msa.INCONCLUSIVE_),
               msa.DetectorReport("MEL-02", "y", msa.HIGH, msa.CLEAN_)]
    assert msa.verdict(reports) == "INCONCLUSIVE"
    assert msa.EXIT[msa.verdict(reports)] == 2, "inconclusive must exit non-zero -- it is not a pass"


def test_all_clean_or_not_applicable_yields_clean(msa):
    reports = [msa.DetectorReport("MEL-01", "x", msa.CRITICAL, msa.NOT_APPLICABLE),
               msa.DetectorReport("MEL-02", "y", msa.HIGH, msa.CLEAN_)]
    assert msa.verdict(reports) == "CLEAN"
    assert msa.EXIT["CLEAN"] == 0


def test_a_crashing_detector_is_inconclusive_not_clean(msa, monkeypatch):
    def boom(_doc):
        raise RuntimeError("simulated detector crash")
    boom.__name__ = "d99_boom"
    monkeypatch.setattr(msa, "DETECTORS", (boom,))
    reports = msa.audit(doc(msa, "<p>x</p>"))
    assert reports[0].status == msa.INCONCLUSIVE_
    assert msa.verdict(reports) == "INCONCLUSIVE"


def test_the_word_passed_never_appears_in_a_verdict(msa):
    """No verdict may read as a blanket pass. Guards against the false-green-badge
    failure the tool itself detects."""
    assert set(msa.EXIT) == {"CLEAN", "DEFECTS-FOUND", "INCONCLUSIVE"}
    assert not any("PASS" in v for v in msa.EXIT)


# ---------------------------------------------------------------- overmind witness
def test_metamorphic_witness_reports_skip_when_probe_is_missing(msa):
    out = msa.metamorphic_witness("no-such-probe.py", ".")
    assert out["status"] == "SKIPPED"
    assert "reason" in out


PROBE = REPO_ROOT / "templates" / "meta-self-audit" / "pooling_probe.py"
WITNESS_INPUT = {"effects": [0.5, 0.3, 0.8, 0.1, 0.6],
                 "variances": [0.01, 0.04, 0.0225, 0.0625, 0.0144]}


@pytest.fixture(scope="module")
def probe():
    spec = importlib.util.spec_from_file_location("pooling_probe", PROBE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pooling_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_probe_reproduces_a_hand_checked_random_effects_pool(probe):
    r = probe.pool(WITNESS_INPUT["effects"], WITNESS_INPUT["variances"])
    assert r["pooled"] == pytest.approx(0.514567, abs=1e-6)
    assert r["tau2"] == pytest.approx(0.021265, abs=1e-6)
    assert 0 <= r["I2"] <= 100


def test_probe_is_scale_equivariant_under_a_real_unit_change(probe):
    """Doubling the outcome doubles the SEs too -- then RE pooling does scale."""
    base = probe.pool(WITNESS_INPUT["effects"], WITNESS_INPUT["variances"])
    scaled = probe.pool([e * 2 for e in WITNESS_INPUT["effects"]],
                        [v * 4 for v in WITNESS_INPUT["variances"]])
    assert scaled["pooled"] / base["pooled"] == pytest.approx(2.0, abs=1e-9)


def test_random_effects_is_not_invariant_to_the_witness_transform(probe):
    """Documents WHY relation 1 false-FAILs: effects x2 with variances fixed is
    not a unit change, and tau^2 correctly absorbs the extra spread."""
    base = probe.pool(WITNESS_INPUT["effects"], WITNESS_INPUT["variances"])
    bent = probe.pool([e * 2 for e in WITNESS_INPUT["effects"]], WITNESS_INPUT["variances"])
    assert bent["pooled"] / base["pooled"] == pytest.approx(1.8622, abs=1e-3)
    assert bent["tau2"] > base["tau2"]


def test_probe_fixed_mode_is_scale_invariant_under_the_witness_transform(probe):
    base = probe.pool(WITNESS_INPUT["effects"], WITNESS_INPUT["variances"], mode="fixed")
    bent = probe.pool([e * 2 for e in WITNESS_INPUT["effects"]],
                      WITNESS_INPUT["variances"], mode="fixed")
    assert bent["pooled"] / base["pooled"] == pytest.approx(2.0, abs=1e-9)


def test_probe_cli_round_trips_json(tmp_path):
    proc = subprocess.run([sys.executable, str(PROBE)], input=json.dumps(WITNESS_INPUT),
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["model"] == "random"
    assert set(("pooled", "tau2", "I2")) <= set(out)


def test_probe_rejects_a_bad_mode():
    import os
    env = {**os.environ, "POOLING_PROBE_MODE": "sideways"}
    proc = subprocess.run([sys.executable, str(PROBE)], input=json.dumps(WITNESS_INPUT),
                          capture_output=True, text=True, timeout=60, env=env)
    assert proc.returncode == 2


def test_probe_fails_closed_on_a_non_positive_variance(probe):
    with pytest.raises(ValueError):
        probe.pool([0.1, 0.2], [0.01, 0.0])


def test_a_skipped_witness_is_never_rendered_as_a_pass(msa):
    reports = [msa.DetectorReport("MEL-01", "x", msa.CRITICAL, msa.CLEAN_)]
    text = msa.render_text(Path("f.html"), reports, {"status": "SKIPPED", "reason": "not installed"})
    assert "SKIPPED" in text
    assert "VERDICT: CLEAN" in text
    # a CLEAN verdict must still say the pooled arithmetic was not vouched for
    assert "Blind spots" in text


def test_render_says_pooling_not_recomputed_when_no_probe_given(msa):
    reports = [msa.DetectorReport("MEL-01", "x", msa.CRITICAL, msa.CLEAN_)]
    text = msa.render_text(Path("f.html"), reports, None)
    assert "NOT RUN" in text
    assert "has not been independently recomputed" in text


# ---------------------------------------------------------------- CLI
def _cli(tmp_path: Path, html: str, *extra: str):
    f = tmp_path / "review.html"
    f.write_text(html, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH), str(f), *extra],
                          capture_output=True, text=True, timeout=120)
    return proc


def test_cli_exits_1_and_names_the_defect(tmp_path):
    proc = _cli(tmp_path, f"<html><body>{BAD_03}</body></html>")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "DEFECTS-FOUND" in proc.stdout
    assert "MEL-03" in proc.stdout


def test_cli_json_is_parseable_and_carries_the_verdict(tmp_path):
    proc = _cli(tmp_path, f"<html><body>{BAD_03}</body></html>", "--json")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["verdict"] == "DEFECTS-FOUND"
    assert any(d["code"] == "MEL-03" and d["status"] == "fired" for d in payload["detectors"])
    assert payload["pooling_invariants"] is None


def test_the_shipped_clean_example_actually_returns_clean():
    """A suite that can only ever fire is not a check.

    This is the counterpart to every known-bad fixture above: an end-to-end run
    over a deliberately correct review must exit 0. If a detector regresses into
    matching everything, this test is what catches it.
    """
    example = REPO_ROOT / "templates" / "meta-self-audit" / "example_clean_review.html"
    assert example.is_file()
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH), str(example), "--json"],
                          capture_output=True, text=True, timeout=120)
    payload = json.loads(proc.stdout)
    fired = [d["code"] for d in payload["detectors"] if d["status"] == "fired"]
    unclear = [d["code"] for d in payload["detectors"] if d["status"] == "inconclusive"]
    assert payload["verdict"] == "CLEAN", f"fired={fired} inconclusive={unclear}"
    assert proc.returncode == 0


def test_cli_exits_3_on_an_unreadable_file(tmp_path):
    proc = subprocess.run([sys.executable, str(SCRIPT_PATH), str(tmp_path / "nope.html")],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 3


def test_cli_reports_skipped_metamorphic_without_claiming_a_pass(tmp_path):
    proc = _cli(tmp_path, f"<html><body>{BAD_03}</body></html>", "--metamorphic", "missing-probe.py")
    assert proc.returncode == 1
    assert "SKIPPED" in proc.stdout
