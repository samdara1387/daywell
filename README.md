# Daywell

Daywell is a local personal money and everyday planning app. Its backend is mostly Python; HTML, CSS, and JavaScript draw the interface and read statement files. This repository contains source code and fictional tests. Personal records and credentials stay outside the repository.

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

## Stage 6: statement preview calculations

`public/statement-model.js` reads extracted PDF text and CSV rows locally, suggests categories, and flags card payments, mismatched currencies, and possible duplicate expenses before saving. `tests/statement-model.test.cjs` checks those decisions using fictional data. Run it with `node --test tests/statement-model.test.cjs`. PDF text extraction and the review screen will be published with the remaining browser interface.

## Stage 7: local account screens

`public/auth.*` supplies sign-in, account creation, and emailed-code confirmation once an administrator configures email delivery. `public/admin.*` supplies the local administrator dashboard and password confirmation for sensitive actions. `public/window-icon.svg` is the shared icon. The access tests verify that a signed-in administrator can open the dashboard while a member cannot. These pages work with the local API; the main finance interface is still being staged.

## Stage 8: complete browser interface

`public/index.html` and its local scripts and styles now provide the overview, transactions, charts, calendar, planning, settings, account navigation, and reviewed statement import. The bundled PDF.js files support readable PDF text extraction in the browser; their license and version record are in `public/vendor`. The three browser tests cover page history and the interactive month comparison. Run them with `node --test tests/*.test.cjs` in a shell that expands the wildcard, or pass each file to Node explicitly.

## Run the source on Windows

Install Python 3.13 or newer. In PowerShell, from this folder, use a disposable data directory and let the server choose a free local port:

```powershell
python -m unittest discover -s tests -p "test_*.py" -q
node --test tests/*.test.cjs
$env:DAYWELL_ACCOUNTS = "1"
python server.py --port 0 --data-dir "$env:TEMP\DaywellSourceDemo"
```

Open the local address printed by the server. Stop it with Ctrl+C. The JavaScript tests require Node.js. `Start Daywell.cmd`, `Start Daywell.vbs`, and `launcher.py` are for the packaged Windows desktop edition, which includes a separately distributed Python runtime. That runtime, personal databases, statements, exports, backups, and credentials are excluded from GitHub.

See `DEVELOPMENT.md` for the work loop, `LEARN_PYTHON.md` for annotated code, and `SECURITY_READINESS.md` for the online release gate. The cloud schema in `cloud/` is source only; Daywell is not deployed online.
