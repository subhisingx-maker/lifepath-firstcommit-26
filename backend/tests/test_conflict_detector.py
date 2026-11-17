import unittest

from app.services.conflict_detector import ConflictItem, detect_conflicts


def deadline(i, doc, key, iso, page=1):
    return ConflictItem(i, doc, f"{doc}.pdf", "deadline", key, page, "q", event_key=key, date_iso=iso)


def document(i, doc, name, level, page=2):
    return ConflictItem(i, doc, f"{doc}.pdf", "document", name, page, "q", level=level)


class DeadlineConflicts(unittest.TestCase):
    def test_different_dates_for_same_event_conflict_and_show_both_sources(self):
        found = detect_conflicts([deadline("a", "notice", "registration_close", "2027-06-05", 3),
                                  deadline("b", "corrigendum", "registration_close", "2027-06-12", 1)])
        self.assertEqual(len(found), 1)
        c = found[0]
        self.assertEqual((c.key, c.kind), ("deadline:registration_close", "deadline"))
        self.assertEqual({(s.document_name, s.page, s.value) for s in c.sides},
                         {("notice.pdf", 3, "2027-06-05"), ("corrigendum.pdf", 1, "2027-06-12")})

    def test_same_date_is_not_a_conflict(self):
        self.assertEqual(detect_conflicts([deadline("a", "n", "registration_close", "2027-06-05"),
                                           deadline("b", "n", "registration_close", "2027-06-05", 3)]), [])

    def test_different_events_do_not_conflict(self):
        self.assertEqual(detect_conflicts([deadline("a", "n", "registration_close", "2027-06-05"),
                                           deadline("b", "n", "fee_payment_close", "2027-06-07")]), [])

    def test_items_without_a_date_or_key_are_ignored(self):
        self.assertEqual(detect_conflicts([deadline("a", "n", "x", None), deadline("b", "n", "x", "2027-01-01")]), [])


class DocumentConflicts(unittest.TestCase):
    def test_mandatory_vs_not_required_conflicts(self):
        found = detect_conflicts([document("a", "n", "Income certificate for Fee Waiver Scheme", "conditional"),
                                  document("b", "r", "Income certificate", "not_required", 1)])
        self.assertEqual(len(found), 1)
        self.assertEqual({s.value for s in found[0].sides}, {"conditional", "not_required"})

    def test_same_level_is_fine(self):
        self.assertEqual(detect_conflicts([document("a", "n", "Class 12 marksheet", "mandatory"),
                                           document("b", "m", "Class 12 marksheet", "mandatory")]), [])

    def test_different_documents_do_not_conflict(self):
        self.assertEqual(detect_conflicts([document("a", "n", "Category certificate", "conditional"),
                                           document("b", "n", "Domicile certificate", "mandatory")]), [])

    def test_not_specified_never_conflicts(self):
        self.assertEqual(detect_conflicts([document("a", "n", "Medical fitness certificate", "not_specified"),
                                           document("b", "m", "Medical fitness certificate", "mandatory")]), [])

    def test_single_word_names_are_not_merged(self):
        self.assertEqual(detect_conflicts([document("a", "n", "Certificate", "mandatory"),
                                           document("b", "n", "Category certificate", "optional")]), [])


if __name__ == "__main__":
    unittest.main()
