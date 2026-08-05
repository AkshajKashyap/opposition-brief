
# Opposition Brief

Opposition Brief turns a small set of public soccer event files into a concise,
evidence-linked opponent report. Milestone 1 intentionally covers a narrow,
auditable workflow rather than a predictive model.

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
