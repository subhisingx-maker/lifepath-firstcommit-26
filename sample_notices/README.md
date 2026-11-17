# Fictional sample admission notices

Every page of every file says FICTIONAL. No real institution is described. Regenerate them with
`python backend/scripts/generate_sample_notices.py`.

| File | Pages | Scenario | What it is good for testing |
|---|---|---|---|
| `01_demo_national_university_bsc_2027-28.pdf` | 4 | Simple merit-based B.Sc. | The bundled demo journey. Eligibility, mandatory / conditional / optional documents, registration and form deadlines, merit list, selected vs. not-selected, and an explicit "not specified" gap. |
| `02_meridian_state_technical_university_btech_2027-28.pdf` | 6 | Entrance-rank B.Tech with 3 counselling rounds | Rank-based eligibility, age limit, domicile quota, four conditional documents, a "will be notified later" document, a table of dates, mixed date formats (`5th June 2027`, `07/06/2027`, `22/06/2027`, `9 June` with no year), Freeze / Float / Slide, waitlist, not-allotted gap, refund rule. |
| `02b_meridian_state_technical_university_corrigendum_1.pdf` | 1 | Revision of notice 02 | **Conflicts on purpose:** registration deadline (5 June vs 12 June 2027), fee deadline, rank-list date, and a changed document rule (income certificate). Also a two-digit year (`02/06/27`). Use it with notice 02 to test conflict detection. |
| `03_riverbend_central_college_ba_bcom_2027-28.pdf` | 5 | Cut-off-list B.A. / B.Com. | Three cut-off lists, upgrade, automatic consideration for the next list, waitlist with a 48-hour reply rule, conditional documents (EWS, sports, gap declaration), documents needed only if selected, vague dates (`31st July`, `second week of August`), and "no further steps" gaps. |

Test-only fixtures live in `backend/tests/fixtures/`: `scanned_notice.pdf` (image only, no text) and
`corrupted.pdf` (invalid bytes).
