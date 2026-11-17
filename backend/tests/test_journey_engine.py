import dataclasses
import json
import unittest

from app.services.journey_engine import (AVAILABLE, COMPLETED, CONDITIONAL, LOCKED, NEEDS_REVIEW, NOT_APPLICABLE,
                                         JourneyBlocked, JourneyItem, build_journey, load_templates,
                                         partition_items)

_n = [0]


def it(category, name, *, check="verified", state="pending", doc="notice.pdf", page=1, **kw):
    _n[0] += 1
    return JourneyItem(id=f"i{_n[0]}", document_name=doc, category=category, name=name,
                       explanation=f"AI reading of {name}", quote=f"Official text for {name}.", page=page,
                       quote_check=check, review_state=state, **kw)


def demo_like_items():
    """Items shaped like what the AI would propose for the fictional Demo National University notice."""
    return [
        it("eligibility", "Class 12 subjects", page=1),
        it("eligibility", "Minimum 50% aggregate", page=1),
        it("document", "Class 12 marksheet", page=2, requirement_level="mandatory"),
        it("document", "Photo ID proof", page=2, requirement_level="mandatory"),
        it("document", "Category certificate", page=2, requirement_level="conditional",
           condition="Only if claiming a reserved seat"),
        it("document", "Extracurricular certificates", page=2, requirement_level="optional"),
        it("deadline", "Registration opens", page=3, event_key="registration_open", date_iso="2027-02-01", date_status="ok"),
        it("deadline", "Registration closes", page=3, event_key="registration_close", date_iso="2027-02-28", date_status="ok"),
        it("deadline", "Form submission", page=3, event_key="application_close", date_iso="2027-03-15", date_status="ok"),
        it("deadline", "Merit list", page=4, event_key="merit_list_publication", date_iso="2027-04-01", date_status="ok"),
        it("outcome_pathway", "Accept the seat", page=4, outcome="selected"),
        it("outcome_pathway", "Pay the admission fee", page=4, outcome="selected", depends_on=("Accept the seat",)),
        it("outcome_pathway", "Bring originals for verification", page=4, outcome="selected",
           depends_on=("Pay the admission fee",)),
        it("outcome_pathway", "Check the waitlist notice", page=4, outcome="not_selected"),
    ]


def by_key(journey):
    return {s.key: s for s in journey.steps}


def dep_keys(step):
    return {d.step_key for d in step.depends_on}


class UsableItemRules(unittest.TestCase):
    def test_rules(self):
        verified = it("eligibility", "A")
        unverified = it("eligibility", "B", check="unverified")
        accepted = it("eligibility", "C", check="needs_review", state="accepted")
        edited = it("eligibility", "D", check="unverified", state="edited")
        rejected = it("eligibility", "E", state="rejected")
        excluded = it("eligibility", "F")
        usable, skipped = partition_items([verified, unverified, accepted, edited, rejected, excluded], [excluded.id])
        self.assertEqual({i.name for i in usable}, {"A", "C", "D"})
        self.assertEqual({s.name for s in skipped}, {"B", "E", "F"})          # nothing is dropped silently
        self.assertTrue(all(s.reason for s in skipped))

    def test_reviewer_accepted_evidence_is_labelled(self):
        j = build_journey([it("eligibility", "C", check="needs_review", state="accepted"),
                           it("eligibility", "V")])
        refs = {r.item_id: r.evidence for r in by_key(j)["check_eligibility"].sources}
        self.assertEqual(sorted(refs.values()), ["reviewer_accepted", "verified"])


