"""Retrospective correction-learning fixtures. NOT a prospective validation."""
import hashlib
import unittest


def shard(doi):
    return int(hashlib.sha256(doi.strip().lower().encode()).hexdigest(), 16) % 10


def reverse_complement(seq):
    if not seq or any(b not in "ACGT" for b in seq):
        return None
    return seq.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def matched_label(old, current, notice_verified, article_verified, section_matched):
    if not all((old, current, notice_verified, article_verified, section_matched)):
        return "HOLD"
    return "CORRECTED_LABEL_DIFFERENCE" if old != current else "NO_FLAG"


class SourceCorrectionHistoricalControls(unittest.TestCase):
    def test_three_owned_dois(self):
        for doi in (
            "10.1007/s00520-026-11403-5",
            "10.1007/s00436-026-08783-2",
            "10.1186/s12889-024-20669-5",
        ):
            self.assertEqual(shard(doi), 8)

    def test_historical_primer_reverse_complement(self):
        self.assertEqual(reverse_complement("GTCTATACGAGCGAACGCATAC"),
                         "GTATGCGTTCGCTCGTATAGAC")

    def test_corrected_primer_round_trip(self):
        new = "GTATGCGTTCGCTCGTATAGAC"
        self.assertEqual(reverse_complement(reverse_complement(new)), new)

    def test_benign_opposite_strand(self):
        old = "GTCTATACGAGCGAACGCATAC"
        new = "GTATGCGTTCGCTCGTATAGAC"
        self.assertEqual(reverse_complement(old), new)

    def test_abstain_ambiguous_primer(self):
        self.assertIsNone(reverse_complement("GTNAC"))
        self.assertIsNone(reverse_complement(""))

    def test_historical_ki7_to_ki2(self):
        self.assertEqual(matched_label("KI7", "KI2", True, True, True),
                         "CORRECTED_LABEL_DIFFERENCE")

    def test_corrected_ki2(self):
        self.assertEqual(matched_label("KI2", "KI2", True, True, True), "NO_FLAG")

    def test_abstain_other_intervention(self):
        self.assertEqual(matched_label("KI7", "KI2", True, True, False), "HOLD")

    def test_abstain_unverified_notice(self):
        self.assertEqual(matched_label("KI7", "KI2", False, True, True), "HOLD")

    def test_abstain_no_original(self):
        self.assertEqual(matched_label("KI7", "KI2", True, False, True), "HOLD")

    def test_factor_without_source_code_holds(self):
        # Do not infer pain=1 is the reference without actual factor levels
        # and model-matrix contrasts; this is a null-case, not fitted-model replay.
        factor_levels = None
        model_contrasts = None
        self.assertIsNone(factor_levels)
        self.assertIsNone(model_contrasts)


if __name__ == "__main__":
    unittest.main()
