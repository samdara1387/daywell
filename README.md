# Daywell

Daywell is a personal money and everyday planning app. This repository is being rebuilt in small, reviewable parts from the complete local project. The desktop app and personal records remain on the owner's computer while the source is published in stages.

## Stage 1: core rules

`core.py` contains the Python rules for valid dates, amounts, records, and recurring bill dates. It has no third-party dependencies. The first upload is a foundation, not yet a runnable copy of the full app.

## Stage 2: local money insights

`insights.py` adds the calculations used for spending charts, budget comparisons, category suggestions, and the offline money helper. `tests/test_insights.py` checks these calculations with fictional records. This remains a partial source upload; the data server and interface are still in the complete local project.

## Stage 3: safe local migration

`migrate.py` copies the earlier Daywell SQLite database, compares every table before switching to the copy, and preserves the original. `tests/test_migration.py` checks the copy with fictional records, import history, bill history, and an opaque test key. No customer database or key is included in this repository.

Run its tests with Python 3.13 or newer:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

## Stage 4: local storage and API

The Python server adds SQLite persistence, backups, account sessions, and local HTTP routes. The helper and email delivery modules are included as source; the tests use temporary databases and do not send live email or make live AI requests. This stage does not yet include the browser interface or desktop launcher and is not an online deployment.

## Stage 5: spending view calculations

`public/money-model.js` calculates the monthly spending breakdown, daily calendar totals, bill timeline, and savings scenarios used by the browser interface. `tests/money-model.test.cjs` checks those calculations with fictional transactions. This model can be tested with `node --test tests/money-model.test.cjs`; the interface that displays it will follow in a later stage.

## Planned stages

1. Statement import, duplicate detection, and backup tools.
2. Browser interface, charts, calendar, and interactions.
3. Windows launcher, documentation, and end-to-end checks.

Each stage will be committed when it is ready and tested. The commit dates will reflect the actual work; uploads will not be delayed or backdated for appearance.

Personal databases, account statements, credentials, and the bundled Windows runtime are excluded from GitHub.