class NoInventedContent(unittest.TestCase):
    def test_only_supported_steps_are_created(self):
        j = build_journey([it("eligibility", "Age limit")])
        supported = [s.key for s in j.steps if s.kind == "supported"]
        self.assertEqual(supported, ["check_eligibility"])                       # no register / submit / fee steps
        self.assertTrue(any("required documents" in g for g in j.gaps))

    def test_empty_or_unusable_input_is_blocked_not_an_empty_roadmap(self):
        with self.assertRaises(JourneyBlocked) as ctx:
            build_journey([])
        self.assertEqual(ctx.exception.code, "insufficient_information")
        with self.assertRaises(JourneyBlocked):
            build_journey([it("eligibility", "X", check="unverified")])           # pending + unverified -> skipped
        with self.assertRaises(JourneyBlocked):
            build_journey([it("warning", "Only a warning")])

    def test_suggested_steps_are_labelled_undated_and_not_counted(self):
        j = build_journey(demo_like_items())
        suggested = [s for s in j.steps if s.kind == "suggested"]
        self.assertTrue(suggested)
        for s in suggested:
            self.assertEqual((s.sources, s.deadlines, s.documents), ([], [], []))
            self.assertTrue(any("Suggested by LIFEPATH" in n for n in s.notes))
            self.assertEqual(s.guidance.origin, "lifepath_general_guidance")
        counted_total = j.progress.total
        self.assertEqual(counted_total, len([s for s in j.steps if s.kind == "supported" and s.branch is None]))

    def test_branch_without_instructions_gets_a_suggested_step_and_a_gap_not_invented_rules(self):
        j = build_journey(demo_like_items())
        waitlist = by_key(j)["suggested_no_instructions_waitlisted"]
        self.assertEqual((waitlist.kind, waitlist.branch, waitlist.sources), ("suggested", "waitlisted", []))
        self.assertTrue(any("waitlisted" in g for g in j.gaps))
        self.assertNotIn("suggested_no_instructions_selected", by_key(j))         # selected has real instructions

    def test_no_merit_list_means_no_outcome_branches_at_all(self):
        j = build_journey([it("eligibility", "Age limit"), it("outcome_pathway", "Accept the seat", outcome="selected")])
        self.assertFalse([s for s in j.steps if s.key.startswith("suggested_no_instructions")])

    def test_quotes_and_ai_text_stay_separate(self):
        j = build_journey(demo_like_items())
        ref = by_key(j)["check_eligibility"].sources[0]
        self.assertTrue(ref.quote.startswith("Official text"))
        self.assertTrue(ref.explanation.startswith("AI reading"))
        self.assertEqual(ref.document_name, "notice.pdf")


class StepsAndDependencies(unittest.TestCase):
    def setUp(self):
        self.j = build_journey(demo_like_items())
        self.s = by_key(self.j)

    def test_expected_steps_exist(self):
        for key in ("check_eligibility", "prepare_documents", "register", "complete_application", "check_merit_list"):
            self.assertIn(key, self.s)
        self.assertNotIn("pay_application_fee", self.s)                           # no fee item -> no fee step

    def test_template_dependencies_are_marked_general_flow(self):
        self.assertEqual(dep_keys(self.s["complete_application"]), {"register", "prepare_documents"})
        self.assertEqual({d.basis for d in self.s["complete_application"].depends_on}, {"general_flow"})
        self.assertEqual(dep_keys(self.s["check_merit_list"]), {"complete_application"})

    def test_notice_stated_order_creates_notice_dependencies_in_a_chain(self):
        pay = next(v for k, v in self.s.items() if k.startswith("selected_pay"))
        bring = next(v for k, v in self.s.items() if k.startswith("selected_bring"))
        accept = next(v for k, v in self.s.items() if k.startswith("selected_accept"))
        self.assertIn((accept.key, "notice"), {(d.step_key, d.basis) for d in pay.depends_on})
        self.assertIn((pay.key, "notice"), {(d.step_key, d.basis) for d in bring.depends_on})
        self.assertIn(("check_merit_list", "general_flow"), {(d.step_key, d.basis) for d in accept.depends_on})

    def test_order_respects_dependencies(self):
        position = {s.key: s.order for s in self.j.steps}
        for s in self.j.steps:
            for d in s.depends_on:
                self.assertLess(position[d.step_key], s.order, f"{s.key} before {d.step_key}")

    def test_documents_are_grouped_and_conditional_is_never_mandatory(self):
        docs = {d.name: d for d in self.s["prepare_documents"].documents}
        self.assertEqual(docs["Class 12 marksheet"].level, "mandatory")
        self.assertEqual((docs["Category certificate"].level, docs["Category certificate"].condition),
                         ("conditional", "Only if claiming a reserved seat"))
        self.assertEqual(docs["Extracurricular certificates"].level, "optional")

    def test_document_without_a_level_is_not_specified_not_mandatory(self):
        j = build_journey([it("document", "Medical fitness certificate", requirement_level=None,
                              missing_information="Format to be announced")])
        d = by_key(j)["prepare_documents"].documents[0]
        self.assertEqual((d.level, d.format_or_missing_note), ("not_specified", "Format to be announced"))

    def test_stage_items_merge_into_template_steps_or_are_flagged_unplaced(self):
        items = demo_like_items() + [it("stage", "Register on the admissions portal", page=3),
                                     it("stage", "Counselling Round 1 choice filling", page=4)]
        j = build_journey(items)
        s = by_key(j)
        self.assertEqual(len([k for k in s if "regist" in k]), 1)                 # merged, not duplicated
        self.assertEqual(len(s["register"].sources), 3)                           # 2 deadlines + the stage item
        unplaced = next(v for k, v in s.items() if k.startswith("notice_counselling"))
        self.assertEqual((unplaced.status, unplaced.needs_review), (NEEDS_REVIEW, True))
        self.assertTrue(any("cannot tell when" in n for n in unplaced.notes))
        self.assertEqual(unplaced.depends_on, [])                                 # no invented ordering

    def test_unmatched_and_looping_hints_are_reported_not_applied(self):
        items = demo_like_items()
        items.append(it("outcome_pathway", "Collect the allotment letter", outcome="selected",
                        depends_on=("Something that is not in the notice",)))
        j = build_journey(items)
        self.assertTrue(any("Something that is not in the notice" in w for w in j.warnings))
        loop = [it("outcome_pathway", "Alpha step", outcome="selected", depends_on=("Beta step",)),
                it("outcome_pathway", "Beta step", outcome="selected", depends_on=("Alpha step",)),
                it("deadline", "Merit", event_key="merit_list_publication", date_iso="2027-01-01", date_status="ok"),
                it("deadline", "Apply", event_key="application_close", date_iso="2026-12-01", date_status="ok")]
        j2 = build_journey(loop)
        self.assertTrue(any("loop" in w for w in j2.warnings))
        position = {s.key: s.order for s in j2.steps}
        for s in j2.steps:                                                        # still a valid order
            for d in s.depends_on:
                self.assertLess(position[d.step_key], s.order)

    def test_templates_are_configurable(self):
        custom = load_templates()
        custom["steps"] = [t for t in custom["steps"] if t["key"] != "register"]
        for t in custom["steps"]:
            t["depends_on"] = [d for d in t["depends_on"] if d != "register"]
        j = build_journey(demo_like_items(), custom)
        self.assertNotIn("register", by_key(j))
        self.assertNotIn("register", dep_keys(by_key(j)["complete_application"]))
        self.assertIn("registration_open", {u.event_key for u in j.unattached_deadlines})   # shown, not lost


