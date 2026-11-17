import unittest

from app.services.pdf_extractor import (ExtractionError, PageText, analyse_pages, safe_filename,
                                        validate_upload)

LIMIT = 1024 * 1024
TEXT = "This page has plenty of readable text for the test."


def codes(fn, *a):
    try:
        fn(*a)
    except ExtractionError as e:
        return e.code
    return None


class ValidateUploadTests(unittest.TestCase):
    def test_good_pdf_passes(self):
        self.assertIsNone(codes(validate_upload, "a.pdf", b"%PDF-1.7 data", LIMIT))

    def test_empty(self):
        self.assertEqual(codes(validate_upload, "a.pdf", b"", LIMIT), "empty_file")

    def test_wrong_extension(self):
        self.assertEqual(codes(validate_upload, "a.png", b"%PDF-1.7", LIMIT), "unsupported_type")
        self.assertEqual(codes(validate_upload, "a.exe", b"MZ", LIMIT), "unsupported_type")

    def test_oversized(self):
        self.assertEqual(codes(validate_upload, "a.pdf", b"%PDF-" + b"0" * LIMIT, LIMIT), "too_large")

    def test_text_file_renamed_to_pdf(self):
        self.assertEqual(codes(validate_upload, "a.pdf", b"hello world", LIMIT), "not_a_pdf")

    def test_safe_filename(self):
        self.assertEqual(safe_filename(r"C:\Users\me\notice.pdf"), "notice.pdf")
        self.assertEqual(safe_filename("../../etc/passwd.pdf"), "passwd.pdf")
        self.assertEqual(safe_filename("a\x00b\n.pdf"), "ab.pdf")
        self.assertEqual(safe_filename(None), "document.pdf")
        self.assertLessEqual(len(safe_filename("x" * 500 + ".pdf")), 120)


class AnalysePagesTests(unittest.TestCase):
    def test_all_readable_is_ok(self):
        a = analyse_pages([PageText(1, TEXT), PageText(2, TEXT)])
        self.assertEqual((a.status, a.warnings), ("ok", []))

    def test_image_only_document_needs_ocr(self):
        a = analyse_pages([PageText(1, "", image_count=1)])
        self.assertEqual((a.status, a.scanned_pages), ("needs_ocr", [1]))
        self.assertIn("OCR is not implemented", a.warnings[0])

    def test_mostly_scanned_needs_ocr_even_with_one_text_page(self):
        a = analyse_pages([PageText(1, TEXT), PageText(2, "", 1), PageText(3, "", 1)])
        self.assertEqual(a.status, "needs_ocr")

    def test_one_scanned_page_in_four_is_partial_and_reported(self):
        a = analyse_pages([PageText(i, TEXT) for i in (1, 2, 4)] + [PageText(3, "", 2)])
        self.assertEqual((a.status, a.scanned_pages), ("partial", [3]))

    def test_failed_page_is_reported_never_hidden(self):
        a = analyse_pages([PageText(1, TEXT), PageText(2, "", 0, error="RuntimeError: boom")])
        self.assertEqual((a.status, a.failed_pages), ("partial", [2]))
        self.assertIn("2", a.warnings[0])

    def test_blank_document_is_no_text(self):
        a = analyse_pages([PageText(1, ""), PageText(2, "  ")])
        self.assertEqual(a.status, "no_text")

    def test_blank_page_among_text_pages_is_partial(self):
        a = analyse_pages([PageText(1, TEXT), PageText(2, "")])
        self.assertEqual((a.status, a.blank_pages), ("partial", [2]))


if __name__ == "__main__":
    unittest.main()
