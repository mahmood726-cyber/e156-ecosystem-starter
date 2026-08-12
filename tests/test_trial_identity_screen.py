"""Tests for scripts/trial-identity-screen.py.

Same house rule as the self-audit suite: a screen that can only report "found
something" is not a screen. Every check gets BOTH directions -- a table that must
fire it and a table that must not.

The specific failure this suite guards against is subtler than a missed detection.
The screen's headline signal is a CONJUNCTION (duplication *and* near-zero
heterogeneity). A sloppy implementation would flag low I-squared on its own, which
would teach every user of this tool that consistent trials are suspicious -- an
actively harmful lesson, and one that would look like the tool working. So the
low-I2-alone case is tested explicitly, in both the unit and the subprocess path.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "trial-identity-screen.py"
EXAMPLE_DIR = REPO_ROOT / "templates" / "trial-identity"


@pytest.fixture(scope="module")
def tis():
    spec = importlib.util.spec_from_file_location("trial_identity_screen", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register before exec -- `from __future__ import annotations` + @dataclass
    # resolves string annotations through sys.modules[cls.__module__].
    sys.modules["trial_identity_screen"] = mod
    spec.loader.exec_module(mod)
    return mod


def cfg(tis, **kw):
    kw.setdefault("universe", None)
    kw.setdefault("i2", None)
    kw.setdefault("tol", tis.DEFAULT_ARM_TOLERANCE)
    return tis._Cfg(**kw)


# The confirmed case: two trials plus their own pooled analysis, each trial
# entered twice. Arm splits as printed in the published characteristics table.
def duplicated_rows(tis):
    return [
        tis.Row("Bakris (2020)", 2833, 2841),
        tis.Row("Bertram (2021)", 3686, 3666),
        tis.Row("Gerasimos (2021)", 2833, 2841),
        tis.Row("Agarwal (2022)", 6519, 6507),
        tis.Row("Gerasimos (2022)", 3686, 3666),
    ]


def clean_rows(tis):
    return [
        tis.Row("Trial A", 120, 118),
        tis.Row("Trial B", 340, 337),
        tis.Row("Trial C", 811, 795),
        tis.Row("Trial D", 1502, 1488),
        tis.Row("Trial E", 2610, 2590),
    ]


def checks_at(rep, severity):
    return {f.check for f in rep.findings if f.severity == severity}


# --------------------------------------------------------------------------
# The bundled self-test must pass, and must be able to fail
# --------------------------------------------------------------------------

def test_selftest_passes():
    r = subprocess.run([sys.executable, str(SCRIPT_PATH), "--selftest"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SELF-TEST PASS" in r.stdout


# --------------------------------------------------------------------------
# S1 -- a pooled analysis sitting alongside its own components
# --------------------------------------------------------------------------

def test_s1_fires_on_pooled_alongside_components(tis):
    rep = tis.screen(duplicated_rows(tis), cfg(tis))
    hits = [f for f in rep.findings
            if f.check == "S1_ARM_SUBSET_SUM" and f.severity == "BLOCK"]
    assert len(hits) == 1
    assert hits[0].subject == "Agarwal (2022)"
    # both arms must be named in the message -- the whole point is that it
    # reconciles twice independently
    assert "6519" in hits[0].message and "6507" in hits[0].message


def test_s1_silent_on_clean_table(tis):
    rep = tis.screen(clean_rows(tis), cfg(tis))
    assert "S1_ARM_SUBSET_SUM" not in checks_at(rep, "BLOCK")


def test_s1_requires_both_arms_to_reconcile(tis):
    """One arm matching is a coincidence; the check must not fire on it."""
    rows = [
        tis.Row("pooled?", 6519, 9999),   # treat arm reconciles, control does not
        tis.Row("A", 2833, 2841),
        tis.Row("B", 3686, 3666),
    ]
    rep = tis.screen(rows, cfg(tis))
    assert "S1_ARM_SUBSET_SUM" not in checks_at(rep, "BLOCK")


# --------------------------------------------------------------------------
# S3 -- the same trial under two names
# --------------------------------------------------------------------------

def test_s3_fires_on_exact_duplicate_arms(tis):
    rep = tis.screen(duplicated_rows(tis), cfg(tis))
    subjects = {f.subject for f in rep.findings
                if f.check == "S3_NEAR_DUPLICATE_ARMS" and f.severity == "BLOCK"}
    assert "Bakris (2020) / Gerasimos (2021)" in subjects
    assert "Bertram (2021) / Gerasimos (2022)" in subjects


def test_s3_fires_on_transposed_arms(tis):
    rep = tis.screen([tis.Row("X", 500, 480), tis.Row("Y", 480, 500)], cfg(tis))
    hits = [f for f in rep.findings if f.check == "S3_NEAR_DUPLICATE_ARMS"]
    assert hits and "TRANSPOSED" in hits[0].message


def test_s3_near_duplicate_is_warn_not_block(tis):
    """Within tolerance but not exact -- real, but weaker. Must not read as certain."""
    rep = tis.screen([tis.Row("X", 2833, 2841), tis.Row("Y", 2840, 2833)], cfg(tis))
    hits = [f for f in rep.findings if f.check == "S3_NEAR_DUPLICATE_ARMS"]
    assert len(hits) == 1
    assert hits[0].severity == "WARN"


def test_s3_respects_zero_tolerance(tis):
    rep = tis.screen([tis.Row("X", 2833, 2841), tis.Row("Y", 2840, 2833)],
                     cfg(tis, tol=0))
    assert not [f for f in rep.findings if f.check == "S3_NEAR_DUPLICATE_ARMS"]


def test_s3_silent_on_distinct_trials(tis):
    rep = tis.screen(clean_rows(tis), cfg(tis))
    assert not [f for f in rep.findings if f.check == "S3_NEAR_DUPLICATE_ARMS"]


# --------------------------------------------------------------------------
# S4 -- inflation past the randomised universe
# --------------------------------------------------------------------------

def test_s4_fires_on_inflation(tis):
    rep = tis.screen(duplicated_rows(tis), cfg(tis, universe=22000))
    hits = [f for f in rep.findings
            if f.check == "S4_UNIVERSE_INFLATION" and f.severity == "BLOCK"]
    assert len(hits) == 1


def test_s4_silent_within_universe(tis):
    rep = tis.screen(clean_rows(tis), cfg(tis, universe=11000))
    assert "S4_UNIVERSE_INFLATION" not in checks_at(rep, "BLOCK")
    assert "S4_UNIVERSE_INFLATION" not in checks_at(rep, "WARN")


def test_s4_does_not_run_without_universe(tis):
    """The screen must not invent a universe. Absent the input, it says so."""
    rep = tis.screen(duplicated_rows(tis), cfg(tis))
    assert "S4_UNIVERSE_INFLATION" not in checks_at(rep, "BLOCK")
    assert any("no --universe supplied" in f.message for f in rep.findings)


# --------------------------------------------------------------------------
# S5 -- the co-signature, and the harmful-lesson guard
# --------------------------------------------------------------------------

def test_s5_fires_only_in_conjunction(tis):
    rep = tis.screen(duplicated_rows(tis), cfg(tis, universe=22000, i2=0))
    assert "S5_I2_COSIGNATURE" in checks_at(rep, "BLOCK")


def test_s5_low_i2_alone_is_not_a_defect(tis):
    """THE test this suite exists for.

    A clean table with I2 = 0 must stay CLEAN. Flagging low heterogeneity on its
    own would teach exactly the wrong lesson, and would do it while looking like
    the tool working correctly.
    """
    rep = tis.screen(clean_rows(tis), cfg(tis, universe=11000, i2=0))
    assert "S5_I2_COSIGNATURE" not in checks_at(rep, "BLOCK")
    assert rep.verdict == tis.CLEAN


def test_s5_high_i2_with_duplication_does_not_fire(tis):
    rep = tis.screen(duplicated_rows(tis), cfg(tis, universe=22000, i2=60))
    assert "S5_I2_COSIGNATURE" not in checks_at(rep, "BLOCK")


def test_s5_does_not_run_without_i2(tis):
    rep = tis.screen(duplicated_rows(tis), cfg(tis, universe=22000))
    assert not [f for f in rep.findings if f.check == "S5_I2_COSIGNATURE"]


# --------------------------------------------------------------------------
# Verdict algebra -- fail closed
# --------------------------------------------------------------------------

def test_block_never_yields_clean(tis):
    rep = tis.screen(duplicated_rows(tis), cfg(tis, universe=22000, i2=0))
    assert rep.verdict == tis.DEFECTS


def test_oversized_table_is_inconclusive_not_clean(tis):
    rows = [tis.Row(f"T{i}", 100 + i * 7, 100 + i * 5)
            for i in range(tis.MAX_ROWS_FOR_SUBSET_SUM + 5)]
    rep = tis.screen(rows, cfg(tis))
    assert rep.verdict == tis.INCONCLUSIVE
    assert rep.verdict != tis.CLEAN


def test_clean_table_is_clean(tis):
    rep = tis.screen(clean_rows(tis), cfg(tis, universe=11000, i2=41))
    assert rep.verdict == tis.CLEAN


def test_clean_verdict_still_prints_blind_spots(tis):
    """A CLEAN that does not say what it did not check is the failure mode this
    whole layer exists to prevent."""
    rep = tis.screen(clean_rows(tis), cfg(tis, universe=11000, i2=41))
    out = tis.render(rep)
    assert "blind spots" in out.lower()
    assert "comparator" in out


# --------------------------------------------------------------------------
# CLI + input handling
# --------------------------------------------------------------------------

def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT_PATH), *args],
                          capture_output=True, text=True)


def test_cli_exit_codes_match_verdicts():
    bad = run_cli(str(EXAMPLE_DIR / "finerenone_table1_example.csv"),
                  "--universe", "22000", "--i2", "0")
    assert bad.returncode == 1, bad.stdout
    assert "DEFECTS-FOUND" in bad.stdout

    good = run_cli(str(EXAMPLE_DIR / "clean_table_example.csv"),
                   "--universe", "11000", "--i2", "41")
    assert good.returncode == 0, good.stdout
    assert "CLEAN" in good.stdout


def test_cli_json_is_parseable():
    r = run_cli(str(EXAMPLE_DIR / "finerenone_table1_example.csv"),
                "--universe", "22000", "--i2", "0", "--json")
    payload = json.loads(r.stdout)
    assert payload["summary"]["verdict"] == "DEFECTS-FOUND"
    assert payload["summary"]["blocks"] >= 4


def test_shipped_examples_exist():
    assert (EXAMPLE_DIR / "finerenone_table1_example.csv").is_file()
    assert (EXAMPLE_DIR / "clean_table_example.csv").is_file()


def test_missing_file_is_inconclusive_not_clean(tmp_path):
    r = run_cli(str(tmp_path / "nope.csv"))
    assert r.returncode == 2
    assert "INCONCLUSIVE" in r.stderr


def test_unreadable_header_is_inconclusive(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("colour,shape\nred,round\n", encoding="utf-8")
    r = run_cli(str(p))
    assert r.returncode == 2
    assert "INCONCLUSIVE" in r.stderr


def test_thousands_separators_parse(tis, tmp_path):
    p = tmp_path / "commas.csv"
    p.write_text("study,n_treat,n_ctrl\nA,\"2,833\",\"2,841\"\nB,\"3,686\",\"3,666\"\n"
                 "C,\"6,519\",\"6,507\"\n", encoding="utf-8")
    rows = tis.load_csv(str(p))
    assert rows[0].arms() == (2833, 2841)
    rep = tis.screen(rows, cfg(tis))
    assert "S1_ARM_SUBSET_SUM" in checks_at(rep, "BLOCK")


def test_totals_only_table_uses_s2(tis, tmp_path):
    p = tmp_path / "totals.csv"
    p.write_text("study,n\nA,5674\nB,7352\nPooled,13026\n", encoding="utf-8")
    rows = tis.load_csv(str(p))
    rep = tis.screen(rows, cfg(tis))
    hits = [f for f in rep.findings if f.check == "S2_TOTAL_SUBSET_SUM"]
    assert hits and hits[0].severity == "WARN"


def test_s2_suppressed_when_s1_already_flagged(tis):
    """The reader must not be told the same thing twice under two names."""
    rep = tis.screen(duplicated_rows(tis), cfg(tis))
    s1 = {f.subject for f in rep.findings if f.check == "S1_ARM_SUBSET_SUM"}
    s2 = {f.subject for f in rep.findings if f.check == "S2_TOTAL_SUBSET_SUM"}
    assert not (s1 & s2)