class StatusesBranchesAndProgress(unittest.TestCase):
    def test_initial_statuses_without_outcome(self):
        s = by_key(build_journey(demo_like_items()))
        self.assertEqual(s["check_eligibility"].status, AVAILABLE)
        self.assertEqual(s["prepare_documents"].status, LOCKED)
        self.assertIn("Check your eligibility", s["prepare_documents"].locked_reason)
        branch = [v for v in s.values() if v.branch and v.kind == "supported"]
        self.assertTrue(branch and all(v.status == CONDITIONAL for v in branch))
        self.assertTrue(all("Record your result" in v.locked_reason for v in branch))

    def test_locked_step_cannot_be_completed_early(self):
        j = build_journey(demo_like_items(), completed={"complete_application"})
        s = by_key(j)
        self.assertEqual(s["complete_application"].status, LOCKED)
        self.assertTrue(any("cannot be completed before" in w for w in j.warnings))

    def test_completing_prerequisites_unlocks_in_order(self):
        j = build_journey(demo_like_items(), completed={"check_eligibility", "prepare_documents", "register"})
        s = by_key(j)
        self.assertEqual((s["register"].status, s["complete_application"].status, s["check_merit_list"].status),
                         (COMPLETED, AVAILABLE, LOCKED))

    def test_selected_outcome_pathway(self):
        done = {"check_eligibility", "prepare_documents", "register", "complete_application", "check_merit_list"}
        s = by_key(build_journey(demo_like_items(), outcome="selected", completed=done))
        accept = next(v for k, v in s.items() if k.startswith("selected_accept"))
        pay = next(v for k, v in s.items() if k.startswith("selected_pay"))
        wait = next(v for k, v in s.items() if k.startswith("not_selected_"))
        self.assertEqual((accept.status, pay.status, wait.status), (AVAILABLE, LOCKED, NOT_APPLICABLE))
        self.assertIn("Accept the seat", pay.locked_reason)

    def test_not_selected_outcome_gets_only_what_the_notice_says(self):
        s = by_key(build_journey(demo_like_items(), outcome="not_selected"))
        applicable = [v.title for v in s.values() if v.branch and v.status != NOT_APPLICABLE and v.kind == "supported"]
        self.assertEqual(applicable, ["Check the waitlist notice"])
        self.assertNotIn("suggested_no_instructions_not_selected", s)             # the notice HAS instructions for this case

    def test_waitlisted_outcome_shows_the_suggested_check_not_invented_steps(self):
        s = by_key(build_journey(demo_like_items(), outcome="waitlisted"))
        live = [v for v in s.values() if v.branch and v.status != NOT_APPLICABLE]
        self.assertEqual([v.key for v in live], ["suggested_no_instructions_waitlisted"])
        self.assertEqual(live[0].kind, "suggested")

    def test_changing_outcome_keeps_progress(self):
        done = {"check_eligibility", "prepare_documents", "register"}
        a = build_journey(demo_like_items(), outcome="selected", completed=done)
        b = build_journey(demo_like_items(), outcome="not_selected", completed=done)
        self.assertEqual({s.key for s in a.steps if s.status == COMPLETED},
                         {s.key for s in b.steps if s.status == COMPLETED})
        self.assertEqual(a.progress.completed, b.progress.completed)

    def test_progress_excludes_outcome_steps_until_outcome_known(self):
        done = {"check_eligibility"}
        none = build_journey(demo_like_items(), completed=done).progress
        sel = build_journey(demo_like_items(), outcome="selected", completed=done).progress
        self.assertEqual(none.completed, 1)
        self.assertGreater(sel.total, none.total)
        self.assertIn("not counted until you record it", none.note)
        self.assertEqual(none.percent, round(100 / none.total))

    def test_unknown_completed_keys_are_reported(self):
        j = build_journey(demo_like_items(), completed={"nope"})
        self.assertTrue(any("unknown step 'nope'" in w for w in j.warnings))


