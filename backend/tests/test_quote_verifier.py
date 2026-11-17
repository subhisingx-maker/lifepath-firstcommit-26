import unittest

from app.services.quote_verifier import NEEDS_REVIEW, UNVERIFIED, VERIFIED, PageIndex, verify_quote

PAGES = [
    "Eligibility:\nCandidates must have passed Class 12 with Physics,\nChemistry and Mathematics or Biology.",
    "Documents required.\nMandatory: Class 12 marksheet.\nConditional: Category certificate is required only if the "
    "candidate is claiming a reserved seat.",
    "Registration closes on 5th June 2027.\nThe application fee is Rs. 1,200 \u2013 pay online.",
]
IDX = PageIndex(PAGES)


class VerifyQuoteTests(unittest.TestCase):
    def test_exact_quote_on_claimed_page_is_verified(self):
        r = verify_quote("Mandatory: Class 12 marksheet.", 2, IDX)
        self.assertEqual((r.status, r.page, r.reason), (VERIFIED, 2, None))

    def test_line_breaks_case_and_spacing_do_not_matter(self):
        r = verify_quote("candidates MUST have passed class 12 with physics, chemistry and mathematics", 1, IDX)
        self.assertEqual(r.status, VERIFIED)

    def test_curly_quotes_and_dashes_are_normalised(self):
        r = verify_quote("The application fee is Rs. 1,200 - pay online.", 3, IDX)
        self.assertEqual(r.status, VERIFIED)

    def test_wrong_page_is_corrected_deterministically(self):
        r = verify_quote("Registration closes on 5th June 2027.", 1, IDX)
        self.assertEqual((r.status, r.page), (VERIFIED, 3))
        self.assertIn("corrected from 1 to 3", r.reason)

    def test_invalid_page_number_is_handled(self):
        r = verify_quote("Registration closes on 5th June 2027.", 99, IDX)
        self.assertEqual((r.status, r.page), (VERIFIED, 3))

    def test_quote_on_several_pages_needs_review(self):
        idx = PageIndex(["Fees are paid online only.", "Fees are paid online only.", "other text here"])
        r = verify_quote("Fees are paid online only.", 3, idx)
        self.assertEqual(r.status, NEEDS_REVIEW)

    def test_invented_quote_is_unverified(self):
        r = verify_quote("Registration closes on 12th June 2027 for all candidates.", 3, IDX)
        self.assertEqual(r.status, UNVERIFIED)

    def test_paraphrase_is_never_verified(self):
        r = verify_quote("You need your marksheet from class twelve.", 2, IDX)
        self.assertNotEqual(r.status, VERIFIED)

    def test_near_match_needs_review_not_verified(self):
        r = verify_quote("Registration closes on 5th June 2026.", 3, IDX)  # wrong year
        self.assertEqual(r.status, NEEDS_REVIEW)
        self.assertIn("differs", r.reason)

    def test_too_short_quote_cannot_be_verified(self):
        for q in ("Class 12", "ok", ""):
            self.assertEqual(verify_quote(q, 2, IDX).status, NEEDS_REVIEW, q)

    def test_ellipsis_quote_is_not_exact(self):
        r = verify_quote("Candidates must have passed Class 12 ... Chemistry and Mathematics or Biology.", 1, IDX)
        self.assertEqual(r.status, NEEDS_REVIEW)

    def test_ellipsis_with_missing_part_is_unverified(self):
        r = verify_quote("Candidates must have passed Class 12 ... and Economics or Law.", 1, IDX)
        self.assertEqual(r.status, UNVERIFIED)


if __name__ == "__main__":
    unittest.main()
