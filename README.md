
# Opposition Brief

Opposition Brief turns public soccer event files into a coach-first opponent
report. Milestone 3 prioritizes recurring behaviors that were associated with
downstream possession outcomes, so scarce video time goes beyond the most
obvious frequency leaders.

## Build a report

With internet access, the default command retrieves only the StatsBomb Open
Data competition match list plus the five selected Argentina 2022 World Cup
matches and their event and lineup files. It caches those files under
`data/raw/statsbomb/`; it never clones or commits the upstream dataset.

```bash
opposition-brief build-demo-report
# or
python -m opposition_brief build-demo-report
```

The report is written to `reports/generated/opposition_brief.html`. To use a
previously cached selection, add `--offline`. `list-competitions` lists the
available official competition/season records. A local bundle can be used for
reproducible work with `--input-dir path/to/bundle`; it must contain
`matches.json` and `events/<match_id>.json` files in StatsBomb's JSON shape.

```bash
opposition-brief list-competitions
opposition-brief build-demo-report --input-dir tests/fixtures/demo --team "Meridian FC"
```

## Opposition brief app (Milestone 2.5)

After building once, start the app from the repository root. It reads cached
StatsBomb files only, so opening the demo does not need internet access.

```bash
streamlit run app/streamlit_app.py
```

The app has three coach-facing stages:

- **Opposition brief** opens on up to five patterns worth video time. Each card
  states the non-causal finding, comparison, downstream outcome, sample size,
  match coverage, review tier, and why it may deserve review.
- **Pattern detail** focuses on one pattern with its comparison, within-match
  outcome rates, pitch locations, and representative timestamped possessions.
  “See other examples” is optional context, while definitions and data notes
  sit inside a secondary **Data & methodology** expander.
- **Final report** contains only patterns the analyst marked **Include in
  brief** or **Needs context**. Download it as a standalone, high-contrast,
  print-friendly HTML file.

Decisions and optional analyst comments are kept for the browser session only;
the factual finding remains derived from the cached event data.

## Definitions

The canonical schema retains match, timing, team/player, possession, action,
outcome, and start/end coordinates for each event. StatsBomb's 120 × 80
locations are linearly normalized to a documented 0–100 × 0–100 pitch, with
x increasing toward the source's attacking goal. Partial or malformed events
are retained with nullable fields and surfaced as data-quality warnings.

A progressive action is a pass or carry whose end location is at least 10
normalized units farther forward *and* at least 10 units closer in straight-line
distance to the opponent goal at `(100, 50)`. A progressive attempt may fail;
a completed progression has a completed provider outcome. Routes use the
action's starting left/central/right width channel and origin/destination
length thirds.

Possession-loss locations include incomplete passes, `Dispossessed`,
`Miscontrol`, and incomplete dribbles. This is an event-based descriptive
count, not a complete measurement of pressing vulnerability. Player rankings
flag fewer than three progressive attempts as a small sample.

### Possession outcome definitions

A possession reaches the **final third** when a later event has a start or end
location at `x >= 66.7`; it **enters the box** when a later location is at
`x >= 85` and `y = 22.5–77.5`; and it **produces a shot** when a later event
has type `Shot`. Route outcomes use the first completed progressive action in
that route within a possession, then inspect only later events in that same
possession. A qualifying player-association possession contains a completed
progressive action starting outside the final third; the comparison group is
other qualifying possessions. Buildup paths use the start/end 3×3 zones of
progressive actions, collapse consecutive repeats, and retain 2–5-zone paths.

Review priority is deterministic: **High** requires at least 12 possessions,
three matches, a 15-point-or-more box-entry difference, and a 20%-or-more
box-entry rate; **Moderate** requires six possessions, two matches, a 10-point
difference, and a 10% rate. All other results are low/insufficient evidence.
These are associations only, not causal claims.

## Current limitations

The demo covers five matches, uses event data only, and does not supply video
links or claim tactical intent, causal pressure mechanisms, or a correct
tactical response. Evidence timestamps are intended to help an analyst find
the relevant footage. Candidate strength should guide review priority, not
replace it.

See [the Milestone 3 report](docs/milestone_3_report.md) for the analytical
definitions, priority rules, findings, and remaining product risks.

## Attribution and use

This project reads the official [StatsBomb Open Data](https://github.com/statsbomb/open-data)
format. Users must follow that repository's license and attribution terms and
credit StatsBomb when using the data or derivative outputs. The source data is
not included in this repository.

## Development

```bash
ruff check .
ruff format --check .
pytest -q
```
