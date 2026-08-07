# Milestone 3: Decision-relevant pattern mining

## Motivation and coverage

The prior brief accurately described what Argentina did most often, but route,
player, and turnover frequency alone did not say where to spend limited video
review time. This milestone uses the same StatsBomb event feed and existing
possession IDs for the five most recent Argentina matches in the 2022 World
Cup: Poland, Australia, Netherlands, Croatia, and France.

## Definitions and denominators

- A possession reaches the final third if a later event starts or ends at
  `x >= 66.7`; it enters the box at `x >= 85`, `22.5 <= y <= 77.5`; and it
  produces a shot if a later event is a `Shot`.
- Route outcomes use possessions containing a completed progressive action in
  a left, central, or right start channel. Only the events after the first such
  action in that possession count as the downstream outcome.
- Player association compares qualifying possessions with an early completed
  progressive action by that player against other qualifying possessions. It
  is not player impact or a counterfactual claim.
- Pathways use start/end 3×3 zones for progressive actions, collapse consecutive
  repeats, retain the first 2–5 zones, and need at least four possessions in
  two matches.
- Turnover consequences link an Argentina loss only to the immediate next
  possession when it belongs to the opponent. Unlinked losses remain counted
  in their source zone but do not fabricate an outcome.

Priority is transparent: High requires 12 qualifying possessions, three
matches, a 15-point-or-greater box-entry difference, and a 20%-or-greater
rate. Moderate requires 6, 2, 10 points, and 10%; the remainder is low or
insufficient evidence. Ties retain “among leaders” wording rather than a
single-winner claim.

## Current highest-priority findings

- Defensive-third/right Argentina losses were followed by an opponent box entry
  in **44% of 39** reliably linked following possessions, versus **27%** after
  losses in other zones.
- Qualifying possessions with **Lionel Andrés Messi Cuccittini** involved in an
  early completed progression entered the box **80% of 30** times, versus
  **43%** in other qualifying possessions.
- **Nicolás Hernán Otamendi**: **62% of 29** versus **45%**; **Enzo Fernandez**:
  **68% of 25** versus **45%**. These are associations with game state, field
  position, role, and possession quality—not evidence that a player caused the
  outcome.

Representative possessions show their match, minute, start zone, short action
chain, and recorded final-third/box/shot outcome without provider IDs or raw
coordinates.

## Limitations and assessment

The analysis uses five matches, event locations, and provider possession IDs;
it has no video, player tracking, causal design, or tactical-response model.
Malformed/unassigned possession events are retained as an explicit analysis
count rather than silently treated as an outcome. Small samples, ties, missing
links after losses, and extra time remain reasons to inspect video carefully.

**LIMITED GO.** Conditional player and turnover findings are materially more
specific than the prior frequency cards and are plausible video-review
hypotheses. They remain vulnerable to selection, match state, and possession
quality, so external analyst testing—not automated tactical advice—is the
recommended next step.

## Verification

```bash
opposition-brief build-demo-report --offline
streamlit run app/streamlit_app.py
ruff check .
ruff format --check .
pytest -q
```
