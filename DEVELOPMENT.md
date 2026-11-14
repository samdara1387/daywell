# Daywell development

Daywell is a local personal finance app. Python owns validation, storage, statement import, backups, and the HTTP API. The browser code in `public/` renders the interface. Customer records live outside this source folder under `%LOCALAPPDATA%\DaywellPython`.

## Product direction

- Make the first screen understandable in a few seconds. Use one clear action for each task and keep related information together.
- Let real income and expense records drive every chart. Always show the month, currency, and what the number represents.
- Keep motion subtle and useful. Respect reduced-motion settings and keyboard navigation.
- Use a consistent visual language across pages. Avoid decorative effects that compete with the customer's money decisions.
- Preserve data across updates and never use personal financial records as test fixtures or commit them to source control.

## Development loop

1. Work in this source folder. Do not edit the installed desktop copy until a change has passed checks.
2. Run `python -m unittest discover -s tests -p "test_*.py"` and `node --test tests/*.test.cjs`.
3. Review the affected screen at desktop and narrow widths, including an empty workspace and a populated workspace.
4. Copy tested source files to the desktop app folder. Keep `%LOCALAPPDATA%\DaywellPython` untouched.
5. Package the desktop folder only after verifying that it contains no database, backup, or local key files.

## Next work

1. Make every page follow the same spacing, type scale, controls, and empty-state pattern.
2. Audit statement import with varied bank formats, especially multi-line descriptions and credit/refund rows.
3. Improve backup recovery and confirm that the downloaded backup restores import and bill history.
4. Check keyboard access, contrast, and reduced motion on each page.
5. Review desktop and smaller laptop layouts before each release.

This public repository contains source code and fictional test data only. The local desktop app remains the place where real records live.
