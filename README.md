
# Opposition Brief

Opposition Brief turns a small set of public soccer event files into an
evidence-linked opponent report and analyst decision board. Milestone 2 keeps
the workflow deliberately descriptive: the application proposes patterns and
the analyst decides what enters the final brief.

## Build a report

With internet access, the default command retrieves only the StatsBomb Open
Data competition match list plus the three selected Argentina 2022 World Cup
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

## Analyst decision board (Milestone 2)

After building once, start the app from the repository root. It reads cached
StatsBomb files only, so opening the demo does not need internet access.

```bash
streamlit run app/streamlit_app.py
```

The four sections are:

- **Project Overview**: opponent, coverage, counts, warnings, and limitations.
- **Decision Board**: two or three structured candidate cards. The calculated
  claim is immutable; the analyst can change status, title, interpretation, and
  note in session state.
- **Evidence Explorer**: filtered supporting and comparison events, source
  timestamps, and a normalized pitch view of selected rows.
- **Report Review**: previews and downloads a print-friendly standalone HTML
  brief containing only **Accepted** and **Needs revision** observations.

Review state is intentionally not stored in a database. Download the JSON
review-state export if it should be retained between browser sessions.

Candidate observations use deterministic evidence labels. **Low** covers fewer
than six supporting events or fewer than two matches; **Moderate** requires at
least six events across two matches; **Strong** requires at least 12 events
across every selected match. These labels describe data coverage, not tactical
certainty. Supporting events are the actions counted by the pattern;
counterexamples are equivalent events outside its leading channel, player, or
zone and are labelled as comparisons rather than refutations.

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

## Current limitations

The demo covers three matches, uses event data only, and does not supply video
links or claim tactical intent, causal pressure mechanisms, or a correct
tactical response. Evidence timestamps are intended to help an analyst find
the relevant footage. Candidate strength should guide review priority, not
replace it.

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
