# Learn Python with Daywell

This is the source code for the working Daywell app. All backend features use Python. The `#` lines beside the Python code are comments: they explain what each part does, and Python ignores them when running.

## Reading order

1. `core.py` — learn functions and input checks. Start with `money()` and `date()`.
2. `insights.py` — see how lists of transactions become totals and charts.
3. `server.py` — find `DaywellApp.state()` and `DaywellApp.dispatch()` to follow a request from the browser into SQLite.
4. `migrate.py` — learn how a database copy is checked without changing the original.
5. `launcher.py` — follow the steps that start the server and open the window.
6. `helper.py` and `key_store.py` — read the optional money helper and Windows key protection.

## Example: money in cents

```python
# Add the stored integer cents from every transaction.
total_cents = sum(transaction['amount'] for transaction in transactions)

# Convert to dollars only when displaying the amount.
display_amount = total_cents / 100
```

`transactions` is a list. Each `transaction` is a dictionary with names such as `amount`, `date`, and `category`. `sum(...)` adds the amounts. Whole cents avoid floating-point mistakes in saved money.

## What happens when you save an expense

```text
Browser form -> local /api request -> server.py -> core.py validation
             -> SQLite database -> JSON response -> updated browser page
```

`/api` is a local address on this computer. JSON is a text format for lists and dictionaries. SQLite is the database stored in `%LOCALAPPDATA%\DaywellPython\daywell.sqlite`.

The `public` folder contains the browser code. JavaScript is still needed for clicking, drawing charts, showing the calendar, and reading a PDF into a preview. The server checks and saves the result in Python.

## Practice safely

The `tests` folder uses temporary fictional data. Run the test command in `README.md` before and after making a change. For your own experiments, copy the app folder and set a different `DAYWELL_PYTHON_DATA_DIR` and `PORT` so your learning work cannot modify your everyday records.
