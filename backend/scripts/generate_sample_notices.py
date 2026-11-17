"""Generate the FICTIONAL sample admission notices (and test fixtures).

Run from the backend folder:   python scripts/generate_sample_notices.py
Needs:  pip install -r requirements-dev.txt   (reportlab, pillow)

Every page carries a "FICTIONAL" footer. No real institution is described.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "sample_notices"
FIXTURES = ROOT / "backend" / "tests" / "fixtures"
NAVY = colors.HexColor("#17243A")

base = getSampleStyleSheet()
ST = {
    "title": ParagraphStyle("t", parent=base["Title"], fontName="Helvetica-Bold", fontSize=17,
                            textColor=NAVY, alignment=0, spaceAfter=4),
    "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=10.5, textColor=colors.HexColor("#56627A"),
                          spaceAfter=10),
    "h": ParagraphStyle("h", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12.5,
                        textColor=NAVY, spaceBefore=10, spaceAfter=4),
    "p": ParagraphStyle("p", parent=base["Normal"], fontSize=10, leading=14.5, spaceAfter=5),
    "b": ParagraphStyle("b", parent=base["Normal"], fontSize=10, leading=14.5, leftIndent=16,
                        bulletIndent=4, spaceAfter=3),
    "note": ParagraphStyle("n", parent=base["Normal"], fontSize=9.5, leading=13.5, backColor=colors.HexColor("#FFF4DC"),
                           borderColor=colors.HexColor("#D99B35"), borderWidth=0.6, borderPadding=5,
                           spaceBefore=4, spaceAfter=8),
}


def render(path: Path, banner: str, ref: str, pages: list[list[tuple]]) -> None:
    total = len(pages)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#56627A"))
        canvas.drawString(2 * cm, 1.2 * cm,
                          f"FICTIONAL SAMPLE - NOT AN OFFICIAL NOTIFICATION - {ref}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page} of {total}")
        canvas.setStrokeColor(NAVY)
        canvas.setLineWidth(1.2)
        canvas.line(2 * cm, A4[1] - 1.3 * cm, A4[0] - 2 * cm, A4[1] - 1.3 * cm)
        canvas.restoreState()

    story = []
    for i, items in enumerate(pages):
        for kind, *content in items:
            if kind == "table":
                rows = [[Paragraph(c, ST["p"]) for c in row] for row in content[0]]
                t = Table(rows, colWidths=[8.2 * cm, 8.8 * cm], repeatRows=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF0FF")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DFE3EF")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                story += [t, Spacer(1, 6)]
            elif kind == "b":
                story.append(Paragraph(content[0], ST["b"], bulletText="-"))
            else:
                story.append(Paragraph(content[0], ST[kind]))
        if i < total - 1:
            story.append(PageBreak())
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.9 * cm, bottomMargin=1.9 * cm, title=banner,
                            author="LIFEPATH fictional sample")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"wrote {path.relative_to(ROOT)} ({total} pages)")


FICT = ("note", "DEMO DATA - NOT AN OFFICIAL UNIVERSITY NOTIFICATION. This is a fictional document "
        "created for software testing.")

# ---------------------------------------------------------------- Notice 1
N1 = [
    [("title", "Admission Notification 2027-28"), ("sub", "Bachelor of Science (B.Sc.) - Demo National University"), FICT,
     ("p", "Demo National University. Admission Notification 2027-28 for Bachelor of Science."),
     ("p", "Notice No. DNU/ADM/2027/01. Programmes: B.Sc. Physics, B.Sc. Chemistry and B.Sc. Biology (all fictional)."),
     ("h", "1. Eligibility"),
     ("p", "Candidates must have passed Class 12 with Physics, Chemistry and Mathematics or Biology."),
     ("p", "Candidates must have a minimum of 50% aggregate marks (fictional rule)."),
     ("p", "Admission is based on merit in the Class 12 examination. There is no entrance test.")],
    [("h", "2. Documents required"),
     ("p", "Documents required. The documents listed below must be uploaded with the online form."),
     ("b", "Mandatory: Class 12 marksheet."),
     ("b", "Mandatory: Photo ID proof."),
     ("b", "Mandatory: Passport-size photograph in JPG format, maximum 100 KB."),
     ("b", "Conditional: Category certificate is required only if the candidate is claiming a reserved seat."),
     ("b", "Conditional: Migration certificate is required only if the Class 12 board is outside the home state."),
     ("b", "Optional: Extracurricular certificates may be uploaded for the profile section.")],
    [("h", "3. Registration and application"),
     ("p", "Registration: Register on the Demo Admissions Portal using an email address and mobile number "
           "between 1 February 2027 and 28 February 2027 (fictional dates)."),
     ("p", "Application form: After registration, fill in academic details, upload the required documents, "
           "pay the application fee and submit the form by 15 March 2027 (fictional date)."),
     ("p", "Forms that are not submitted by the last date will not be considered for the merit list.")],
    [("h", "4. Merit list and admission"),
     ("p", "Merit list: The merit list will be published on 1 April 2027 (fictional date)."),
     ("p", "Selected candidates must accept the seat within 5 days, pay the admission fee and bring original "
           "documents for verification."),
     ("p", "Candidates who are not selected may check the waitlist notice. This notice does not specify any other "
           "steps for candidates who are not selected."),
     ("note", "Everything in this document, including all dates and rules, is fictional.")],
]

# ---------------------------------------------------------------- Notice 2 (+ revision)
N2 = [
    [("title", "Admission Notification 2027-28"), ("sub", "B.Tech Programmes - Meridian State Technical University (MSTU)"), FICT,
     ("p", "Notice No. MSTU/ADM/2027/01 dated 28 April 2027. Academic year 2027-28."),
     ("h", "1. Programmes and seats"),
     ("b", "B.Tech Computer Science and Engineering: 120 seats."),
     ("b", "B.Tech Electronics and Communication Engineering: 90 seats."),
     ("b", "B.Tech Mechanical Engineering: 60 seats."),
     ("p", "85% of seats are reserved for candidates with state domicile. The remaining 15% are open to "
           "all-India candidates."),
     ("h", "2. Eligibility"),
     ("b", "The candidate must have passed Class 12 with Physics and Mathematics, and one of Chemistry, Computer "
           "Science, Biology or a Technical Vocational subject."),
     ("b", "The candidate must have at least 60% aggregate marks in Physics, Mathematics and the third subject. "
           "Candidates claiming a seat under a reserved category need at least 55%."),
     ("b", "The candidate must hold a valid Meridian Entrance Test (MET) 2027 rank. Candidates without a valid MET "
           "2027 rank are not eligible."),
     ("b", "The candidate must not be older than 24 years as on 1 October 2027.")],
    [("h", "3. Documents required"),
     ("p", "Scanned copies must be uploaded during registration. Originals are checked at reporting."),
     ("p", "<b>Mandatory documents</b>"),
     ("b", "Mandatory: MET 2027 scorecard."),
     ("b", "Mandatory: Class 10 certificate as proof of date of birth."),
     ("b", "Mandatory: Class 12 marksheet."),
     ("b", "Mandatory: Government-issued photo ID."),
     ("p", "<b>Conditional documents</b>"),
     ("b", "Category certificate in the format given in Annexure B is required only if the candidate is claiming a "
           "reserved category seat or the reduced fee."),
     ("b", "Domicile certificate is required only if the candidate is claiming a seat under the state domicile quota."),
     ("b", "Migration certificate is required only if the Class 12 board is outside Meridian State."),
     ("b", "Income certificate is required only for candidates applying for the Fee Waiver Scheme."),
     ("p", "<b>Optional and other documents</b>"),
     ("b", "Optional: Sports achievement certificate, for the 2% sports weightage."),
     ("b", "Medical fitness certificate: the format and the requirement will be notified separately before reporting."),
     ("p", "<b>File formats.</b> Photograph: JPG, 20 KB to 50 KB. Signature: JPG, 10 KB to 30 KB. Every other "
           "document: PDF, maximum 200 KB.")],
    [("h", "4. Registration, fee and key dates"),
     ("p", "Register on the MSTU admissions portal with an email address and mobile number, fill in the form, upload "
           "the documents and pay the application fee. The application fee is Rs. 1,200. Candidates claiming a reserved "
           "category seat pay Rs. 600."),
     ("table", [["Activity", "Date"],
                ["Online registration opens", "10th May 2027"],
                ["Last date of registration", "5th June 2027"],
                ["Last date of fee payment", "07/06/2027"],
                ["Correction window", "8 June 2027 to 9 June 2027"],
                ["Provisional rank list", "20 June 2027"],
                ["Round 1 choice filling", "22/06/2027 to 24/06/2027"],
                ["Round 1 allotment result", "25 June 2027"],
                ["Round 1 reporting and seat acceptance", "26 June 2027 to 29 June 2027"]]),
     ("p", "Application forms received after 5th June 2027 will not be accepted. The helpdesk closes on 9 June."),
     ("note", "Dates for Round 2 and Round 3 are given on the next pages.")],
    [("h", "5. Rank list and counselling rounds"),
     ("p", "Seats are allotted in order of MET 2027 rank. The provisional rank list will be published on "
           "20 June 2027. Candidates can raise objections within 2 days of publication."),
     ("p", "Counselling has three rounds. Candidates must register and fill in their choices of college and branch "
           "in each round in which they wish to be considered."),
     ("b", "Round 1: choice filling from 22/06/2027 to 24/06/2027; result on 25 June 2027."),
     ("b", "Round 2: choice filling from 3 July 2027 to 5 July 2027; result on 6 July 2027."),
     ("b", "Round 3 (spot round): held on 14 July 2027 for vacant seats only. Spot round candidates must attend in "
           "person with original documents.")],
    [("h", "6. After the seat is allotted"),
     ("p", "A candidate who is allotted a seat must choose one of three options on the portal."),
     ("b", "Freeze: accept the seat and leave the counselling process."),
     ("b", "Float: accept the seat and stay in the next round for a better option."),
     ("b", "Slide: accept the seat and stay in the next round for a better branch in the same college only."),
     ("p", "A candidate who accepts a seat must pay a seat acceptance fee of Rs. 25,000 within 4 days of the "
           "allotment result and report to the allotted college with original documents for verification. "
           "Candidates who do not report in the reporting window lose the allotted seat and cannot take part in "
           "later rounds."),
     ("p", "<b>Waitlisted candidates.</b> Candidates on the waitlist are considered in Round 2 and Round 3 only if "
           "seats fall vacant. Waitlisted candidates do not need to apply again."),
     ("p", "<b>Candidates who are not allotted a seat.</b> Candidates who are not allotted a seat in Round 1 are "
           "considered automatically in Round 2 if they have not withdrawn. This notice does not specify a separate "
           "appeal process for candidates who are not allotted any seat after Round 3."),
     ("p", "<b>Withdrawal and refund.</b> Candidates who withdraw before 10 July 2027 receive a refund of the seat "
           "acceptance fee less Rs. 1,000 as processing charge.")],
    [("h", "7. General instructions and warnings"),
     ("p", "Providing false information or forged documents will lead to cancellation of candidature and admission."),
     ("p", "The university may revise this notification. Candidates must check the university website regularly for "
           "revisions. Where a revision is issued, candidates should read it together with this notice."),
     ("p", "Annexure B (category certificate format) was updated on 3 May 2027."),
     ("p", "Queries: helpdesk@mstu.example (fictional address). The helpdesk is available on working days from "
           "10:00 to 17:00."),
     ("note", "This document is fictional. Do not use it to make real admission decisions.")],
]

N2_REV = [
    [("title", "Revised Admission Notification - Corrigendum No. 1"),
     ("sub", "Meridian State Technical University (MSTU) - B.Tech 2027-28"), FICT,
     ("p", "Reference: MSTU/ADM/2027/01-R1 dated 02/06/27. This corrigendum amends Notice No. MSTU/ADM/2027/01 "
           "dated 28 April 2027."),
     ("h", "Amendments"),
     ("b", "The last date of registration is extended to 12th June 2027."),
     ("b", "The last date of fee payment is extended to 14 June 2027."),
     ("b", "The provisional rank list will now be published on 24 June 2027."),
     ("b", "Income certificate is no longer required for the Fee Waiver Scheme. Applicants must upload a signed "
           "self-declaration instead."),
     ("b", "The dates of the counselling rounds will be announced separately on the university website."),
     ("p", "All other terms and conditions of the notification dated 28 April 2027 remain unchanged."),
     ("note", "This document is fictional. It deliberately conflicts with the original notice so that conflict "
              "detection can be tested.")],
]

# ---------------------------------------------------------------- Notice 3
N3 = [
    [("title", "Undergraduate Admissions 2027-28"), ("sub", "B.A. and B.Com. (Honours) - Riverbend Central College"), FICT,
     ("p", "Notice No. RCC/UG/2027/05. Admission is on the basis of Class 12 merit through cut-off lists. "
           "There is no entrance test."),
     ("h", "1. Eligibility"),
     ("b", "The candidate must have passed Class 12 from a recognised board."),
     ("b", "B.A. (Honours): at least 45% aggregate marks in the best four subjects. Any stream is eligible."),
     ("b", "B.Com. (Honours): at least 50% aggregate marks in the best four subjects, including Accountancy or "
           "Mathematics."),
     ("b", "Merit is calculated on the best four subjects, including one language. Bonus marks of up to 2% are "
           "given for NCC or NSS certificates."),
     ("p", "A candidate who has a gap of more than one year after Class 12 is eligible but must submit a gap "
           "declaration at admission.")],
    [("h", "2. Documents"),
     ("p", "Upload the following with the online form."),
     ("b", "Mandatory: Class 12 marksheet."),
     ("b", "Mandatory: Photo ID proof."),
     ("b", "Mandatory: Recent photograph and signature, JPG, maximum 60 KB each."),
     ("b", "Conditional: Category certificate if the candidate is claiming a reserved seat."),
     ("b", "Conditional: EWS certificate, required only if the candidate is claiming the EWS seat."),
     ("b", "Conditional: Sports certificate, required only if the candidate is claiming the sports quota."),
     ("b", "Conditional: Gap declaration, required only if there is a gap of more than one year after Class 12."),
     ("b", "Optional: NCC or NSS certificate for bonus marks."),
     ("p", "The Transfer Certificate and Character Certificate are not needed with the form. They must be shown "
           "in original only by candidates who are selected, at document verification.")],
    [("h", "3. Application dates"),
     ("p", "The online application opens on 15 June 2027 and closes on 10 July 2027. The application fee must be "
           "paid by 11 July 2027."),
     ("p", "Cut-off List 1 will be published on 20 July 2027. Cut-off List 2 will be published on 30 July 2027. "
           "Cut-off List 3 will be published on 8 August 2027."),
     ("p", "Last date to submit corrections to the application is 31st July."),
     ("p", "The spot round for vacant seats will be held in the second week of August. The exact date will be "
           "announced on the college website."),
     ("note", "Applications must be completed by the closing date. Late applications will not be accepted.")],
    [("h", "4. After a cut-off list is published"),
     ("p", "<b>Selected.</b> A candidate whose name is on a cut-off list must accept the seat online and pay the "
           "admission fee of Rs. 12,500 within 3 working days of the list. Then attend physical document "
           "verification at the college. A seat that is not confirmed in time is released."),
     ("p", "<b>Upgrade.</b> A candidate admitted in an earlier list may upgrade to a preferred course in a later "
           "list by paying any difference in fee."),
     ("p", "<b>Not selected in a list.</b> A candidate who is not selected in a list is considered automatically "
           "in the next list if eligible. Re-application is not needed."),
     ("p", "<b>Waitlist.</b> A waitlist of 50 candidates per programme will be published with Cut-off List 3. "
           "Waitlisted candidates are offered seats in order if seats become vacant before 20 August 2027. "
           "Candidates are informed by email and must reply within 48 hours or the offer lapses."),
     ("p", "<b>No seat after the last list.</b> This notice does not describe any further steps for candidates "
           "who are not selected after Cut-off List 3 and the waitlist, other than the spot round.")],
    [("h", "5. Fees, refunds and general instructions"),
     ("p", "Fees are paid online only. Payment made in cash at the college will not be accepted."),
     ("p", "A candidate who withdraws before 5 August 2027 receives a refund of the admission fee less Rs. 500. "
           "No refund is made after that date."),
     ("p", "Giving false information will lead to cancellation of admission."),
     ("p", "Queries: admissions@riverbend.example (fictional address)."),
     ("note", "This document is fictional. Do not use it to make real admission decisions.")],
]


def scanned_fixture(path: Path, lines: list[str]) -> None:
    """An image-only PDF (no text layer) to test scanned-document detection."""
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    img = Image.new("L", (827, 1169), 255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:
        font = ImageFont.load_default()
    y = 80
    for line in lines:
        draw.text((60, y), line, fill=0, font=font)
        y += 34
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawImage(ImageReader(img), 0, 0, width=A4[0], height=A4[1])
    c.showPage()
    c.save()
    print(f"wrote {path.relative_to(ROOT)} (image-only)")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    render(OUT / "01_demo_national_university_bsc_2027-28.pdf", "Demo National University B.Sc. 2027-28",
           "Demo National University", N1)
    render(OUT / "02_meridian_state_technical_university_btech_2027-28.pdf", "MSTU B.Tech 2027-28",
           "Meridian State Technical University", N2)
    render(OUT / "02b_meridian_state_technical_university_corrigendum_1.pdf", "MSTU Corrigendum 1",
           "MSTU Corrigendum 1", N2_REV)
    render(OUT / "03_riverbend_central_college_ba_bcom_2027-28.pdf", "Riverbend Central College UG 2027-28",
           "Riverbend Central College", N3)
    scanned_fixture(FIXTURES / "scanned_notice.pdf", [
        "FICTIONAL SCANNED NOTICE (image only, no text layer)",
        "Sample College - Admission 2027-28",
        "Last date to apply: 10 July 2027",
        "This page is a picture. Text extraction should find nothing."])
    (FIXTURES / "corrupted.pdf").write_bytes(b"%PDF-1.7\n" + bytes(range(256)) * 20)
    print("wrote backend/tests/fixtures/corrupted.pdf (invalid bytes)")


if __name__ == "__main__":
    main()