class DatesAndGaps(unittest.TestCase):
    def test_dates_are_copied_never_invented(self):
        s = by_key(build_journey(demo_like_items()))
        reg = {d.event_key: d.date_iso for d in s["register"].deadlines}
        self.assertEqual(reg, {"registration_open": "2027-02-01", "registration_close": "2027-02-28"})
        self.assertEqual(s["check_eligibility"].deadlines, [])
        undated = build_journey([it("eligibility", "x"), it("deadline", "Merit", event_key="merit_list_publication",
                                                            date_iso=None, date_reason="No date was found in the quote.")])
        d = by_key(undated)["check_merit_list"].deadlines[0]
        self.assertIsNone(d.date_iso)

    def test_conflicting_dates_are_not_resolved_by_the_engine(self):
        items = [it("eligibility", "x"),
                 it("deadline", "Registration closes", doc="notice.pdf", event_key="registration_close", date_iso="2027-06-05", date_status="ok"),
                 it("deadline", "Registration closes", doc="corrigendum.pdf", event_key="registration_close", date_iso="2027-06-12", date_status="ok")]
        j = build_journey(items, completed={"check_eligibility"})
        reg = by_key(j)["register"]
        self.assertEqual((reg.status, reg.needs_review), (NEEDS_REVIEW, True))
        self.assertEqual({d.date_iso for d in reg.deadlines}, {"2027-06-05", "2027-06-12"})   # both kept
        self.assertTrue(any("LIFEPATH has not chosen one" in n for n in reg.notes))
        self.assertTrue(any("more than one date" in w for w in j.warnings))

    def test_chosen_conflict_side_leaves_a_single_date(self):
        a = it("deadline", "Registration closes", event_key="registration_close", date_iso="2027-06-05", date_status="ok")
        b = it("deadline", "Registration closes", event_key="registration_close", date_iso="2027-06-12", date_status="ok")
        j = build_journey([it("eligibility", "x"), a, b], excluded_ids=[a.id])
        reg = by_key(j)["register"]
        self.assertEqual([d.date_iso for d in reg.deadlines], ["2027-06-12"])
        self.assertNotEqual(reg.status, NEEDS_REVIEW)
        self.assertEqual([k.item_id for k in j.skipped_items], [a.id])

    def test_ambiguous_date_is_flagged_on_the_step(self):
        j = build_journey([it("eligibility", "x"), it("deadline", "Fee", event_key="fee_payment_close",
                                                      date_iso="2027-06-07", date_status="needs_review")])
        self.assertTrue(any("ambiguous" in n for n in by_key(j)["pay_application_fee"].notes))

    def test_unknown_event_deadline_is_listed_not_turned_into_a_step(self):
        j = build_journey([it("eligibility", "x"), it("deadline", "Round 2 result", event_key="counselling_round_2_result",
                                                      date_iso="2027-07-06", date_status="ok")])
        self.assertEqual([d.event_key for d in j.unattached_deadlines], ["counselling_round_2_result"])
        self.assertEqual([s.key for s in j.steps if s.kind == "supported"], ["check_eligibility"])

    def test_gaps_from_missing_information_and_not_found_topics(self):
        j = build_journey([it("eligibility", "Age", missing_information="Reserved-category age relaxation not stated")],
                          not_found_topics=["appeal process"])
        self.assertIn("Age: Reserved-category age relaxation not stated", j.gaps)
        self.assertIn("Not found in the documents: appeal process.", j.gaps)

    def test_fees_and_warnings_are_carried_as_notes(self):
        j = build_journey([it("eligibility", "x"), it("fee", "Seat acceptance fee"), it("warning", "False information")])
        self.assertEqual([n.name for n in j.fees], ["Seat acceptance fee"])
        self.assertEqual([n.name for n in j.notice_warnings], ["False information"])


