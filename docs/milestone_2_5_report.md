# Milestone 2.5: Coach-first UX redesign

## Problem found in product review

The Milestone 2 app exposed its internal workflow before its soccer insight.
The landing page led with project counts, validation warnings, IDs, and a
decision board; evidence exploration and report review looked like separate
software modules. A coach or analyst had to navigate the interface before they
could answer what Argentina tends to do.

## Information architecture

The old flow was **Project Overview → Decision Board → Evidence Explorer →
Report Review**. The new flow is **Opposition brief → Pattern detail → Final
report**.

- The landing brief names the opponent, competition, match coverage and date
  range, then presents each computed pattern as a visual card. Every card gives
  a factual finding, percentage comparison, sample, match coverage, key
  players when relevant, a small share chart, a review rationale, and one
  direct **Review sequences** action.
- Pattern detail concentrates on one finding. It shows what was seen,
  match-by-match consistency, a large pitch map, relevant players, and
  readable timestamped representative sequences. The analyst decision is last.
- Final report lists only patterns marked **Include in brief** or **Needs
  context**, then downloads a controlled-light, high-contrast standalone HTML
  report suitable for printing.

## Language removed from the primary experience

The primary screens no longer display evidence IDs, observation IDs, raw match
IDs, UUIDs, normalized-event counts, possession counts, review-state JSON,
“computed evidence (immutable)”, “candidate observation”, or “counterexample
evidence”. The product instead uses “patterns”, “what we saw”, “representative
sequences”, and “See other examples”. Method details, retained data-quality
notes, and limitations are secondary in **Data & methodology**.

## Screen descriptions

1. **Opposition brief** — Header: `ARGENTINA`, `Opposition brief`, World Cup
   coverage and dates. The next content is the pattern cards, so a first-time
   user can read the main routes, player involvement, and possession-loss area
   in one scan.
2. **Pattern detail** — A back action retains orientation. The page gives a
   factual share, per-match bar chart, full pitch arrows, player context, and
   cards such as `Argentina vs France · 18 Dec 2022 · 23:41 · player`. Provider
   IDs do not appear. Alternative routes are available only under **See other
   examples** with an explanation that they help judge consistency.
3. **Final report** — Selected findings, analyst interpretation and notes are
   visible before downloading. The downloaded report uses explicit white
   background, dark text, green headings, bounded tables, and print rules so
   browser dark mode cannot make it unreadable.

## Verification

Run from the repository root after installing the project dependencies:

```bash
ruff check .
ruff format --check .
pytest -q
streamlit run app/streamlit_app.py
```

The focused tests cover derived shares, readable match labels and timestamps,
pattern-card preparation, detail consistency and evidence fields, technical-ID
hiding, final-report contrast markers, and included/dismissed report filtering.

## Remaining usability risks

- The brief covers only three matches and event data cannot explain tactical
  intent or replace video review.
- The pitch is an event-location view, not a reconstructed possession or video
  player.
- Decisions are session-only. Persistence and collaborative workflow remain
  out of scope for this milestone.
