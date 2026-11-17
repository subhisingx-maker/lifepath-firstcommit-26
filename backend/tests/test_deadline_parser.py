import unittest

from app.services.deadline_parser import (INVALID, NEEDS_REVIEW, OK, find_dates,
                                          find_dates_in_pages, has_date)


def one(text):
    found = find_dates(text)
    assert len(found) == 1, found
    return found[0]


class DateFormatTests(unittest.TestCase):
    def test_indian_ordinal_format(self):
        d = one("Registration opens on 10th May 2027.")
        self.assertEqual((d.status, d.iso, d.raw), (OK, "2027-05-10", "10th May 2027"))

    def test_plain_and_abbreviated_month(self):
        self.assertEqual(one("by 5 June 2027").iso, "2027-06-05")
        self.assertEqual(one("by 5 Sept. 2027").iso, "2027-09-05")

    def test_month_first_with_comma(self):
        self.assertEqual(one("closes June 8, 2027").iso, "2027-06-08")

    def test_unambiguous_numeric_day_first(self):
        d = one("result on 22/06/2027")
        self.assertEqual((d.status, d.iso), (OK, "2027-06-22"))

    def test_ambiguous_numeric_is_flagged_not_trusted(self):
        d = one("fee by 07/06/2027")
        self.assertEqual(d.status, NEEDS_REVIEW)
        self.assertEqual(d.iso, "2027-06-07")
        self.assertIn("day-first", d.reason)

    def test_same_day_and_month_is_not_ambiguous(self):
        self.assertEqual(one("on 05/05/2027").status, OK)

    def test_two_digit_year_flagged(self):
        d = one("dated 02/06/27")
        self.assertEqual(d.status, NEEDS_REVIEW)
        self.assertIn("Two-digit year", d.reason)

    def test_month_first_numeric_flagged(self):
        d = one("on 03/15/2027")
        self.assertEqual((d.status, d.iso), (NEEDS_REVIEW, "2027-03-15"))

    def test_iso_format(self):
        self.assertEqual(one("on 2027-03-15").iso, "2027-03-15")


class SafetyTests(unittest.TestCase):
    def test_missing_year_is_never_invented(self):
        for text in ("closes on 9 June.", "by 31st July", "on June 8 at noon"):
            d = one(text)
            self.assertEqual(d.status, NEEDS_REVIEW, text)
            self.assertIsNone(d.date, text)

    def test_impossible_date_is_invalid(self):
        d = one("on 31/02/2027")
        self.assertEqual((d.status, d.iso), (INVALID, None))

    def test_month_and_year_only_is_not_a_deadline(self):
        self.assertEqual(find_dates("Admission 2027 session May 2027 intake"), [])

    def test_lowercase_may_is_not_a_month(self):
        self.assertEqual(find_dates("Candidates may 5 times apply"), [])

    def test_numbers_that_are_not_dates(self):
        self.assertEqual(find_dates("Score 60.5.25 and version 3.14.159"), [])

    def test_full_date_not_double_counted_as_missing_year(self):
        found = find_dates("from 10th May 2027 to 5 June 2027")
        self.assertEqual([d.iso for d in found], ["2027-05-10", "2027-06-05"])


class RegressionTests(unittest.TestCase):
    """The old prototype shared one global regex, so dateRe.test() skipped sentences."""

    SENTENCES = [
        "Registration closes on 5 June 2027.",
        "Fee payment closes on 7 June 2027.",
        "The rank list is published on 20 June 2027.",
        "Round 2 result is on 6 July 2027.",
    ]

    def test_every_sentence_with_a_date_is_found(self):
        self.assertEqual(len([s for s in self.SENTENCES if has_date(s)]), len(self.SENTENCES))

    def test_same_input_always_gives_same_output(self):
        text = " ".join(self.SENTENCES)
        first = [d.iso for d in find_dates(text)]
        for _ in range(5):
            self.assertEqual([d.iso for d in find_dates(text)], first)
        self.assertEqual(len(first), 4)

    def test_page_numbers_are_kept(self):
        found = find_dates_in_pages(["no dates here", "closes 5 June 2027", "", "result 6 July 2027"])
        self.assertEqual([(d.page, d.iso) for d in found], [(2, "2027-06-05"), (4, "2027-07-06")])


if __name__ == "__main__":
    unittest.main()