class Output(unittest.TestCase):
    def test_deterministic_and_json_serialisable(self):
        items = demo_like_items()                                                  # one list: ids must be identical
        a = build_journey(items, outcome="selected", completed={"check_eligibility"})
        b = build_journey(items, outcome="selected", completed={"check_eligibility"})
        self.assertEqual(a, b)
        text = json.dumps(dataclasses.asdict(a))
        self.assertIn("check_eligibility", text)

    def test_matches_the_shape_of_the_hand_written_demo_journey(self):
        """Sanity check against app/data/demo_journey.json: same branches and the same chain for 'selected'."""
        from pathlib import Path
        demo = json.loads((Path(__file__).resolve().parents[1] / "app/data/demo_journey.json").read_text(encoding="utf-8"))
        demo_branches = {s["branch"] for s in demo["steps"] if s["branch"]}
        j = build_journey(demo_like_items())
        engine_branches = {s.branch for s in j.steps if s.branch and s.kind == "supported"}
        self.assertEqual(demo_branches, engine_branches)
        self.assertEqual(len([s for s in demo["steps"] if s["branch"] == "selected"]),
                         len([s for s in j.steps if s.branch == "selected" and s.kind == "supported"]))


class ConflictGate(unittest.TestCase):
    """The journey must never be built while conflicts are unresolved, and never silently pick a side."""

    def setUp(self):
        from app.services.conflict_detector import ConflictItem, detect_conflicts
        self.a = ConflictItem("a", "d1", "notice.pdf", "deadline", "Reg", 3, "q", event_key="registration_close",
                              date_iso="2027-06-05")
        self.b = ConflictItem("b", "d2", "corrigendum.pdf", "deadline", "Reg", 1, "q", event_key="registration_close",
                              date_iso="2027-06-12")
        self.conflicts = detect_conflicts([self.a, self.b])

    def test_unresolved_conflict_blocks_and_lists_it(self):
        from app.services.journey_engine import conflict_exclusions
        with self.assertRaises(JourneyBlocked) as ctx:
            conflict_exclusions(self.conflicts, {})
        self.assertEqual(ctx.exception.code, "unresolved_conflicts")
        self.assertEqual(ctx.exception.details[0]["key"], "deadline:registration_close")

    def test_choosing_a_side_excludes_only_the_other_side(self):
        from app.services.journey_engine import conflict_exclusions
        self.assertEqual(conflict_exclusions(self.conflicts, {"deadline:registration_close": "b"}), {"a"})

    def test_resolving_by_note_excludes_nothing_so_both_dates_stay_visible(self):
        from app.services.journey_engine import conflict_exclusions
        self.assertEqual(conflict_exclusions(self.conflicts, {"deadline:registration_close": None}), set())

    def test_no_conflicts_means_nothing_excluded(self):
        from app.services.journey_engine import conflict_exclusions
        self.assertEqual(conflict_exclusions([], {}), set())

    def test_end_to_end_choice_gives_one_date_in_the_journey(self):
        from app.services.journey_engine import conflict_exclusions
        reg_a = it("deadline", "Registration closes", doc="notice.pdf", event_key="registration_close",
                   date_iso="2027-06-05", date_status="ok")
        reg_b = it("deadline", "Registration closes", doc="corrigendum.pdf", event_key="registration_close",
                   date_iso="2027-06-12", date_status="ok")
        from app.services.conflict_detector import ConflictItem, detect_conflicts
        conflicts = detect_conflicts([ConflictItem(i.id, i.document_name, i.document_name, "deadline", i.name, i.page,
                                                   i.quote, event_key=i.event_key, date_iso=i.date_iso)
                                      for i in (reg_a, reg_b)])
        excluded = conflict_exclusions(conflicts, {conflicts[0].key: reg_b.id})
        j = build_journey([it("eligibility", "x"), reg_a, reg_b], excluded_ids=excluded)
        self.assertEqual([d.date_iso for d in by_key(j)["register"].deadlines], ["2027-06-12"])
        self.assertEqual(by_key(j)["register"].deadlines[0].source.document_name, "corrigendum.pdf")


