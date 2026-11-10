# Daywell

Daywell is a personal money and everyday planning app. This repository is being rebuilt in small, reviewable parts from the complete local project. The desktop app and personal records remain on the owner's computer while the source is published in stages.

## Stage 1: core rules

`core.py` contains the Python rules for valid dates, amounts, records, and recurring bill dates. It has no third-party dependencies. The first upload is a foundation, not yet a runnable copy of the full app.

Run its tests with Python 3.13 or newer:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

## Planned stages

1. Python data storage and API.
2. Statement import, duplicate detection, and backup tools.
3. Browser interface, charts, calendar, and interactions.
4. Windows launcher, documentation, and end-to-end checks.

Each stage will be committed when it is ready and tested. The commit dates will reflect the actual work; uploads will not be delayed or backdated for appearance.

Personal databases, account statements, credentials, and the bundled Windows runtime are excluded from GitHub.
