# Milestone 2: Analyst Decision Board and Evidence Review Workflow

## Product objective

Help a part-time opposition analyst decide which proposed opponent tendencies
deserve video review and which should enter a coaching brief. The application
keeps the analyst in control: computed evidence is immutable, while titles,
interpretations, notes, and review status are analyst-owned.

## Implemented workflow

1. `opposition-brief build-demo-report` retrieves or reuses the three-match
   Argentina demo and writes the original static report.
2. `streamlit run app/streamlit_app.py` opens cached files without downloading.
3. **Project Overview** shows coverage, counts, warnings, and limitations.
4. **Decision Board** presents three cards: route, player involvement, and
   possession-loss candidates. Each exposes its computed claim, support count,
   match coverage, strength, caution, and editable review fields.
5. **Evidence Explorer** separates representative source events from
   comparison/counterexample events, filters by match and player, sorts by
   timestamp, and draws selected rows on a 0–100 pitch.
6. **Report Review** previews and downloads a standalone print-friendly HTML
   report with only Accepted or Needs revision observations.

## Observation schema

`CandidateObservation` is a frozen dataclass containing:

- `observation_id`, `category`, and `title`;
- immutable `computed_claim` and default `interpretation`;
- `sample_size`, `matches_observed`, and `evidence_strength`;
- `supporting_event_ids` and `counterexample_event_ids`;
- `limitations`.

`ReviewState` holds only editable fields: observation ID, status, title,
interpretation, and analyst note. It deliberately has no computed-claim field.

## Evidence rules

Strength is deterministic and based on coverage: Low is under six supporting
events or under two matches; Moderate is six or more events across two matches;
Strong is 12 or more events across every selected match. A high completion
percentage alone cannot produce a strong label.

Route support is completed progressive actions from the leading channel; its
counterexamples are successful progressions from other channels. Player support
is that player’s completed progressive actions; its counterexamples are other
players’ completed progressions. Turnover support is event-defined losses in
the leading zone; its counterexamples are losses in other zones. These are
comparisons, not statistical refutations.

## Generated artifacts

- `reports/generated/opposition_brief.html` — original static computation
  report.
- Browser download `reviewed_opposition_brief.html` — reviewed export.
- Browser download `opposition_brief_review_state.json` — optional local
  review-state handoff.

## Verification

`ruff check .`, `ruff format --check .`, and `pytest -q` pass offline. The
test suite covers validation, IDs, strength boundaries, small samples,
support/counterexample selection, immutable claims, report filtering, edited
text escaping, empty data, malformed cache behavior, report generation, and
CLI smoke behavior.

## Known limitations and readiness

The dashboard uses a small three-match event sample, contains no video clips,
and cannot infer intent, pressing cause, or tactical response. The pitch view
is an event-review aid rather than a possession reconstruction. It is ready
for an external usability test because all key review paths are usable offline
after initial caching; feedback should determine the next priority.