def no_application_step_items():
    """The audit scenario: the notice has a registration date and a merit-list date, but NO application-form item."""
    return [
        it("eligibility", "Class 12 subjects", page=1),
        it("document", "Class 12 marksheet", page=2, requirement_level="mandatory"),
        it("deadline", "Registration closes", page=3, event_key="registration_close", date_iso="2027-02-28", date_status="ok"),
        it("deadline", "Merit list", page=4, event_key="merit_list_publication", date_iso="2027-04-01", date_status="ok"),
        it("outcome_pathway", "Accept the seat", page=4, outcome="selected"),
        it("outcome_pathway", "Check the waitlist notice", page=4, outcome="not_selected"),
    ]


class MissingIntermediateSteps(unittest.TestCase):
    """When a template step has no supporting item it is not created, and the steps that depended on it must INHERIT
    its dependencies. Otherwise later steps (like the merit list) would look available far too early."""

    def test_merit_list_inherits_the_dependencies_of_the_missing_application_step(self):
        s = by_key(build_journey(no_application_step_items()))
        self.assertNotIn("complete_application", s)                         # not invented
        merit = s["check_merit_list"]
        self.assertEqual(dep_keys(merit), {"register", "prepare_documents"})
        self.assertEqual({d.basis for d in merit.depends_on}, {"general_flow"})
        self.assertEqual(merit.status, LOCKED)                              # was AVAILABLE before the fix
        self.assertIn("Register", merit.locked_reason)
        self.assertIn("Prepare your documents", merit.locked_reason)
        self.assertTrue(any("Fill in and submit the application form" in n for n in merit.notes))

    def test_merit_list_unlocks_only_when_every_inherited_prerequisite_is_done(self):
        items = no_application_step_items()
        partial = by_key(build_journey(items, completed={"check_eligibility", "prepare_documents"}))
        self.assertEqual(partial["check_merit_list"].status, LOCKED)        # register still missing
        done = by_key(build_journey(items, completed={"check_eligibility", "prepare_documents", "register"}))
        self.assertEqual(done["check_merit_list"].status, AVAILABLE)

    def test_inheritance_is_transitive_when_several_steps_are_missing(self):
        items = [it("eligibility", "Age", page=1), it("document", "Marksheet", requirement_level="mandatory"),
                 it("deadline", "Merit list", event_key="merit_list_publication", date_iso="2027-04-01", date_status="ok")]
        s = by_key(build_journey(items))
        self.assertNotIn("register", s)
        self.assertNotIn("complete_application", s)
        self.assertEqual(dep_keys(s["check_merit_list"]), {"check_eligibility", "prepare_documents"})
        self.assertEqual(s["check_merit_list"].status, LOCKED)

    def test_nothing_to_inherit_means_the_step_is_available(self):
        j = build_journey([it("deadline", "Merit list", event_key="merit_list_publication", date_iso="2027-04-01",
                              date_status="ok")])
        self.assertEqual(by_key(j)["check_merit_list"].depends_on, [])
        self.assertEqual(by_key(j)["check_merit_list"].status, AVAILABLE)

    def test_present_steps_keep_their_normal_dependencies_and_get_no_inheritance_note(self):
        s = by_key(build_journey(demo_like_items()))
        self.assertEqual(dep_keys(s["check_merit_list"]), {"complete_application"})
        self.assertEqual(s["check_merit_list"].notes, [])

    def test_no_duplicate_dependencies(self):
        deps = [d.step_key for d in by_key(build_journey(no_application_step_items()))["check_merit_list"].depends_on]
        self.assertEqual(len(deps), len(set(deps)))

    def test_order_is_still_valid(self):
        j = build_journey(no_application_step_items())
        position = {s.key: s.order for s in j.steps}
        for s in j.steps:
            for d in s.depends_on:
                self.assertLess(position[d.step_key], s.order, f"{s.key} before {d.step_key}")

    def test_pathway_steps_inherit_when_there_is_no_merit_list_step_either(self):
        items = [it("eligibility", "Age"), it("document", "Marksheet", requirement_level="mandatory"),
                 it("deadline", "Registration closes", event_key="registration_close", date_iso="2027-02-28", date_status="ok"),
                 it("outcome_pathway", "Accept the seat", outcome="selected")]
        accept = lambda j: next(v for k, v in by_key(j).items() if k.startswith("selected_accept"))
        j = build_journey(items, outcome="selected")
        self.assertEqual(dep_keys(accept(j)), {"register", "prepare_documents"})
        self.assertEqual(accept(j).status, LOCKED)                          # not available from the start
        self.assertEqual(accept(build_journey(items)).status, CONDITIONAL)  # outcome unknown
        done = {"check_eligibility", "prepare_documents", "register"}
        self.assertEqual(accept(build_journey(items, outcome="selected", completed=done)).status, AVAILABLE)

    def test_cyclic_custom_templates_terminate(self):
        custom = load_templates()
        for t in custom["steps"]:
            if t["key"] == "register":
                t["depends_on"] = ["complete_application"]
            if t["key"] == "complete_application":
                t["depends_on"] = ["register"]
        j = build_journey([it("eligibility", "Age"), it("deadline", "Merit list", event_key="merit_list_publication",
                                                        date_iso="2027-04-01", date_status="ok")], custom)
        self.assertIn("check_merit_list", by_key(j))                        # finished, did not hang or crash


