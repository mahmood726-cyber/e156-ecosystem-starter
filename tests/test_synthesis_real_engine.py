"""Real pinned-engine integration: source-publication table, NOT original-trial audit.

Run with SYNTHESIS_PINNED_ENGINE_FILE pointing to the reviewed upstream
meta-starter-kit/metakit/engine.py checked out at commit 464fd88... .
Without this environment variable, broad local pytest skips the integration.
No network, author contact, model substitution, or research accuracy claim.
"""
from __future__ import annotations

import hashlib
import importlib.util
import math
import os
import tempfile
from pathlib import Path
import unittest

TEST_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "_synthesis_pairwise_integrated", TEST_ROOT / "scripts" / "synthesis_paired_model_replay.py"
)
paired = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(paired)

# Public DOI 10.3389/fmed.2026.1985280, Frontiers in Medicine 5 Nov 2026.
# Three randomized trials, Figure 2 counts as printed in the *review*:
# these have NOT been independently re-extracted from original trial reports.
PAPER_FIGURE_COUNTS = (
    ("Li 2014", 3, 30, 1, 30),
    ("Vasavada 2018", 4, 29, 4, 25),
    ("Freedman 2021", 12, 57, 13, 57),
)
PAPER_PRIMARY_HK = {"pooled_or": "1.01", "ci_low": "0.31", "ci_high": "3.24"}
PAPER_MODIFIED_HK = {"pooled_or": "1.01", "ci_low": "0.20", "ci_high": "4.95"}
SOURCE_URL = "https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2026.1985280/full"


class PinnedEngineIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        filename = os.environ.get("SYNTHESIS_PINNED_ENGINE_FILE")
        if not filename:
            raise unittest.SkipTest("real trusted engine path not supplied; no numerical-engine claim")
        engine_path = Path(filename)
        if not engine_path.is_file():
            raise AssertionError("explicit pinned engine checkout missing")
        digest = hashlib.sha256(engine_path.read_bytes()).hexdigest()
        cls.engine = paired._engine_at(engine_path, digest)
        cls.digest = digest

    def _run_published_table(self):
        effect_rows = []
        for name, a, n1, c, n0 in PAPER_FIGURE_COUNTS:
            effect = self.engine.binary_effect(name, a, n1, c, n0)
            self.assertIsNotNone(effect)
            effect_rows.append(effect)
        pool = self.engine.pool_effects(effect_rows, "OR")
        self.assertIsNotNone(pool)
        self.assertEqual(pool.k, 3)
        return pool

    def test_real_engine_reproduces_published_modified_hk_sensitivity(self):
        pool = self._run_published_table()
        self.assertAlmostEqual(pool.tau2, 0, places=12)
        self.assertTrue(pool.hksj_floor_applied)
        for key, printed in PAPER_MODIFIED_HK.items():
            field = "pooled" if key == "pooled_or" else key
            with self.subTest(field=field):
                self.assertTrue(
                    paired._precision_overlap(printed, getattr(pool, field)),
                    f"real pinned engine {field} not compatible with paper's printed modified-HK value",
                )

    def test_real_engine_must_not_be_mislabeled_as_primary_unmodified_hk(self):
        pool = self._run_published_table()
        self.assertTrue(paired._precision_overlap(PAPER_PRIMARY_HK["pooled_or"], pool.pooled))
        self.assertFalse(paired._precision_overlap(PAPER_PRIMARY_HK["ci_low"], pool.ci_low))
        self.assertFalse(paired._precision_overlap(PAPER_PRIMARY_HK["ci_high"], pool.ci_high))

    def test_independent_fixed_weight_closed_form_reproduces_real_engine_when_tau_zero(self):
        # Independent closed-form calculation for this low-heterogeneity
        # special case. Does NOT prove full PM optimization in general.
        estimates = []
        variances = []
        for _, a, n1, c, n0 in PAPER_FIGURE_COUNTS:
            b, d = n1 - a, n0 - c
            estimates.append(math.log(a * d / (b * c)))
            variances.append(1 / a + 1 / b + 1 / c + 1 / d)
        weights = [1 / v for v in variances]
        mu = sum(w * y for w, y in zip(weights, estimates)) / sum(weights)
        q = sum(w * (y - mu) ** 2 for w, y in zip(weights, estimates))
        self.assertLessEqual(q, 2)  # PM tau²=0 for three trials.
        se_floor = math.sqrt(1 / sum(weights))
        # Student t .975 quantile for 2 df, reference from standard t table.
        tcrit = 4.302652729749462
        expected = {
            "pooled": math.exp(mu),
            "ci_low": math.exp(mu - tcrit * se_floor),
            "ci_high": math.exp(mu + tcrit * se_floor),
        }
        pool = self._run_published_table()
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertAlmostEqual(getattr(pool, key), value, delta=2e-5)
        # Unmodified HK uses the residual q/(k-1), legitimately narrower.
        se_unmodified = math.sqrt((q / 2) / sum(weights))
        self.assertTrue(paired._precision_overlap(
            PAPER_PRIMARY_HK["ci_low"], math.exp(mu - tcrit * se_unmodified)
        ))
        self.assertTrue(paired._precision_overlap(
            PAPER_PRIMARY_HK["ci_high"], math.exp(mu + tcrit * se_unmodified)
        ))

    def _synthetic_paired_packet(self, root):
        """Invented evidence text; never a real published correction record."""
        def capture(filename, quote):
            path = root / filename
            path.write_text(quote, encoding="utf-8")
            return {"path": filename, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "version": "INVENTED-FIXTURE-ONLY", "locator": "fabricated demo row",
                    "quote": quote}

        def token(text, label, value):
            string = str(value)
            return {"text": string, "offset": text.index(label + "=" + string) + len(label) + 1}

        analysis = {
            "population": "invented infants", "endpoint": "synthetic glaucoma outcome",
            "time_window": "invented standardized day",
            "analysis_set": "invented ITT",
            "intervention": "invented IOL", "comparator": "invented aphakia",
            "effect_measure": "OR", "estimand": "UNADJUSTED_TWO_ARM_LOG_OR",
        }
        rows = []
        for i, (_, a, n1, c, n0) in enumerate(PAPER_FIGURE_COUNTS, start=1):
            key = f"INVENTED-TRIAL-{i}"
            original = {"tE": a, "tN": n1, "cE": c, "cN": n0}
            corrected = {**original, "tE": a + 1 if i == 1 else a}
            def make_quote(hint, counts):
                return (f"{key} invented {hint} tE={counts['tE']} tN={counts['tN']} "
                        f"cE={counts['cE']} cN={counts['cN']} people")
            before = make_quote("published", original)
            after = make_quote("primary", corrected)
            rows.append({
                "trial_key": key, "trial_family_id": f"INVENTED-FAMILY-{i}",
                "trial_identity_source_checked": True, "source_tier": "T1",
                "independent_trial_source_verified": True, "analysis": dict(analysis),
                "published_extraction": capture(f"old-{i}.txt", before),
                "primary_trial": capture(f"source-{i}.txt", after),
                "trial_key_binding": {"text": key, "offset": after.index(key)},
                "original": original, "corrected": corrected,
                "original_bindings": {k: token(before, k, v) for k, v in original.items()},
                "corrected_bindings": {k: token(after, k, v) for k, v in corrected.items()},
                "correction_source_checked": True,
                "correction_rationale": "invented count adjustment for software test",
            })
        methods = ("Invented published methods: Paule-Mandel modified Hartung-Knapp "
                   "variance floor. Original OR 1.005 (95% CI 0.204 to 4.948) in invented set")
        return {
            "schema_version": "0.1", "claim_version_status": "CURRENT_UNCORRECTED",
            "analysis": analysis,
            "publication": {
                "snapshot": capture("invented-publication.txt", methods),
                "model": paired.METHOD, "published_method_source_checked": True,
                "method_quote": "Paule-Mandel modified Hartung-Knapp",
                "published_variance_floor_source_verified": True,
                "variance_floor_quote": "modified Hartung-Knapp variance floor",
                "trial_set_complete_source_checked": True,
                "pooled_or_text": "1.005",
                "pooled_or_binding": token(methods, "OR", "1.005"),
                "ci_low_text": "0.204",
                "ci_low_binding": {"text": "0.204", "offset": methods.index("0.204")},
                "ci_high_text": "4.948",
                "ci_high_binding": {"text": "4.948", "offset": methods.index("4.948")},
            },
            "trials": rows,
        }

    def test_real_engine_full_synthetic_original_then_corrected_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            packet = self._synthetic_paired_packet(root)
            result = paired.check_replay(packet, root,
                engine_path=Path(os.environ["SYNTHESIS_PINNED_ENGINE_FILE"]),
                engine_sha256=self.digest)
        self.assertEqual(result["status"], "PAIRED_MODEL_REPLAYED_FOR_REVIEW", result)
        self.assertEqual(result["model_fit"], "ACTUALLY_EXECUTED")
        self.assertEqual(result["changed_trials"], 1)
        self.assertNotEqual(result["corrected_replay"]["pooled"],
                            result["published_replay"]["pooled"])
        self.assertFalse(result["scientific_error_confirmed"])
        self.assertEqual(result["conclusion_impact"], "NOT_ASSESSED")

    def test_real_engine_original_ci_mismatch_blocks_corrected_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            packet = self._synthetic_paired_packet(root)
            pub = packet["publication"]
            changed_text = pub["snapshot"]["quote"].replace("4.948", "4.949")
            file = root / pub["snapshot"]["path"]
            file.write_text(changed_text, encoding="utf-8")
            pub["snapshot"]["sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
            pub["snapshot"]["quote"] = changed_text
            pub["ci_high_text"] = "4.949"
            pub["ci_high_binding"]["text"] = "4.949"
            result = paired.check_replay(packet, root,
                engine_path=Path(os.environ["SYNTHESIS_PINNED_ENGINE_FILE"]),
                engine_sha256=self.digest)
        self.assertEqual(result["status"], "PUBLISHED_REPLAY_MISMATCH", result)
        self.assertEqual(result["corrected_replay"], "NOT_RUN")
        self.assertFalse(result["scientific_error_confirmed"])

    def test_real_engine_source_pin_is_not_a_user_supplied_sha_only(self):
        # _engine_at checks source Git blob as well as caller SHA.
        self.assertEqual(paired.SUPPORTED_ENGINE_GIT_BLOB_SHA1,
                         "9b25f4a98bb882c2d09c18288f93028de5bcf83b")
        self.assertEqual(len(self.digest), 64)


if __name__ == "__main__":
    unittest.main()
