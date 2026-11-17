"""LIFEPATH journey engine: reviewed admission items -> a dependency-aware list of steps.

Pure Python (standard library only). No database, no HTTP, no AI. The same input always gives the same output.

Honesty rules, enforced here:
* A step exists only if reviewed items support it, OR it is labelled kind="suggested" (and then it never
  counts towards progress and carries no dates).
* An item may drive a step only if its quote is VERIFIED against the document, or a person accepted it.
* Official text (quotes) and AI wording (explanations) are kept in separate fields. General LIFEPATH guidance
  comes from the template file and is labelled as such.
* Dates are copied from the reviewed items. They are never computed or guessed here.
* Dependencies say where they come from: "notice" (stated by the document) or "general_flow" (template).
  A dependency never silently disappears: unmatched hints are reported as warnings.
* If two different dates remain for one step, none is chosen: the step is flagged for review.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from app.services.conflict_detector import Conflict

TEMPLATE_FILE = Path(__file__).resolve().parents[1] / "data" / "journey_templates.json"

# Step statuses
COMPLETED, AVAILABLE, LOCKED = "completed", "available", "locked"
CONDITIONAL, NOT_APPLICABLE, NEEDS_REVIEW = "conditional", "not_applicable", "needs_review"

OUTCOME_LABELS = {"selected": "selected", "waitlisted": "waitlisted", "not_selected": "not selected"}


class JourneyBlocked(Exception):
    """Journey generation must not proceed. ``code`` is stable; ``details`` is machine-readable."""

    def __init__(self, code: str, message: str, details: Optional[list] = None) -> None:
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or []


# ----------------------------------------------------------------------------- inputs
@dataclass(frozen=True)
class JourneyItem:
    id: str
    document_name: str
    category: str
    name: str
    explanation: str
    quote: str
    page: int
    quote_check: str                       # verified | needs_review | unverified
    review_state: str                      # pending | accepted | rejected | edited
    requirement_level: Optional[str] = None
    condition: Optional[str] = None
    event_key: Optional[str] = None
    outcome: Optional[str] = None
    depends_on: tuple[str, ...] = ()
    missing_information: Optional[str] = None
    date_iso: Optional[str] = None
    date_status: Optional[str] = None
    date_reason: Optional[str] = None


# ----------------------------------------------------------------------------- outputs
@dataclass
class SourceRef:
    item_id: str
    document_name: str
    page: int
    quote: str                             # official words
    explanation: str                       # AI-written reading, NOT official
    evidence: str                          # "verified" | "reviewer_accepted"
    condition: Optional[str] = None


@dataclass
class DocRef:
    name: str
    level: str                             # mandatory | conditional | optional | not_specified | not_required
    condition: Optional[str]
    format_or_missing_note: Optional[str]
    source: SourceRef


@dataclass
class StepDeadline:
    label: str
    event_key: Optional[str]
    date_iso: Optional[str]                # None when the notice gives no usable date
    date_status: Optional[str]             # ok | needs_review | invalid | user_confirmed
    reason: Optional[str]
    source: SourceRef


@dataclass
class Dependency:
    step_key: str
    basis: str                             # "notice" | "general_flow"


@dataclass
class Guidance:
    why_it_matters: str
    what_to_do: str
    origin: str = "lifepath_general_guidance"   # NOT text from the notice


@dataclass
class Step:
    key: str
    order: int
    title: str
    kind: str                              # "supported" | "suggested"
    status: str = AVAILABLE
    locked_reason: Optional[str] = None
    branch: Optional[str] = None           # selected | waitlisted | not_selected | None
    depends_on: list[Dependency] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)
    deadlines: list[StepDeadline] = field(default_factory=list)
    documents: list[DocRef] = field(default_factory=list)
    guidance: Optional[Guidance] = None
    notes: list[str] = field(default_factory=list)
    needs_review: bool = False


@dataclass
class SkippedItem:
    item_id: str
    name: str
    reason: str


@dataclass
class Note:
    name: str
    explanation: str
    source: SourceRef


@dataclass
class Progress:
    completed: int
    total: int
    percent: int
    note: str


@dataclass
class Journey:
    meta: dict
    outcome: Optional[str]
    steps: list[Step]
    progress: Progress
    gaps: list[str]
    warnings: list[str]
    skipped_items: list[SkippedItem]
    unattached_deadlines: list[StepDeadline]
    fees: list[Note]
    notice_warnings: list[Note]


# ----------------------------------------------------------------------------- helpers
def load_templates(path: Path = TEMPLATE_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")[:40] or "step"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.casefold())).strip()


def _ref(item: JourneyItem) -> SourceRef:
    return SourceRef(item.id, item.document_name, item.page, item.quote, item.explanation,
                     "verified" if item.quote_check == "verified" else "reviewer_accepted", item.condition)


def _deadline(item: JourneyItem) -> StepDeadline:
    return StepDeadline(item.name, item.event_key, item.date_iso, item.date_status, item.date_reason, _ref(item))


def _keyword_hit(name: str, keywords: Sequence[str]) -> bool:
    n = " " + _norm(name)
    return any((" " + _norm(k)) in n for k in keywords)


def partition_items(items: Iterable[JourneyItem], excluded_ids: Iterable[str] = ()
                    ) -> tuple[list[JourneyItem], list[SkippedItem]]:
    """Decide which items may drive steps. Everything not used is reported, never dropped silently."""
    excluded = set(excluded_ids)
    usable: list[JourneyItem] = []
    skipped: list[SkippedItem] = []
    for it in items:
        if it.review_state == "rejected":
            skipped.append(SkippedItem(it.id, it.name, "You rejected this item."))
        elif it.id in excluded:
            skipped.append(SkippedItem(it.id, it.name, "Another document's value was chosen when resolving a conflict."))
        elif it.quote_check != "verified" and it.review_state not in ("accepted", "edited"):
            skipped.append(SkippedItem(it.id, it.name,
                                       "The quote could not be verified in the document and you have not accepted this item."))
        else:
            usable.append(it)
    return usable, skipped


def conflict_exclusions(conflicts: Sequence[Conflict], decisions: Mapping[str, Optional[str]]) -> set[str]:
    """Apply the person's decisions about document conflicts.

    ``decisions`` maps conflict key -> chosen item id (None = resolved with a note only, nothing excluded).
    A conflict with NO decision blocks the journey: the engine never picks a side. Returns the item ids that
    must be left out because another side was chosen.
    """
    open_conflicts = [c for c in conflicts if c.key not in decisions]
    if open_conflicts:
        raise JourneyBlocked(
            "unresolved_conflicts",
            f"{len(open_conflicts)} conflict(s) between your documents must be resolved before a journey can be built.",
            [{"key": c.key, "title": c.title} for c in open_conflicts])
    excluded: set[str] = set()
    for c in conflicts:
        chosen = decisions[c.key]
        if chosen:
            excluded |= {side.item_id for side in c.sides if side.item_id != chosen}
    return excluded


# ----------------------------------------------------------------------------- building
def _find_by_hint(hint: str, steps: Sequence[Step], own: Step) -> Optional[Step]:
    """Match a notice-stated 'comes after X' hint to a step by title. No match -> None (reported by the caller)."""
    target = _norm(hint)
    if not target:
        return None
    for s in steps:
        title = _norm(s.title)
        if s is not own and title and (target == title or target in title or title in target):
            return s
    return None


def _reaches(deps: Mapping[str, set[str]], start: str, goal: str, seen: Optional[set[str]] = None) -> bool:
    if start == goal:
        return True
    seen = seen or set()
    seen.add(start)
    return any(_reaches(deps, d, goal, seen) for d in deps.get(start, ()) if d not in seen)


def _toposort(steps: list[Step]) -> list[Step]:
    """Stable topological order: keeps the planned order wherever dependencies allow."""
    by_key = {s.key: s for s in steps}
    placed: list[Step] = []
    done: set[str] = set()
    remaining = list(steps)
    while remaining:
        for s in remaining:
            if all(d.step_key in done or d.step_key not in by_key for d in s.depends_on):
                placed.append(s)
                done.add(s.key)
                remaining.remove(s)
                break
        else:                                   # cannot happen: cycles are prevented when edges are added
            raise RuntimeError("dependency cycle")
    return placed


def _dedupe_refs(refs: list[SourceRef]) -> list[SourceRef]:
    seen, out = set(), []
    for r in refs:
        if r.item_id not in seen:
            seen.add(r.item_id)
            out.append(r)
    return out


def _set_deadlines(step: Step, warnings: list[str]) -> None:
    dated = {d.date_iso for d in step.deadlines if d.date_iso}
    if len(dated) > 1:
        step.needs_review = True
        step.notes.append("Different dates are recorded for this step (" + ", ".join(sorted(dated)) +
                          "). LIFEPATH has not chosen one. Check the documents and decide.")
        warnings.append(f"Step '{step.title}' has more than one date and needs your review.")
    if any(d.date_status == "needs_review" for d in step.deadlines):
        step.notes.append("At least one date on this step is ambiguous or incomplete. Check it in the notice.")


def build_journey(items: Sequence[JourneyItem], templates: Optional[Mapping] = None, *,
                  excluded_ids: Iterable[str] = (), outcome: Optional[str] = None,
                  completed: Iterable[str] = (), meta: Optional[Mapping] = None,
                  not_found_topics: Iterable[str] = ()) -> Journey:
    tpl = templates or load_templates()
    usable, skipped = partition_items(items, excluded_ids)
    warnings: list[str] = []
    gaps: list[str] = []
    steps: list[Step] = []
    used: set[str] = set()                      # ids of items that became part of a step

    # ---- template steps: created only when at least one reviewed item supports them
    template_keys = [t["key"] for t in tpl["steps"]]
    stage_items = [i for i in usable if i.category == "stage"]
    for t in tpl["steps"]:
        sources = [i for i in usable if i.category in t.get("categories", []) and i.category != "stage"]
        sources += [i for i in stage_items if i.id not in used and _keyword_hit(i.name, t.get("stage_keywords", []))]
        deadline_items = [i for i in usable if i.category == "deadline" and i.event_key in t.get("event_keys", [])]
        if not sources and not deadline_items:
            continue
        step = Step(key=t["key"], order=0, title=t["title"], kind="supported",
                    guidance=Guidance(**t["guidance"]))
        step.sources = _dedupe_refs([_ref(i) for i in sources + deadline_items if i.category != "document"])
        step.deadlines = [_deadline(i) for i in deadline_items]
        for i in sources + deadline_items:
            used.add(i.id)
        if t["key"] == "prepare_documents":
            for i in usable:
                if i.category != "document":
                    continue
                level = i.requirement_level or "not_specified"
                note = i.missing_information or (None if i.requirement_level else "The notice excerpt does not state whether this is mandatory.")
                step.documents.append(DocRef(i.name, level, i.condition, note, _ref(i)))
            step.sources = _dedupe_refs([d.source for d in step.documents] + step.sources)
        for dep in t.get("depends_on", []):
            step.depends_on.append(Dependency(dep, "general_flow"))
        _set_deadlines(step, warnings)
        steps.append(step)
    present = {s.key for s in steps}
    template_deps = {t["key"]: t.get("depends_on", []) for t in tpl["steps"]}
    template_titles = {t["key"]: t["title"] for t in tpl["steps"]}

    def resolve_deps(keys: Sequence[str], missing: list[str], seen: frozenset = frozenset()) -> list[str]:
        """Keep dependencies on steps that exist. A step that does NOT exist (the notice has no item for it)
        is replaced by ITS OWN dependencies, recursively, so the ordering is never lost. ``missing`` collects
        the titles of the absent steps so the step can explain itself. ``seen`` stops loops in edited templates."""
        out: list[str] = []
        for k in keys:
            found = [k] if k in present else []
            if k not in present and k not in seen:
                missing.append(template_titles.get(k, k))
                found = resolve_deps(template_deps.get(k, []), missing, seen | {k})
            out += [f for f in found if f not in out]
        return out

    def missing_note(missing: list[str]) -> str:
        names = "', '".join(dict.fromkeys(missing))
        return (f"The documents contain no '{names}' step, so this step is placed after the steps that "
                "would have come before it.")

    for s in steps:                              # template steps: inherit from absent steps instead of dropping
        missing: list[str] = []
        s.depends_on = [Dependency(k, "general_flow") for k in resolve_deps([d.step_key for d in s.depends_on], missing)]
        if missing:
            s.notes.append(missing_note(missing))

    # ---- stage items that match no template: shown, but their place in the sequence is unknown
    for i in stage_items:
        if i.id in used:
            continue
        key = f"notice_{_slug(i.name)}"
        n = 2
        while key in {s.key for s in steps}:
            key, n = f"notice_{_slug(i.name)}_{n}", n + 1
        step = Step(key=key, order=0, title=i.name, kind="supported", sources=[_ref(i)], needs_review=True,
                    notes=["The notice describes this step, but LIFEPATH cannot tell when it happens relative to "
                           "the other steps. Check the notice before relying on its position."])
        steps.append(step)
        used.add(i.id)

    # ---- outcome pathways (selected / waitlisted / not selected): each pathway item is a step
    anchor = tpl.get("outcome_anchor")
    anchor_present = anchor in present
    pathway_branches: set[str] = set()
    for i in usable:
        if i.category != "outcome_pathway":
            continue
        branch = i.outcome if i.outcome in tpl["outcomes"] else None
        key = f"{branch or 'any'}_{_slug(i.name)}"
        n = 2
        while key in {s.key for s in steps}:
            key, n = f"{branch or 'any'}_{_slug(i.name)}_{n}", n + 1
        step = Step(key=key, order=0, title=i.name, kind="supported", branch=branch, sources=[_ref(i)])
        if anchor:                               # follow the merit/rank-list step, or what it would have followed
            missing = []
            step.depends_on += [Dependency(k, "general_flow") for k in resolve_deps([anchor], missing)]
            if missing:
                step.notes.append(missing_note(missing))
        steps.append(step)
        used.add(i.id)
        if branch:
            pathway_branches.add(branch)

    # ---- dependencies the notice states (depends_on hints on items)
    deps_map: dict[str, set[str]] = {s.key: {d.step_key for d in s.depends_on} for s in steps}
    item_by_id = {i.id: i for i in usable}
    for s in list(steps):
        hints = [h for src in s.sources if src.item_id in item_by_id for h in item_by_id[src.item_id].depends_on]
        for hint in hints:
            target = _find_by_hint(hint, steps, s)
            if target is None:
                warnings.append(f"The notice suggests '{s.title}' comes after '{hint}', but no matching step was found.")
            elif any(d.step_key == target.key for d in s.depends_on):
                s.depends_on = [Dependency(d.step_key, "notice") if d.step_key == target.key else d
                                for d in s.depends_on]
            elif _reaches(deps_map, target.key, s.key):
                warnings.append(f"Ignored the stated order '{target.title}' before '{s.title}': it would create a loop.")
            else:
                s.depends_on.append(Dependency(target.key, "notice"))
                deps_map[s.key].add(target.key)

    # ---- suggested steps (labelled; never counted in progress; no dates)
    sug = tpl["suggested"]
    for branch in tpl["outcomes"]:
        if anchor_present and branch not in pathway_branches:
            label = OUTCOME_LABELS[branch]
            g = sug["no_instructions"]["guidance"]
            steps.append(Step(key=f"suggested_no_instructions_{branch}", order=0, kind="suggested", branch=branch,
                              title=sug["no_instructions"]["title_template"].format(outcome=label),
                              depends_on=[Dependency(anchor, "general_flow")], guidance=Guidance(**g),
                              notes=[f"Suggested by LIFEPATH. The documents do not describe what to do if you are {label}."]))
            gaps.append(f"The documents do not describe any steps if you are {label}.")
    steps.insert(0, Step(key="suggested_confirm_official_notice", order=0, kind="suggested",
                         title=sug["confirm_official_notice"]["title"], guidance=Guidance(**sug["confirm_official_notice"]["guidance"]),
                         notes=["Suggested by LIFEPATH. This step is not part of the notice."]))

    # ---- deadlines that match no step, fees, warnings, gaps
    attached = {d.source.item_id for s in steps for d in s.deadlines}
    unattached = [_deadline(i) for i in usable if i.category == "deadline" and i.id not in attached]
    fees = [Note(i.name, i.explanation, _ref(i)) for i in usable if i.category == "fee"]
    notice_warnings = [Note(i.name, i.explanation, _ref(i)) for i in usable if i.category == "warning"]
    for i in usable:
        if i.missing_information:
            gaps.append(f"{i.name}: {i.missing_information}")
    for topic in not_found_topics:
        gaps.append(f"Not found in the documents: {topic}.")
    for needed, label in (("check_eligibility", "eligibility conditions"), ("prepare_documents", "required documents")):
        if needed not in present:
            gaps.append(f"No reviewed {label} were found, so LIFEPATH cannot show that step.")
    gaps = list(dict.fromkeys(gaps))

    # ---- order, then statuses
    ordered = _toposort(steps)
    for idx, s in enumerate(ordered, start=1):
        s.order = idx
    _apply_statuses(ordered, outcome, set(completed), warnings)

    supported = [s for s in ordered if s.kind == "supported"]
    if not supported:
        raise JourneyBlocked("insufficient_information",
                             "The reviewed items do not support any journey step yet. Review or accept more items.")
    counted = [s for s in supported if s.status != NOT_APPLICABLE and (s.branch is None or outcome is not None)]
    done = sum(1 for s in counted if s.status == COMPLETED)
    note = ("Progress counts only steps backed by the documents. Suggested steps are not counted."
            + ("" if outcome else " Steps that depend on your result are not counted until you record it."))
    progress = Progress(done, len(counted), int(round(100 * done / len(counted))) if counted else 0, note)
    return Journey(dict(meta or {}), outcome, ordered, progress, gaps, warnings, skipped, unattached, fees, notice_warnings)


def _apply_statuses(steps: list[Step], outcome: Optional[str], completed: set[str], warnings: list[str]) -> None:
    by_key = {s.key: s for s in steps}
    for key in sorted(completed - set(by_key)):
        warnings.append(f"Ignored unknown step '{key}' in the completed list.")
    state: dict[str, str] = {}
    for s in steps:                              # steps are in dependency order
        if s.branch and outcome is not None and s.branch != outcome:
            s.status = NOT_APPLICABLE
        else:
            unmet = [by_key[d.step_key] for d in s.depends_on
                     if d.step_key in by_key and state.get(d.step_key) not in (COMPLETED, NOT_APPLICABLE)]
            if s.key in completed and unmet:
                warnings.append(f"'{s.title}' was marked done, but it cannot be completed before: "
                                + ", ".join(f"'{u.title}'" for u in unmet) + ".")
            if s.branch and outcome is None:
                s.status = CONDITIONAL
                s.locked_reason = (f"Applies only if your result is '{OUTCOME_LABELS[s.branch]}'. "
                                   "Record your result after the list is published.")
            elif unmet:
                s.status = LOCKED
                s.locked_reason = "Complete first: " + ", ".join(f"'{u.title}'" for u in unmet) + "."
            elif s.key in completed:
                s.status = COMPLETED
            elif s.needs_review:
                s.status = NEEDS_REVIEW
            else:
                s.status = AVAILABLE
        state[s.key] = s.status