class BranchesWithMissingIntermediateSteps(unittest.TestCase):
    """Selected / waitlisted / not-selected must keep working when the application step is missing."""
    DONE = {"check_eligibility", "prepare_documents", "register", "check_merit_list"}

    def live(self, journey):
        return [v for v in journey.steps if v.branch and v.status != NOT_APPLICABLE]

    def test_selected(self):
        items = no_application_step_items()
        before = by_key(build_journey(items, outcome="selected"))
        accept = next(v for k, v in before.items() if k.startswith("selected_accept"))
        self.assertEqual(accept.status, LOCKED)
        self.assertIn("Check the merit or rank list", accept.locked_reason)
        after = by_key(build_journey(items, outcome="selected", completed=self.DONE))
        self.assertEqual(next(v for k, v in after.items() if k.startswith("selected_accept")).status, AVAILABLE)
        self.assertEqual(next(v for k, v in after.items() if k.startswith("not_selected_")).status, NOT_APPLICABLE)

    def test_not_selected(self):
        j = build_journey(no_application_step_items(), outcome="not_selected", completed=self.DONE)
        self.assertEqual([(v.title, v.status) for v in self.live(j)], [("Check the waitlist notice", AVAILABLE)])

    def test_waitlisted_gets_only_the_suggested_check_never_invented_steps(self):
        j = build_journey(no_application_step_items(), outcome="waitlisted", completed=self.DONE)
        live = self.live(j)
        self.assertEqual([(v.key, v.kind) for v in live], [("suggested_no_instructions_waitlisted", "suggested")])
        self.assertEqual(live[0].status, AVAILABLE)
        self.assertTrue(any("waitlisted" in g for g in j.gaps))

    def test_no_outcome_keeps_all_branches_conditional_and_out_of_progress(self):
        j = build_journey(no_application_step_items())
        self.assertTrue(all(v.status == CONDITIONAL for v in j.steps if v.branch and v.kind == "supported"))
        self.assertIn("not counted until you record it", j.progress.note)

    def test_changing_outcome_keeps_progress(self):
        items = no_application_step_items()
        a = build_journey(items, outcome="selected", completed=self.DONE)
        b = build_journey(items, outcome="not_selected", completed=self.DONE)
        self.assertEqual({s.key for s in a.steps if s.status == COMPLETED}, {s.key for s in b.steps if s.status == COMPLETED})


if __name__ == "__main__":
    unittest.main()
