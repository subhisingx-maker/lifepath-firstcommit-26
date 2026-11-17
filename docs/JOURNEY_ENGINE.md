# Journey engine (Step B: preview only)

Turns REVIEWED items from an analysis into a dependency-aware list of steps. No AI is used and nothing is saved.

```
reviewed items --partition--> usable items --templates--> steps --hints--> dependencies --> order --> statuses
(analysis_service)  (quote verified or accepted by you)   (journey_templates.json)           (outcome + completed)
```

## What may become a step
* An item drives a step only if its quote is **verified** against the document, or **you accepted/edited** it.
  Rejected, unverified-and-unreviewed, and conflict-losing items are listed in `skipped_items` with a reason.
* A step exists only if a reviewed item supports it. No registration item means no "Register" step.
* Anything else is `kind: "suggested"`: labelled, undated, never counted in progress.

## Evidence vs. guidance
Each step keeps three separate things: `sources` (official quote + page + document), the AI `explanation` inside each
source (never official), and `guidance` (general LIFEPATH advice from the template file, `origin:
lifepath_general_guidance`).

## Dependencies
**Missing steps pass their dependencies on.** A template step exists only if the documents support it. When one is
absent (for example the notice has no "fill in the application form" item), the steps that would have followed it
inherit ITS dependencies, recursively, instead of losing them. Without this, the merit-list step would look
available from day one. Each affected step carries a note naming the absent step, e.g. "The documents contain no
'Fill in and submit the application form' step, so this step is placed after the steps that would have come
before it." If nothing earlier exists either, the step simply has no dependencies. Outcome (selected / waitlisted /
not selected) steps follow the merit-list step, or whatever it would have followed. Edited templates that contain
loops are handled safely.

Each dependency has a `basis`: `notice` (the document states the order, via the item's `depends_on` hint) or
`general_flow` (from `journey_templates.json`). Hints that match no step become warnings. A hint that would create a
loop is ignored with a warning. Steps the notice describes but whose position is unknown get status `needs_review`
and NO invented dependencies.

## Statuses
`completed`, `available`, `locked` (with the exact steps required), `conditional` (outcome not recorded yet),
`not_applicable` (another outcome applies), `needs_review` (conflicting dates, or unknown position).
A step marked done while locked stays locked and a warning is returned.

## Outcomes
Branches: `selected`, `waitlisted`, `not_selected`. Changing the outcome recomputes statuses from the same
`completed` list, so progress is kept. If the documents say nothing for an outcome, a *suggested* "check the official
instructions" step and a `gaps` entry appear. No instructions are invented.

## Conflicts
Generation is blocked (HTTP 409, `unresolved_conflicts`) until each conflict has a decision. Choosing one side
removes the other sides from the journey. Resolving with a note only keeps both, and the step is flagged for review.

## Editing the templates
`backend/app/data/journey_templates.json`: add or remove steps, change `stage_keywords` (matched against an item's
NAME), `event_keys`, and `depends_on`. No Python change is needed.

## Endpoint
`POST /api/analyses/{id}/journey` with optional body `{"outcome": "selected|waitlisted|not_selected", "completed": ["step_key"]}`.
Errors: 404 unknown analysis; 409 `unresolved_conflicts`, `no_reviewed_items`, `insufficient_information`.
